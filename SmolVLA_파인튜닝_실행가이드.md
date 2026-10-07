# SmolVLA 파인튜닝 실행 가이드 (LeRobot 0.6.1, 로컬 GPU)

연구실 GPU PC(RTX 3090)에서 시연 데이터로 1차 학습을 하고, 개입 데이터를 더해 2차 학습을 하는 순서입니다. 각 단계를 왜 그렇게 하는지는 `SmolVLA_파인튜닝_진행기록.md`에 있습니다. 클라우드 A100으로 1차 학습만 할 때의 방법은 `학습방법_SmolVLA_파인튜닝.md`를 보세요.

경로는 GPU PC 기준입니다. 이 저장소는 `/home/aivlab/PAC_robotarm/pac2026-film-folding-vla`, 데이터셋은 `/home/aivlab/PAC_robotarm/lerobot_data/lerobot_data`, 학습 결과는 `/home/aivlab/PAC_robotarm/outputs/train`에 둡니다. 아래 명령은 모두 `/home/aivlab/PAC_robotarm`에서 실행합니다.

## 0. 환경 준비 (한 번만)

```
conda create -y -n lerobot061 python=3.12 && conda activate lerobot061
conda install -y ffmpeg -c conda-forge
pip install "lerobot[training,smolvla,feetech,sarm]==0.6.1"
pip install --no-deps pynput python-xlib
```

- 마지막 줄은 로봇을 이 PC에 직접 연결해 키보드로 조작할 때만 필요합니다. `pynput`을 그냥 설치하면 의존 패키지 `evdev`가 커널 헤더와 맞지 않아 빌드에 실패합니다. `evdev`는 풋페달에만 쓰입니다.
- `nvidia-smi`로 GPU가 보이는지, `python -c "import torch; print(torch.cuda.is_available())"`가 `True`인지 확인합니다.
- 같은 PC에 있는 다른 lerobot 환경(`lerobot`, `lerobot_main`)은 버전이 달라서 쓰지 않습니다.

## 1. 시연 데이터 점검과 정지 구간 자르기

```
DATA=lerobot_data/lerobot_data
python pac2026-film-folding-vla/training/trim_idle.py $DATA/fold_film_onearm_demo $DATA/fold_film_onearm_demo_trimmed
```

- 에피소드마다 처음 움직이기 0.3초 전부터, 마지막 움직임 1초 뒤까지만 남깁니다(관절 하나라도 2도 넘게 움직이면 움직임으로 봄).
- 영상은 다시 인코딩하지 않고 통계(`stats.json`)까지 다시 계산합니다. 원본은 그대로 둡니다.
- 출력 마지막 줄의 프레임 수 변화를 확인합니다. 우리 데이터는 33,807 → 23,804였습니다.

## 2. 1차 학습

```
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=kangkb7701/fold_film_onearm_demo_trimmed \
  --dataset.root=$PWD/$DATA/fold_film_onearm_demo_trimmed \
  --batch_size=64 \
  --steps=20000 \
  --output_dir=outputs/train/smolvla_onearm_v1 \
  --job_name=smolvla_onearm_v1 \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --save_freq=5000 \
  --wandb.enable=false
```

- 3090에서 스텝당 약 1초, 2만 스텝에 약 5시간 40분입니다. VRAM은 약 14.4GB입니다.
- `--dataset.root`를 주면 Hugging Face에 데이터셋을 올리지 않아도 됩니다. `repo_id`는 이름표 역할만 합니다.
- 체크포인트는 `outputs/train/smolvla_onearm_v1/checkpoints/<스텝>/pretrained_model`에 생깁니다. Hugging Face에 올리려면 `--policy.push_to_hub=false` 대신 `--policy.repo_id=<아이디>/<이름> --save_checkpoint_to_hub=true`를 줍니다. 저장소는 기본으로 공개로 만들어지니, 비공개로 하려면 `--policy.private=true`도 줍니다.
- 로그 첫머리에 `Auto-scaling LR scheduler`가 나오는 건 정상입니다(워밍업 1000→666, 감쇠 30000→20000).

## 3. 로봇에서 돌려보기 (원격 추론)

로봇은 노트북에, 추론은 GPU PC에 둡니다. 정책 서버 실행과 노트북 설정은 `remote_edge/README.md`를 따릅니다. 서버 명령의 `--policy_path`만 쓰려는 체크포인트로 바꾸면 됩니다.

