"""Start the project's CUDA Ollama and the local UI without changing system settings."""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:11435'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ready():
    try:
        with HTTP.open(URL + '/api/version', timeout=1) as response:
            return bool(json.load(response).get('version'))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main():
    os.chdir(ROOT)
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE='1', ASSISTANT_OLLAMA=URL)
    if not ready():
        executable = shutil.which('ollama')
        if not executable:
            raise RuntimeError('Ollama not found. Install Ollama and download the assistant model first.')
        ollama_env = env.copy()
        ollama_env.update(OLLAMA_HOST='127.0.0.1:11435', OLLAMA_LLM_LIBRARY='cuda_v12',
                          OLLAMA_NUM_PARALLEL='1', OLLAMA_NO_CLOUD='1')
        with (ROOT / 'ollama-gpu.stdout.log').open('ab') as stdout, (ROOT / 'ollama-gpu.stderr.log').open('ab') as stderr:
            process = subprocess.Popen([executable, 'serve'], env=ollama_env, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(60):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError('Project Ollama exited. See ollama-gpu.stderr.log.')
            time.sleep(0.5)
        else:
            raise RuntimeError('Project Ollama did not start. See ollama-gpu.stderr.log.')
    print('Local assistant: http://127.0.0.1:8765 | Ollama CUDA: ' + URL, flush=True)
    result = subprocess.run([sys.executable, '-m', 'uvicorn', 'assistant.main:app', '--host', '127.0.0.1',
                             '--port', '8765', '--ws-max-size', '400000'], env=env)
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
