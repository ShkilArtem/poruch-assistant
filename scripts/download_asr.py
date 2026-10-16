"""Explicit ASR model download; the assistant itself stays offline."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ['HF_HOME'] = str(ROOT / 'models' / 'hf-cache')
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ.pop('HF_HUB_OFFLINE', None)
from faster_whisper.utils import download_model

print('Downloading multilingual Whisper large-v3-turbo...', flush=True)
download_model('turbo', output_dir=str(ROOT / 'models' / 'whisper-turbo'))
print('Whisper turbo ready.', flush=True)
