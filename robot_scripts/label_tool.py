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

# Competition task: tear one plastic bag off the roll, lay it flat, fold it in half twice, move it onto
# the A4 paper, then pick it up and put it into the target.
# Each key marks "from here on, this subtask" (stage `starts`; len(STAGES) = done).
# The episode starts in the first subtask (pulling) even without a mark, and the last marked
# subtask runs to the episode end unless "완료" is marked; see export_sarm_labels.py.
# The page keeps one mark per subtask per episode (pressing a key again moves that mark).
EVENTS = [
    {"key": "pull_out", "hotkey": "1", "starts": 0, "name": "끌어오기", "desc": "여기서부터 비닐 끌어오기 (에피소드 시작은 자동으로 끌어오기)"},
    {"key": "tear_off", "hotkey": "2", "starts": 1, "name": "뜯기", "desc": "여기서부터 절취선 잡고 뜯기"},
    {"key": "lay_flat", "hotkey": "3", "starts": 2, "name": "펴 놓기", "desc": "여기서부터 뜯은 비닐을 가운데에 펴 놓기"},
    {"key": "fold_twice", "hotkey": "4", "starts": 3, "name": "접기", "desc": "여기서부터 두 번 접기"},
    {"key": "place", "hotkey": "5", "starts": 4, "name": "옮겨 놓기", "desc": "여기서부터 접은 비닐을 A4 용지 위로 옮겨 놓기"},
    {"key": "pick_place", "hotkey": "6", "starts": 5, "name": "집어 넣기", "desc": "여기서부터 A4 용지 위의 비닐을 집어 목표에 넣기"},
    {"key": "done", "hotkey": "7", "starts": 6, "name": "완료", "desc": "작업이 끝난 순간 (안 찍으면 에피소드 끝이 완료)"},
]
# "instruction" is the per-stage task string for the policy.
STAGES = [
    {"key": "pull_out", "name": "끌어오기", "instruction": "Pull out the plastic bag."},
    {"key": "tear_off", "name": "뜯기", "instruction": "Tear off the plastic bag."},
    {"key": "lay_flat", "name": "펴 놓기", "instruction": "Lay the plastic bag flat."},
    {"key": "fold_twice", "name": "접기", "instruction": "Fold the plastic bag twice."},
    {"key": "place", "name": "옮겨 놓기", "instruction": "Place the plastic bag on the paper."},
    {"key": "pick_place", "name": "집어 넣기", "instruction": "Pick up the plastic bag and put it into the target."},
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
