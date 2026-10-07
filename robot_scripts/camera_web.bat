@echo off
REM Browser viewer for the robot cameras: open http://127.0.0.1:8000
REM   camera_web.bat          both cameras
REM   camera_web.bat top      only the top camera
REM   camera_web.bat wrist    only the wrist camera
REM Stop with Ctrl+C before teleoperating or recording, since it holds the cameras.
call C:\Users\kangk\anaconda3\Scripts\activate.bat lerobot312
python "%~dp0camera_web.py" %*
