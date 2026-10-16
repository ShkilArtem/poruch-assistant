"""Explicit network setup. Runtime never downloads models."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['HF_HOME'] = str(ROOT / 'models' / 'hf-cache')
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from huggingface_hub import snapshot_download, hf_hub_download

target = ROOT / 'models'
target.mkdir(exist_ok=True)
print('Downloading Whisper small...', flush=True)
snapshot_download('Systran/faster-whisper-small', local_dir=target / 'whisper-small',
                  allow_patterns=['*.json', '*.bin', '*.txt'])
print('Downloading Ukrainian voice...', flush=True)
base = 'uk/uk_UA/ukrainian_tts/medium/'
for filename in ['uk_UA-ukrainian_tts-medium.onnx', 'uk_UA-ukrainian_tts-medium.onnx.json', 'MODEL_CARD']:
    cached = hf_hub_download('rhasspy/piper-voices', base + filename)
    import shutil
    shutil.copyfile(cached, target / filename)
print('Models ready.', flush=True)
