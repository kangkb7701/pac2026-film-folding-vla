@echo off
REM Laptop side: robot + cameras run locally at 30Hz, SmolVLA runs on the lab GPU PC.
REM Start act_policy_server.py on the GPU PC first (see README.md), with the same token.
REM SERVER_URL: GPU PC over Tailscale (the server listens only on its Tailscale IP).
set SERVER_URL=ws://100.81.190.27:8765
REM Shared secret (same value as the server's --token), kept out of git in policy_token.txt.
set /p POLICY_TOKEN=<"%~dp0policy_token.txt"
REM Two arms (bi_so_follower). Ports differ per PC: check with lerobot-find-port and set both here.
REM Calibration ids: bimanual_follower_left / bimanual_follower_right (--robot_id bimanual_follower).
set ROBOT_PORT_LEFT=
set ROBOT_PORT_RIGHT=COM3
REM Camera indices (top, left_wrist, right_wrist) come from edge_cameras.json.
REM After replugging, run "run_edge.bat --identify" to store them again.
REM Add --dry_run to test the link without moving the robot.

call "%USERPROFILE%\anaconda3\Scripts\activate.bat" lerobot312
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

python -m so101_pipeline.runtime.main_edge ^
  --server_url %SERVER_URL% ^
  --robot_id bimanual_follower ^
  --app_host 127.0.0.1 ^
  --control_fps 30 ^
  --duration_s 150 ^
  --episode_start_gripper -1 ^
  --no-auto_stop_on_release ^
  --zero_velocity_consecutive_steps 100000 ^
  --chunk_stability_consecutive_steps 100000 ^
  --ensemble_chunks 1 ^
  --max_inflight 1 ^
  --first_chunk_timeout_s 15 ^
  --camera_drop_limit 60 ^
  --print_every 30 %*
