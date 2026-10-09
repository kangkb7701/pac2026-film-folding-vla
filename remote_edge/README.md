# 원격 추론: 노트북(로봇) + 연구실 GPU PC(SmolVLA)

캡스톤 경진대회 때 만든 원격 배포 코드(`so101-vla-pipeline`)를 복사해서 SmolVLA용으로 고친 것입니다. 원본은 건드리지 않았습니다.

LeRobot 기본 원격 추론(`robot_client`)은 동작 도중에 자꾸 멈췄습니다. 원인은 압축하지 않은 카메라 영상(한 번에 약 1.8MB)을 보내는 동안 로봇 제어 루프가 기다리기 때문입니다. 이 코드는 영상을 JPEG로 줄여서(두 장에 약 60KB) 보내고, 응답을 기다리지 않고 로봇을 30Hz로 계속 움직입니다. 응답이 늦게 와도 그만큼 지난 시간을 계산해서 동작 묶음(50스텝, 1.7초 분량)의 알맞은 위치부터 이어서 실행합니다.

## 1. GPU PC (서버)

`so101_pipeline/servers/act_policy_server.py` 파일 하나만 GPU PC로 옮기면 됩니다. GPU PC는 SSH가 열려 있지 않아서 Tailscale 파일 전송(Taildrop)으로 보냅니다. 노트북에서 `pac_policy_server.py`라는 이름으로 복사한 뒤 보냅니다.

```
tailscale file cp pac_policy_server.py aivlab-b650-aorus-elite-ax-v2:
```

GPU PC에서 받은 파일을 꺼내고, 처음 한 번만 설치합니다.

```
mkdir -p ~/PAC_robotarm && sudo tailscale file get ~/PAC_robotarm/
conda activate lerobot
pip install websockets msgpack
```

서버를 켭니다. 환경은 체크포인트를 학습한 LeRobot 0.6.1 환경(`lerobot061`)을 씁니다. `--host`에 Tailscale 주소를 넣어서 내 Tailscale 기기에서만 접속되게 하고, `--token`과 같은 비밀값을 가진 요청만 받습니다. 같은 값이 노트북의 `run_edge.bat`에도 들어 있습니다. 학습에 쓴 데이터셋은 체크포인트 폴더의 `train_config.json`에서 자동으로 읽습니다.

```
conda activate lerobot061
cd ~/PAC_robotarm
python pac_policy_server.py --host 100.81.190.27 --port 8765 --token <토큰> --device cuda --policy_path /home/aivlab/PAC_robotarm/outputs/train/smolvla_onearm_v1/checkpoints/020000/pretrained_model
```

토큰은 git에 올리지 않습니다. 노트북에서는 `remote_edge/policy_token.txt`에 토큰 한 줄을 저장해 두면 `run_edge.bat`이 읽어 갑니다. 새로 받은 컴퓨터라면 이 파일을 직접 만들고, 서버의 `--token`에도 같은 값을 넣습니다.

`dataset from ...`, `policy loaded`, `ACT policy server listening on 100.81.190.27:8765`가 차례로 나오면 준비된 것입니다. 마지막 줄의 ACT는 원래 코드 이름일 뿐이고 실제로는 SmolVLA를 씁니다. 연구실 공인 IP의 40001번은 다른 프로젝트의 nginx가 쓰고 있어서 쓰지 않습니다.

## 2. 노트북 (로봇)

1. 예전에 켜 둔 `robot_client`가 있으면 끕니다. 팔 포트와 카메라는 한 프로그램만 잡을 수 있기 때문입니다.
   - 팔은 양팔(`bi_so_follower`)입니다. `lerobot-find-port`로 왼팔·오른팔 팔로워 포트를 찾아 `run_edge.bat`의 `ROBOT_PORT_LEFT`, `ROBOT_PORT_RIGHT`에 적습니다. 캘리브레이션 파일은 `bimanual_follower_left.json`, `bimanual_follower_right.json`을 씁니다.
   - 카메라는 3대(`top`, `left_wrist`, `right_wrist`)입니다. USB를 꽂을 때마다 번호가 바뀌니 `run_edge.bat --identify`로 미리보기를 보고 번호를 저장합니다.
