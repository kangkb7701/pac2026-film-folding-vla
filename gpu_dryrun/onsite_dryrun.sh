#!/usr/bin/env bash
# Rehearse the on-site training path on the GPU PC before the event (about 15-20 minutes):
#   1) two copies of a recorded dataset get different task strings (stand-ins for the grab / fold recordings)
#   2) merge them into one multi-task dataset
#   3) train 200 steps from the rehearsal v2 checkpoint (batch 8, just to prove it runs)
#   4) load the result the way the policy server does and predict under both task strings
# Nothing here touches the real datasets or checkpoints; everything goes to $WORK.
#
# Usage (conda env lerobot061, from the repo root):
#   bash gpu_dryrun/onsite_dryrun.sh <recorded dataset dir> <v2 checkpoint pretrained_model dir>
# Example:
#   bash gpu_dryrun/onsite_dryrun.sh datasets/fold_film_onearm_hil \
#     ~/PAC_robotarm/outputs/train/smolvla_onearm_v2/checkpoints/020000/pretrained_model
set -euo pipefail

SRC=$(realpath "$1")
CKPT=$(realpath "$2")
WORK=${WORK:-/tmp/pac_dryrun}
GRAB="Grab the film end."
FOLD="Fold the film into the square."
rm -rf "$WORK"; mkdir -p "$WORK"
T0=$(date +%s)

echo "== 1) copies with new task strings"
cp -r "$SRC" "$WORK/pac_grab"; cp -r "$SRC" "$WORK/pac_fold"
rm -rf "$WORK/pac_grab/images" "$WORK/pac_fold/images"
lerobot-edit-dataset --repo_id local/pac_grab --root "$WORK/pac_grab" --operation.type modify_tasks --operation.new_task "$GRAB"
lerobot-edit-dataset --repo_id local/pac_fold --root "$WORK/pac_fold" --operation.type modify_tasks --operation.new_task "$FOLD"

echo "== 2) merge"
lerobot-edit-dataset --new_repo_id local/pac_multitask --new_root "$WORK/pac_multitask" --operation.type merge \
  --operation.repo_ids "['local/pac_grab','local/pac_fold']" \
  --operation.roots "['$WORK/pac_grab','$WORK/pac_fold']" \
  --operation.concatenate_videos false

echo "== 3) train 200 steps from $CKPT"
T1=$(date +%s)
lerobot-train --policy.path="$CKPT" \
  --dataset.repo_id=local/pac_multitask --dataset.root="$WORK/pac_multitask" \
  --batch_size=8 --steps=200 --save_freq=200 --log_freq=50 \
  --output_dir="$WORK/train" --job_name=pac_dryrun \
  --policy.device=cuda --policy.push_to_hub=false --num_workers=4 --wandb.enable=false
T2=$(date +%s)

echo "== 4) server-style predict under both tasks"
python gpu_dryrun/dryrun_predict.py --policy_path "$WORK/train/checkpoints/000200/pretrained_model" --tasks "$GRAB" "$FOLD"

echo "== done: data prep $((T1 - T0))s, 200 training steps $((T2 - T1))s (batch 8), total $(( $(date +%s) - T0 ))s"
echo "   (the real run uses batch 64: about 1.0 s/step on the 3090 per SmolVLA_파인튜닝_진행기록.md)"
