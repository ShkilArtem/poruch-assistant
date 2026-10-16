"""Explicit one-time download; synthesis itself never accesses the network."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ['HF_HOME'] = str(ROOT / 'models' / 'hf-cache')
os.environ.pop('HF_HUB_OFFLINE', None)
from huggingface_hub import snapshot_download
from supertonic.config import get_model_revision

snapshot_download('Supertone/supertonic-3', revision=get_model_revision('supertonic-3'),
                  local_dir=ROOT / 'models' / 'supertonic-3',
                  allow_patterns=['onnx/*', 'voice_styles/*.json', 'LICENSE', 'README.md'])
print('Supertonic 3 ready.', flush=True)
