#!/usr/bin/env bash
# SARM(dense_only, 6단계 라벨) 학습. 대회 과제 51개 기준 A100 80GB에서 스텝당 약 1.5초, 5천 스텝 2시간 11분.
# 데이터셋은 make_sarm_top_copy.py로 만든 상단 카메라 298x224 사본입니다.
# 사용: DATA=<사본 폴더> EPISODES="[0..10, 12..31, 33..36, 38..50]" bash train_sarm_dense.sh
set -euo pipefail
DATA=${DATA:?데이터셋 폴더}
RUN=${RUN:-sarm_pac_dense}
EP_ARG=()
[ -n "${EPISODES:-}" ] && EP_ARG=(--dataset.episodes="${EPISODES}")
lerobot-train \
  --dataset.repo_id=local/$(basename "$DATA") \
  --dataset.root="$DATA" \
  "${EP_ARG[@]}" \
  --reward_model.type=sarm \
  --reward_model.annotation_mode=dense_only \
  --reward_model.image_key=observation.images.top \
  --reward_model.push_to_hub=false \
  --reward_model.device=cuda \
  --output_dir=outputs/train/${RUN} \
  --job_name=${RUN} \
  --batch_size=32 \
  --steps=${STEPS:-5000} \
  --save_freq=1000 \
  --log_freq=50 \
  --num_workers=8 \
  --prefetch_factor=1 \
  --wandb.enable=false 2>&1 | tee train_${RUN}.log
