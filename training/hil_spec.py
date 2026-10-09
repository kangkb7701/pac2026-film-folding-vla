"""Turn hil_labels.json of a human-only intervention recording into a build_hil_subset.py spec.

Usage: python hil_spec.py <hil_labels.json> <spec.json> [--success-only]

The recorder (remote_edge main_edge.py) keeps only the human corrections of an attempt, stored back to
back as one episode; "interventions" holds each correction's [start, end) frames. Every correction becomes
its own training episode, so the jump between two corrections never sits inside an episode.
Corrections from failed attempts are kept by default: the outcome is about the whole attempt, not about
each correction (a clean tear-off can come before a failed fold). --success-only drops them.
"""

import json
import sys

labels = json.loads(open(sys.argv[1], encoding="utf-8").read())
success_only = "--success-only" in sys.argv[3:]
spec = [
    {"episode": e["episode_index"], "start": start, "end": end}
    for e in labels
    if e["success"] or not success_only
    for start, end in e["interventions"]
]
with open(sys.argv[2], "w") as f:
    json.dump(spec, f, indent=1)
print(f"{len(spec)} corrections from {len({s['episode'] for s in spec})} episodes -> {sys.argv[2]}")
