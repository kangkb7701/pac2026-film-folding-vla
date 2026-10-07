# PAC 2026 비닐 접기 VLA (SO-101)

Physical AI Challenge 2026 준비 자료입니다. 투명 비닐을 반으로 접어 정해진 곳에 놓는 과제를 SO-101 로봇팔과 SmolVLA로 풉니다. 환경은 LeRobot 0.6.1입니다(노트북 conda 환경 `lerobot312`, GPU 서버 `lerobot061`).

## 구성

- `PAC2026_비닐접기_VLA_준비노트.md`: 선행 연구 조사, 방법론(시연 → SmolVLA → 개입 데이터 → SARM 진행도 → RA-BC 재학습), 일정
- `학습방법_SmolVLA_파인튜닝.md`, `train_smolvla.sh`: 데이터 점검부터 SmolVLA 파인튜닝까지
- `리허설_한팔_LeRobot_명령어.md`: 한 팔 리허설 명령어. 포트와 카메라 이름은 예전 설정이라, 실제 값은 `remote_edge`와 학습 방법 문서를 따릅니다.
- `remote_edge/`: 로봇은 노트북에서, SmolVLA 추론은 GPU 서버에서 돌리는 원격 실행 코드와 개입(DAgger) 데이터 수집 모드. 캡스톤 프로젝트 [so101-vla-pipeline](https://github.com/kangkb7701/so101-vla-pipeline)의 원격 배포 코드를 고친 것입니다. 사용법은 `remote_edge/README.md`에 있습니다.
- `robot_scripts/`: 데이터셋 점검, 카메라 웹 뷰어, 한 팔 텔레오퍼레이션
- `calibration/`: SO-101 캘리브레이션 파일. 오른팔 파일은 예전 버전이니 `calibration/README.md`를 보세요.

## 올리지 않은 것

참가신청서, 3D 프린팅 파일, 학습 데이터, 실행 로그, 서버 토큰(`remote_edge/policy_token.txt`)