- 서버는 반드시 `lerobot061` 환경에서 띄웁니다. 체크포인트를 만든 버전과 같아야 합니다.
- 체크포인트를 비교할 때는 같은 조건으로 여러 번 돌리고, 일부러 비닐을 놓치게 한 상황도 넣어서 복구하는지 봅니다.

## 4. 개입 데이터 모으기

노트북에서 `remote_edge\run_edge_hil.bat`으로 모읍니다. 사용법과 키는 `remote_edge/README.md`와 `SARM_사람개입데이터_정리.md`에 있습니다. 결과는 LeRobot 데이터셋 하나와 `hil_labels.json`(에피소드별 성공 여부와 사람이 조종한 프레임 구간)입니다.

- 실패했는데 실수로 저장한 에피소드가 있으면 `hil_labels.json`에 적어 두거나 기억해 두었다가 5단계에서 뺍니다(이번 데이터의 23번).
- 시도가 끝나면 사람 손이 화면에 들어오기 전에 저장 키를 누릅니다. 손이 비닐을 만지는 장면이 섞이면 잘라내야 합니다.

## 5. 2차 학습 데이터 만들기

규칙은 이렇습니다.
- 정책만으로 성공한 에피소드는 통째로 넣습니다.
- 사람이 넘겨받아 성공한 에피소드는 넘겨받은 순간부터 끝까지만 잘라 **두 번** 넣습니다. 두 번 넣는 게 가중치 2배와 같은 효과를 냅니다.
- 실패한 에피소드와 넘겨받기 전의 자율 구간은 뺍니다.

### 5-1. 잘라낼 구간 정하기

```
HIL=pac2026-film-folding-vla/datasets/fold_film_onearm_hil
python - <<'EOF'
import json
L = json.load(open('pac2026-film-folding-vla/datasets/fold_film_onearm_hil/hil_labels.json'))
EXCLUDE = {23}             # 실패했는데 저장된 에피소드
CUT_END = {10: 60, 13: 60}  # 끝에 사람 손이 들어온 에피소드: 잘라낼 프레임 수
auto = [{"episode": e["episode_index"], "start": 0, "end": e["frames"]}
        for e in L if not e["interventions"] and e["success"]]
corr = [{"episode": e["episode_index"], "start": e["interventions"][0][0],
         "end": e["frames"] - CUT_END.get(e["episode_index"], 0)}
        for e in L if e["interventions"] and e["success"] and e["episode_index"] not in EXCLUDE]
json.dump(auto, open('spec_autosuccess.json', 'w')); json.dump(corr, open('spec_corrections.json', 'w'))
print(len(auto), 'auto successes,', len(corr), 'corrections')
EOF
```

이번 데이터는 넘겨받기를 에피소드마다 한 번씩만 했습니다. 여러 번 넘겨받은 에피소드가 생기면 구간마다 따로 항목을 만듭니다.

### 5-2. 부분 데이터셋 만들기

```
python pac2026-film-folding-vla/training/build_hil_subset.py $HIL $DATA/fold_film_onearm_hil_autosuccess spec_autosuccess.json
python pac2026-film-folding-vla/training/build_hil_subset.py $HIL $DATA/fold_film_onearm_hil_corrections_a spec_corrections.json
cp -r $DATA/fold_film_onearm_hil_corrections_a $DATA/fold_film_onearm_hil_corrections_b
```

영상은 다시 인코딩하지 않고, 구간 안의 정지 구간은 1단계와 같은 기준으로 자르며, 통계도 다시 계산합니다.

### 5-3. 합치기

```
R=$PWD/$DATA
lerobot-edit-dataset \
  --new_repo_id=kangkb7701/fold_film_onearm_v2data --new_root=$R/fold_film_onearm_v2data \
  --operation.type=merge \
  --operation.repo_ids="['kangkb7701/fold_film_onearm_demo_trimmed','kangkb7701/fold_film_onearm_hil_autosuccess','kangkb7701/fold_film_onearm_hil_corrections_a','kangkb7701/fold_film_onearm_hil_corrections_b']" \
  --operation.roots="['$R/fold_film_onearm_demo_trimmed','$R/fold_film_onearm_hil_autosuccess','$R/fold_film_onearm_hil_corrections_a','$R/fold_film_onearm_hil_corrections_b']" \
  --operation.concatenate_videos=false
```

