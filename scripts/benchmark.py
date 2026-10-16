import asyncio
import base64
import io
import json
import os
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
from PIL import Image, ImageDraw
import numpy as np
from assistant.llm import Ollama
from assistant.speech import Speech, Segmenter
from assistant.schemas import Extraction


async def main():
    (ROOT / 'data').mkdir(exist_ok=True)
    report = {}
    llm = Ollama()
    report['health'] = await llm.health()
    t = time.monotonic()
    vad = Segmenter()
    report['vad_silence_segments'] = len(vad.feed(np.zeros(16000, dtype=np.float32)))
    report['vad_load_seconds'] = round(time.monotonic() - t, 2)
    speech = Speech()
    phrase = 'Привіт, Артеме. Я твій домашній асистент. Можу слухати, бачити та запам’ятовувати.'
    t = time.monotonic()
    wav = speech.synthesize(phrase)
    (ROOT / 'data' / 'voice-sample.wav').write_bytes(wav)
    report['tts_seconds'] = round(time.monotonic() - t, 2)
    print('TTS', report['tts_seconds'], flush=True)
    # Decode the generated voice using Whisper's audio decoder (resamples to 16 kHz).
    from faster_whisper.audio import decode_audio
    samples = decode_audio(io.BytesIO(wav), sampling_rate=16000)
    t = time.monotonic()
    report['transcript'] = speech.transcribe(samples)
    report['asr_seconds'] = round(time.monotonic() - t, 2)
    print('ASR', report['transcript'], flush=True)
    report['vad_speech_segments'] = len(vad.feed(np.concatenate((samples, np.zeros(16000, dtype=np.float32)))))
    t = time.monotonic()
    report['reply'] = await llm.complete([{'role': 'user', 'content': 'Привіт! Представся одним реченням українською як домашній асистент.'}], tokens=100)
    report['llm_cold_seconds'] = round(time.monotonic() - t, 2)
    print('LLM', report['reply'], flush=True)
    image = Image.new('RGB', (480, 320), 'white')
    ImageDraw.Draw(image).rectangle((100, 60, 300, 260), fill='red')
    output = io.BytesIO(); image.save(output, 'JPEG')
    t = time.monotonic()
    report['vision'] = await llm.complete([{'role': 'user', 'content': 'Яка фігура і колір на зображенні? Одне речення українською.', 'images': [base64.b64encode(output.getvalue()).decode()]}], tokens=80)
    report['vision_seconds'] = round(time.monotonic() - t, 2)
    report['extraction'] = await llm.complete([
        {'role': 'system', 'content': 'Extract explicit facts into facts. topic and text Ukrainian. evidence exact quote.'},
        {'role': 'user', 'content': 'Мене звати Артем.'}], schema=Extraction.model_json_schema())
    Extraction.model_validate_json(report['extraction'])
    (ROOT / 'data' / 'benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