2. 처음에는 로봇이 움직이지 않는 시험 모드로 연결만 확인합니다. 명령 프롬프트에서 실행합니다.
   ```
   run_edge.bat --dry_run
   ```
3. 문제없으면 Ctrl+C로 끄고 `run_edge.bat`을 실제로 실행합니다.
4. `waiting for app command`가 나오면 `episode_start.bat`을 더블클릭합니다. 150초 동안 동작합니다.
5. 중간에 멈추려면 `episode_stop.bat`을 실행합니다. 에피소드가 끝나면 팔은 홈 자세로 돌아가고 다음 명령을 기다립니다.
6. 완전히 끝낼 때는 `run_edge.bat` 창에서 Ctrl+C를 누릅니다. 홈 자세로 돌아간 뒤 토크가 풀리니 팔을 잡을 준비를 하세요.

## 2-1. 개입 데이터 수집 (`run_edge_hil.bat`)

정책은 GPU 서버가 돌리고, 사람이 개입할 때는 노트북에 꽂은 리더암 두 대로 넘겨받습니다. 리더 포트는 `run_edge_hil.bat`의 `TELEOP_PORT_LEFT`, `TELEOP_PORT_RIGHT`에 적고, 캘리브레이션 파일은 `bimanual_leader_left.json`, `bimanual_leader_right.json`을 씁니다. 멈추고 넘겨받기는 두 팔을 함께 합니다. LeRobot의 개입 수집 기능(`lerobot-rollout --strategy.type=dagger`)은 정책이 같은 컴퓨터에 있어야 해서, 같은 방식을 이 프로그램에 넣었습니다. 넘겨받는 순서는 LeRobot 코드(`rollout/strategies/dagger.py`)를 따릅니다.

**키** (전역 키라서 다른 창이 앞에 있어도 먹습니다)
- Enter: 시도 시작
- Space: 정책 멈춤 / 정책 재개
- Tab: 넘겨받기 / 돌려주기 (멈춘 상태에서만)
- S: 성공으로 저장, F: 실패로 저장, Backspace: 버리기
- Esc: 프로그램 종료 (Ctrl+C도 됨)

**한 번의 시도 흐름**
1. Enter를 누르면 정책이 움직입니다.
2. 실패할 것 같으면 Space를 누릅니다. 두 팔로워는 그 자리에서 버티고, 두 리더암이 스스로 2초 동안 팔로워 자세로 움직입니다. 이때 리더암에서 손을 떼거나 가볍게만 잡으세요.
3. Tab을 누르면 리더암의 힘이 풀립니다. 이제 사람이 조종하고, 이 구간이 녹화됩니다. 먼저 익숙한 상태로 되돌리고, 그 단계를 끝까지 깔끔하게 해 보입니다(LeRobot 문서의 회복+교정 방식).
4. 다시 Tab을 누르면 교정이 끝나고 리더암이 그 자리에서 버팁니다.
5. 다음은 둘 중 하나입니다. Space로 정책에 돌려주면, 새 동작 계획이 올 때까지 약 0.5초 멈췄다가 이어서 움직입니다. 끝났으면 S나 F를 누릅니다.
6. 팔이 홈으로 돌아간 뒤 영상을 인코딩하며 저장합니다. 그동안 비닐을 다시 놓고, `ready`가 뜨면 Enter로 다음 시도를 시작합니다. 저장 중에 누른 키는 버려집니다.

시간 제한(180초)이 지나면 정책이 멈추고 S, F, Backspace 중 하나를 기다립니다. 처음에는 `run_edge_hil.bat --dry_run`으로 키 흐름만 확인하세요. 이때는 팔로워와 리더 모두 움직이지 않습니다.