마지막에 `Episodes: 128, Frames: 49138`처럼 개수가 나옵니다(이번 데이터 기준). 지시문과 카메라 이름이 모두 같아야 합쳐집니다.

## 6. SARM 학습과 RA-BC 준비 (선택)

SARM이 성공과 실패를 구분할 때만 RA-BC를 씁니다. 구분하지 못하면 6단계를 건너뛰고 7단계를 RA-BC 없이 합니다.

### 6-1. SARM 학습

```
lerobot-train \
  --dataset.repo_id=kangkb7701/fold_film_onearm_demo_trimmed \
  --dataset.root=$PWD/$DATA/fold_film_onearm_demo_trimmed \
  --reward_model.type=sarm \
  --reward_model.annotation_mode=single_stage \
  --reward_model.image_key=observation.images.camera1 \
  --reward_model.push_to_hub=false \
  --reward_model.device=cuda \
  --output_dir=outputs/train/sarm_demo_single \
  --job_name=sarm_demo_single \
  --batch_size=32 \
  --steps=5000 \
  --save_freq=1000 \
  --num_workers=4 \
  --prefetch_factor=2 \
  --wandb.enable=false
```

- 공식 문서에는 `--policy.type=sarm`이라고 돼 있지만, 0.6.1에서는 `--reward_model.type=sarm`이어야 합니다.
- `single_stage`는 라벨 없이 "에피소드에서 지난 시간 비율"을 진행도 정답으로 씁니다. 그래서 깨끗한 성공 시연으로만 학습합니다.
- 스텝당 약 2초, 5천 스텝에 약 2시간 50분입니다. 병목은 영상 디코딩이고, 데이터 로딩 작업자를 늘려도 빨라지지 않습니다. 오히려 14개로 늘렸다가 메모리가 부족해진 적이 있으니 4개로 둡니다.

### 6-2. 진행도 계산

진행도 계산 스크립트는 데이터셋 경로 옵션이 없어서, `HF_LEROBOT_HOME` 폴더 안에 데이터셋 링크를 두고 저장소 이름으로 찾게 합니다.

```
HOME_DIR=$PWD/lerobot_data/hf_home
mkdir -p $HOME_DIR/kangkb7701
ln -sfn $PWD/$DATA/fold_film_onearm_v2data $HOME_DIR/kangkb7701/fold_film_onearm_v2data
HF_LEROBOT_HOME=$HOME_DIR HF_HUB_OFFLINE=1 python -m lerobot.rewards.sarm.compute_rabc_weights \
  --dataset-repo-id kangkb7701/fold_film_onearm_v2data \
  --reward-model-path outputs/train/sarm_demo_single/checkpoints/last/pretrained_model \
  --head-mode sparse --device cuda --stride 5
```

- **`HF_HUB_OFFLINE=1`을 빼면 안 됩니다.** 0.6.1의 이 스크립트는 `--push-to-hub` 기본값이 `True`라서 끌 수 없고, 계산이 끝나면 결과를 Hugging Face의 같은 이름 데이터셋 저장소에 올리려 합니다. 오프라인으로 두면 업로드 단계에서 오류로 끝나지만, 결과 파일은 그 전에 이미 저장돼 있습니다.
- 결과는 데이터셋 폴더의 `sarm_progress.parquet`에 저장됩니다. 학습할 때 프레임 번호로 이 파일을 찾으므로, 반드시 최종 학습 데이터셋(합친 것)에 대해 계산합니다.
- `--stride 5`는 5프레임마다 계산하고 사이는 보간합니다. 빼면 5배 느립니다.

### 6-3. 성공과 실패를 구분하는지 판정

정책만 돌린 에피소드(성공과 실패가 섞인 것)에 대해 6-2처럼 진행도를 계산한 뒤 판정합니다.

```
python pac2026-film-folding-vla/training/eval_sarm.py <진행도 parquet> <hil_labels.json>
```

마지막 1초의 진행도로 실패 중앙값 0.6 미만, 성공 중앙값 0.8 초과, AUROC 0.85 이상이면 `PASS`입니다. `FAIL`이면 RA-BC를 쓰지 않습니다. SARM이 팔 동작만 보고 비닐 상태를 못 보면, 실패하는 동작에 높은 가중치를 주게 되기 때문입니다.

### 6-4. `kappa` 정하기

