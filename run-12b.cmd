@echo off
setlocal
cd /d "%~dp0"
set "ASSISTANT_MODEL=hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0"
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\launch.py"
endlocal
