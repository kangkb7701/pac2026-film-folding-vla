# pac_full_task_hil 데이터셋 (zip 조각)

양팔 전체 과제에서 사람이 개입해 조종한 구간(HIL)만 녹화한 데이터 원본입니다. GitHub 파일 크기 제한(100MB) 때문에 zip을 95MB 조각 6개로 나눠 올렸습니다.

- 형식: LeRobot v3.0, `bi_so_follower`, 30fps, 카메라 top / left_wrist / right_wrist
- 규모: 14개 에피소드, 22,660프레임
- zip 안의 폴더 이름: `pac_full_task_hil/`

## 합쳐서 풀기 (Linux, 코랩)

```
cd datasets/pac_full_task_hil/zip && cat pac_full_task_hil.zip.part* > /content/pac_full_task_hil.zip && sha256sum /content/pac_full_task_hil.zip && cat pac_full_task_hil.zip.sha256
mkdir -p /content/data && unzip -q /content/pac_full_task_hil.zip -d /content/data
```

두 sha256 값이 같아야 합니다. 풀면 `/content/data/pac_full_task_hil`이 생깁니다.

Windows에서는 `copy /b pac_full_task_hil.zip.part00+pac_full_task_hil.zip.part01+... pac_full_task_hil.zip` 또는 Git Bash의 `cat`을 씁니다.

## 추가분: 에피소드 14~22 (`pac_full_task_hil_ep14-22.zip`, 조각 5개)

위 zip(에피소드 0~13) 다음에 녹화한 에피소드 14~22만 담았습니다. 메타데이터(`meta/`)와 `hil_labels.json`은 23개 에피소드 전체 기준으로 새로 들어 있습니다.

- 합계: 23개 에피소드(0~22), 41,632프레임
- 에피소드 18은 실패(`success: false`)로 바꿨습니다. 원래 22번 시도는 지웠고, 그 뒤 시도가 22번이 됐습니다(파일 이름은 `file-023`).

첫 zip을 푼 뒤 옛 `meta/`와 `hil_labels.json`을 지우고 이 zip을 덮어 풉니다. 옛 `meta/episodes` 파일이 남아 있으면 에피소드 정보가 겹쳐서 데이터셋이 깨집니다.

```
cd datasets/pac_full_task_hil/zip && cat pac_full_task_hil_ep14-22.zip.part* > /content/pac_full_task_hil_ep14-22.zip && sha256sum /content/pac_full_task_hil_ep14-22.zip && cat pac_full_task_hil_ep14-22.zip.sha256
rm -rf /content/data/pac_full_task_hil/meta /content/data/pac_full_task_hil/hil_labels.json
unzip -q -o /content/pac_full_task_hil_ep14-22.zip -d /content/data
```

## 추가분: 에피소드 23~29 (`pac_full_task_hil_ep23-29.zip`, 조각 4개)

에피소드 23~29(파일 이름 `file-024`~`file-030`)와 30개 에피소드 전체 기준 `meta/`, `hil_labels.json`을 담았습니다. 합계 30개 에피소드, 55,347프레임입니다.

0~13번 zip과 14~22번 추가분을 푼 다음, 옛 `meta/`와 `hil_labels.json`을 지우고 이 zip을 덮어 풉니다.

```
cd datasets/pac_full_task_hil/zip && cat pac_full_task_hil_ep23-29.zip.part* > /content/pac_full_task_hil_ep23-29.zip && sha256sum /content/pac_full_task_hil_ep23-29.zip && cat pac_full_task_hil_ep23-29.zip.sha256
rm -rf /content/data/pac_full_task_hil/meta /content/data/pac_full_task_hil/hil_labels.json
unzip -q -o /content/pac_full_task_hil_ep23-29.zip -d /content/data
```