```
python pac2026-film-folding-vla/training/choose_kappa.py $DATA/fold_film_onearm_v2data/sarm_progress.parquet 50
```

마지막 인자는 합친 데이터 맨 앞에 있는 시연 에피소드 수입니다. 기본값 `kappa=0.01`은 약 90초짜리 작업 기준이라, 평균 16초인 우리 작업에서는 거의 모든 프레임이 가중치 1이 됩니다. 스크립트는 평균 가중치가 약 0.6이 되는 값을 고릅니다(LeRobot 권장 0.3~0.8).

## 7. 2차 학습

```
lerobot-train \
  --policy.path=outputs/train/smolvla_onearm_v1/checkpoints/015000/pretrained_model \
  --dataset.repo_id=kangkb7701/fold_film_onearm_v2data \
  --dataset.root=$PWD/$DATA/fold_film_onearm_v2data \
  --batch_size=64 \
  --steps=20000 \
  --output_dir=outputs/train/smolvla_onearm_v2 \
  --job_name=smolvla_onearm_v2 \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --save_freq=5000 \
  --num_workers=4 \
  --prefetch_factor=2 \
  --wandb.enable=false
```

RA-BC를 쓸 때는 아래를 덧붙입니다.

```
  --sample_weighting.type=rabc \
  --sample_weighting.progress_path=$PWD/$DATA/fold_film_onearm_v2data/sarm_progress.parquet \
  --sample_weighting.head_mode=sparse \
  --sample_weighting.kappa=<6-4에서 고른 값>
```

- 1차의 마지막(2만)이 아니라 1만5천 스텝에서 시작하는 이유는 진행기록 문서에 있습니다. LeRobot 개입 데이터 문서는 이전 정책 체크포인트에서 2만 스텝 이어 학습하라고 합니다.
- 체크포인트에서 시작해도 정규화 통계는 새 데이터셋 것으로 바뀝니다. 정상 동작입니다.
- RA-BC를 쓰면 로그에 `sample_weight` 관련 값이 찍힙니다. 평균 가중치가 0.3~0.8 범위인지 봅니다.

## 8. 학습 중 관리

- **터미널과 분리해서 실행:** 원격 접속이 끊겨도 학습이 계속되도록 `setsid nohup <명령> > <로그> 2>&1 &`로 띄우거나 `tmux` 안에서 돌립니다. 이 PC에는 tmux가 없습니다.
- **메모리 감시:** `training/mem_guard.sh <pgid 파일> <로그>`는 사용 가능한 RAM이 5GB 아래로 떨어지면 학습 프로세스 그룹(데이터 로딩 작업자 포함)을 멈춥니다. 다른 사람의 서비스와 같이 쓰는 PC라 꼭 붙입니다.
- **학습은 하나씩만:** SmolVLA(약 16GB)와 SARM(약 6~12GB)을 동시에 돌리면 GPU 24GB를 넘습니다.
- **진행 확인:** 로그에서 `step:` 줄을 봅니다. 손실(`loss`), 학습률(`lr`), 데이터 대기 시간(`data_s`), 메모리(`mem_gb`)가 찍힙니다. 프로세스를 찾을 때는 `ps -eo pid,cmd | grep "[l]erobot-train"`을 씁니다. `pkill -f`에 작업 이름을 넣으면 그 명령을 실행한 셸까지 같이 죽을 수 있습니다.
- **중간에 죽었을 때:** 마지막 체크포인트부터 이어 학습합니다. 이때는 체크포인트에 저장된 정규화 통계를 그대로 씁니다. 아래 명령은 0.6.1 코드로 확인한 것이고, 아직 실제로 재개해 본 적은 없습니다.

```
lerobot-train --config_path=outputs/train/smolvla_onearm_v2/checkpoints/last/pretrained_model/train_config.json --resume=true
```

## 9. 결과 쓰기

- 로봇 쪽에서는 `checkpoints/<스텝>/pretrained_model` 폴더만 있으면 됩니다(약 0.9GB). `training_state`는 이어 학습할 때만 필요합니다.
- 원격 추론이면 3단계처럼 서버의 `--policy_path`만 바꿉니다.
- 한 팔 작업의 팔 이름은 2026-10-07 캘리브레이션 정리 이후 `bimanual_follower_right`, `bimanual_leader_right`입니다(`calibration/README.md`).
