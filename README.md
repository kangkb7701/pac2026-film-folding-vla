# PAC 2026 비닐 접기 VLA (SO-101)

Physical AI Challenge 2026 준비 자료입니다. 투명 비닐을 반으로 접어 정해진 곳에 놓는 과제를 SO-101 로봇팔과 SmolVLA로 풉니다. 환경은 LeRobot 0.6.1입니다(노트북 conda 환경 `lerobot312`, GPU 서버 `lerobot061`).

## 구성

- `PAC2026_비닐접기_VLA_준비노트.md`: 선행 연구 조사, 방법론(시연 → SmolVLA → 개입 데이터 → SARM 진행도 → RA-BC 재학습), 일정
- `SARM_사람개입데이터_정리.md`: 1차 모델 실행 뒤 정리한 사람 개입 데이터 수집과 SARM(가치함수) 설계, 근거와 실행 순서
- `학습방법_SmolVLA_파인튜닝.md`, `train_smolvla.sh`: 데이터 점검부터 SmolVLA 파인튜닝까지(클라우드 A100 기준)
- `SmolVLA_파인튜닝_진행기록.md`: 연구실 GPU PC(RTX 3090)에서 한 1차·2차 학습의 과정, 결과, 결정과 근거
- `SmolVLA_파인튜닝_실행가이드.md`: 위 과정을 그대로 따라 하는 명령어(정지 구간 자르기, 개입 데이터 정리와 합치기, SARM과 RA-BC, 2차 학습, 재개)
- `training/`: 실행 가이드에서 쓰는 스크립트(정지 구간 자르기, 개입 데이터 부분집합 만들기, SARM 판정, `kappa` 고르기, 메모리 감시)
- `리허설_한팔_LeRobot_명령어.md`: 한 팔 리허설 명령어. 포트와 카메라 이름은 예전 설정이라, 실제 값은 `remote_edge`와 학습 방법 문서를 따릅니다.
- `remote_edge/`: 로봇은 노트북에서, SmolVLA 추론은 GPU 서버에서 돌리는 원격 실행 코드와 개입(DAgger) 데이터 수집 모드. 캡스톤 프로젝트 [so101-vla-pipeline](https://github.com/kangkb7701/so101-vla-pipeline)의 원격 배포 코드를 고친 것입니다. 사용법은 `remote_edge/README.md`에 있습니다.
- `robot_scripts/`: 데이터셋 점검, 카메라 웹 뷰어, 한 팔 텔레오퍼레이션, 에피소드 라벨링 도구
    - `label_tool.bat <데이터셋 폴더>` 실행 후 http://127.0.0.1:8010 에서 영상을 보며 단계 경계 6개(시작, 끌어옴, 뜯김, 펴 놓음, 접음, 놓음)와 결과(성공, 정렬 불량, 실패, 제외)를 표시합니다. 데이터셋 폴더의 `human_labels.json`에 바로 저장됩니다. 단계와 지시문은 `SARM_사람개입데이터_정리.md`의 "대회 과제 단계와 지시문"을 보세요.
    - `python export_sarm_labels.py <데이터셋 폴더>`: 라벨을 SARM 단계 라벨(LeRobot 형식)로 데이터셋에 써 넣고, SARM 학습 옵션을 출력합니다. 쓰기 전에 `meta/episodes`를 백업합니다.
- `datasets/fold_film_onearm_hil/`: 2026-10-07 사람 개입 데이터(LeRobot v3.0, 53 에피소드, 26,311프레임, 30fps). 0~9번은 개입 없는 기준 실행(성공 2/10)이고, 누가 조종했는지와 성공/실패는 `hil_labels.json`에 있습니다. 시연 데이터(`fold_film_onearm_demo`, 50 에피소드)와 항목이 같아 그대로 합칠 수 있으며, 합치면 에피소드 번호가 밀리니 `hil_labels.json`도 같이 맞춰야 합니다.
- `calibration/`: SO-101 캘리브레이션 파일. 2026-10-07에 실제 팔 위치에 맞게 이름을 바꿨습니다(예전 `_left`는 실제 오른팔). `calibration/README.md`를 보세요.
- `3D프린팅_STL/`: 출력용 카메라 거치대(상단)와 카메라 일체형 그리퍼
- `_카메라마운트_작업자료/`: 위 부품을 만든 작업 폴더(생성 스크립트, 원본 메시, 미리보기, 이전 버전)

## 다른 PC에서 실행

1. 저장소를 받습니다.
2. `remote_edge/policy_token.txt`에 GPU 서버 토큰 한 줄을 저장합니다. 토큰은 공개 저장소에 올리지 않았습니다.
3. bat 파일은 `%USERPROFILE%\anaconda3`의 conda 환경 `lerobot312`을 씁니다. 다른 위치에 설치했다면 각 bat의 `activate.bat` 줄을 고칩니다.
4. 포트(COM3 팔로워, COM5 리더)와 카메라 번호(`remote_edge/edge_cameras.json`)는 PC마다 다를 수 있으니 `lerobot-find-port`와 `lerobot-find-cameras opencv`로 확인합니다.
5. 캘리브레이션 파일은 `calibration/README.md`대로 LeRobot 캘리브레이션 폴더에 넣습니다.

## 라이선스 고지

3D 프린팅 부품은 [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)의 카메라 거치대와 SO-101 메시를 바탕으로 수정한 것입니다. 원본은 Apache License 2.0이며, 전문은 `LICENSE-SO-ARM100.txt`에 있습니다.

## 올리지 않은 것

참가신청서(개인정보 포함), 학습 데이터(위 개입 데이터 제외), 실행 로그, 서버 토큰, 3D 미리보기 도구의 캐시와 오류 덤프