**저장 형식**
- 위치: `%USERPROFILE%\lerobot_data\pac_full_task_hil`. 다시 켜면 이어서 저장합니다.
- S나 F를 눌러 `saved episode ...`가 뜬 시도는 그 자리에서 디스크에 확정됩니다. 창을 닫거나 강제로 꺼도 그때까지 저장된 시도는 남고, 진행 중이던 시도만 사라집니다. 원래 LeRobot은 프로그램이 정상 종료될 때 파일을 마무리해서, 강제로 끄면 그 세션 전체가 깨졌습니다. 그래서 시도마다 마무리하고 다시 여는 방식으로 바꿨습니다. 강제 종료 뒤 다시 켰을 때 남아 있던 임시 이미지는 자동으로 지웁니다.
- **사람이 조종한 구간만 저장합니다.** 한 시도에서 교정한 구간들을 이어 붙여 에피소드 하나로 저장하고, 정책이 움직인 구간과 멈춰 있던 구간은 저장하지 않습니다. 넘겨받기가 한 번도 없던 시도는 S를 눌러도 저장되지 않습니다(`no human frames in this attempt`). LeRobot dagger는 정책 구간도 저장하지만, 학습에는 사람 구간만 쓰고 올릴 용량을 줄이려고 뺐습니다.
- 행동값은 리더암 자세입니다(시연 녹화와 같음).
- 항목은 대회 시연 데이터(`pac_full_task`)와 똑같습니다(`bi_so_follower`, 관절 12개 이름, 카메라 `top`/`left_wrist`/`right_wrist`, 30fps, 지시문). 가짜 장치로 녹화한 데이터셋의 항목이 `pac_full_task`와 같은 것을 확인했습니다. 실제로 합쳐 보지는 않았습니다.
- 교정 구간의 경계와 성공/실패는 데이터셋 안이 아니라 같은 폴더의 `hil_labels.json`에 적습니다. 예: `{"episode_index": 0, "success": true, "frames": 75, "interventions": [[0, 30], [30, 75]]}`. `interventions`는 교정 하나하나의 프레임 구간이고, 끝 번호는 포함하지 않습니다.
- **학습 전에 반드시 교정 단위로 자릅니다.** 이어 붙인 경계에서 장면이 끊기기 때문입니다. 자르면 교정 하나가 에피소드 하나가 됩니다.
  ```
  python training/hil_spec.py <녹화 폴더>/hil_labels.json spec.json
  python training/build_hil_subset.py <녹화 폴더> <새 폴더> spec.json
  ```
  실패한 시도의 교정도 기본으로 넣습니다. 성공/실패는 시도 전체의 결과이고, 그 안의 교정 하나하나가 잘못됐다는 뜻은 아니기 때문입니다(예: 뜯기는 사람이 깔끔하게 했는데 그 뒤 접기에서 정책이 실패). 빼려면 `hil_spec.py`에 `--success-only`를 붙입니다.
- 영상은 시도마다 저장할 때 인코딩합니다. LeRobot 0.6.1은 영상을 10개씩 모아 인코딩하는 설정에서, 10개를 못 채운 채 끝내면 저장이 실패합니다. LeRobot만으로 재현해서 확인했습니다. 시험에서는 6초짜리 시도를 저장하는 데 약 5초가 걸렸고, 실제 영상은 더 걸릴 수 있습니다.

**확인한 것과 안 한 것**
- 로봇, 카메라, 리더암을 가짜로 바꾼 시험에서 확인한 것: 키 흐름, 정책 재개, 녹화, 성공/실패/버리기, 시간 제한 뒤 라벨 대기, 라벨 파일, 시연 데이터와 합치기. 정책 서버와 LeRobot 녹화 코드는 실제 코드를 썼습니다.
- 실제 리더암을 모터로 움직이는 넘겨받기는 아직 안 해봤습니다. 첫 실행 때는 손을 리더암 가까이 두고 천천히 확인하세요.
- 사람 구간만 저장하는 방식은 가짜 장치로 한 시도를 처음부터 끝까지 돌려 확인했습니다(정책 → 교정 → 정책 재개 → 교정 → 성공). 정책 구간은 저장되지 않았고, 교정 두 개가 한 에피소드로 저장됐습니다. `hil_spec.py`와 `build_hil_subset.py`로 두 에피소드로 잘리고, 잘린 데이터셋이 정상으로 열렸습니다. 정책만 돈 시도는 저장되지 않았습니다.
- 양팔로 고친 뒤에는 LeRobot 0.6.1의 실제 양팔 설정(`BiSOFollowerConfig`, `BiSOLeaderConfig`)에 가짜 모터 버스, 카메라, 리더를 붙여 확인했습니다. 확인한 것은 관절 12개 읽기와 팔별 쓰기, 팔별 이동 제한, 리더 넘겨받기 키 이름, 서버 응답의 관절 순서, 서버 입력 형식, 녹화와 `hil_labels.json` 저장입니다. 실제 양팔 로봇으로는 아직 돌려 보지 않았습니다.

