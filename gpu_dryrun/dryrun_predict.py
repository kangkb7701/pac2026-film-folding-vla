"""Load a checkpoint the way the policy server does and ask it for action chunks under several task strings.

Checks the on-site path end to end before the event: a multi-task checkpoint loads in the server's ActPolicy,
accepts the new task strings, returns (n_steps, 6) chunks, and the task string actually changes the output.

    python gpu_dryrun/dryrun_predict.py --policy_path <checkpoint>/pretrained_model \
        --tasks "Grab the film end." "Fold the film into the square."
The dataset is read from train_config.json next to the weights (same as the server).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "remote_edge"))
from so101_pipeline.servers.act_policy_server import ActPolicy  # noqa: E402


def frame_request(ds, idx: int, task: str) -> dict:
    item = ds[idx]
    images = {}
    for key in ds.meta.camera_keys:
        rgb = (item[key].permute(1, 2, 0).numpy() * 255).clip(0, 255).astype(np.uint8)
        ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        images[key.split(".")[-1]] = jpg.tobytes()  # the edge sends camera1/camera2 as JPEG bytes
    names = ds.features["observation.state"]["names"]
    joints = {n.removesuffix(".pos"): float(v) for n, v in zip(names, item["observation.state"])}
    return {"task": task, "joints": joints, "images": images}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--policy_path", required=True)
    p.add_argument("--tasks", nargs="+", required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--frames", type=int, nargs="*", default=None, help="Dataset frame indices (default: first and middle).")
    a = p.parse_args()

    cfg = json.loads((Path(a.policy_path) / "train_config.json").read_text())["dataset"]
    args = argparse.Namespace(policy_path=a.policy_path, dataset_repo_id=cfg["repo_id"], dataset_root=cfg.get("root"),
                              device=a.device, robot_type="so_follower", token=None, mock=False)
    t0 = time.perf_counter()
    pol = ActPolicy(args)
    print(f"loaded in {time.perf_counter() - t0:.1f}s; dataset tasks: {list(pol.dataset.meta.tasks.index)}")
    unknown = [t for t in a.tasks if t not in set(pol.dataset.meta.tasks.index)]
    if unknown:
        print(f"WARNING: not in the training data (exact text matters): {unknown}")

    frames = a.frames or [0, pol.dataset.num_frames // 2]
    ok = True
    for idx in frames:
        chunks = {}
        for task in a.tasks:
            pol.reset()
            t = time.perf_counter()
            out = pol.predict(frame_request(pol.dataset, idx, task))
            ms = (time.perf_counter() - t) * 1000
            c = np.asarray(out["chunk"])
            chunks[task] = c
            print(f"frame {idx} task={task!r}: chunk {c.shape} in {ms:.0f} ms, first step {np.round(c[0], 1).tolist()}")
            ok &= c.ndim == 2 and c.shape[1] == 6 and np.isfinite(c).all()
        if len(chunks) > 1:
            vals = list(chunks.values())
            diff = max(float(np.abs(vals[0] - v).mean()) for v in vals[1:])
            print(f"frame {idx}: mean |difference| between tasks = {diff:.2f} deg "
                  f"({'task string changes the output' if diff > 0.5 else 'task string barely matters'})")
    print("DRY RUN PREDICT:", "OK" if ok else "PROBLEM")


if __name__ == "__main__":
    main()
