@echo off
REM Starts one episode on the running edge agent (run_edge.bat).
curl -s -X POST http://127.0.0.1:8000/command/voice -H "Content-Type: application/json" -d "{\"text\":\"Fold the plastic film in half.\"}"
echo.