## 3. 로그 보는 법

1초마다 `[edge ...]` 줄이 찍힙니다.

- `link=up`: 서버와 연결됨
- `holds`: 실행할 동작이 없어 제자리에서 기다린 횟수. 0 근처를 유지해야 정상입니다. 계속 늘면 응답이 0.83초(25스텝)보다 늦게 온다는 뜻입니다. 그때는 `run_edge.bat --chunk_size_threshold 0.7`처럼 값을 올려 더 일찍 요청하게 합니다.
- `chunk_age`: 지금 실행 중인 동작이 몇 초 전 관측으로 만든 것인지. 묶음을 절반쯤 쓸 때까지 계속 쓰므로 0.3~1.2초 사이를 오가는 게 정상입니다.
- `infer`: GPU 추론 시간(ms)
- `clamps`: 한 틱에 너무 크게 움직이려 해서 안전 제한에 걸린 횟수
- 응답이 5초 넘게 끊기면 스스로 멈추고 홈으로 돌아갑니다.

## 4. 캡스톤 코드에서 바꾼 것과 근거

- **지시문:** 바나나 과제 3개 대신 대회 상위 지시문 `Pull out, tear off, lay flat, fold twice, and place the plastic bag on the paper, then pick it up and put it into the target.` 하나. 데이터셋에 저장된 문장과 글자 하나까지 같아야 합니다. 원래 코드는 명령을 소문자로 바꿨는데, 이 문장은 그대로 넘깁니다.
- **카메라 이름:** `top`, `left_wrist`, `right_wrist`를 이름 그대로 서버에 보냅니다. 대회 데이터의 이름과 같습니다. 한 팔 리허설 때는 `camera1`, `camera2`로 바꿔 보냈습니다.
- **카메라 설정:** `fourcc=MJPG`, OpenCV 기본 백엔드. 녹화할 때와 같은 설정이고, MJPG가 없으면 같은 허브의 두 번째 카메라부터 안 열립니다.
- **제어 주기 30Hz:** 데이터셋 fps가 30입니다. 원래 코드는 10Hz였습니다.
- **홈 자세:** 대회 데이터 51개 에피소드의 첫 프레임 평균. 왼팔 `[-8.4, -99.7, 97.5, 66.9, 13.4, 2.9]`, 오른팔 `[5.4, -99.5, 92.4, 70.9, 23.3, 5.1]`. 학습 데이터가 모두 그리퍼를 닫은 채 시작하므로, 시작할 때 그리퍼를 여는 기능은 껐습니다(`--episode_start_gripper -1`).
- **한 틱 이동 제한:** 기본값 6도(그리퍼 25)를 팔마다 그대로 둡니다. 한 팔 리허설 데이터에서 한 스텝 최대 변화가 팔 4.9도, 그리퍼 6.2였습니다.
- **자동 종료 끔:** 원래 코드는 바나나를 잡았다 놓으면, 또는 동작이 멈춰 있으면 끝냈습니다. 비닐 과제에는 맞지 않아서 끄고, 150초 시간 제한과 `episode_stop.bat`으로 끝냅니다. 150초는 대회 시연 한 번(61~100초)에 여유를 둔 제 선택입니다.
- **동작 묶음 합치기:** LeRobot 원격 추론의 기본값(`weighted_average`)과 같은 방식으로 바꿨습니다. 새 묶음이 도착하면, 기존 계획과 시간이 겹치는 스텝은 `0.3 × 기존 계획 + 0.7 × 새 묶음`으로 바꾸고, 겹치지 않는 뒷부분은 새 묶음 값을 그대로 씁니다. 기존 계획도 이미 섞인 값이라, 가장 최근 묶음 70%, 그 전 21%, 그 전 6.3%처럼 오래된 묶음일수록 영향이 줄어듭니다. LeRobot 코드(`robot_client._aggregate_action_queues`)에 같은 입력을 넣어 결과가 똑같은 것을 확인했습니다. 원래 코드의 ACT식 temporal ensemble은 끄고(`--ensemble_chunks 1`), 비율은 `--blend_old_weight`로 바꿉니다(0이면 최신 묶음만 사용).
- **관측 보내는 시점:** 이것도 LeRobot 기본값(`chunk_size_threshold=0.5`)에 맞췄습니다. 지금 계획에서 아직 실행하지 않은 동작이 25스텝(묶음의 절반) 이하로 줄었을 때만 새 관측을 보내고, 한 번에 요청 하나만 보냅니다(`--max_inflight 1`). 응답을 0.3초 늦게 주는 가짜 서버로 시험했을 때 요청이 약 0.86초(약 25스텝)마다 나갔고, 기다린 횟수는 0이었습니다. LeRobot과 다른 점은 둘입니다. 관측을 압축해서 보내고 그동안 로봇을 멈추지 않는 것, 그리고 LeRobot 서버의 "직전 관측과 관절이 거의 같으면 추론을 건너뛰는" 기능을 넣지 않은 것입니다.
- **서버:** ACT 전용 설정값을 읽던 한 줄이 SmolVLA에서 에러가 나서 고쳤습니다. 정규화 값은 체크포인트 폴더에 저장된 것을 그대로 씁니다.
- **버그 수정:** 대기 중에 멈춤을 누르면 다음 에피소드가 시작하자마자 끝나던 문제(캡스톤 원본에도 있음)를 고쳤습니다.

