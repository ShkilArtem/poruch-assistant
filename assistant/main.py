import json
import asyncio
import logging
import mimetypes
import base64
import binascii
import numpy as np
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import ROOT, DATA, MODELS, VOICE, ASR_PATHS, asr_ready, tts_ready
from .llm import Ollama
from .memory import Memory
from .speech import Speech, Segmenter
from .session import Session
from .schemas import FactInput, ProfileInput, ASRComparison
from .asr_check import compare

logging.basicConfig(level=logging.INFO)
llm, speech = Ollama(), Speech()
current = None
memory = None
asr_check_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    global memory
    DATA.mkdir(exist_ok=True)
    memory = Memory(DATA / 'memory.sqlite3')
    try:
        await asyncio.to_thread(Segmenter)
    except Exception:
        logging.exception('VAD warmup failed; text dialogue is still available')
    if tts_ready():
        try:
            await asyncio.to_thread(speech.warmup)
        except Exception:
            logging.exception('Voice warmup failed; text dialogue is still available')
    yield
    memory.close()


app = FastAPI(lifespan=lifespan)
# Windows registry may classify .mjs as text/plain; browsers reject module imports.
mimetypes.add_type('text/javascript', '.mjs')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


def same_origin(origin, host):
    return origin in {f'http://{host}', f'https://{host}'}


@app.middleware('http')
async def local_only(request: Request, call_next):
    if request.method not in ('GET', 'HEAD'):
        if not same_origin(request.headers.get('origin'), request.headers.get('host')):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Origin rejected'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/')
async def index():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.get('/asr-test')
async def asr_test():
    return FileResponse(ROOT / 'static' / 'asr-test.html')


@app.post('/api/asr/compare')
async def asr_compare(item: ASRComparison):
    if current is not None or asr_check_lock.locked():
        raise HTTPException(409, 'Зупини розмовну сесію перед порівнянням; дочекайся завершення поточного тесту.')
    models = [model for model in ASR_PATHS if asr_ready(model, ASR_PATHS)]
    if not models:
        raise HTTPException(503, 'Спочатку завантаж моделі розпізнавання.')
    try:
        data = base64.b64decode(item.audio, validate=True)
        if not data or len(data) % 4 or len(data) > 16000 * 15 * 4:
            raise ValueError()
        audio = np.frombuffer(data, dtype='<f4').copy()
        if not np.isfinite(audio).all() or not item.reference.strip():
            raise ValueError()
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'Потрібен коректний аудіозапис до 15 секунд і текст прочитаної фрази.') from None
    async with asr_check_lock:
        return {'reference': item.reference, 'language': item.language,
                'results': await asyncio.to_thread(compare, speech, audio, item.reference, models=models, language=item.language)}


@app.get('/api/health')
async def health():
    asr_model = current.asr_model if current else speech.asr_model
    return {'ollama': await llm.health(), 'whisper': asr_ready(asr_model),
            'asr_model': asr_model,
            'voice': tts_ready(), 'tts_model': 'supertonic-3', 'local_only': True}


@app.get('/api/memory')
async def memories():
    return memory.all()


@app.post('/api/memory')
async def add_memory(fact: FactInput):
    if current:
        await current.cancel_reply()
    memory.put(fact.topic, fact.text, 'Вручну користувачем', kind=fact.kind, active=fact.active)
    if current:
        current.reset_memory_context()
    return memory.all()


@app.delete('/api/memory/{fact_id}')
async def delete_memory(fact_id: int):
    if current:
        await current.cancel_reply()
    memory.delete(fact_id)
    if current:
        current.reset_memory_context()
    return memory.all()


@app.get('/api/summaries')
async def summaries():
    return memory.summaries()


@app.delete('/api/summaries/{summary_id}')
async def delete_summary(summary_id: int):
    if current:
        await current.cancel_reply()
    memory.delete_summary(summary_id)
    if current:
        current.reset_memory_context()
    return memory.summaries()


@app.post('/api/profile')
async def profile(profile: ProfileInput):
    if current:
        await current.cancel_reply()
    for topic, value in [('ім’я', profile.name), ('звертання', profile.address),
                         ('кімната', profile.room), ('інтереси', profile.interests)]:
        if value:
            memory.put(topic, value, 'Початкове знайомство: введено користувачем', kind='profile')
    if current:
        current.reset_memory_context()
    return memory.all()


@app.websocket('/ws')
async def socket(ws: WebSocket):
    global current
    if not same_origin(ws.headers.get('origin'), ws.headers.get('host')):
        await ws.close(code=1008)
        return
    await ws.accept()
    if current is not None or asr_check_lock.locked():
        await ws.send_json({'type': 'error', 'text': 'Вже відкрита інша сесія. Зупини її перед новою.'})
        await ws.close(code=1008)
        return
    session = Session(ws, llm, memory, speech)
    current = session
    try:
        await session.start()
        while True:
            message = await ws.receive()
            if message['type'] == 'websocket.disconnect':
                break
            try:
                if message.get('bytes') is not None:
                    await session.audio(message['bytes'])
                else:
                    raw = message.get('text', '')
                    if len(raw) > 360000:
                        raise ValueError('Повідомлення завелике')
                    item = json.loads(raw)
                    if not isinstance(item, dict):
                        raise ValueError('Очікується об’єкт')
                    if item.get('type') == 'stop':
                        break
                    await session.control(item)
            except (ValueError, KeyError, TypeError) as exc:
                await session.send('error', text=str(exc))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await session.stop()
        except (RuntimeError, WebSocketDisconnect):
            pass
        current = None
