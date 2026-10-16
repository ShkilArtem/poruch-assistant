"""Measure real text generation + Piper delivery, excluding microphone/ASR and browser playback."""
import argparse
import asyncio
import base64
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from assistant.llm import Ollama
from assistant.memory import Memory
from assistant.session import Session
from assistant.speech import Speech


class Socket:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append((time.monotonic(), event))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', default=['qwen3-vl:4b-instruct', 'qwen3.5:9b'])
    parser.add_argument('--runs', type=int, default=2)
    args = parser.parse_args()
    speech = Speech()
    await asyncio.to_thread(speech.synthesize, 'Привіт, я поруч.')
    image = Image.new('RGB', (640, 480), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 100, 240, 290), fill='red')
    draw.ellipse((380, 100, 550, 270), fill='blue')
    output = io.BytesIO()
    image.save(output, 'JPEG')
    frame = base64.b64encode(output.getvalue()).decode()
    report = []
    for model in args.models:
        llm = Ollama(model)
        print('Warming ' + model, flush=True)
        await llm.complete([{'role': 'user', 'content': 'Скажи «привіт».'}], tokens=12)
        for camera, prompt in [(False, 'Я вчуся робити домашнього робота. Як перевірити, що камера справді допомагає асистенту? Дай одну конкретну пораду.'),
                               (True, 'Що ти бачиш на камері? Порівняй дві фігури, не вигадуй нічого поза кадром.')]:
            for run in range(args.runs):
                socket, memory = Socket(), Memory(':memory:')
                session = Session(socket, llm, memory, speech)
                session.active, session.auto_memory = True, False
                if camera:
                    session.frames.append((time.monotonic(), frame))
                started = time.monotonic()
                await session.reply(prompt, 0)
                def at(kind):
                    return next((round(t - started, 3) for t, e in socket.events if e['type'] == kind), None)
                answer = next((e['text'] for t, e in socket.events if e['type'] == 'reply'), '')
                record = {'model': model, 'camera': camera, 'run': run + 1, 'first_text_seconds': at('delta'),
                          'first_audio_seconds': at('audio'), 'full_text_seconds': at('reply'),
                          'answer': answer, 'errors': [e['text'] for t, e in socket.events if e['type'] == 'error']}
                report.append(record)
                print(json.dumps(record, ensure_ascii=False), flush=True)
                memory.close()
    path = ROOT / 'data' / 'model-comparison.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
