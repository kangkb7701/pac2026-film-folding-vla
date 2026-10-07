# SO-101 캘리브레이션 파일 (LeRobot 0.6.1)

2026-10-07에 rick1 노트북의 LeRobot 캘리브레이션 폴더에서 복사했습니다. 폴더 구조는 LeRobot과 같습니다.

| 파일 | 장치 | 만든 날 |
|---|---|---|
| `robots/so_follower/bimanual_follower_left.json` | 왼팔 팔로워 | 2026-10-07 20:18 |
| `teleoperators/so_leader/bimanual_leader_left.json` | 왼팔 리더 | 2026-10-07 20:19 |
| `robots/so_follower/bimanual_follower_right.json` | 오른팔 팔로워 | 2026-10-06 16:11 |
| `teleoperators/so_leader/bimanual_leader_right.json` | 오른팔 리더 | 2026-10-06 16:06 |

네 파일 모두 손목 회전을 가운데에 두고 만든 최신 파일입니다.

## 2026-10-07 이름 변경 (중요)

예전에 `bimanual_*_left`라고 부르던 파일은 실제로는 **오른팔** 것이었습니다. 그래서 내용은 그대로 두고 `bimanual_*_right`로 이름을 바꿨습니다. 실제 왼팔은 `bimanual_*_left`로 새로 캘리브레이션했습니다.

- 예전 이름의 파일을 쓰는 컴퓨터는 이 폴더의 파일로 모두 바꾸세요. 섞어 쓰면 반대 팔에 적용됩니다.
- 한 팔(예전 "왼팔", 실제 오른팔)로 녹화하거나 원격 실행하던 명령은 id를 `bimanual_follower_right`, `bimanual_leader_right`로 바꿉니다.

## 다른 컴퓨터에서 쓰는 법 (셋 중 하나)

1. **LeRobot 기본 폴더에 복사.** 이 폴더의 `robots`, `teleoperators`를 그대로 아래 위치에 넣습니다.
   - Windows: `%USERPROFILE%\.cache\huggingface\lerobot\calibration\`
   - Linux/macOS: `~/.cache/huggingface/lerobot/calibration/`
2. **환경 변수로 이 폴더를 지정.** `HF_LEROBOT_CALIBRATION`을 이 `calibration` 폴더 경로로 설정합니다.
3. **명령마다 경로를 지정.** 명령에 아래 두 옵션을 붙입니다.
   `--robot.calibration_dir=<이 폴더>/robots/so_follower --teleop.calibration_dir=<이 폴더>/teleoperators/so_leader`

## 주의

- 명령의 id가 파일 이름과 같아야 합니다. 예: `--robot.id=bimanual_follower_right --teleop.id=bimanual_leader_right`
- 양팔(`bi_so_follower`, `bi_so_leader`)은 `--robot.id=bimanual_follower --teleop.id=bimanual_leader`로 주면 `_left`, `_right`가 자동으로 붙어 위 파일을 읽습니다. `left_arm_config.port`에는 실제 왼팔 포트를 넣습니다.
- 같은 물리적 팔에만 맞습니다. 포트 번호(COM3, /dev/ttyACM0 등)는 컴퓨터마다 달라도 됩니다.
- 처음 연결할 때 기존 파일을 쓸지 묻는 질문이 나오면 그냥 Enter를 누릅니다. `c`를 누르면 새로 캘리브레이션합니다(한글 입력 상태면 `ㅊ`이 들어가 새로 하지 않습니다).
- 관절 단위 문제를 피하려면 다른 컴퓨터에도 LeRobot 0.6.1을 설치하세요.
