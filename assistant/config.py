import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MODELS = ROOT / 'models'
MODEL = os.getenv('ASSISTANT_MODEL', 'hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0')
OLLAMA = os.getenv('ASSISTANT_OLLAMA', 'http://127.0.0.1:11435').rstrip('/')
VOICE = MODELS / 'uk_UA-ukrainian_tts-medium.onnx'
TTS_PATH = MODELS / 'supertonic-3'
TTS_LANGUAGES = ('auto', 'uk', 'ru', 'fr', 'en', 'de', 'es', 'it', 'pl', 'pt', 'ja', 'ko',
                 'ar', 'bg', 'cs', 'da', 'el', 'et', 'fi', 'hi', 'hr', 'hu', 'id', 'lt',
                 'lv', 'nl', 'ro', 'sk', 'sl', 'sv', 'tr', 'vi')


def tts_ready():
    return all((TTS_PATH / name).is_file() for name in (
        'onnx/tts.json', 'onnx/unicode_indexer.json', 'onnx/duration_predictor.onnx',
        'onnx/text_encoder.onnx', 'onnx/vector_estimator.onnx', 'onnx/vocoder.onnx', 'voice_styles/M1.json'))


ASR_MODEL = os.getenv('ASSISTANT_ASR_MODEL', 'parakeet')
ASR_PATHS = {'small': MODELS / 'whisper-small', 'turbo': MODELS / 'whisper-turbo',
             'parakeet': MODELS / 'parakeet-v3'}


def asr_ready(model, paths=None):
    path = (ASR_PATHS if paths is None else paths)[model]
    files = ('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt') if model == 'parakeet' else ('model.bin',)
    return all((path / filename).is_file() for filename in files)
