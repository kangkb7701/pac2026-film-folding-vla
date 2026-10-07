"""Judge whether SARM separates success from failure on the policy-only HIL episodes.

Usage: python eval_sarm.py <hil progress parquet> <hil_labels.json>
Pass rule (agreed with the user): failure median final progress < 0.6, success median > 0.8, AUROC >= 0.85.
"""

import json
import sys

import numpy as np
import pandas as pd

df = pd.read_parquet(sys.argv[1])
labels = json.load(open(sys.argv[2]))
col = "progress_sparse"

final = {}
for ep, g in df.sort_values("index").groupby("episode_index"):
    final[int(ep)] = float(np.nanmean(g[col].values[-30:]))  # last 1 s

auto = [e for e in labels if not e["interventions"]]
succ = np.array([final[e["episode_index"]] for e in auto if e["success"]])
fail = np.array([final[e["episode_index"]] for e in auto if not e["success"]])
auroc = np.mean([[s > f for f in fail] for s in succ]) + 0.5 * np.mean([[s == f for f in fail] for s in succ])

print("policy-only episodes, final progress (mean of last 1 s):")
for e in auto:
    print(f"  ep{e['episode_index']:3d} {'success' if e['success'] else 'FAIL   '} {final[e['episode_index']]:.2f}")
print(f"success median {np.median(succ):.2f} | failure median {np.median(fail):.2f} | AUROC {auroc:.2f}")

rise = []
for e in labels:
    if e["interventions"] and e["success"]:
        g = df[df.episode_index == e["episode_index"]].sort_values("index")[col].values
        t = e["interventions"][0][0]
        rise.append((g[max(0, t - 15):t + 15].mean(), g[-30:].mean()))
if rise:
    rise = np.array(rise)
    print(f"corrected episodes: progress at takeover {np.median(rise[:, 0]):.2f} -> at end {np.median(rise[:, 1]):.2f} (median)")

passed = np.median(fail) < 0.6 and np.median(succ) > 0.8 and auroc >= 0.85
print("DECISION:", "PASS -> use RA-BC" if passed else "FAIL -> train without RA-BC")
