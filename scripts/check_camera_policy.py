"""Real-model regression check for ordinary chat, visual questions and scene transitions."""
import asyncio
import argparse
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


def image(extra=False):
    picture = Image.new('RGB', (480, 320), 'white')
    draw = ImageDraw.Draw(picture)
    draw.rectangle((20, 80, 180, 240), fill='red')
    if extra:
        draw.ellipse((240, 30, 460, 250), fill='blue')
    buffer = io.BytesIO()
    picture.save(buffer, 'JPEG')
    return base64.b64encode(buffer.getvalue()).decode()


class Model(Ollama):
    def __init__(self):
        super().__init__()
        self.observations = []

    async def complete(self, *args, **kwargs):
        text = await super().complete(*args, **kwargs)
        self.observations.append(json.loads(text))
        return text


class Socket:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append(event)
        if event['type'] == 'error':
            raise RuntimeError(event['text'])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dialogue-only', action='store_true')
    args = parser.parse_args()
    model, memory, socket = Model(), Memory(':memory:'), Socket()
    session = Session(socket, model, memory, None)
    session.active, session.voice_enabled, session.auto_memory = True, False, False
    for frame in ([] if args.dialogue_only else [image(), image(True), image(True)]):
        session.frames.append((time.monotonic(), frame))
        session.changed = True
        await session.observe_once()
    proactive = [e['text'] for e in socket.events if e['type'] == 'reply']
    answers = {}
    for query in ['Розкажи, що ти можеш зробити.', 'Що ти бачиш на камері?',
                  'У мене було 7 яблук. Я віддав 2 і купив ще 4. Скільки стало? Поясни одним реченням.']:
        session.frames.append((time.monotonic(), image(True)))
        await session.reply(query, 0)
        answers[query] = [e['text'] for e in socket.events if e['type'] == 'reply'][-1]
    report = {'observations': model.observations, 'spontaneous_comments': proactive, 'answers': answers}
    (ROOT / 'data' / 'camera-policy-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    memory.close()


if __name__ == '__main__':
    asyncio.run(main())
