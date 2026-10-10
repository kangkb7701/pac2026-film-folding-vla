"""SARM 진행도 곡선 점검: 정상 재생, 60%까지 갔다가 처음으로 되감기, 전체 역재생.

사용: python sarm_curve_check.py <데이터셋 폴더> <SARM pretrained_model> <결과 json> <에피소드들, 예: 32,37,11,0>
결과 json에는 에피소드마다 (위치, 진행도, 예측 단계)가 10프레임 간격으로 들어갑니다. 라벨이 있으면 정답 진행도(gt)도 넣습니다.
"""
import sys, json, glob, numpy as np, pandas as pd, torch
from lerobot.datasets import LeRobotDataset
from lerobot.rewards.sarm.modeling_sarm import SARMRewardModel
from lerobot.rewards.sarm.processor_sarm import make_sarm_pre_post_processors
from lerobot.rewards.sarm.sarm_utils import find_stage_and_tau, normalize_stage_tau

ROOT = sys.argv[1]; CKPT = sys.argv[2]; OUT = sys.argv[3]
EPS = [int(x) for x in sys.argv[4].split(",")]
STEP = 10
m = SARMRewardModel.from_pretrained(CKPT); m.config.device = "cuda"; m.to("cuda").eval()
cfg = m.config
ds = LeRobotDataset("local/x", root=ROOT)
pre, _ = make_sarm_pre_post_processors(config=cfg, dataset_stats=ds.meta.stats, dataset_meta=None)
pre.eval() if hasattr(pre, "eval") else None
for s in pre.steps:
    if hasattr(s, "eval"): s.eval()
deltas = np.array(cfg.observation_delta_indices); c = cfg.n_obs_steps // 2
eps_df = ds.meta.episodes.to_pandas()
props = dict(zip(cfg.dense_subtask_names, cfg.dense_temporal_proportions))

def query(img, st, seq, ep, task):
    out = []
    for p in range(0, len(seq), STEP):
        w = seq[np.clip(p + deltas, 0, len(seq) - 1)]
        b = {cfg.image_key: img[w], cfg.state_key: st[w], "task": task, "index": p, "episode_index": ep}
        with torch.no_grad():
            pr = pre(b)
            r, probs = m.calculate_rewards(pr["text_features"], pr["video_features"], pr.get("state_features"),
                                           pr.get("lengths"), return_all_frames=True, return_stages=True, head_mode="dense")
        out.append((p, float(r[0, c]), int(probs[0, c].argmax())))
    return out

res = {}
for ep in EPS:
    row = eps_df[eps_df.episode_index == ep].iloc[0]
    a, b = int(row.dataset_from_index), int(row.dataset_to_index); L = b - a
    frames = [ds[i] for i in range(a, b)]
    img = torch.stack([f[cfg.image_key] for f in frames]); st = torch.stack([f[cfg.state_key] for f in frames])
    task = frames[0]["task"]
    fwd = query(img, st, np.arange(L), ep, task)
    M = int(L * 0.6)
    rw_seq = np.concatenate([np.arange(M), np.arange(M - 1, -1, -1)])  # 60%까지 진행 후 처음으로 되감기
    rw = query(img, st, rw_seq, ep, task)
    rev = query(img, st, np.arange(L)[::-1].copy(), ep, task)  # 전체 역재생
    gt = None
    names = row.get("dense_subtask_names")
    if names is not None and not (isinstance(names, float)):
        gt = [float(normalize_stage_tau(find_stage_and_tau(p, L, list(names), list(row.dense_subtask_start_frames),
               list(row.dense_subtask_end_frames), cfg.dense_subtask_names, props, return_combined=True),
               temporal_proportions=props, subtask_names=cfg.dense_subtask_names)) for p, _, _ in fwd]
    res[ep] = dict(L=L, M=M, task=task, fwd=fwd, rewind=rw, reverse=rev, gt=gt)
    print(ep, L, "done", flush=True)
json.dump(res, open(OUT, "w"))
