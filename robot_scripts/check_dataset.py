"""Quality check for a recorded LeRobot dataset before fine-tuning. Read-only.

Usage (conda env lerobot312):
    python check_dataset.py C:/Users/kangk/lerobot_data/fold_film_onearm_demo

Reports: task strings, episode lengths, per-step action jumps (e.g. wrist_roll wrapping past
+-180 deg), idle time at the start/end of each episode, and whether the first/last video
frames of every episode decode.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

JUMP_LIMIT = 20.0  # per-step change; 20 deg per step at 30 fps = 600 deg/s, not a human teleop motion
IDLE_EPS = 0.5  # max per-step change counted as "not moving"


def idle_frames(actions, from_end=False):
    deltas = np.abs(np.diff(actions, axis=0)).max(axis=1)
    if from_end:
        deltas = deltas[::-1]
    moving = np.nonzero(deltas > IDLE_EPS)[0]
    return len(deltas) if len(moving) == 0 else int(moving[0])


def main(root):
    root = Path(root)
    info = json.loads((root / "meta/info.json").read_text())
    fps = info["fps"]
    names = info["features"]["action"]["names"]
    cams = [k for k in info["features"] if k.startswith("observation.images.")]
    print(f"codebase {info.get('codebase_version')} | fps {fps} | episodes {info['total_episodes']} | frames {info['total_frames']}")
    print(f"cameras: {cams}")
    print(f"tasks: {pd.read_parquet(root / 'meta/tasks.parquet').index.tolist()}")

    data = pd.concat(pd.read_parquet(f) for f in sorted((root / "data").rglob("*.parquet")))
    print(f"\n{'ep':>3} {'frames':>6} {'sec':>5} {'idle_start_s':>12} {'idle_end_s':>10}  max per-step jump (joint)")
    flagged = []
    for ep, df in data.groupby("episode_index"):
        actions = np.stack(df.sort_values("frame_index")["action"].to_numpy())
        jumps = np.abs(np.diff(actions, axis=0)).max(axis=0)
        worst = int(jumps.argmax())
        mark = "  <-- check" if jumps[worst] > JUMP_LIMIT else ""
        if mark:
            flagged.append(ep)
        print(
            f"{ep:>3} {len(actions):>6} {len(actions) / fps:>5.1f} "
            f"{idle_frames(actions) / fps:>12.1f} {idle_frames(actions, from_end=True) / fps:>10.1f}  "
            f"{jumps[worst]:.1f} ({names[worst]}){mark}"
        )
    print(f"\nepisodes with a per-step jump > {JUMP_LIMIT}: {flagged or 'none'}")

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    ds = LeRobotDataset(repo_id="local/check", root=root)
    bad = []
    for ep, df in data.groupby("episode_index"):
        for idx in (int(df["index"].min()), int(df["index"].max())):
            try:
                item = ds[idx]
                assert all(item[c].numel() > 0 for c in cams)
            except Exception as e:  # report every decode failure, keep checking the rest
                bad.append((ep, idx, repr(e)[:120]))
    print(f"video decode check (first/last frame of every episode): {'all OK' if not bad else bad}")


if __name__ == "__main__":
    main(sys.argv[1])
