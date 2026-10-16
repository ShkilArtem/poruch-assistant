import asyncio
import base64
import io
import json
from PIL import Image
import numpy as np
from assistant.memory import Memory
from assistant.session import Session
from assistant.speech import Segmenter


class Socket:
    def __init__(self): self.events = []
    async def send_json(self, data): self.events.append(data)


def test_memory_update_delete_persistence(tmp_path):
    path = tmp_path / 'memory.db'
    memory = Memory(path)
    memory.put('ім’я', 'Артем', 'Мене звати Артем')
    memory.put('ім’я', 'Тарас', 'Називай мене Тарас')
    assert len(memory.all()) == 1
    assert 'Тарас' in memory.context('ім’я')
    memory.close()
    memory = Memory(path)
    memory.delete(memory.all()[0]['id'])
    assert memory.context('Тарас') == ''
    memory.close()


def test_vad_silence_and_reset():
    vad = Segmenter()
    assert vad.feed(np.zeros(16000, dtype=np.float32)) == []
    assert not vad.active
    vad.reset()
    assert not vad.frames


def test_frame_bounded_and_invalid():
    s = Session(Socket(), None, None, None)
    output = io.BytesIO()
    Image.new('RGB', (64, 48)).save(output, 'JPEG')
    encoded = base64.b64encode(output.getvalue()).decode()
    for _ in range(10): s.frame(encoded)
    assert len(s.frames) == 3
    import pytest
    with pytest.raises(ValueError): s.frame('x' * 350001)
    with pytest.raises(ValueError, match='кадр'):
        s.frame(base64.b64encode(b'not an image').decode())
    assert len(s.frames) == 3


def test_cancel_reply_prevents_late_output():
    async def check():
        s = Session(Socket(), None, None, None)
        async def delayed():
            await asyncio.sleep(10)
            await s.send('reply', text='stale')
        s.task = asyncio.create_task(delayed())
        await s.cancel_reply()
        assert s.task.cancelled()
        assert s.turn == 1
        assert [e['type'] for e in s.ws.events] == ['cancel']
    asyncio.run(check())


def test_extraction_requires_source_evidence(tmp_path):
    class Model:
        async def complete(self, *args, **kwargs):
            return json.dumps({'facts':[{'topic':'ім’я','text':'Артем','evidence':'Мене звати Артем'},
                                       {'topic':'професія','text':'лікар','evidence':'Я лікар'}]})
    async def check():
        m = Memory(tmp_path / 'm.db')
        s = Session(Socket(), Model(), m, None)
        await s.extract('Мене звати Артем')
        assert len(m.all()) == 1
        assert m.all()[0]['topic'] == 'ім’я'
        m.close()
    asyncio.run(check())
