"""Trim the still frames at the start and end of every episode of a LeRobot v3.0 dataset.

Usage: python trim_idle.py <src_dataset_dir> <dst_dataset_dir>

Videos are copied as-is, not re-encoded: each episode points to a time range inside the
mp4 files, so only the data rows and the episode time ranges change. Per-episode stats of the
numeric features and stats.json are recomputed; image stats are kept from the source episodes.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from lerobot.datasets.compute_stats import aggregate_stats, compute_episode_stats
from lerobot.datasets.io_utils import write_stats

THRESHOLD = 2.0  # any joint moving more than this from the first/last action counts as motion
START_MARGIN_S = 0.3  # stillness kept before the first motion
END_MARGIN_S = 1.0  # stillness kept after the last motion

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    sys.exit(f"{dst} already exists")

info = json.loads((src / "meta/info.json").read_text())
fps = info["fps"]
action_dim = info["features"]["action"]["shape"][0]
video_keys = [k for k, f in info["features"].items() if f["dtype"] == "video"]
numeric_features = {k: f for k, f in info["features"].items() if f["dtype"] not in ("video", "image", "string")}

shutil.copytree(src / "meta", dst / "meta")
shutil.copytree(src / "videos", dst / "videos")


def replace_column(table, name, values):
    i = table.schema.get_field_index(name)
    field = table.schema.field(i)
    return table.set_column(i, field, pa.array(values, type=field.type))


# Data files: drop the still rows and renumber frame_index, timestamp and index.
cuts = {}  # episode_index -> (start, end, original length), end exclusive
episode_stats = {}
next_index = 0
for path in sorted((src / "data").glob("*/*.parquet")):
    table = pq.read_table(path)
    episode_col = table["episode_index"].to_numpy()
    actions = table["action"].combine_chunks().values.to_numpy().reshape(-1, action_dim)
    keep = np.zeros(table.num_rows, dtype=bool)
    frame_index = np.zeros(table.num_rows, dtype=np.int64)
    for ep in np.unique(episode_col):
        rows = np.flatnonzero(episode_col == ep)
        action = actions[rows]
        moved_from_first = np.abs(action - action[0]).max(axis=1) > THRESHOLD
        moved_from_last = np.abs(action - action[-1]).max(axis=1) > THRESHOLD
        first_motion = int(np.argmax(moved_from_first))
        last_motion = len(rows) - 1 - int(np.argmax(moved_from_last[::-1]))
        start = max(0, first_motion - round(START_MARGIN_S * fps))
        end = min(len(rows), last_motion + 1 + round(END_MARGIN_S * fps))
        keep[rows[start:end]] = True
        frame_index[rows[start:end]] = np.arange(end - start)
        cuts[int(ep)] = (start, end, len(rows))

    new = table.filter(pa.array(keep))
    new_frame_index = frame_index[keep]
    new = replace_column(new, "frame_index", new_frame_index)
    new = replace_column(new, "timestamp", (new_frame_index / fps).astype(np.float32))
    new = replace_column(new, "index", np.arange(next_index, next_index + new.num_rows))
    next_index += new.num_rows
    out = dst / path.relative_to(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(new, out)

    # Per-episode stats of the numeric features, computed the same way as recompute_stats.
    df = new.to_pandas()
    for ep in sorted(df["episode_index"].unique()):
        ep_df = df[df["episode_index"] == ep]
        episode_data = {}
        for key in numeric_features:
            values = ep_df[key].values
            episode_data[key] = np.stack(values) if hasattr(values[0], "__len__") else np.array(values)
        episode_stats[int(ep)] = compute_episode_stats(episode_data, numeric_features)

# Episode metadata: new lengths, index ranges, video time ranges and numeric stats.
from_index = 0
all_stats = []
for path in sorted((src / "meta/episodes").glob("*/*.parquet")):
    table = pq.read_table(path)
    episodes = table["episode_index"].to_pylist()
    columns = {name: table[name].to_pylist() for name in table.column_names}
    for row, ep in enumerate(episodes):
        start, end, _ = cuts[ep]
        length = end - start
        columns["length"][row] = length
        columns["dataset_from_index"][row] = from_index
        columns["dataset_to_index"][row] = from_index + length
        from_index += length
        for key in video_keys:
            video_start = columns[f"videos/{key}/from_timestamp"][row]
            columns[f"videos/{key}/from_timestamp"][row] = video_start + start / fps
            columns[f"videos/{key}/to_timestamp"][row] = video_start + end / fps
        for key, stats in episode_stats[ep].items():
            for stat_name, value in stats.items():
                columns[f"stats/{key}/{stat_name}"][row] = np.asarray(value).tolist()
        full_stats = dict(episode_stats[ep])
        for key in video_keys:
            full_stats[key] = {s: np.asarray(columns[f"stats/{key}/{s}"][row]) for s in episode_stats[ep]["action"]}
        all_stats.append(full_stats)
    for name, values in columns.items():
        table = replace_column(table, name, values)
    pq.write_table(table, dst / path.relative_to(src))

write_stats(aggregate_stats(all_stats), dst)
info["total_frames"] = next_index
(dst / "meta/info.json").write_text(json.dumps(info, indent=4))

old_total = json.loads((src / "meta/info.json").read_text())["total_frames"]
for ep, (start, end, old_length) in cuts.items():
    print(f"episode {ep:3d}: cut {start / fps:4.1f}s at start, {(old_length - end) / fps:4.1f}s at end")
print(f"total frames {old_total} -> {next_index} ({old_total / fps / 60:.1f} min -> {next_index / fps / 60:.1f} min)")
