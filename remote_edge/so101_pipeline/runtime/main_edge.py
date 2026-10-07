#!/usr/bin/env python3
"""Edge agent: the laptop half of the split ACT deployment.

Owns everything at the robot side so the WAN link is never inside a control
loop and never between the stop button and the motors:

  - SO-101 bus + two cameras via lerobot (local, 10Hz)
  - the app backend the Flutter app talks to (commands + /video_feed, one port)
  - a websocket client that streams observations OUT to the ACT policy server
    and replays the returned action chunks locally
  - safety: per-step delta clamp, absolute joint limits, chunk-consumption cap,
    watchdog (hold -> home on link loss), local home primitive
  - auto-stop (zero-velocity / chunk-stability), ported from main_act.py but
    time-based instead of tick-based because the inference rate is adaptive

Inference pacing is "one request in flight": a new observation is sent the
moment the previous chunk arrives, so the effective rate adapts to the link.
Chunks are indexed by (now - t_obs) on the laptop's own monotonic clock (the
server echoes t_obs untouched), which skips exactly the steps the network
delay already consumed.

First run per cable-plug: `python -m so101_pipeline.runtime.main_edge
--identify` - camera indices shuffle on every reconnect, so the mapping is
confirmed by eye and stored in edge_cameras.json.

Test without GPU/robot motion: run `act_policy_server --mock` locally and
start this agent with --dry_run (never enables torque, never writes goals).
"""

from __future__ import annotations

import argparse
import json
import queue
import shutil
import threading
import time
from pathlib import Path

import cv2
import msgpack
import numpy as np

from so101_pipeline.interfaces.command_bridge import normalize_command
from so101_pipeline.interfaces.edge_app_backend import CommandStore, build_app, start_app_server
from lerobot.cameras.configs import Cv2Backends
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.common.control_utils import teleop_smooth_move_to
from lerobot.datasets import LeRobotDataset
from lerobot.robots import make_robot_from_config
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.teleoperators import make_teleoperator_from_config
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features
from lerobot.utils.robot_utils import precise_sleep

JOINT_NAMES = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
# PAC 2026: mean first-frame state of the fold_film_onearm_demo episodes (rest pose, gripper closed).
HOME_POSITION_DEG = np.asarray([1.6, -99.5, 90.7, 73.7, 17.6, 1.9], dtype=np.float32)
HOME_MOVE_DURATION_S = 2.5
HOME_MOVE_HZ = 30
CAMERA_PRIME_TIMEOUT_MS = 2000  # first frame after connect; the sensor is still settling
# PAC 2026: must match the dataset task string exactly (SmolVLA reads it as language input).
ACT_ALLOWED_TASKS = ("Fold the plastic film in half.",)
# PAC 2026: dataset camera keys, in SmolVLA's pretraining order (top=1, wrist=2).
POLICY_CAMERA_KEYS = {"top": "camera1", "wrist": "camera2"}
# Intervention mode: space/tab as in lerobot-rollout --strategy.type=dagger, plus start and attempt labels.
HIL_KEYS = {
    "enter": "start",
    "space": "pause_resume",
    "tab": "correction",
    "s": "success",
    "f": "failure",
    "backspace": "discard",
    "esc": "quit",
}
# Absolute command limits (deg; gripper is 0-100). Home pose must fit inside.
JOINT_LIMITS = {
    "shoulder_pan": (-115.0, 115.0),
    "shoulder_lift": (-115.0, 115.0),
    "elbow_flex": (-115.0, 115.0),
    "wrist_flex": (-115.0, 115.0),
    "wrist_roll": (-180.0, 180.0),
    "gripper": (0.0, 100.0),
}
LIMIT_LOW = np.asarray([JOINT_LIMITS[n][0] for n in JOINT_NAMES], dtype=np.float32)
LIMIT_HIGH = np.asarray([JOINT_LIMITS[n][1] for n in JOINT_NAMES], dtype=np.float32)


# ---------------------------------------------------------------- cameras

def camera_config_path(args) -> Path:
    if args.camera_config:
        return Path(args.camera_config)
    return Path(__file__).resolve().parents[2] / "edge_cameras.json"


def identify_cameras(args) -> None:
    """Probe indices, save preview frames, ask which is which, store mapping."""
    out_dir = camera_config_path(args).parent
    found = []
    for index in range(args.identify_max_index + 1):
        cap = cv2.VideoCapture(index, cv2.CAP_ANY)  # same backend as lerobot-find-cameras / recording
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        for _ in range(8):  # let exposure settle
            cap.read()
        ok, frame = cap.read()
        cap.release()
        if not ok:
            continue
        preview = out_dir / f"edge_camera_preview_{index}.png"
        # cv2.imwrite silently fails on non-ASCII (Korean) paths on Windows
        ok, encoded = cv2.imencode(".png", frame)
        if not ok:
            raise SystemExit(f"index {index}: could not encode preview")
        preview.write_bytes(encoded.tobytes())
        found.append(index)
        print(f"  index {index}: preview saved -> {preview}")
    if len(found) < 2:
        raise SystemExit(f"need at least 2 cameras, found indices {found}")
    top = int(input(f"top camera index {found}: ").strip())
    wrist = int(input(f"wrist camera index {found}: ").strip())
    if top == wrist or top not in found or wrist not in found:
        raise SystemExit("invalid selection")
    path = camera_config_path(args)
    path.write_text(json.dumps({"top": top, "wrist": wrist}, indent=2))
    print(f"saved: {path}")


def load_camera_mapping(args) -> dict:
    path = camera_config_path(args)
    if not path.exists():
        raise SystemExit(f"{path} not found - run with --identify first (indices shuffle on every reconnect)")
    mapping = json.loads(path.read_text())
    return {"top": int(mapping["top"]), "wrist": int(mapping["wrist"])}


def start_key_listener(push) -> None:
    """Global keyboard hook (pynput, as lerobot-record uses): keys act whichever window has focus."""
    from pynput import keyboard

    def on_press(key):
        name = key.char.lower() if isinstance(key, keyboard.KeyCode) and key.char else getattr(key, "name", None)
        if name in HIL_KEYS:
            push(HIL_KEYS[name])

    keyboard.Listener(on_press=on_press).start()


