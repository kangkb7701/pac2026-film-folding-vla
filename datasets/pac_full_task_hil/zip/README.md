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
