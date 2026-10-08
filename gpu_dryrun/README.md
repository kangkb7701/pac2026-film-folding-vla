# GPU PC 리허설: 현장 학습 경로 점검 (약 15~20분)

대회(PAC 2026 에코프로비엠, 10/9~10) 현장에서는 단계별로 녹화한 데이터(예: 잡기, 접기)를 **지시문이 다른 채로 합쳐서 SmolVLA 모델 하나로 학습**하고, 정책 서버에 새 지시문으로 동작을 요청합니다. 이 폴더는 그 경로가 GPU PC에서 막힘없이 도는지 대회 전에 한 바퀴 돌려 보는 리허설입니다.

## 이 문서를 읽는 사람(또는 CLI 에이전트)이 할 일

1. 저장소를 최신으로 받습니다: `git pull`
2. conda 환경을 켭니다: `conda activate lerobot061` (LeRobot 0.6.1)
3. 저장소 루트에서 실행합니다. 두 경로는 이 PC에 맞게 바꿉니다.
   ```bash
   bash gpu_dryrun/onsite_dryrun.sh datasets/fold_film_onearm_hil \
     ~/PAC_robotarm/outputs/train/smolvla_onearm_v2/checkpoints/020000/pretrained_model
   ```
   - 첫 번째 인자: 녹화된 LeRobot 데이터셋 폴더. 저장소의 `datasets/fold_film_onearm_hil`(개입 데이터 53개)을 그대로 쓰면 됩니다.
   - 두 번째 인자: 리허설 2차 학습 체크포인트(`smolvla_onearm_v2`의 2만 스텝 `pretrained_model` 폴더). 위치가 다르면 찾아서 넣습니다(`find ~ -path "*smolvla_onearm_v2*020000*pretrained_model" -maxdepth 8`).
4. 결과를 아래 형식으로 보고합니다.

## 스크립트가 하는 일

모든 결과물은 `/tmp/pac_dryrun`에만 만듭니다(바꾸려면 `WORK=<경로>`). 원본 데이터셋과 체크포인트는 건드리지 않습니다.

1. 데이터셋 복사본 두 개에 지시문 `"Grab the film end."`, `"Fold the film into the square."`를 넣습니다(`lerobot-edit-dataset --operation.type modify_tasks`).
2. 둘을 합칩니다(`--operation.type merge`).
3. v2 체크포인트에서 **200스텝만** 학습합니다(배치 8). 학습이 되는지만 보는 것이고 성능은 의미 없습니다.
4. 결과 체크포인트를 정책 서버(`remote_edge/so101_pipeline/servers/act_policy_server.py`의 `ActPolicy`)와 같은 방식으로 불러, 두 지시문으로 동작 묶음을 요청합니다(`dryrun_predict.py`).

## 보고할 것

- 성공 여부: 마지막 근처의 `DRY RUN PREDICT: OK` 또는 `PROBLEM`
- 단계별 시간: 마지막 줄 `== done: data prep ...s, 200 training steps ...s ...`
- `dryrun_predict.py` 출력: 동작 묶음 크기(예: `(50, 6)`), 추론 시간(ms), 지시문 사이 평균 차이(도)
- 실패했다면 처음 나온 에러 메시지와 몇 번째 단계(== 1 ~ 4)에서 났는지

## 참고

- 학습 로그의 손실 값은 200스텝이라 의미가 없습니다. 오류 없이 끝나는지만 봅니다.
- 지시문 사이 차이가 작게 나와도(200스텝, 같은 영상) 이상한 것이 아닙니다. 현장에서는 단계마다 장면이 달라서 구분됩니다.
- 끝나면 `/tmp/pac_dryrun`을 지워도 됩니다(`rm -rf /tmp/pac_dryrun`).
