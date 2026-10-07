# 리허설 한 팔 LeRobot 명령어 (LeRobot v0.6.1)

과제는 한쪽이 고정된 비닐을 한 팔로 반 접기입니다. 모든 명령어와 옵션 이름은 LeRobot v0.6.1(2026-08-03 배포)의 공식 문서와 소스 코드로 확인했습니다. 실제 로봇에서 돌려 본 것은 아니니, 처음 실행할 때 출력 메시지를 꼭 확인하세요.

## 공통으로 정해 둘 값

아래 값들은 녹화, 학습, 실행 내내 바꾸지 않습니다.

- **LeRobot 버전:** 0.6.1. 로봇 PC와 클라우드 모두 같은 버전입니다.
- **로봇 id:** `rehearsal_follower`, `rehearsal_leader`. 캘리브레이션 파일이 이 이름으로 저장되니 모든 명령에 같은 id를 씁니다.
- **카메라 이름:** `top`, `wrist`. 둘 다 640×480, 30fps입니다.
- **지시문:** `Fold the plastic film in half.` 한 글자도 바꾸지 않습니다.
- **에피소드 최대 길이:** 30초, 리셋 시간은 20초입니다.

포트 이름은 OS마다 다릅니다. Linux는 `/dev/ttyACM0`, macOS는 `/dev/tty.usbmodem…`, Windows는 `COM3` 같은 형식입니다. 아래 명령은 Linux 기준이니 자기 포트로 바꾸세요.

## 1. 설치 (로봇 PC)

```bash
conda create -y -n lerobot python=3.12
conda activate lerobot
conda install ffmpeg -c conda-forge
pip install "lerobot[core_scripts,feetech,smolvla]==0.6.1"
hf auth login        # 쓰기 권한 토큰
HF_USER=$(NO_COLOR=1 hf auth whoami | awk -F': *' 'NR==1 {print $2}')
echo $HF_USER
```

- `core_scripts`는 녹화, 재생, 캘리브레이션용이고, `feetech`는 SO-101 모터 드라이버, `smolvla`는 로봇 PC에서 정책을 돌릴 때 필요합니다.
- Python은 3.12 이상이 필요합니다.

## 2. 포트 찾기

```bash
lerobot-find-port
```

팔로워와 리더를 하나씩 뽑았다 꽂으며 각각의 포트를 확인합니다. Linux에서 권한 에러가 나면 `sudo chmod 666 /dev/ttyACM0`처럼 권한을 줍니다.

모터 id를 처음 설정하는 경우(새 모터)에만 아래를 실행합니다. 이미 조립해서 써 왔다면 건너뜁니다.

```bash
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/ttyACM0
lerobot-setup-motors --teleop.type=so101_leader --teleop.port=/dev/ttyACM1
```

## 3. 캘리브레이션 (고무 끝단을 붙인 뒤에)

고무를 붙이면 그리퍼가 닫히는 위치가 바뀌니, 반드시 붙인 다음에 합니다. 이후로는 고무를 바꾸지 마세요.

```bash
lerobot-calibrate \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower

lerobot-calibrate \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM1 \
    --teleop.id=rehearsal_leader
```

먼저 모든 관절을 가동 범위 가운데쯤에 두고 Enter를 누른 뒤, 각 관절을 끝에서 끝까지 움직입니다.

## 4. 카메라 찾기

```bash
lerobot-find-cameras opencv
```

나온 번호(`Id`)로 상단과 손목 카메라를 구분합니다. 번호는 재부팅하거나 다시 꽂으면 바뀔 수 있으니, 녹화 전마다 확인합니다. 손목 카메라는 PC에 USB 카메라(UVC)로 잡혀야 합니다. Raspberry Pi 전용 리본 케이블(CSI) 카메라는 여기서 보이지 않습니다.

## 5. 카메라를 띄운 채로 조종해 보기

```bash
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower \
    --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM1 \
    --teleop.id=rehearsal_leader \
    --display_data=true
```

화면만 보고도 과제를 할 수 있는지 확인합니다. 공식 문서의 기준이 "카메라 화면만 보고 사람이 과제를 할 수 있어야 한다"입니다. 비닐이 화면에 잘 안 보이면 이 단계에서 조명, 배경, 카메라 위치를 고칩니다.

## 6. 시연 녹화 (50개)

비닐 위치나 상태를 5가지로 정하고, 한 가지당 10개씩 세션을 나눠 녹화합니다. 각 세션에 복구 시연(놓친 비닐 다시 집기 등)을 1~2개씩 섞습니다.

