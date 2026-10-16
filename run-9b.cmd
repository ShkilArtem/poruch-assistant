@echo off
setlocal
cd /d "%~dp0"
set "ASSISTANT_MODEL=qwen3.5:9b"
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\launch.py"
endlocal
