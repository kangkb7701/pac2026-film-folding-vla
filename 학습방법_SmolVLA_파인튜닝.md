# SmolVLA 파인튜닝 방법 (LeRobot 0.6.1)

녹화한 데이터를 점검해서 Hugging Face에 올리고, GPU가 있는 원격 서버(클라우드 A100)에서 `train_smolvla.sh`로 학습합니다. 학습된 체크포인트는 Hugging Face에 자동으로 올라가고, 로봇을 돌릴 컴퓨터에서 바로 불러 씁니다. 이 노트북에는 NVIDIA GPU가 없어서 학습은 원격 서버에서 합니다.

## 0. 시작 전 조건

- 데이터는 아래 설정으로 녹화한 것이어야 합니다. 이 설정은 SmolVLA 공식 예시 데이터셋(`lerobot/svla_so100_pickplace`)과 같습니다.
    - 카메라 `camera1` = 상단, `camera2` = 손목. 각 640×480, 30fps, `fourcc: MJPG`
    - 지시문 하나: `Fold the plastic film in half.`
    - `--dataset.streaming_encoding=true`를 쓰지 않고, `--dataset.video_encoding_batch_size=10`을 씁니다. 실시간 인코딩을 켰더니 기록 속도가 15Hz까지 떨어졌습니다.
- 녹화 중에 `Record loop is running slower` 경고가 계속 나왔다면 그 세션은 쓰지 않습니다.
- 에피소드는 약 50개를 모읍니다. 공식 문서는 약 50개를 권하고, 25개로는 부족했다고 합니다.

## 1. 데이터 점검 (노트북)

```
conda activate lerobot312
python robot_scripts\check_dataset.py C:/Users/kangk/lerobot_data/fold_film_onearm_demo
```

확인할 것은 이렇습니다.
- 지시문이 하나인지, 카메라 이름이 `camera1`·`camera2`인지
- `<-- check` 표시가 있는지. 한 스텝에 관절 값이 20 넘게 튄 에피소드라는 뜻으로, 손목이 반 바퀴를 넘어 값이 넘어간 경우 등입니다.
- 시작과 끝에 멈춰 있는 시간(`idle_start_s`, `idle_end_s`)이 너무 긴 에피소드가 있는지
- 마지막 줄이 `all OK`인지. 아니면 영상이 깨진 에피소드가 있다는 뜻입니다.

과제를 실패했거나 문제가 있는 에피소드는 지웁니다.

```
lerobot-edit-dataset --repo_id kangk/fold_film_onearm_demo --root C:/Users/kangk/lerobot_data/fold_film_onearm_demo --operation.type delete_episodes --operation.episode_indices "[3, 17]"
```

관절 값 정규화나 이미지 크기 조절 같은 전처리는 LeRobot이 학습할 때 알아서 하니 따로 할 필요가 없습니다.

## 2. Hugging Face에 업로드 (노트북)

```
hf auth login
hf upload <HF아이디>/fold_film_onearm_demo C:\Users\kangk\lerobot_data\fold_film_onearm_demo --repo-type dataset
```

로그인할 때는 쓰기 권한이 있는 토큰을 씁니다.

## 3. 클라우드 서버 준비

1. 콘솔에서 **A100 80GB 1장짜리 서버**(G-NAHP-80, vCPU 16개, 할인가 시간당 2,500원)를 만듭니다. OS는 Ubuntu로 하고, 가능하면 PyTorch나 CUDA가 깔린 이미지를 고릅니다.
    - MIG 조각 상품(3g-40GB, 2g-20GB)은 연산과 CPU가 모자라서 더 느리고, 총비용도 비슷하거나 더 비쌉니다.
2. 업체가 안내하는 방법(SSH, 웹 터미널 등)으로 서버 터미널에 접속합니다.
3. 환경을 설치합니다.

```
nvidia-smi
conda create -y -n lerobot python=3.12 && conda activate lerobot
conda install -y ffmpeg -c conda-forge
pip install "lerobot[training,smolvla]==0.6.1"
hf auth login
```

`nvidia-smi`에 나오는 드라이버 버전이 580.65보다 낮으면, 위의 `pip install` 전에 CUDA 12.8용 torch를 먼저 설치합니다(드라이버 570.86 이상 필요).

```
pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
```

## 4. 학습 실행 (서버)

`train_smolvla.sh`를 서버로 옮깁니다. 업체의 파일 업로드 기능을 쓰거나 `scp train_smolvla.sh 사용자@서버주소:~/`로 보냅니다. 그다음 접속이 끊겨도 학습이 계속되도록 `tmux` 안에서 실행합니다.

```
tmux new -s train
conda activate lerobot
bash train_smolvla.sh <HF아이디>/fold_film_onearm_demo smolvla_onearm_v1
```

- 창을 닫아도 학습은 계속됩니다. 다시 접속한 뒤 `tmux attach -t train`으로 돌아옵니다.
- 로그는 200스텝마다 찍힙니다. 첫 로그의 스텝당 시간으로 종료 시각을 계산합니다.
- 예상 시간은 A100 1장 기준 2만 스텝에 4~6시간이고, 비용은 약 1만~1만 5천 원입니다.
- 로그는 서버의 `train_smolvla_onearm_v1.log`에도 저장됩니다.

