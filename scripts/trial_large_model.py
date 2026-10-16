"""Compare installed models through the actual dialogue pipeline, using isolated memory."""
import argparse
import asyncio
import base64
import io
import json
import re
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
from assistant.schemas import Observation, Extraction


class Socket:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append((time.monotonic(), event))


async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--audio', action='store_true')
    parser.add_argument('--structured', action='store_true')
    parser.add_argument('--output', default='large-model-trial.json')
    args = parser.parse_args()
    image = Image.new('RGB', (640, 480), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 100, 240, 290), fill='red')
    draw.ellipse((380, 100, 550, 270), fill='blue')
    output = io.BytesIO()
    image.save(output, 'JPEG')
    frame = base64.b64encode(output.getvalue()).decode()
    speech = Speech() if args.audio else None
    if speech:
        await asyncio.to_thread(speech.warmup)
    cases = [
        ('switch_to_french', 'Parle-moi en français. Comment vas-tu ?', False,
         [{'role': 'user', 'content': 'Привіт!'}, {'role': 'assistant', 'content': 'Привіт, Артеме!'}]),
        ('stay_in_french', 'Ça va bien, et toi ?', False,
         [{'role': 'user', 'content': 'Parle-moi en français.'}, {'role': 'assistant', 'content': 'Bien sûr, parlons français.'}]),
        ('instruction', 'Відповідай лише числом: я мав 7 яблук, віддав 2 та купив ще 4. Скільки яблук тепер?', False, []),
        ('memory', 'Як мене звати і над чим я працюю?', False, []),
        ('camera', 'Опиши дві фігури на кадрі: їхні кольори та розташування. Нічого не вигадуй.', True, []),
    ]
    report = []
    path = ROOT / 'data' / args.output
    for model in args.models:
        llm = Ollama(model)
        print('Loading: ' + model, flush=True)
        started = time.monotonic()
        try:
            await llm.complete([{'role': 'user', 'content': 'Скажи привіт.'}], tokens=16)
        except Exception as exc:
            report.append(dict(model=model, error=str(exc), phase='load'))
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(str(exc), flush=True)
            continue
        print(f'Load + first query: {time.monotonic()-started:.2f}s', flush=True)
        for name, prompt, camera, history in cases:
            socket, memory = Socket(), Memory(':memory:')
            memory.put('ім’я', 'Артем', 'Тестовий профіль', kind='profile')
            memory.put('проєкт', 'Домашній робот', 'Тестовий профіль', kind='profile')
            session = Session(socket, llm, memory, speech)
            session.active, session.auto_memory, session.voice_enabled = True, False, args.audio
            session.history = history
            if camera:
                session.frames.append((time.monotonic(), frame))
            started = time.monotonic()
            await session.reply(prompt, 0)
            def at(kind):
                return next((round(t-started, 3) for t, event in socket.events if event['type'] == kind), None)
            answer = next((event['text'] for _, event in socket.events if event['type'] == 'reply'), '')
            passed = (bool(answer) and not re.search('[А-Яа-яІіЇїЄєҐґ]', answer)) if 'french' in name else (
                answer.strip() == '9' if name == 'instruction' else None)
            row = dict(model=model, case=name, answer=answer, simple_check=passed,
                       first_text_seconds=at('delta'), first_audio_seconds=at('audio'), full_text_seconds=at('reply'),
                       errors=[event['text'] for _, event in socket.events if event['type'] == 'error'])
            report.append(row)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            memory.close()
        if args.structured:
            for name, schema, prompt in [
                ('observation_json', Observation, 'Опиши геометричні фігури на кадрі. Це перший кадр: significance=none, event і remark порожні, confidence=0.9.'),
                ('memory_json', Extraction, 'Виділи факт із повідомлення «Мене звати Артем». evidence має бути точною цитатою «Мене звати Артем».')]:
                started = time.monotonic()
                try:
                    message = dict(role='user', content=prompt)
                    if name == 'observation_json':
                        message['images'] = [frame]
                    answer = await llm.complete([message], schema=schema.model_json_schema(), tokens=300)
                    value = schema.model_validate_json(answer)
                    row = dict(model=model, case=name, seconds=round(time.monotonic()-started, 3), value=value.model_dump(), valid_json=True)
                except Exception as exc:
                    row = dict(model=model, case=name, error=str(exc), valid_json=False)
                report.append(row)
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
