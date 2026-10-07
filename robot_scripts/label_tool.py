"""Episode labeling tool for SARM stage annotations (browser UI at http://127.0.0.1:8010).

Usage (conda env lerobot312):
    python label_tool.py C:/Users/kangk/lerobot_data/fold_film_onearm_demo

Plays camera1/camera2 of each episode side by side. Keys mark the film events that bound
the SARM stages and the episode outcome; labels are saved to <dataset>/human_labels.json on
every change. Turn them into SARM annotations with export_sarm_labels.py.
If <dataset>/hil_labels.json exists (intervention recordings), human-driven frames are shaded.
"""

import json
import sys
import threading
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

# Film events (in order). Each stage runs from one event to the next; see export_sarm_labels.py.
EVENTS = [
    {"key": "start", "name": "출발", "desc": "팔이 움직이기 시작"},
    {"key": "lift", "name": "뜸", "desc": "비닐 가장자리가 들림"},
    {"key": "laid", "name": "얹힘", "desc": "접힌 쪽이 반대쪽 절반 위에 얹힘"},
    {"key": "release", "name": "놓음", "desc": "그리퍼가 놓고 팔이 떠남"},
    {"key": "rest", "name": "복귀", "desc": "팔이 쉬는 자세로 돌아옴"},
]
STAGES = [
    {"key": "reach_lift", "name": "다가가 들기"},
    {"key": "fold_over", "name": "넘기기"},
    {"key": "place_adjust", "name": "얹고 정리"},
    {"key": "retreat", "name": "물러나기"},
]
OUTCOMES = {
    "success": "성공",
    "misaligned": "성공(정렬 불량)",
    "failure": "실패",
    "exclude": "제외",
}
PORT = 8010


def load_meta(root: Path) -> dict:
    info = json.loads((root / "meta/info.json").read_text())
    cams = [k for k, v in info["features"].items() if v["dtype"] == "video"]
    episodes = pd.concat(pd.read_parquet(f) for f in sorted((root / "meta/episodes").rglob("*.parquet")))
    eps = []
    for _, row in episodes.sort_values("episode_index").iterrows():
        videos = {}
        for cam in cams:
            chunk, file = int(row[f"videos/{cam}/chunk_index"]), int(row[f"videos/{cam}/file_index"])
            rel = info["video_path"].format(video_key=cam, chunk_index=chunk, file_index=file)  # "videos/..."
            videos[cam] = {
                "url": "/" + rel.replace("\\", "/"),
                "from": float(row[f"videos/{cam}/from_timestamp"]),
                "to": float(row[f"videos/{cam}/to_timestamp"]),
            }
        eps.append({"index": int(row["episode_index"]), "length": int(row["length"]), "videos": videos})
    hil_path = root / "hil_labels.json"
    hil = {str(e["episode_index"]): e for e in json.loads(hil_path.read_text())} if hil_path.exists() else {}
    return {"fps": info["fps"], "cameras": cams, "episodes": eps, "hil": hil}


def make_app(root: Path) -> FastAPI:
    app = FastAPI()
    meta = load_meta(root)
    labels_path = root / "human_labels.json"
    save_lock = threading.Lock()
    html =(Path(__file__).with_name("label_tool.html")).read_text(encoding="utf-8")

    def read_labels() -> dict:
        return json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {"episodes": {}}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return html

    @app.get("/api/meta")
    def api_meta():
        return {**meta, "events": EVENTS, "stages": STAGES, "outcomes": OUTCOMES, "labels": read_labels()["episodes"]}

    @app.post("/api/label/{episode}")
    def api_label(episode: int, label: dict = Body(...)):
        with save_lock:  # requests run in a thread pool; serialize the read-modify-write
            data = read_labels()
            data.update({"dataset": str(root), "fps": meta["fps"], "events": [e["key"] for e in EVENTS]})
            data["episodes"][str(episode)] = {
                "events": sorted(label.get("events", []), key=lambda e: e["frame"]),
                "outcome": label.get("outcome"),
                "note": label.get("note", ""),
            }
            tmp = labels_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(labels_path)  # atomic: a crash never leaves a half-written label file
        return {"ok": True}

    @app.get("/videos/{path:path}")
    def videos(path: str):
        file = (root / "videos" / path).resolve()
        if not file.is_file() or (root / "videos").resolve() not in file.parents:
            raise HTTPException(404)
        return FileResponse(file, media_type="video/mp4")  # supports Range requests (seeking)

    return app


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python label_tool.py <LeRobot dataset folder>")
    root = Path(sys.argv[1])
    if not (root / "meta/info.json").exists():
        raise SystemExit(f"not a LeRobot dataset: {root}")
    print(f"labeling {root}\nopen http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    uvicorn.run(make_app(root), host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
