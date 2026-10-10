"""SARM 학습용으로 상단 카메라만 298x224로 줄인 데이터셋 사본을 만듭니다.

SARM은 상단 카메라만 쓰고 CLIP이 어차피 224로 줄여 봅니다. 원본(640x480, 카메라 3대)
그대로 학습하면 배치 하나가 약 4.6GB라 /dev/shm(4GB)이 모자라 데이터 로딩이 죽었습니다.
데이터(parquet)는 링크로 두고, meta는 복사해 손목 카메라 항목을 지우고, 상단 영상만
다시 인코딩합니다. 프레임 수는 원본과 같아야 하므로 끝에서 확인합니다.

사용: python make_sarm_top_copy.py <원본 데이터셋 폴더> <새 폴더>
"""
import json, shutil, subprocess, sys
from pathlib import Path

KEY = "observation.images.top"
W, H = 298, 224  # 640x480 비율 유지, 짧은 변 224

src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
dst.mkdir(parents=True)
(dst / "data").symlink_to(src / "data")
shutil.copytree(src / "meta", dst / "meta")
for f in src.glob("*.json"):
    shutil.copy(f, dst / f.name)

info = json.load(open(dst / "meta/info.json"))
for k in [k for k in info["features"] if k.startswith("observation.images.") and k != KEY]:
    del info["features"][k]
ft = info["features"][KEY]
ft["shape"] = [H, W, 3]
ft["info"].update({"video.height": H, "video.width": W, "video.codec": "h264", "video.g": 2})
json.dump(info, open(dst / "meta/info.json", "w"), indent=4)

stats = json.load(open(dst / "meta/stats.json"))
for k in [k for k in stats if k.startswith("observation.images.") and k != KEY]:
    del stats[k]
json.dump(stats, open(dst / "meta/stats.json", "w"), indent=4)

def nframes(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return int(out.strip())

for v in sorted((src / "videos" / KEY).rglob("*.mp4")):
    o = dst / "videos" / KEY / v.relative_to(src / "videos" / KEY)
    o.parent.mkdir(parents=True, exist_ok=True)
    # -fps_mode passthrough: 타임스탬프를 그대로 둬야 에피소드 시작 위치(from_timestamp)가 맞습니다
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-vf", f"scale={W}:{H}:flags=area",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-g", "2", "-pix_fmt", "yuv420p",
                    "-fps_mode", "passthrough", "-an", str(o)], check=True)
    a, b = nframes(v), nframes(o)
    assert a == b, f"{v.name}: 프레임 수 다름 {a} != {b}"
    print(v.relative_to(src), a, "frames ok", flush=True)
