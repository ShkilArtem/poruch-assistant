"""Exercise the actual dialogue prompt with a synthetic camera image; no private media."""
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


class Socket:
    def __init__(self):
        self.replies = []

    async def send_json(self, event):
        if event['type'] == 'error':
            raise RuntimeError(event['text'])
        if event['type'] == 'reply':
            self.replies.append(event['text'])


async def main():
    image = Image.new('RGB', (480, 320), 'white')
    ImageDraw.Draw(image).rectangle((130, 50, 350, 270), fill='red')
    output = io.BytesIO()
    image.save(output, 'JPEG')
    memory = Memory(':memory:')
    socket = Socket()
    session = Session(socket, Ollama(), memory, None)
    session.active, session.voice_enabled, session.auto_memory = True, False, False
    session.frames.append((time.monotonic(), base64.b64encode(output.getvalue()).decode()))
    await session.reply('Опиши, що ти бачиш на камері.', 0)
    await session.control({'type': 'camera_off'})
    await session.reply('А що ти бачиш зараз на камері?', 0)
    report = {'with_frame': socket.replies[0], 'camera_off': socket.replies[1]}
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data' / 'camera-dialogue-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    memory.close()


if __name__ == '__main__':
    asyncio.run(main())
