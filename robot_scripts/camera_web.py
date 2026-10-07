"""Browser viewer for the robot cameras: open http://127.0.0.1:8000

Run (conda env lerobot312):  python camera_web.py            both cameras
                             python camera_web.py top        only the top camera
                             python camera_web.py wrist      only the wrist camera
Stop with Ctrl+C. It holds the cameras while running, so stop it before teleoperating or recording.

Cameras are opened in MJPG. In the default uncompressed format (YUY2) the two cameras on the
same USB hub exceed its bandwidth and the second one fails to open.
"""

import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig

# OpenCV index. 0 is the laptop webcam. Re-check with `lerobot-find-cameras opencv` after replugging or rebooting.
CAMERAS = {"top": 2, "wrist": 1}
PORT = 8000

frames = {}  # camera name -> latest JPEG bytes
lock = threading.Lock()
ACTIVE = dict(CAMERAS)  # cameras served, chosen in main()


def capture(name, cam):
    while True:
        rgb = cam.async_read(timeout_ms=1000)
        ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if ok:
            with lock:
                frames[name] = jpg.tobytes()


def make_page(cams):
    return (
        "<!doctype html><meta charset='utf-8'><title>Robot cameras</title>"
        "<body style='margin:0;background:#111;color:#eee;font-family:sans-serif'>"
        "<div style='display:flex;flex-wrap:wrap;gap:16px;padding:16px'>"
        + "".join(
            f"<figure style='margin:0'><figcaption>{name} (index {index})</figcaption>"
            f"<img src='/stream/{name}' width='640' height='480'></figure>"
            for name, index in cams.items()
        )
        + "</div></body>"
    ).encode()


PAGE = make_page(ACTIVE)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.path.startswith("/stream/") and self.path[len("/stream/"):] in ACTIVE:
            name = self.path[len("/stream/"):]
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with lock:
                        jpg = frames.get(name)
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                    time.sleep(1 / 30)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        elif self.path.startswith("/snapshot/") and self.path[len("/snapshot/"):] in ACTIVE:
            with lock:
                jpg = frames.get(self.path[len("/snapshot/"):])
            if jpg is None:
                self.send_error(503, "no frame yet")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(jpg)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def main():
    global ACTIVE, PAGE
    names = sys.argv[1:] or list(CAMERAS)
    ACTIVE = {name: CAMERAS[name] for name in names}
    PAGE = make_page(ACTIVE)
    cams = {
        name: OpenCVCamera(OpenCVCameraConfig(index_or_path=index, width=640, height=480, fps=30, fourcc="MJPG"))
        for name, index in ACTIVE.items()
    }
    for name, cam in cams.items():
        cam.connect()
        print(f"[{name}] camera {ACTIVE[name]} opened", flush=True)
        threading.Thread(target=capture, args=(name, cam), daemon=True).start()
    print(f"Open http://127.0.0.1:{PORT} in a browser. Stop with Ctrl+C.", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