# ---------------------------------------------------------------- policy link

class PolicyClient(threading.Thread):
    """Up to max_inflight requests on the wire; reconnects with backoff.

    Pipelining: while the server runs inference on request N, request N+1 is
    already uploading, so the vote rate approaches 1/max(upload, infer) instead
    of 1/(upload + infer + rtt). The server handles one frame at a time per
    connection, so replies come back in request order; snapshots are paired
    FIFO, and the consumer's t_obs guard drops anything that still arrives
    out of order.
    """

    def __init__(self, url: str, on_chunk, on_error, max_inflight: int = 2):
        super().__init__(name="policy-client", daemon=True)
        self.url = url
        self.on_chunk = on_chunk
        self.on_error = on_error
        self.max_inflight = max(1, int(max_inflight))
        self._requests: queue.Queue = queue.Queue(maxsize=self.max_inflight)
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._stop = threading.Event()
        self.connected = threading.Event()

    def submit(self, request: dict, snapshot: dict) -> bool:
        """Non-blocking; False when max_inflight requests are already pending."""
        with self._inflight_lock:
            if self._inflight >= self.max_inflight:
                return False
            self._inflight += 1
        try:
            self._requests.put_nowait((request, snapshot))
            return True
        except queue.Full:
            with self._inflight_lock:
                self._inflight -= 1
            return False

    def _release(self) -> None:
        with self._inflight_lock:
            self._inflight = max(0, self._inflight - 1)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        from collections import deque

        from websockets.sync.client import connect

        backoff = 0.5
        while not self._stop.is_set():
            conn_dead = threading.Event()  # stops this connection's sender on teardown
            try:
                with connect(self.url, max_size=32 * 1024 * 1024, open_timeout=5) as ws:
                    self.connected.set()
                    backoff = 0.5
                    print(f"policy server connected: {self.url} (pipeline depth {self.max_inflight})")
                    pending: deque = deque()  # snapshots FIFO; server replies in request order
                    send_exc: list[Exception] = []

                    def send_loop() -> None:
                        try:
                            while not self._stop.is_set() and not conn_dead.is_set():
                                try:
                                    request, snapshot = self._requests.get(timeout=0.2)
                                except queue.Empty:
                                    continue
                                pending.append(snapshot)
                                ws.send(msgpack.packb(request))
                        except Exception as exc:  # noqa: BLE001 - surface to the recv loop
                            send_exc.append(exc)

                    sender = threading.Thread(target=send_loop, name="policy-sender", daemon=True)
                    sender.start()
                    while not self._stop.is_set():
                        if send_exc:
                            raise send_exc[0]
                        try:
                            raw = ws.recv(timeout=0.5)
                        except TimeoutError:
                            continue  # idle poll; genuine link failures raise other errors
                        reply = msgpack.unpackb(raw, raw=False)
                        snapshot = pending.popleft() if pending else None
                        self._release()
                        if reply.get("type") == "chunk" and snapshot is not None:
                            self.on_chunk(reply, snapshot)
                        elif reply.get("type") != "chunk":
                            self.on_error(f"server error: {reply.get('message')}")
            except Exception as exc:  # noqa: BLE001 - any link failure -> reconnect
                self.connected.clear()
                conn_dead.set()
                while True:  # drop queued-but-unsent requests; their observations are stale now
                    try:
                        self._requests.get_nowait()
                    except queue.Empty:
                        break
                with self._inflight_lock:
                    self._inflight = 0  # in-flight requests died with the connection
                self.on_error(f"policy link down ({type(exc).__name__}: {exc}); retrying in {backoff:.1f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
        self.connected.clear()


# ---------------------------------------------------------------- agent

class EdgeAgent:
    def __init__(self, args):
        self.args = args
        self.store = CommandStore()
        mapping = load_camera_mapping(args)
        print(f"cameras: top=idx{mapping['top']} wrist=idx{mapping['wrist']} (from {camera_config_path(args)})")
        self.robot = make_robot_from_config(
            SOFollowerRobotConfig(
                id=args.robot_id,
                port=args.robot_port,
                calibration_dir=Path(args.calibration_dir) if args.calibration_dir else None,
                disable_torque_on_disconnect=True,
                use_degrees=True,
                cameras={
                    # Same settings the dataset was recorded with; without MJPG the second
                    # camera on the shared hub fails to open (YUY2 exceeds the USB bandwidth).
                    name: OpenCVCameraConfig(
                        index_or_path=index, fps=30, width=640, height=480, backend=Cv2Backends.ANY, fourcc="MJPG"
                    )
                    for name, index in mapping.items()
                },
            )
        )
        self._lock = threading.Lock()
        self._chunk = None            # np (n_steps, 6) in JOINT_NAMES order
        self._chunk_t0 = 0.0          # laptop monotonic time of the source observation
        self._chunk_fps = 10
        self._chunk_arrival = 0.0
        self._chunk_obs_joints = None
        self._chunk_buf = []          # newest-last [(chunk, t0, fps)] for the temporal ensemble
        self._zero_count = 0            # consecutive qualifying chunks, like main_act's counters
        self._stable_count = 0
        self._zero_metrics = (float("inf"), float("inf"))
        self._stable_metrics = (float("inf"), float("inf"))
        self._episode_start = 0.0
        self._infer_ms_log = []
        self._episode_id = 0
        self._app_jpeg = None
        self._configured = False
        self._last_submit_t = 0.0
        self._last_frames = {}        # per camera, for reuse across a dropped read
        self._drop_streak = 0         # consecutive loop ticks with any dropped frame
        self._drops_total = 0
        self.client = PolicyClient(
            args.server_url, self._handle_chunk, lambda msg: print(f"[link] {msg}"), max_inflight=args.max_inflight
        )
        # Intervention mode (leader arm attached): pause the policy, take over with the leader, hand back.
        self.teleop = None
        if args.teleop_port:
            self.teleop = make_teleoperator_from_config(
                SOLeaderTeleopConfig(id=args.teleop_id, port=args.teleop_port, use_degrees=True)
            )
        self.events: queue.Queue = queue.Queue()  # intervention keys (keyboard or POST /command/key)
        self.dataset = None
        self._rec_frames = 0
        self._labels = []
        self._labels_path = None
        self._pending_save = None  # (outcome, interventions) of the attempt that just ended

    # ---- hardware ----

    def connect(self) -> None:
        if self.teleop is not None:
            self.teleop.connect()  # before the robot, like lerobot-record
            print(f"leader arm connected on {self.args.teleop_port} (intervention mode)")
        self.robot.bus.connect()
        if not self.robot.bus.is_calibrated:
            raise SystemExit("motor calibration mismatch - check --calibration_dir / --robot_id")
        for cam in self.robot.cameras.values():
            cam.connect()
        # Prime the reuse buffer patiently: read_frames() falls back to the last
        # good frame, so every camera needs one before any loop starts.
        for name, cam in self.robot.cameras.items():
            self._last_frames[name] = cam.async_read(timeout_ms=CAMERA_PRIME_TIMEOUT_MS)
        print(f"bus connected on {self.args.robot_port}; cameras up; dry_run={self.args.dry_run}")

    def read_frames(self) -> dict | None:
        """Latest frame per camera, tolerating dropped reads.

        lerobot's async_read raises TimeoutError when the USB read thread is
        late (200ms default), which a hub hiccup triggers on its own. That used
        to kill the agent outright - app backend, watchdog and torque state with
        it - so a miss reuses the previous frame instead. Returns None once
        --camera_drop_limit consecutive ticks have missed, i.e. the camera is
        actually gone rather than merely late; acting on a frozen image past
        that point is worse than stopping.
        """
        frames, dropped = {}, []
        for name, cam in self.robot.cameras.items():
            try:
                frames[name] = self._last_frames[name] = cam.async_read()
            except (TimeoutError, RuntimeError) as exc:
                frames[name] = self._last_frames[name]
                dropped.append(f"{name}({type(exc).__name__})")
        if not dropped:
            self._drop_streak = 0
            return frames
        self._drop_streak += 1
        self._drops_total += 1
        if self._drop_streak == 1 or self._drop_streak % 10 == 0:
            print(f"[camera] frame drop: {', '.join(dropped)}; streak={self._drop_streak} total={self._drops_total}")
        return None if self._drop_streak > self.args.camera_drop_limit else frames

    def read_joints(self) -> np.ndarray:
        positions = self.robot.bus.sync_read("Present_Position")
        return np.asarray([positions[name] for name in JOINT_NAMES], dtype=np.float32)

    def write_joints(self, target: np.ndarray) -> None:
        if self.args.dry_run:
            return
        self.robot.bus.sync_write("Goal_Position", {name: float(target[i]) for i, name in enumerate(JOINT_NAMES)})

    def clamp(self, target: np.ndarray, reference: np.ndarray) -> np.ndarray:
        step = np.asarray(
            [self.args.max_step_deg] * 5 + [self.args.max_step_gripper], dtype=np.float32
        )
        clamped = np.clip(target, reference - step, reference + step)
        return np.clip(clamped, LIMIT_LOW, LIMIT_HIGH)

    def preset_gripper(self, target: float) -> None:
        """Ramp only the gripper to the training-data start state.

        The home pose parks the gripper closed (2.3), but every training episode
        starts with it open (~40, the pipeline's canonical open position - see
        GRIPPER_BINARY_OPEN_POS / ik_ctrl.gripper_open_pos). Starting an episode
        closed is out of distribution and the policy just holds it shut, so the
        episode precondition is restored explicitly instead of changing home.
        """
        current = self.read_joints()
        if abs(float(current[5]) - target) < 2.0:
            return
        goal = current.copy()
        steps = max(1, round(0.8 * HOME_MOVE_HZ))
        for step in range(1, steps + 1):
            goal[5] = current[5] + (step / steps) * (target - current[5])
            self.write_joints(goal)
            precise_sleep(1.0 / HOME_MOVE_HZ)
        print(f"gripper preset to {target:.0f} (training start state)")

    def move_home(self, reason: str) -> None:
        print(f"returning home ({reason})...")
        if self.args.dry_run:
            print("dry_run: home skipped")
            return
        current = self.read_joints()
        steps = max(1, round(HOME_MOVE_DURATION_S * HOME_MOVE_HZ))
        for step in range(1, steps + 1):
            alpha = step / steps
            self.write_joints(current + alpha * (HOME_POSITION_DEG - current))
            precise_sleep(1.0 / HOME_MOVE_HZ)
        print("home pose reached")

    # ---- intervention (lerobot dagger handover, rollout/strategies/dagger.py) ----

    def _hold_leader_here(self) -> None:
        # Goal = present pose before torque comes on, so the leader can't snap back to an older goal.
        self.teleop.send_feedback(self.teleop.get_action())
        self.teleop.enable_torque()

    def pause_to_leader(self, follower_target: np.ndarray) -> None:
        """Policy paused: the follower holds its last goal; the leader is driven to that pose."""
        if self.args.dry_run:
            print("dry_run: leader handover skipped")
            return
        self._hold_leader_here()
        teleop_smooth_move_to(self.teleop, {f"{n}.pos": float(follower_target[i]) for i, n in enumerate(JOINT_NAMES)})

    def release_leader(self) -> None:
        if not self.args.dry_run:
            self.teleop.disable_torque()

    def hold_leader(self) -> None:
        if not self.args.dry_run:
            self._hold_leader_here()

    def reset_plan(self) -> None:
        """Drop the pre-pause plan; a new episode id makes the server reset the policy and the
        client ignore replies to observations taken before the pause."""
        with self._lock:
            self._episode_id += 1
            self._chunk = self._chunk_obs_joints = None
            self._chunk_buf = []

    # ---- recording ----

    def open_dataset(self) -> None:
        """Same features as the teleop demos (camera1/camera2, joint names, fps), so the datasets merge as is.
        Who drove each frame and the attempt outcome go to hil_labels.json, not into the dataset."""
        args = self.args
        joints = {f"{n}.pos": float for n in JOINT_NAMES}
        cams = {
            POLICY_CAMERA_KEYS[name]: (cfg.height, cfg.width, 3) for name, cfg in self.robot.config.cameras.items()
        }
        features = {**hw_to_dataset_features(joints, ACTION), **hw_to_dataset_features({**joints, **cams}, OBS_STR)}
        root = Path(args.record_root)
        writer = dict(batch_encoding_size=args.video_encoding_batch_size, image_writer_threads=4 * len(cams))
        self._writer_kwargs = writer
        if (root / "meta" / "info.json").exists():
            self.dataset = LeRobotDataset.resume(args.record_repo_id, root=root, **writer)
        else:
            self.dataset = LeRobotDataset.create(
                args.record_repo_id, args.control_fps, features=features, root=root, robot_type=self.robot.name, **writer
            )
        # Staged frames left by a killed attempt would be globbed into the next episode's video
        # (same episode index); every saved attempt is already encoded and finalized, so drop them.
        if (root / "images").exists():
            shutil.rmtree(root / "images")
            print("removed staged frames of an unfinished attempt from the last session")
        self._labels_path = root / "hil_labels.json"
        self._labels = json.loads(self._labels_path.read_text()) if self._labels_path.exists() else []
        print(f"recording to {root} ({self.dataset.num_episodes} episodes so far)")

    def record_frame(self, task: str, joints: np.ndarray, frames: dict, action: np.ndarray) -> None:
        values = {f"{n}.pos": float(joints[i]) for i, n in enumerate(JOINT_NAMES)}
        values.update({POLICY_CAMERA_KEYS[name]: frame for name, frame in frames.items()})
        act = {f"{n}.pos": float(action[i]) for i, n in enumerate(JOINT_NAMES)}
        self.dataset.add_frame(
            {
                **build_dataset_frame(self.dataset.features, values, prefix=OBS_STR),
                **build_dataset_frame(self.dataset.features, act, prefix=ACTION),
                "task": task,
            }
        )
        self._rec_frames += 1

    def save_attempt(self, outcome: str | None, interventions: list) -> None:
        """'success'/'failure' saves the attempt as one episode; None discards it."""
        if self.dataset is None:
            return
        if outcome is None or self._rec_frames == 0:
            self.dataset.clear_episode_buffer()
            print("attempt discarded (not saved)")
        else:
            self.dataset.save_episode()
            # Commit now: LeRobot keeps the data parquet open and buffers episode metadata until
            # finalize(), so a killed process (window closed) would otherwise lose the whole session.
            self.dataset.finalize()
            entry = {
                "episode_index": self.dataset.num_episodes - 1,
                "success": outcome == "success",
                "frames": self._rec_frames,
                "interventions": interventions,  # [start, end) frame ranges driven by the human
            }
            self._labels.append(entry)
            self._labels_path.write_text(json.dumps(self._labels, indent=1))
            print(
                f"saved episode {entry['episode_index']}: {outcome}, "
                f"{len(interventions)} intervention(s), {self._rec_frames} frames"
            )
            self.dataset = LeRobotDataset.resume(
                self.args.record_repo_id, root=Path(self.args.record_root), **self._writer_kwargs
            )
        self._rec_frames = 0

    def end_attempt(self, outcome: str | None, interventions: list, phase: str) -> None:
        """Release the leader and queue the save; run() saves after the arm is home."""
        if phase == "correcting" and interventions and interventions[-1][1] is None:
            interventions[-1][1] = self._rec_frames
        if self.teleop is not None:
            self.release_leader()
        self._pending_save = (outcome, interventions)

    # ---- chunk handling (called from the client thread) ----

    def _handle_chunk(self, reply: dict, snapshot: dict) -> None:
        names = reply["joint_names"]
        raw = np.asarray(reply["chunk"], dtype=np.float32)
        try:
            order = [names.index(f"{n}.pos") if f"{n}.pos" in names else names.index(n) for n in JOINT_NAMES]
        except ValueError:
            print(f"[link] chunk joint names {names} don't match {JOINT_NAMES}; dropping")
            return
        chunk = raw[:, order]
        with self._lock:
            if reply["episode_id"] != self._episode_id:
                return  # stale reply from a previous task
            if self._chunk is not None and reply["t_obs"] <= self._chunk_t0:
                return  # out-of-order reply; keep the newer plan
            raw_chunk = chunk  # the ensemble/auto-stop buffer keeps the unblended chunk
            if self._chunk is not None and self.args.blend_old_weight > 0.0:
                # LeRobot async weighted_average (robot_client._aggregate_action_queues):
                # steps the current plan still covers become w*old + (1-w)*new; the
                # rest are taken as is. The plan is itself a blend, so older chunks decay.
                w = self.args.blend_old_weight
                fps = int(reply["fps"])
                shift = round((reply["t_obs"] - self._chunk_t0) * fps)
                chunk = chunk.copy()
                for i in range(len(chunk)):
                    j = shift + i
                    if 0 <= j < len(self._chunk):
                        chunk[i] = w * self._chunk[j] + (1.0 - w) * chunk[i]
            self._chunk = chunk
            self._chunk_t0 = reply["t_obs"]
            self._chunk_fps = int(reply["fps"])
            self._chunk_arrival = time.monotonic()
            self._chunk_obs_joints = snapshot["joints"]
            # Buffer every chunk until it expires (its last step is in the past);
            # the ensemble needs the full set, like the baseline TemporalEnsembler.
            mono = time.monotonic()
            self._chunk_buf = [e for e in self._chunk_buf if int((mono - e[1]) * e[2]) < len(e[0])]
            self._chunk_buf.append((raw_chunk, reply["t_obs"], int(reply["fps"])))
            # keep at least 2: the chunk-stability auto-stop compares newest vs previous
            del self._chunk_buf[: -max(self.args.ensemble_chunks, 2)]
            self._infer_ms_log.append(reply.get("infer_ms", 0.0))
        self._update_auto_stop(raw_chunk, reply["t_obs"], snapshot["joints"])

    def _update_auto_stop(self, chunk, t0, obs_joints) -> None:
        """Baseline auto-stop, per arriving chunk (main_act checks per inference).

        Like main_act: a condition must hold for N CONSECUTIVE chunks
        (*_consecutive_steps), any miss resets its counter, and counting only
        starts after the per-condition minimum episode duration.
        """
        args = self.args
        elapsed = time.monotonic() - self._episode_start
        horizon = max(1, min(args.auto_stop_horizon, len(chunk)))

        zero_delta = np.abs(chunk[:horizon] - obs_joints[None, :])
        self._zero_metrics = (float(zero_delta.max()), float(zero_delta.mean()))
        is_zero = (
            elapsed >= args.zero_velocity_min_duration_s
            and self._zero_metrics[0] <= args.zero_velocity_max_delta_deg
            and self._zero_metrics[1] <= args.zero_velocity_mean_delta_deg
        )
        self._zero_count = self._zero_count + 1 if is_zero else 0

        with self._lock:
            # buf[-1] is the chunk passed in; buf[-2] is the plan it replaced
            prev, prev_t0 = self._chunk_buf[-2][:2] if len(self._chunk_buf) > 1 else (None, 0.0)
        self._stable_metrics = (float("inf"), float("inf"))
        is_stable = False
        if prev is not None:
            # main_act compares prev shifted by exactly one step; chunks here are
            # spaced by the link, so shift by the observed spacing instead.
            # offset 0 (a pipelined burst) is a valid comparison, not a reset.
            offset = max(0, round((t0 - prev_t0) * self._chunk_fps))
            aligned = min(horizon, len(chunk), len(prev) - offset)
            if aligned >= 1:
                delta = np.abs(chunk[:aligned] - prev[offset:offset + aligned])
                self._stable_metrics = (float(delta.max()), float(delta.mean()))
                is_stable = (
                    elapsed >= args.chunk_stability_min_duration_s
                    and self._stable_metrics[0] <= args.chunk_stability_max_delta_deg
                    and self._stable_metrics[1] <= args.chunk_stability_mean_delta_deg
                )
        self._stable_count = self._stable_count + 1 if is_stable else 0

    def auto_stop_reason(self) -> str | None:
        args = self.args
        if self._stable_count >= args.chunk_stability_consecutive_steps:
            return (
                f"stable action chunk for {self._stable_count} consecutive chunks "
                f"(max_delta={self._stable_metrics[0]:.2f}, mean_delta={self._stable_metrics[1]:.2f})"
            )
        if self._zero_count >= args.zero_velocity_consecutive_steps:
            return (
                f"zero-velocity chunk for {self._zero_count} consecutive chunks "
                f"(max_delta={self._zero_metrics[0]:.2f}, mean_delta={self._zero_metrics[1]:.2f})"
            )
        return None

    # ---- observation upload ----

    def maybe_submit_observation(self, task: str, joints: np.ndarray, frames: dict) -> None:
        if time.monotonic() - self._last_submit_t < self.args.min_infer_period_s:
            return
        with self._lock:
            chunk, t0, fps = self._chunk, self._chunk_t0, self._chunk_fps
        if chunk is not None:
            # LeRobot async _ready_to_send_observation: only ask for a new chunk once the
            # unexecuted part of the current plan is down to chunk_size_threshold of a chunk.
            remaining = len(chunk) - int((time.monotonic() - t0) * fps)
            if remaining > self.args.chunk_size_threshold * len(chunk):
                return
        encode =[int(cv2.IMWRITE_JPEG_QUALITY), self.args.jpeg_quality]
        images = {}
        for name, frame in frames.items():
            ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), encode)
            if not ok:
                return
            images[POLICY_CAMERA_KEYS[name]] = jpeg.tobytes()
        request = {
            "token": self.args.token,
            "type": "predict",
            "episode_id": self._episode_id,
            "t_obs": time.monotonic(),
            "task": task,
            "joints": {name: float(joints[i]) for i, name in enumerate(JOINT_NAMES)},
            "images": images,
        }
        if self.client.submit(request, {"joints": joints.copy()}):
            self._last_submit_t = time.monotonic()

    # ---- app video ----

    def publish_app_frame(self, frames: dict) -> None:
        ordered = [frames[n] for n in ("top", "wrist") if n in frames]
        if not ordered:
            return
        combined = np.hstack(ordered) if len(ordered) > 1 else ordered[0]
        ok, jpeg = cv2.imencode(
            ".jpg", cv2.cvtColor(combined, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), self.args.app_jpeg_quality]
        )
        if ok:
            self._app_jpeg = jpeg.tobytes()

    def app_jpeg(self):
        return self._app_jpeg

    # ---- episode ----

    def run_episode(self, task: str, consumed_stop_ts) -> str | None:
        """Returns the stop ts if the app stopped us, else None. Home is caller's job."""
        args = self.args
        with self._lock:
            self._episode_id += 1
            self._chunk = self._chunk_obs_joints = None
            self._chunk_buf = []
            self._infer_ms_log = []
        self._zero_count = self._stable_count = 0
        self._zero_metrics = self._stable_metrics = (float("inf"), float("inf"))
        if not args.dry_run:
            if not self._configured:
                # Same motor setup robot.connect() would do in main_act: position
                # mode, P=16 (default 32 causes shakiness), gripper protections.
                self.robot.configure()
                self._configured = True
                print("servo gains configured (P=16, matching main_act)")
            self.robot.bus.enable_torque()
            if args.episode_start_gripper >= 0.0:
                self.preset_gripper(args.episode_start_gripper)
        last_sent = self.read_joints()
        start = time.monotonic()
        self._episode_start = start
        tick, chunks_used, clamp_hits, holds, ensemble_n = 0, 0, 0, 0, 1
        print_t, late, busy_max = start, 0, 0.0
        # Task-cycle stop: after task completion the policy extrapolates outside
        # its training data (demos end right after the place) and may drift
        # instead of settling, so the stillness detectors never fire over the
        # link. The grasp->release cycle IS the task's success signal, and the
        # measured gripper shows it unambiguously: closed (holding) for a while,
        # then reopened at the basket.
        grasp_since, grasped, release_t = None, False, None
        phase = "auto"  # auto: policy drives | paused: follower holds | correcting: human drives via the leader
        wait_start = start  # start of the current wait for a plan (episode start, or policy resume)
        interventions: list = []  # [start, end) recorded-frame ranges driven by the human
        awaiting_label = False
        t0 = 0.0
        chunk = None
        self._rec_frames = 0
        self._pending_save = None
        print(f"episode {self._episode_id} start: {task!r}")

        while True:
            loop_t = time.monotonic()
            if not awaiting_label and loop_t - start >= args.duration_s:
                print(f"episode time limit ({args.duration_s}s) reached")
                if self.dataset is None:
                    self.end_attempt(None, interventions, phase)
                    return None
                # Only the operator knows the outcome: hold until it is labeled.
                if phase == "correcting":
                    interventions[-1][1] = self._rec_frames
                    self.hold_leader()
                phase, awaiting_label = "paused", True
                print("label this attempt: S = success, F = failure, Backspace = discard")
            joints = self.read_joints()
            frames = self.read_frames()
            if frames is None:
                print(f"camera stalled for {self._drop_streak} ticks - safety stop")
                self.end_attempt(None, interventions, phase)
                return None
            self.publish_app_frame(frames)

            label = None
            while not self.events.empty():
                event = self.events.get_nowait()
                if event in ("success", "failure", "discard"):
                    label = event
                elif self.teleop is None or awaiting_label or event not in ("pause_resume", "correction"):
                    print(f"key {event!r} ignored ({'waiting for a label' if awaiting_label else phase})")
                elif event == "pause_resume" and phase == "auto":
                    print("paused - leader moves to the follower pose. Tab = take over, Space = resume policy")
                    phase = "paused"
                    self.pause_to_leader(last_sent)
                elif event == "pause_resume" and phase == "paused":
                    print("policy resumed - waiting for a fresh plan")
                    phase = "auto"
                    self.release_leader()
                    self.reset_plan()
                    wait_start = time.monotonic()
                elif event == "correction" and phase == "paused":
                    print("human control (recording). Tab = stop correcting")
                    phase = "correcting"
                    self.release_leader()
                    interventions.append([self._rec_frames, None])
                elif event == "correction" and phase == "correcting":
                    print("correction ended - holding. Space = resume policy, Tab = correct again")
                    phase = "paused"
                    interventions[-1][1] = self._rec_frames
                    self.hold_leader()
                else:
                    print(f"key {event!r} ignored ({phase})")
            if label is not None:
                print(f"attempt ended by operator: {label}")
                self.end_attempt(None if label == "discard" else label, interventions, phase)
                return None

            stop = self.store.snapshot()["stop"]
            if stop["requested"] and stop["ts"] != consumed_stop_ts:
                print("app stop received")
                self.end_attempt(None, interventions, phase)
                return stop["ts"]

            now = time.monotonic()
            if phase == "correcting":
                leader = self.teleop.get_action()
                action = np.asarray([leader[f"{n}.pos"] for n in JOINT_NAMES], dtype=np.float32)
                target = self.clamp(action, last_sent)
                self.write_joints(target)
                last_sent = target
                if self.dataset is not None:
                    self.record_frame(task, joints, frames, action)  # leader pose, as in teleop demos
            elif phase == "auto":
                self.maybe_submit_observation(task, joints, frames)
                with self._lock:
                    chunk, t0, fps, arrival = self._chunk, self._chunk_t0, self._chunk_fps, self._chunk_arrival
                    buf = list(self._chunk_buf)
                if chunk is None:
                    if now - wait_start > args.first_chunk_timeout_s:
                        print(f"no chunk within {args.first_chunk_timeout_s}s - aborting episode")
                        self.end_attempt(None, interventions, phase)
                        return None
                else:
                    index = int((now - t0) * fps)
                    usable = min(len(chunk), args.consume_cap_steps)
                    if index < 0:
                        index = 0
                    if index < usable:
                        step_target = chunk[index]
                        if args.ensemble_chunks > 1 and len(buf) > 1:
                            # Wall-clock port of the baseline ACTTemporalEnsembler
                            # (modeling_act.py): every chunk that covers this instant
                            # votes, weighted exp(-coeff * rank) with the OLDEST
                            # contributor at rank 0, i.e. weighted highest - exactly
                            # the baseline's w_i = exp(-m*i) with m=0.01. This is what
                            # commits transitions: a plan that scheduled "open the
                            # gripper at T" gets executed at T even if fresher plans
                            # keep deferring it.
                            acc = np.zeros_like(step_target)
                            weight_sum = 0.0
                            ensemble_n = 0
                            for c, c_t0, c_fps in buf:  # buf is oldest-first
                                c_index = int((now - c_t0) * c_fps)
                                if 0 <= c_index < len(c):
                                    w = float(np.exp(-args.ensemble_coeff * ensemble_n))
                                    acc += w * c[c_index]
                                    weight_sum += w
                                    ensemble_n += 1
                            if weight_sum > 0.0:
                                step_target = acc / weight_sum
                        target = self.clamp(step_target, last_sent)
                        if not np.allclose(target, step_target, atol=1e-3):
                            clamp_hits += 1
                        self.write_joints(target)
                        last_sent = target
                        chunks_used += 1
                        if self.dataset is not None:
                            self.record_frame(task, joints, frames, step_target)  # policy action, as lerobot dagger
                    else:
                        holds += 1
                        if now - arrival > args.link_lost_home_s:
                            print(f"link stale for {now - arrival:.1f}s - safety stop")
                            self.end_attempt(None, interventions, phase)
                            return None

            if args.auto_stop_on_release and phase == "auto":
                gripper_pos = float(joints[5])
                if not grasped:
                    if gripper_pos <= args.grasp_close_below:
                        grasp_since = grasp_since or now
                        if now - grasp_since >= args.grasp_min_s:
                            grasped = True
                            print(f"grasp detected (gripper held <= {args.grasp_close_below:.0f} for {args.grasp_min_s:.1f}s)")
                    else:
                        grasp_since = None
                elif release_t is None and gripper_pos >= args.release_open_above:
                    release_t = now  # latched: a later re-close doesn't cancel it
                    print(f"release detected (gripper reopened to {gripper_pos:.0f} after grasp)")
                if release_t is not None and now - release_t >= args.success_settle_s:
                    print("auto stop: grasp-release cycle complete")
                    self.store.record_success(task)
                    self.end_attempt(None, interventions, phase)
                    return None

            reason = self.auto_stop_reason() if phase == "auto" else None
            if reason:
                print(f"auto stop: {reason}")
                self.store.record_success(task)
                self.end_attempt(None, interventions, phase)
                return None

            # Loop timing: a tick whose work exceeds the control period is late (the recorded
            # frame rate drops below control_fps while that happens).
            busy = time.monotonic() - loop_t
            late += busy > 1.0 / args.control_fps
            busy_max = max(busy_max, busy)
            if args.print_every > 0 and tick % args.print_every == 0:
                age = (now - t0) if chunk is not None else float("nan")
                infer = self._infer_ms_log[-1] if self._infer_ms_log else float("nan")
                rec = f"rec={self._rec_frames} " if self.dataset is not None else ""
                hz = args.print_every / (loop_t - print_t) if tick else float("nan")
                print(
                    f"[edge {tick:04d}] {phase} {rec}hz={hz:4.1f} late={late} max={busy_max * 1e3:.0f}ms "
                    f"chunk_age={age:5.2f}s steps={chunks_used} holds={holds} "
                    f"clamps={clamp_hits} drops={self._drops_total} ens={ensemble_n} "
                    f"grip={last_sent[5]:3.0f}/{joints[5]:3.0f} infer={infer:.0f}ms "
                    f"zv={self._zero_metrics[0]:.1f}/{self._zero_metrics[1]:.1f} "
                    f"{self._zero_count}/{args.zero_velocity_consecutive_steps} "
                    f"st={self._stable_metrics[0]:.1f}/{self._stable_metrics[1]:.1f} "
                    f"{self._stable_count}/{args.chunk_stability_consecutive_steps} "
                    f"link={'up' if self.client.connected.is_set() else 'DOWN'}"
                )
                print_t, busy_max = loop_t, 0.0
            tick += 1
            precise_sleep(max(1.0 / args.control_fps - (time.monotonic() - loop_t), 0.0))

    # ---- main ----

    def run(self) -> None:
        args = self.args
        self.connect()
        if args.record_root:
            self.open_dataset()
        app = build_app(self.store, self.app_jpeg)

        @app.post("/command/key")
        def command_key(cmd: dict):
            # Same events as the keyboard ({"key": "pause_resume"} etc.), for buttons or remote tests.
            self.events.put(cmd["key"])
            return {"ok": True}

        start_app_server(app, args.app_host, args.app_port)
        print(f"app backend: http://{args.app_host}:{args.app_port}  (video: /video_feed)")
        self.client.start()
        if self.teleop is not None:
            start_key_listener(self.events.put)
            print(
                "keys: Enter = start attempt, Space = pause/resume policy, Tab = take over/hand back, "
                "S = success, F = failure, Backspace = discard, Esc = quit"
            )

        state = self.store.snapshot()
        consumed_instruction_ts = (state["instruction"] or {}).get("ts")
        consumed_stop_ts = state["stop"].get("ts")
        print("waiting for app command. allowed tasks:")
        for allowed in ACT_ALLOWED_TASKS:
            print(f"  - {allowed}")

        try:
            while True:
                # idle: keep the app camera view alive at ~10fps. A stalled
                # camera must not take the app backend down with it - the
                # operator needs the app to stay up to see something is wrong -
                # so idle only warns and keeps serving the last frame.
                frames = self.read_frames()
                if frames is not None:
                    self.publish_app_frame(frames)

                task, quit_requested = None, False
                while not self.events.empty():
                    event = self.events.get_nowait()
                    if event == "start":
                        task = ACT_ALLOWED_TASKS[0]
                    elif event == "quit":
                        quit_requested = True
                    else:
                        print(f"key {event!r} ignored (no attempt running; Enter starts one)")
                if quit_requested:
                    print("quit requested")
                    break

                state = self.store.snapshot()
                instruction = state["instruction"] or {}
                ts, text = instruction.get("ts"), (instruction.get("text") or "").strip()
                if ts and ts != consumed_instruction_ts:
                    consumed_instruction_ts = ts
                    # Exact task strings pass through untouched (normalize_command lowercases
                    # and only knows the capstone banana tasks).
                    task = text if text in ACT_ALLOWED_TASKS else normalize_command(text)
                    if task not in ACT_ALLOWED_TASKS:
                        print(f"unsupported app command ignored: {text!r}")
                        task = None
                    elif task != text:
                        print(f"command normalized: {text!r} -> {task!r}")
                if task is not None:
                    # A stop pressed while idle must not abort the episode that starts now.
                    consumed_stop_ts = self.store.snapshot()["stop"].get("ts")
                    stop_ts = self.run_episode(task, consumed_stop_ts)
                    if stop_ts:
                        consumed_stop_ts = stop_ts
                    self.move_home("episode finished")
                    if self._pending_save is not None:
                        print("saving the attempt (video encoding) - wait for 'ready'...")
                        self.save_attempt(*self._pending_save)
                        self._pending_save = None
                        while not self.events.empty():  # keys pressed while saving would act unseen
                            self.events.get_nowait()
                    print("ready for next app command" + (" (Enter = next attempt)" if self.teleop else ""))
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("interrupted")
        finally:
            if self.dataset is not None:
                if self._rec_frames:  # an unlabeled attempt was in progress: drop its staged frames
                    self.dataset.clear_episode_buffer()
                self.dataset.finalize()
            if self.teleop is not None and self.teleop.is_connected:
                self.release_leader()
                self.teleop.disconnect()
            self.client.stop()
            if not args.dry_run and self.robot.bus.is_connected:
                self.move_home("shutdown")
                try:
                    self.robot.bus.disable_torque()
                    print("torque disabled")
                except Exception as exc:  # noqa: BLE001
                    print(f"WARNING: failed to disable torque: {exc}")
            if self.robot.bus.is_connected:
                self.robot.bus.disconnect()
            for cam in self.robot.cameras.values():
                try:
                    cam.disconnect()
                except Exception:  # noqa: BLE001
                    pass


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identify", action="store_true", help="Probe cameras, save previews, store the index mapping.")
    parser.add_argument("--identify_max_index", type=int, default=5)
    parser.add_argument("--camera_config", default=os.getenv("EDGE_CAMERA_CONFIG"))
    parser.add_argument("--server_url", default=os.getenv("ACT_SERVER_URL", "ws://127.0.0.1:8765"))
    parser.add_argument("--token", default=os.getenv("POLICY_TOKEN"), help="Shared secret the policy server checks on every request.")
    parser.add_argument("--teleop_port", default=None, help="Leader arm port (e.g. COM5). Enables intervention mode.")
    parser.add_argument("--teleop_id", default="bimanual_leader_right", help="Leader calibration id.")
    parser.add_argument("--record_root", default=None, help="Record every attempt (policy + human frames) into this LeRobot dataset folder; resumes if it exists.")
    parser.add_argument("--record_repo_id", default="kangk/fold_film_onearm_hil")
    parser.add_argument("--video_encoding_batch_size", type=int, default=1, help="1 = encode each attempt while the arm is back home. LeRobot 0.6.1 fails to finalize a partially filled batch (>1), so keep 1.")
    parser.add_argument("--robot_port", default=os.getenv("ROBOT_PORT", "COM3"))
    parser.add_argument("--robot_id", default=os.getenv("ROBOT_ID", "my_follower"))
    parser.add_argument("--calibration_dir", default=os.getenv("LEROBOT_CALIBRATION_DIR"))
    parser.add_argument("--app_host", default="0.0.0.0")
    parser.add_argument("--app_port", type=int, default=8000)
    parser.add_argument("--control_fps", type=int, default=10)
    parser.add_argument("--jpeg_quality", type=int, default=70, help="Policy observation JPEG quality.")
    parser.add_argument("--app_jpeg_quality", type=int, default=70)
    parser.add_argument("--duration_s", type=float, default=30.0)
    parser.add_argument("--consume_cap_steps", type=int, default=50, help="Max chunk steps replayed before holding. Default = full chunk, matching the baseline TemporalEnsembler which votes every step; the link-loss watchdog still homes after link_lost_home_s. Lower to bound how long a stale plan may run.")
    parser.add_argument("--first_chunk_timeout_s", type=float, default=5.0)
    parser.add_argument("--link_lost_home_s", type=float, default=5.0)
    parser.add_argument("--camera_drop_limit", type=int, default=20, help="Consecutive ticks a camera may miss before the episode safety-stops (2.0s at 10Hz); single drops reuse the last frame.")
    parser.add_argument("--episode_start_gripper", type=float, default=40.0, help="Open the gripper to this position at episode start (training episodes begin open; home parks it closed). Negative disables.")
    parser.add_argument("--min_infer_period_s", type=float, default=0.0, help="Throttle observation uploads so several chunk steps replay between inferences (0 = adaptive, as fast as the pipeline allows).")
    parser.add_argument("--max_inflight", type=int, default=2, help="Requests allowed on the wire at once. 2 overlaps upload with server inference (~2x vote rate); 1 restores strict one-in-flight.")
    parser.add_argument("--ensemble_chunks", type=int, default=50, help="Max chunks kept for the wall-clock temporal ensemble (expired ones are pruned anyway). Default keeps every chunk that can still cover the present, matching the baseline TemporalEnsembler; 1 disables.")
    parser.add_argument("--ensemble_coeff", type=float, default=0.01, help="Ensemble rank-decay coefficient w_i=exp(-coeff*i) with rank 0 = oldest. Default matches the checkpoint's own temporal_ensemble_coeff (oldest-heavy, smoother); negative favors NEWER chunks (more reactive).")
    parser.add_argument("--chunk_size_threshold", type=float, default=0.5, help="Send a new observation only when the unexecuted steps of the current plan are <= this fraction of a chunk. 0.5 = LeRobot async default; 1 = send continuously.")
    parser.add_argument("--blend_old_weight", type=float, default=0.3, help="Weight of the current plan where a new chunk overlaps it: w*old + (1-w)*new. 0.3 = LeRobot async default (weighted_average); 0 = newest chunk only (latest_only).")
    parser.add_argument("--max_step_deg", type=float, default=6.0, help="Per-tick clamp for the five arm joints.")
    parser.add_argument("--max_step_gripper", type=float, default=25.0)
    parser.add_argument("--auto_stop_horizon", type=int, default=30)
    parser.add_argument("--auto_stop_on_release", action=argparse.BooleanOptionalAction, default=True, help="Stop when the measured gripper completes a grasp->release cycle (task success for pick-and-place).")
    parser.add_argument("--grasp_close_below", type=float, default=15.0, help="Measured gripper position treated as closed/holding (banana grasp reads ~10, empty close ~2).")
    parser.add_argument("--release_open_above", type=float, default=25.0, help="Measured gripper position treated as released after a grasp (place-open reads ~36).")
    parser.add_argument("--grasp_min_s", type=float, default=1.5, help="How long the gripper must stay closed to count as a grasp (transport takes several seconds; brief dips don't).")
    parser.add_argument("--success_settle_s", type=float, default=3.0, help="Delay between the release event and the stop, so the place finishes cleanly.")
    parser.add_argument("--zero_velocity_consecutive_steps", type=int, default=20, help="Consecutive qualifying chunks before zero-velocity auto-stop (matches main_act's counter).")
    parser.add_argument("--chunk_stability_consecutive_steps", type=int, default=20, help="Consecutive qualifying chunks before stable-chunk auto-stop (matches main_act's counter).")
    parser.add_argument("--zero_velocity_min_duration_s", type=float, default=12.0)
    parser.add_argument("--zero_velocity_max_delta_deg", type=float, default=3.0)
    parser.add_argument("--zero_velocity_mean_delta_deg", type=float, default=0.8)
    parser.add_argument("--chunk_stability_min_duration_s", type=float, default=10.0)
    parser.add_argument("--chunk_stability_max_delta_deg", type=float, default=6.0)
    parser.add_argument("--chunk_stability_mean_delta_deg", type=float, default=1.5)
    parser.add_argument("--print_every", type=int, default=10)
    parser.add_argument("--dry_run", action="store_true", help="Never enable torque or write goals; log only.")
    args = parser.parse_args()

    if args.identify:
        identify_cameras(args)
        return
    EdgeAgent(args).run()


if __name__ == "__main__":
    main()
