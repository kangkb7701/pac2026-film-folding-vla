@echo off
REM Stops the current episode; the arm returns to the home pose.
curl -s -X POST http://127.0.0.1:8000/command/stop
echo.
