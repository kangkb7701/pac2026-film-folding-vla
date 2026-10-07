@echo off
REM Intervention (DAgger) data collection: policy on the GPU server, leader arm (COM5) on this laptop.
REM Every attempt is saved as one episode (policy + human frames) in the same format as the demos;
REM who drove each frame and the outcome go to hil_labels.json in the dataset folder.
REM Keys (global): Enter start, Space pause/resume policy, Tab take over/hand back,
REM                S success, F failure, Backspace discard, Esc quit.
REM Add --dry_run to test without moving either arm.

call "%~dp0run_edge.bat" ^
  --teleop_port COM5 ^
  --teleop_id bimanual_leader_left ^
  --record_root "%USERPROFILE%\lerobot_data\fold_film_onearm_hil" ^
  --record_repo_id kangk/fold_film_onearm_hil ^
  --duration_s 90 %*