## 5. 확인한 것과 안 한 것

- 노트북에서 가짜 서버로 확인했습니다. 실제 COM3 로봇과 카메라 두 대에 연결해 30Hz로 돌렸고, 멈춤(holds)과 프레임 누락은 0이었습니다. 시작·멈춤 명령과 대기 중 멈춤 무시도 확인했습니다. 시험 모드라 로봇은 움직이지 않았습니다.
- 서버가 노트북이 보낸 형식으로 SmolVLA 입력(`observation.state`, `observation.images.camera1`, `camera2`, 지시문)을 만드는 것을 확인했습니다.
- **실제 SmolVLA를 GPU PC에서 띄워 원격으로 돌리는 것은 아직 안 해봤습니다.** 처음 실행할 때 서버 로그와 노트북 로그를 함께 보세요.

## 안 될 때

- **노트북 로그에 `policy link down`이 반복됨:** 서버가 꺼져 있거나 Tailscale이 끊긴 것입니다. 노트북에서 `tailscale ping 100.81.190.27`로 연결부터 확인합니다.
- **서버 로그에 `rejected ...: wrong or missing token`:** 노트북과 서버의 토큰이 다르거나, 모르는 곳에서 접속을 시도한 것입니다.
- **`left arm: motor calibration mismatch` (또는 `right arm`):** 캘리브레이션 파일(`bimanual_follower_left.json`, `bimanual_follower_right.json`)이 없거나, `ROBOT_PORT_LEFT`와 `ROBOT_PORT_RIGHT`가 서로 바뀐 것입니다.
- **카메라 에러:** USB를 다시 꽂으면 번호가 바뀔 수 있습니다. `run_edge.bat --identify`로 다시 저장합니다.
- **`no chunk within 15s`:** 서버가 첫 응답을 못 줬습니다. 서버 로그에 `predict failed`가 있는지 봅니다.
