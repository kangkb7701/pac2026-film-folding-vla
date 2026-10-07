"""Pick RA-BC kappa so the mean training weight is about 0.6 (target 0.5-0.7), using lerobot's rabc.py formula.

Usage: python choose_kappa.py <training-dataset progress parquet> <n_demo_episodes> [chunk_size=50]
"""

import sys

import numpy as np
import pandas as pd

df = pd.read_parquet(sys.argv[1]).sort_values("index")
n_demo = int(sys.argv[2])
chunk = int(sys.argv[3]) if len(sys.argv) > 3 else 50
p = dict(zip(df["index"].values, df["progress_sparse"].values))
end = df.groupby("episode_index")["index"].max().to_dict()
idx, ep = df["index"].values, df["episode_index"].values

deltas = np.array([p[min(i + chunk, end[e])] - p[i] for i, e in zip(idx, ep)], dtype=np.float64)
valid = ~np.isnan(deltas)
mu, sigma = max(np.mean(deltas[valid]), 0.0), max(np.std(deltas[valid]), 1e-6)
print(f"delta mean {mu:.4f} std {sigma:.4f} | share negative {np.mean(deltas[valid] < 0):.2f}")


def weights(kappa):
    soft = np.clip((deltas - (mu - 2 * sigma)) / (4 * sigma + 1e-6), 0, 1)
    w = np.where(deltas > kappa, 1.0, np.where(deltas >= 0, soft, 0.0))
    return np.where(valid, w, 1.0)


grid = np.round(np.arange(0.01, 0.40, 0.005), 3)
means = np.array([weights(k).mean() for k in grid])
for k, m in zip(grid[::6], means[::6]):
    print(f"  kappa {k:.3f}: mean weight {m:.2f}")
best = grid[np.argmin(np.abs(means - 0.6))]
w = weights(best)
demo = ep < n_demo
print(f"CHOSEN kappa {best:.3f}: mean weight {w.mean():.2f} | demo {w[demo].mean():.2f} | HIL {w[~demo].mean():.2f} | zero-weight share {np.mean(w == 0):.2f}")
