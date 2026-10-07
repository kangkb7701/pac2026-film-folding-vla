# SO-101 캘리브레이션 파일 (LeRobot 0.6.1)

2026-10-06에 이 노트북의 LeRobot 캘리브레이션 폴더에서 복사했습니다. 폴더 구조는 LeRobot과 같습니다.

| 파일 | 장치 | 만든 날 |
|---|---|---|
| `robots/so_follower/bimanual_follower_left.json` | 왼팔 팔로워 | 2026-10-06 16:11 (손목 회전을 가운데에 두고 다시 함) |
| `teleoperators/so_leader/bimanual_leader_left.json` | 왼팔 리더 | 2026-10-06 16:06 (손목 회전을 가운데에 두고 다시 함) |
| `robots/so_follower/bimanual_follower_right.json` | 오른팔 팔로워 | 2026-10-05 17:55 |
| `teleoperators/so_leader/bimanual_leader_right.json` | 오른팔 리더 | 2026-10-05 17:56 |

오른팔 파일은 손목 회전 문제(반 바퀴 넘으면 폭주)를 고치기 전에 만든 것입니다. 오른팔도 같은 증상이 있으면 손목 회전을 가운데에 두고 다시 캘리브레이션하세요.

## 다른 컴퓨터에서 쓰는 법 (셋 중 하나)

1. **LeRobot 기본 폴더에 복사.** 이 폴더의 `robots`, `teleoperators`를 그대로 아래 위치에 넣습니다.
   - Windows: `%USERPROFILE%\.cache\huggingface\lerobot\calibration\`
   - Linux/macOS: `~/.cache/huggingface/lerobot/calibration/`
2. **환경 변수로 이 폴더를 지정.** `HF_LEROBOT_CALIBRATION`을 이 `calibration` 폴더 경로로 설정합니다.
3. **명령마다 경로를 지정.** 명령에 아래 두 옵션을 붙입니다.
   `--robot.calibration_dir=<이 폴더>/robots/so_follower --teleop.calibration_dir=<이 폴더>/teleoperators/so_leader`

## 주의

- 명령의 id가 파일 이름과 같아야 합니다. 예: `--robot.id=bimanual_follower_left --teleop.id=bimanual_leader_left`
- 같은 물리적 팔에만 맞습니다. 포트 번호(COM3, /dev/ttyACM0 등)는 컴퓨터마다 달라도 됩니다.
- 처음 연결할 때 기존 파일을 쓸지 묻는 질문이 나오면 그냥 Enter를 누릅니다. `c`를 누르면 새로 캘리브레이션합니다.
- 관절 단위 문제를 피하려면 다른 컴퓨터에도 LeRobot 0.6.1을 설치하세요.
