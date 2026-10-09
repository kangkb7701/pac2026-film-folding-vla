# pac_full_task 데이터셋 (zip 조각)

대회 현장(2026-10-09~10)에서 녹화한 양팔 전체 과제 시연 데이터 원본입니다. GitHub 파일 크기 제한(100MB) 때문에 zip을 95MB 조각 29개로 나눠 올렸습니다.

- 형식: LeRobot v3.0, `bi_so_follower`, 관절 12개, 30fps, 카메라 top / left_wrist / right_wrist(640×480 AV1)
- 규모: 51개 에피소드, 119,835프레임. 앞뒤 대기 구간을 자르지 않은 원본입니다.
- 지시문: `Tear off one sheet of film, fold it, and put it into the basket.`
- zip 안의 폴더 이름: `pac_full_task/`

## 합쳐서 풀기 (Linux, 코랩)

```
cd datasets/pac_full_task/zip && cat pac_full_task.zip.part* > /content/pac_full_task.zip && sha256sum /content/pac_full_task.zip && cat pac_full_task.zip.sha256
mkdir -p /content/data && unzip -q /content/pac_full_task.zip -d /content/data
```

두 sha256 값이 같아야 합니다. 풀면 `/content/data/pac_full_task`가 생깁니다.

Windows에서는 `copy /b pac_full_task.zip.part00+pac_full_task.zip.part01+... pac_full_task.zip` 또는 Git Bash의 `cat`을 씁니다.
