@echo off
REM One-arm teleoperation with camera view (LeRobot 0.6.1, conda env lerobot312)
REM COM3 follower uses calibration "bimanual_follower_right", COM5 leader uses "bimanual_leader_right" (verified match).
REM Cameras: index 2 = top, index 1 = wrist, index 0 = laptop webcam (not used).
REM Indices can change after replugging or rebooting: re-check with "lerobot-find-cameras opencv".
REM Before starting: put the leader in roughly the same pose as the follower (the follower jumps to the leader pose).
REM Before stopping (Ctrl+C): hold or lower the follower arm. Torque is released on exit and the arm will drop.

call "%USERPROFILE%\anaconda3\Scripts\activate.bat" lerobot312

lerobot-teleoperate ^
  --robot.type=so101_follower ^
  --robot.port=COM3 ^
  --robot.id=bimanual_follower_right ^
  --robot.cameras="{ top: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: MJPG}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, fourcc: MJPG}}" ^
  --teleop.type=so101_leader ^
  --teleop.port=COM5 ^
  --teleop.id=bimanual_leader_right ^
  --display_data=true
