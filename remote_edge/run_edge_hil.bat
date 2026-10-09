@echo off
REM Intervention (DAgger) data collection: policy on the GPU server, two leader arms on this laptop.
REM Every attempt is saved as one episode (policy + human frames) in the same format as the demos;
REM who drove each frame and the outcome go to hil_labels.json in the dataset folder.
REM Keys (global): Enter start, Space pause/resume policy, Tab take over/hand back,
REM                S success, F failure, Backspace discard, Esc quit.
REM Add --dry_run to test without moving any arm.
REM Leader ports differ per PC: check with lerobot-find-port and set both here.
REM Calibration ids: bimanual_leader_left / bimanual_leader_right (--teleop_id bimanual_leader).
set TELEOP_PORT_LEFT=
set TELEOP_PORT_RIGHT=COM5

call "%~dp0run_edge.bat" ^
  --teleop_id bimanual_leader ^
  --record_root "%USERPROFILE%\lerobot_data\pac_full_task_hil" ^
  --record_repo_id kangk/pac_full_task_hil ^
  --duration_s 180 %*
