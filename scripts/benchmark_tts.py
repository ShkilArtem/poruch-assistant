"""Measure local synthesis; export samples for listening."""
import io
import json
import sys
import time
import wave
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from assistant.speech import Speech
sys.stdout.reconfigure(encoding='utf-8')

speech = Speech()
started = time.monotonic()
speech.warmup()
print(f'Load and warmup: {time.monotonic()-started:.3f}s', flush=True)
report = []
folder = ROOT / 'data' / 'voice-samples'
folder.mkdir(exist_ok=True)
for language, text in [('uk', 'Привіт! Я можу говорити українською. Чим займемося сьогодні?'),
                       ('ru', 'Привет! Теперь я могу говорить по-русски. Давай обсудим твою идею.'),
                       ('fr', 'Bonjour ! Je peux parler français. Que veux-tu faire aujourd’hui ?'),
                       ('en', 'Hello! I can speak English. What would you like to discuss?')]:
    for mode in (language, 'auto'):
        started = time.monotonic()
        audio = speech.synthesize(text, language=mode)
        elapsed = time.monotonic() - started
        with wave.open(io.BytesIO(audio)) as wav:
            duration = wav.getnframes() / wav.getframerate()
        (folder / f'{language}-{mode}.wav').write_bytes(audio)
        result = dict(language=language, mode=mode, text=text, seconds=round(elapsed, 3), audio_seconds=round(duration, 3))
        report.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
(ROOT / 'data' / 'tts-benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
started = time.monotonic()
speech.synthesize('Привіт! Я тебе слухаю.', language='uk')
print(f'First short chunk: {time.monotonic()-started:.3f}s', flush=True)
