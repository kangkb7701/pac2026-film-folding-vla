@echo off
REM Episode labeler: label_tool.bat <dataset folder>, then open http://127.0.0.1:8010
REM Example: label_tool.bat C:\Users\kangk\lerobot_data\fold_film_onearm_demo
call "%USERPROFILE%\anaconda3\Scripts\activate.bat" lerobot312
python "%~dp0label_tool.py" %*
