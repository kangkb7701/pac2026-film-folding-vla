"""Write human_labels.json (from label_tool.py) into the dataset as SARM stage annotations.

Usage (conda env lerobot312):
    python export_sarm_labels.py C:/Users/kangk/lerobot_data/fold_film_onearm_demo [--include-misaligned]

Writes the same columns LeRobot's own SARM annotation script writes (dense_subtask_names,
dense_subtask_start_frames, ...) into meta/episodes, plus meta/temporal_proportions_dense.json,
so SARM trains with --policy.annotation_mode=dense_only. meta/episodes is backed up first.
Each mark means "from here on, this subtask" (label_tool.EVENTS); the episode starts in the first
subtask, and the last subtask runs to the episode end unless "done" is marked.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

import pandas as pd

from label_tool import EVENTS, STAGES

PREFIX = "dense"
COLUMNS = ["subtask_names", "subtask_start_times", "subtask_end_times", "subtask_start_frames", "subtask_end_frames"]


def segments(events: list[dict], length: int) -> list[tuple[str, int, int]]:
    """[(stage, start_frame, end_frame)] between consecutive boundaries. The episode start (frame 0)
    starts the first stage; each mark starts the stage in its `starts`; repeats are kept. Without a
    "done" mark the last stage runs to the last frame of the episode."""
    starts = {e["key"]: e["starts"] for e in EVENTS}
    bounds = [(0, 0)] + [(e["frame"], starts[e["type"]]) for e in sorted(events, key=lambda e: e["frame"]) if e["type"] in starts]
    if bounds[-1][1] < len(STAGES):
        bounds.append((length - 1, len(STAGES)))
    out = []
    for (a, k), (b, _) in zip(bounds, bounds[1:]):
        if k < len(STAGES) and b > a:
            out.append((STAGES[k]["key"], a, b))
    return out


def temporal_proportions(segs_by_ep: dict[int, list]) -> dict[str, float]:
    """SARM paper formula (1): average over episodes of each stage's share of the episode's stage time.
    Repeated stages are summed (LeRobot's annotation script keeps only the last occurrence)."""
    sums = {s["key"]: 0.0 for s in STAGES}
    for segs in segs_by_ep.values():
        dur = {s["key"]: 0 for s in STAGES}
        for name, a, b in segs:
            dur[name] += b - a
        total = sum(dur.values())
        for name in sums:
            sums[name] += dur[name] / total
    n = len(segs_by_ep)
    props = {name: s / n for name, s in sums.items()}
    missing = [name for name, p in props.items() if p == 0]
    if missing:
        raise SystemExit(f"stages never labeled in the training episodes: {missing}")
    return props


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--labels", default=None, help="default: <root>/human_labels.json")
    ap.add_argument("--include-misaligned", action="store_true", help="also train SARM on 'success (misaligned)' episodes")
    args = ap.parse_args()

    root = Path(args.root)
    labels = json.loads(Path(args.labels or root / "human_labels.json").read_text(encoding="utf-8"))["episodes"]
    info = json.loads((root / "meta/info.json").read_text())
    fps = info["fps"]
    lengths = {
        int(r.episode_index): int(r.length)
        for f in sorted((root / "meta/episodes").rglob("*.parquet"))
        for r in pd.read_parquet(f, columns=["episode_index", "length"]).itertuples()
    }
    cams = [k for k, v in info["features"].items() if v["dtype"] == "video"]
    # SARM reads one camera; the top view worked best in the SARM paper (wrist cameras did not help).
    image_key = next((k for k in cams if "top" in k), cams[0])
    train_outcomes = {"success", "misaligned"} if args.include_misaligned else {"success"}

    annotated, train = {}, []
    for ep, lab in labels.items():
        segs = segments(lab.get("events", []), lengths[int(ep)])
        if lab.get("outcome") in (None, "exclude") or not segs:
            continue
        annotated[int(ep)] = segs
        if lab["outcome"] in train_outcomes:
            train.append(int(ep))
    train.sort()
    if not train:
        raise SystemExit("no episodes to train SARM on (label some as success first)")
    props = temporal_proportions({ep: annotated[ep] for ep in train})

    ep_dir = root / "meta/episodes"
    backup = root / "meta" / f"episodes_backup_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(ep_dir, backup)
    for path in sorted(ep_dir.rglob("*.parquet")):
        df = pd.read_parquet(path)
        for col in COLUMNS:
            df[f"{PREFIX}_{col}"] = None
        for i, ep in df["episode_index"].items():
            segs = annotated.get(int(ep))
            if not segs:
                continue
            df.at[i, f"{PREFIX}_subtask_names"] = [s[0] for s in segs]
            df.at[i, f"{PREFIX}_subtask_start_times"] = [s[1] / fps for s in segs]
            df.at[i, f"{PREFIX}_subtask_end_times"] = [s[2] / fps for s in segs]
            df.at[i, f"{PREFIX}_subtask_start_frames"] = [s[1] for s in segs]
            df.at[i, f"{PREFIX}_subtask_end_frames"] = [s[2] for s in segs]
        df.to_parquet(path, engine="pyarrow", compression="snappy")
    (root / "meta" / f"temporal_proportions_{PREFIX}.json").write_text(json.dumps(props, indent=2))

    outcomes = pd.Series({int(k): v.get("outcome") for k, v in labels.items()}).value_counts().to_dict()
    print(f"backup of meta/episodes: {backup}")
    print(f"annotated episodes: {len(annotated)}   outcomes: {outcomes}")
    print("stage proportions (SARM progress share): " + ", ".join(f"{k} {v:.2f}" for k, v in props.items()))
    print(f"SARM training episodes ({len(train)}): {train}")
    print("\nSARM training flags:")
    print(f"  --policy.type=sarm --policy.annotation_mode=dense_only --policy.image_key={image_key}")
    print(f"  --dataset.episodes=\"{train}\"")
    print("Progress for RA-BC: compute_rabc_weights ... --head-mode dense")


if __name__ == "__main__":
    main()
