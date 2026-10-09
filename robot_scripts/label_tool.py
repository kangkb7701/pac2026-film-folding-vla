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

# Competition task: tear one plastic bag off the roll, fold it in half twice, place it on the target.
# The episode start is the start of the first stage (pulling), so it is not marked.
# Each marked moment starts stage `starts` (len(STAGES) = done) and ends the stage before it;
# see export_sarm_labels.py. "0" is only for going back to pulling after the bag slips.
EVENTS = [
    {"key": "pulled", "hotkey": "1", "starts": 1, "name": "끌어옴", "desc": "두 그리퍼가 비닐을 쥐고 왼팔 앞까지 끌어온 순간 (뜯기 시작)"},
    {"key": "torn", "hotkey": "2", "starts": 2, "name": "뜯김", "desc": "비닐 한 장이 롤에서 완전히 떨어진 순간 (펴 놓기 시작)"},
    {"key": "laid", "hotkey": "3", "starts": 3, "name": "펴 놓음", "desc": "가운데에 펴 놓고 그리퍼를 뗀 순간 (접기 시작)"},
    {"key": "folded", "hotkey": "4", "starts": 4, "name": "접음", "desc": "두 번 접어 1/4 크기로 만들고 그리퍼를 뗀 순간 (옮겨 놓기 시작)"},
    {"key": "placed", "hotkey": "5", "starts": 5, "name": "놓음", "desc": "목표 위치에 놓고 그리퍼를 뗀 순간 (완료)"},
    {"key": "repull", "hotkey": "0", "starts": 0, "name": "다시 끌어오기", "desc": "놓쳐서 끌어오기부터 다시 시작한 순간 (필요할 때만)"},
]
# "instruction" is the per-stage task string for the policy.
STAGES = [
    {"key": "pull_out", "name": "끌어오기", "instruction": "Pull out the plastic bag."},
    {"key": "tear_off", "name": "뜯기", "instruction": "Tear off the plastic bag."},
    {"key": "lay_flat", "name": "펴 놓기", "instruction": "Lay the plastic bag flat."},
    {"key": "fold_twice", "name": "접기", "instruction": "Fold the plastic bag twice."},
    {"key": "place", "name": "옮겨 놓기", "instruction": "Place the plastic bag on the target."},
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
    cams.sort(key=lambda k: "top" not in k)  # top view first: stage boundaries are judged from it (SARM paper)
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
    tasks = pd.read_parquet(root / "meta/tasks.parquet").index.tolist()
    return {"fps": info["fps"], "cameras": cams, "episodes": eps, "hil": hil, "dataset_tasks": tasks}


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
        return {
            **meta,
            "events": EVENTS,
            "stages": STAGES,
            "outcomes": OUTCOMES,
            "labels": read_labels()["episodes"],
        }

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