## 5. 학습 설정과 근거

`train_smolvla.sh`는 아래 값만 지정하고, 나머지는 SmolVLA 기본값을 그대로 씁니다.

- **출발 모델 `lerobot/smolvla_base`:** 커뮤니티 데이터 사전학습이 있으면 성공률이 51.7%에서 78.3%로 올랐습니다(SmolVLA 논문).
- **배치 64, 2만 스텝:** 공식 문서 예시와 해커톤 팀 설정입니다. LeRobot 기본값은 배치 8, 10만 스텝이라 꼭 지정해야 합니다.
- **5천 스텝마다 저장:** 체크포인트를 로봇에서 비교해 고르기 위해서입니다. LeRobot 기본값은 2만 스텝입니다.
- **VLM 고정, 동작 부분만 학습, 학습률 1e-4 스케줄:** SmolVLA 기본값입니다. 논문도 VLM을 고정하고 동작 부분만 학습했습니다.
- **카메라 이름 변환 없음:** smolvla_base는 카메라 이름을 `camera1`~`camera3`으로 기대합니다(논문 기준 top, wrist, side 순서). 우리 데이터가 `camera1`·`camera2`라 그대로 통과합니다. 이름이 겹치지 않으면 LeRobot이 학습을 에러로 멈춥니다(코드로 확인).

## 6. 결과 받기와 평가

스크립트가 5천 스텝마다 체크포인트를 `<HF아이디>/smolvla_onearm_v1`에 올리고, 스텝 번호 태그(`005000`, `010000`, `015000`, `020000`)를 붙입니다.

평가는 GPU가 있는 로봇 컴퓨터에서 합니다. 체크포인트마다 10번씩 돌려서 성공률을 비교합니다. 로봇 쪽 카메라 이름도 학습 데이터와 같은 `camera1`·`camera2`여야 합니다. 이 명령은 아직 실제로 돌려 보지 않았으니, 처음 실행할 때 출력을 확인하세요.

```
lerobot-rollout --strategy.type=episodic --policy.path=<HF아이디>/smolvla_onearm_v1 --policy.pretrained_revision=010000 --robot.type=so101_follower --robot.port=COM3 --robot.id=bimanual_follower_right --robot.cameras="{ camera1: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: MJPG}, camera2: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG}}" --teleop.type=so101_leader --teleop.port=COM5 --teleop.id=bimanual_leader_right --task="Fold the plastic film in half." --dataset.repo_id=kangk/eval_v1_010000 --dataset.root=C:/Users/kangk/lerobot_data/eval_v1_010000 --dataset.single_task="Fold the plastic film in half." --dataset.num_episodes=10 --dataset.episode_time_s=30 --dataset.reset_time_s=20 --dataset.push_to_hub=false --dataset.video_encoding_batch_size=10
```

- 포트(COM3, COM5)와 카메라 번호는 그 컴퓨터에서 다시 확인합니다. 캘리브레이션 파일은 `calibration` 폴더의 README를 따라 옮깁니다.
- 성공/실패는 LeRobot이 기록하지 않습니다. 에피소드마다 `{"0": 1, "1": 0, ...}` 형식의 JSON으로 직접 적어 둡니다. 나중에 가치 함수(SARM) 학습 데이터를 고를 때 씁니다.
- 체크포인트를 바꿀 때는 `--policy.pretrained_revision`과 데이터셋 이름을 함께 바꿉니다.

## 7. 끝나면

- 클라우드 서버를 끕니다. 켜져 있는 동안 계속 과금됩니다.
- 체크포인트는 이미 Hugging Face에 있으니 서버에서 따로 내려받을 필요가 없습니다.

## 이어 학습 (개입 데이터를 모은 뒤)

시연 데이터와 개입 데이터를 합친 다음, 1차 모델 체크포인트에서 이어서 학습합니다.

```
lerobot-edit-dataset --new_repo_id <HF아이디>/fold_film_onearm_v2data --operation.type merge --operation.repo_ids "['<HF아이디>/fold_film_onearm_demo', '<HF아이디>/fold_film_onearm_dagger_v1']"
```

서버에서는 이렇게 실행합니다.

```
hf download <HF아이디>/smolvla_onearm_v1 --revision 010000 --local-dir ckpt_v1_010000
BASE_POLICY=ckpt_v1_010000 bash train_smolvla.sh <HF아이디>/fold_film_onearm_v2data smolvla_onearm_v2
```

## 자주 나올 문제

- **`'repo_id' argument missing`:** `--policy.repo_id`가 없을 때 납니다. 스크립트에는 이미 들어 있습니다.
- **카메라 이름 관련 에러:** 데이터셋 카메라 이름이 `camera1`·`camera2`가 아닐 때 납니다. 녹화 명령의 카메라 이름을 확인하세요.
- **CUDA 관련 에러:** 서버 드라이버가 낮을 때 납니다. 3단계의 cu128 torch 설치를 하세요.
- **연구실 3090으로 돌릴 때:** 방법은 같고, 2만 스텝에 약 10시간 걸립니다(카메라 2대, 배치 64 사례).
