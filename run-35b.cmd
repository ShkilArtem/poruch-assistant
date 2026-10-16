@echo off
setlocal
cd /d "%~dp0"
set "ASSISTANT_MODEL=hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS"
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\launch.py"
endlocal