**첫 세션 (10개)**

```bash
lerobot-record \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower \
    --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM1 \
    --teleop.id=rehearsal_leader \
    --display_data=true \
    --dataset.repo_id=${HF_USER}/fold_film_onearm_demo \
    --dataset.root=$HOME/lerobot_data/fold_film_onearm_demo \
    --dataset.single_task="Fold the plastic film in half." \
    --dataset.num_episodes=10 \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=20 \
    --dataset.fps=30 \
    --dataset.private=true \
    --dataset.streaming_encoding=true
```

**다음 세션부터 (이어서 10개씩)**

같은 명령에 `--resume=true`만 붙입니다. `--dataset.num_episodes`는 총 개수가 아니라 이번에 더 녹화할 개수(10)입니다. 이어 녹화하려면 `--dataset.root`가 꼭 있어야 하니 첫 세션과 같은 경로를 씁니다.

```bash
lerobot-record \
    ... (위와 동일) ... \
    --dataset.num_episodes=10 \
    --resume=true
```

**녹화 중 키보드**
- `→` 또는 `n`: 지금 에피소드(또는 리셋 시간)를 일찍 끝내고 다음으로 넘어갑니다. 과제를 마치면 바로 누르세요.
- `←` 또는 `r`: 지금 에피소드를 버리고 다시 녹화합니다.
- `ESC` 또는 `q`: 세션을 끝내고 영상을 인코딩한 뒤 업로드합니다.

**녹화 규칙**
- 접는 순서와 방식은 매번 같게 합니다.
- 세션마다 상단 카메라를 1~2cm씩 일부러 옮깁니다.
- 몇 개마다 화면을 보고 카메라 두 대가 다 찍히는지 확인합니다.
- 에피소드는 과제를 마치면 바로 `→`로 끝냅니다. 30초를 다 채울 필요는 없습니다.

## 7. 녹화 확인

