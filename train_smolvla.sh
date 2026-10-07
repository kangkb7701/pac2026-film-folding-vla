#!/usr/bin/env bash
# SmolVLA 파인튜닝 (LeRobot v0.6.1, 클라우드 Linux GPU용)
#
# 클라우드 준비 (처음 한 번)
#   nvidia-smi    # 드라이버 버전 확인
#   conda create -y -n lerobot python=3.12 && conda activate lerobot
#   conda install -y ffmpeg -c conda-forge
#   # PyPI 기본 torch는 드라이버 580.65 이상이 필요하다. 그보다 낮으면 cu128 torch를 먼저 설치(드라이버 570.86 이상).
#   # pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
#   pip install "lerobot[training,smolvla]==0.6.1"
#   hf auth login
#
# 처음 학습 (smolvla_base에서 시작)
#   bash train_smolvla.sh <데이터셋 repo_id> <실행 이름>
#   예) bash train_smolvla.sh user/fold_film_onearm_demo smolvla_onearm_v1
#
# 이어 학습 (1차 모델 체크포인트에서 시작, 합친 데이터로)
#   hf download user/smolvla_onearm_v1 --revision 010000 --local-dir ckpt_v1_010000
#   BASE_POLICY=ckpt_v1_010000 bash train_smolvla.sh user/fold_film_onearm_v2data smolvla_onearm_v2
#
# 설정 근거
#   - 배치 64, 2만 스텝: LeRobot SmolVLA 공식 문서 예시, 해커톤 팀 설정과 동일
#   - VLM 고정, 동작 부분만 학습, 학습률 1e-4 스케줄: SmolVLA 기본값(따로 지정하지 않음)
#   - LeRobot 기본값은 배치 8, 10만 스텝, 저장 주기 2만이라 아래 셋은 반드시 지정한다
#   - 5천 스텝마다 체크포인트를 Hub에 올리고 스텝 번호 태그(005000, 010000 ...)를 붙인다
#
# 로그는 200스텝마다 찍힌다. 첫 로그의 스텝당 시간으로 전체 학습 시간을 계산할 것.
set -euo pipefail

DATASET="${1:?데이터셋 repo_id가 필요합니다}"
RUN="${2:?실행 이름이 필요합니다}"

BASE_POLICY="${BASE_POLICY:-lerobot/smolvla_base}"
STEPS="${STEPS:-20000}"
BATCH_SIZE="${BATCH_SIZE:-64}"
SAVE_FREQ="${SAVE_FREQ:-5000}"
NUM_WORKERS="${NUM_WORKERS:-8}"

HF_USER=$(NO_COLOR=1 hf auth whoami | awk -F': *' 'NR==1 {print $2}')

lerobot-train \
    --policy.path="${BASE_POLICY}" \
    --policy.repo_id="${HF_USER}/${RUN}" \
    --policy.device=cuda \
    --dataset.repo_id="${DATASET}" \
    --batch_size="${BATCH_SIZE}" \
    --steps="${STEPS}" \
    --save_freq="${SAVE_FREQ}" \
    --num_workers="${NUM_WORKERS}" \
    --save_checkpoint_to_hub=true \
    --output_dir="outputs/train/${RUN}" \
    --job_name="${RUN}" \
    --wandb.enable=false \
    2>&1 | tee "train_${RUN}.log"
