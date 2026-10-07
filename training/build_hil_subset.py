"""Build a subset of the HIL dataset (one data/video file per episode) with per-episode crops and idle trimming.

Usage: python build_hil_subset.py <src_dataset_dir> <dst_dataset_dir> <spec.json>

spec.json is a list of {"episode": <src episode index>, "start": <first frame>, "end": <end frame, exclusive>}.
Episodes are renumbered in spec order. Inside each crop, still frames are trimmed with the same rule as
trim_idle.py. Videos are copied, not re-encoded; each episode points to its time range inside its file.
Per-episode stats of numeric features are recomputed; image stats are kept from the source episode.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lerobot.datasets.compute_stats import aggregate_stats, compute_episode_stats
from lerobot.datasets.io_utils import write_stats

THRESHOLD = 2.0  # any joint moving more than this from the first/last action counts as motion
START_MARGIN_S = 0.3
END_MARGIN_S = 1.0

def to_array(cell):
    """Nested list column cell (numpy object arrays from parquet) -> plain numpy array."""
    if isinstance(cell, np.ndarray) and cell.dtype == object:
        return np.stack([to_array(v) for v in cell])
    return np.asarray(cell)


src, dst, spec_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
if dst.exists():
    sys.exit(f"{dst} already exists")
spec = json.loads(spec_path.read_text())

info = json.loads((src / "meta/info.json").read_text())
fps = info["fps"]
action_dim = info["features"]["action"]["shape"][0]
video_keys = [k for k, f in info["features"].items() if f["dtype"] == "video"]
numeric_features = {k: f for k, f in info["features"].items() if f["dtype"] not in ("video", "image", "string")}

src_eps = pd.concat([pd.read_parquet(f) for f in sorted((src / "meta/episodes").glob("*/*.parquet"))], ignore_index=True)
src_eps = src_eps.set_index("episode_index")
(dst / "meta").mkdir(parents=True)
shutil.copy(src / "meta/tasks.parquet", dst / "meta/tasks.parquet")

all_stats, next_index, report = [], 0, []
for new_ep, item in enumerate(spec):
    old_ep, crop_start, crop_end = item["episode"], item["start"], item["end"]
    meta = src_eps.loc[old_ep]
    table = pq.read_table(src / f"data/chunk-000/file-{int(meta['data/file_index']):03d}.parquet")
    table = table.filter(pa.array(table["episode_index"].to_numpy() == old_ep))
    action = table["action"].combine_chunks().values.to_numpy().reshape(-1, action_dim)[crop_start:crop_end]
    moved_from_first = np.abs(action - action[0]).max(axis=1) > THRESHOLD
    moved_from_last = np.abs(action - action[-1]).max(axis=1) > THRESHOLD
    first_motion = int(np.argmax(moved_from_first))
    last_motion = len(action) - 1 - int(np.argmax(moved_from_last[::-1]))
    start = crop_start + max(0, first_motion - round(START_MARGIN_S * fps))
    end = crop_start + min(len(action), last_motion + 1 + round(END_MARGIN_S * fps))
    length = end - start

    new = table.slice(start, length)
    frame_index = np.arange(length)
    for name, values in [
        ("frame_index", frame_index),
        ("timestamp", (frame_index / fps).astype(np.float32)),
        ("index", np.arange(next_index, next_index + length)),
        ("episode_index", np.full(length, new_ep)),
    ]:
        i = new.schema.get_field_index(name)
        new = new.set_column(i, new.schema.field(i), pa.array(values, type=new.schema.field(i).type))
    out = dst / f"data/chunk-000/file-{new_ep:03d}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(new, out)

    df = new.to_pandas()
    ep_data = {}
    for key in numeric_features:
        values = df[key].values
        ep_data[key] = np.stack(values) if hasattr(values[0], "__len__") else np.array(values)
    ep_stats = compute_episode_stats(ep_data, numeric_features)
    for key in video_keys:  # image stats: keep the source episode's
        ep_stats[key] = {s: to_array(meta[f"stats/{key}/{s}"]) for s in ep_stats["action"]}
    all_stats.append(ep_stats)

    row = {"episode_index": new_ep, "tasks": list(meta["tasks"]), "length": length,
           "data/chunk_index": 0, "data/file_index": new_ep,
           "dataset_from_index": next_index, "dataset_to_index": next_index + length,
           "meta/episodes/chunk_index": 0, "meta/episodes/file_index": new_ep}
    for key in video_keys:
        src_video = src / f"videos/{key}/chunk-000/file-{int(meta[f'videos/{key}/file_index']):03d}.mp4"
        dst_video = dst / f"videos/{key}/chunk-000/file-{new_ep:03d}.mp4"
        dst_video.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_video, dst_video)
        video_start = float(meta[f"videos/{key}/from_timestamp"])
        row |= {f"videos/{key}/chunk_index": 0, f"videos/{key}/file_index": new_ep,
                f"videos/{key}/from_timestamp": video_start + start / fps,
                f"videos/{key}/to_timestamp": video_start + end / fps}
    for key, stats in ep_stats.items():
        for stat_name, value in stats.items():
            row[f"stats/{key}/{stat_name}"] = np.asarray(value).tolist()
    src_schema = pq.read_schema(src / f"meta/episodes/chunk-000/file-{int(meta['meta/episodes/file_index']):03d}.parquet")
    columns = {f.name: pa.array([row[f.name]], type=f.type) for f in src_schema}
    out = dst / f"meta/episodes/chunk-000/file-{new_ep:03d}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns, schema=src_schema), out)

    next_index += length
    report.append(f"episode {old_ep:3d} -> {new_ep:3d}: crop {crop_start}-{crop_end}, kept {start}-{end - 1} ({length / fps:.1f}s)")

write_stats(aggregate_stats(all_stats), dst)
info["total_episodes"] = len(spec)
info["total_frames"] = next_index
info["splits"] = {"train": f"0:{len(spec)}"}
(dst / "meta/info.json").write_text(json.dumps(info, indent=4))
print("\n".join(report))
print(f"{len(spec)} episodes, {next_index} frames ({next_index / fps / 60:.1f} min)")