- **웹에서 보기:** [LeRobot 데이터셋 시각화](https://huggingface.co/spaces/lerobot/visualize_dataset)에 `${HF_USER}/fold_film_onearm_demo`를 넣습니다. 비공개 데이터셋이면 로그인이 필요합니다.
- **로봇으로 재생해 보기:**

```bash
lerobot-replay \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower \
    --dataset.repo_id=${HF_USER}/fold_film_onearm_demo \
    --dataset.episode=0
```

- **잘못 녹화된 에피소드 지우기:**

```bash
lerobot-edit-dataset \
    --repo_id ${HF_USER}/fold_film_onearm_demo \
    --root $HOME/lerobot_data/fold_film_onearm_demo \
    --operation.type delete_episodes \
    --operation.episode_indices "[3, 17]"
```

## 8. 학습 (클라우드 A100)

같은 폴더의 `train_smolvla.sh`를 클라우드에 올려 실행합니다.

```bash
bash train_smolvla.sh ${HF_USER}/fold_film_onearm_demo smolvla_onearm_v1
```

5천 스텝마다 체크포인트가 Hugging Face에 올라가고, 각 체크포인트에는 스텝 번호 태그(`005000`, `010000` …)가 붙습니다.

## 9. 평가 (10/8 오전)

에피소드 단위로 정책을 돌리고 녹화합니다. 에피소드 사이에는 리셋 시간이 있고, 리더 암으로 로봇을 정리할 수 있습니다.

```bash
lerobot-rollout \
    --strategy.type=episodic \
    --policy.path=${HF_USER}/smolvla_onearm_v1 \
    --policy.pretrained_revision=010000 \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower \
    --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM1 \
    --teleop.id=rehearsal_leader \
    --task="Fold the plastic film in half." \
    --dataset.repo_id=${HF_USER}/fold_film_onearm_eval_v1_010000 \
    --dataset.single_task="Fold the plastic film in half." \
    --dataset.num_episodes=10 \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=20 \
    --dataset.private=true
```

- `--policy.pretrained_revision`을 `005000`, `010000`, `015000`, `020000`으로 바꿔 체크포인트를 비교합니다. 체크포인트마다 데이터셋 이름도 바꿉니다.
- 키보드는 녹화 때와 같습니다(`→` 다음, `←` 다시, `ESC` 종료).
- **성공/실패는 LeRobot이 기록하지 않습니다.** 에피소드마다 바로 적어서 JSON으로 남깁니다. 나중에 가치 함수(SARM) 학습 데이터를 고를 때 씁니다. 형식 예시는 `{"0": 1, "1": 0, "2": 1}`이고, 에피소드 번호에 성공 1, 실패 0입니다.
- 녹화 없이 빠르게 보기만 할 때는 `--strategy.type=base --duration=60`을 쓰고 `--dataset.*`는 뺍니다.

## 10. 사람 개입 데이터 수집 (10/8)

```bash
lerobot-rollout \
    --strategy.type=dagger \
    --strategy.num_episodes=30 \
    --policy.path=${HF_USER}/smolvla_onearm_v1 \
    --policy.pretrained_revision=010000 \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=rehearsal_follower \
    --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyACM1 \
    --teleop.id=rehearsal_leader \
    --task="Fold the plastic film in half." \
    --dataset.repo_id=${HF_USER}/fold_film_onearm_dagger_v1 \
    --dataset.single_task="Fold the plastic film in half." \
    --dataset.private=true
```

**키보드 (v0.6.1 기본값)**
- `space`: 정책 실행을 멈추거나 다시 시작합니다. 멈추면 리더 암이 모터 힘으로 로봇의 현재 자세까지 따라옵니다.
- `tab`: 교정 녹화를 시작하거나 끝냅니다. 교정을 끝내면 그 교정 구간이 에피소드 하나로 저장됩니다.
- `enter`: 데이터셋을 바로 업로드합니다.
- `ESC`: 세션을 끝냅니다.

**한 번의 개입 순서**
1. 정책이 실수하기 시작하면 `space`를 누릅니다. 로봇이 멈추고 리더 암이 같은 자세로 옵니다.
2. `tab`을 누르고 리더 암으로 교정합니다. 먼저 익숙한 상태로 되돌리고, 그다음 그 동작을 끝까지 올바르게 합니다.
3. `tab`을 눌러 교정 녹화를 끝냅니다.
4. `space`를 눌러 정책에게 다시 넘깁니다.

**알아둘 점**
- 기본 설정(`record_autonomous=false`)에서는 사람이 교정한 구간만 저장되고, 교정 하나가 에피소드 하나가 됩니다. 로봇이 혼자 한 구간은 저장되지 않습니다. 이게 LeRobot이 따르는 RaC 방식입니다.
- `--strategy.record_autonomous=true`로 하면 자율 구간까지 저장되지만, 에피소드가 시도 단위가 아니라 일정 시간 단위로 잘립니다. 시도별 성공/실패를 매기기 어려우니 리허설에서는 기본 설정을 씁니다. 성공/실패가 필요한 데이터는 9번의 평가 녹화로 모읍니다.
- 발 페달은 `--strategy.input_device=pedal`로 쓸 수 있지만, 이 모드는 Linux의 입력 장치 경로(`/dev/input/by-id/…`)를 읽습니다. Windows라면 페달을 `space`, `tab`, `enter` 키를 보내도록 설정하고 키보드 모드 그대로 쓰면 됩니다.
- 정책 실행이 끊기거나 움직임이 튀면, 공식 문서가 SmolVLA에 권하는 RTC 추론을 붙여 봅니다. 아래는 문서 예시 값입니다. 평가와 개입 수집은 같은 추론 설정으로 맞추세요.

```bash
    --inference.type=rtc \
    --inference.rtc.execution_horizon=20 \
    --inference.rtc.max_guidance_weight=5.0 \
    --inference.rtc.prefix_attention_schedule=LINEAR
```

## 11. 재학습용 데이터 합치기

시연 데이터와 개입 데이터를 하나로 합친 뒤, 1차 모델에서 이어 학습합니다.

```bash
lerobot-edit-dataset \
    --new_repo_id ${HF_USER}/fold_film_onearm_v2data \
    --operation.type merge \
    --operation.repo_ids "['${HF_USER}/fold_film_onearm_demo', '${HF_USER}/fold_film_onearm_dagger_v1']"
```

이어 학습은 `train_smolvla.sh`의 맨 위 `BASE_POLICY` 값을 1차 모델로 바꿔서 실행합니다. 스크립트 안의 설명을 참고하세요.

## 리허설 동안 기록할 것

- 집기 성공률, 그리고 놓을 때 비닐이 그리퍼에 달라붙는 비율 (고무 끝단 평가)
- 체크포인트별 성공률 (5천, 1만, 1만 5천, 2만 스텝)
- 학습 로그에 찍히는 스텝당 시간 (대회 일정 계산용)
- 개입 1회에 걸리는 시간과, 30번 수집에 걸린 총 시간
