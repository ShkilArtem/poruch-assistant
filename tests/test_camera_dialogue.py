import asyncio
import time

from assistant.memory import Memory
from assistant.session import Session, camera_question


class Socket:
    def __init__(self):
        self.events = []

    async def send_json(self, data):
        self.events.append(data)


def test_general_camera_questions_are_not_mistaken_for_live_vision_requests():
    assert not camera_question('Як перевірити, що камера справді допомагає асистенту?')
    assert camera_question('Що ти бачиш на камері?')
    assert camera_question('Опиши кімнату')


def test_camera_frame_and_source_are_explicit_in_dialogue_context():
    class Model:
        async def stream(self, messages):
            self.messages = messages
            yield 'Бачу кімнату.'

    async def check():
        memory = Memory(':memory:')
        model = Model()
        s = Session(Socket(), model, memory, None)
        s.active, s.voice_enabled, s.auto_memory = True, False, False
        s.frames.append((time.monotonic(), 'latest-camera-frame'))
        s.scene, s.scene_at = 'Старий опис', time.monotonic()
        await s.reply('Що ти бачиш?', 0)
        assert model.messages[-1]['images'] == ['latest-camera-frame']
        assert 'СВІЖИЙ КАДР КАМЕРИ' in model.messages[0]['content']
        assert 'Кадр має пріоритет' in model.messages[0]['content']
        await s.reply('Розкажеш, що ти боїш.', 0, source='speech')
        assert 'може містити помилки' in model.messages[0]['content']
        assert model.messages[-1]['content'] == 'Розкажеш, що ти боїш.'
        memory.close()
    asyncio.run(check())


def test_camera_is_background_context_for_unrelated_dialogue():
    class Model:
        async def stream(self, messages):
            self.messages = messages
            yield 'Я можу розмовляти й пам’ятати важливі факти.'

    async def check():
        memory = Memory(':memory:')
        model = Model()
        s = Session(Socket(), model, memory, None)
        s.active, s.voice_enabled, s.auto_memory = True, False, False
        s.frames.append((time.monotonic(), 'live-camera'))
        s.scene, s.scene_at = 'Чоловік у навушниках біля кухні', time.monotonic()
        s.history = [{'role': 'user', 'content': 'Що ти бачиш?'},
                     {'role': 'assistant', 'content': 'Бачу чоловіка у навушниках біля кухні.'}]
        await s.reply('Розкажи, що ти можеш зробити.', 0)
        assert model.messages[-1]['images'] == ['live-camera']
        assert 'навушниках' not in str(model.messages)
        assert 'НЕ команда описати' in model.messages[0]['content']
        assert 'Головне — відповісти на зміст' in model.messages[0]['content']
        assert 'не кажи, що вона вимкнена' in model.messages[0]['content']
        await s.reply('Опиши, що ти бачиш на камері', 0)
        assert model.messages[-1]['images'] == ['live-camera']
        memory.close()
    asyncio.run(check())


def test_stop_narration_keeps_major_change_notifications_enabled():
    async def check():
        memory = Memory(':memory:')
        s = Session(Socket(), None, memory, None)
        s.active, s.voice_enabled, s.chatty = True, False, True
        await s.reply('досить мені описувати камеру', 0)
        assert s.initiative and not s.chatty
        assert any(e['type'] == 'preferences' and e['chatty'] is False for e in s.ws.events)
        assert any(e['type'] == 'reply' and 'суттєві' in e['text'] for e in s.ws.events)
        memory.close()
    asyncio.run(check())


def test_stale_or_disabled_camera_is_not_presented_as_live_vision():
    class Model:
        async def stream(self, messages):
            self.messages = messages
            yield 'Увімкни камеру.'

    async def check():
        memory = Memory(':memory:')
        model = Model()
        s = Session(Socket(), model, memory, None)
        s.active, s.voice_enabled, s.auto_memory = True, False, False
        s.frames.append((time.monotonic() - 10, 'stale-frame'))
        s.scene, s.scene_at = 'Попередня кімната', time.monotonic()
        await s.reply('Привіт', 0)
        assert 'images' not in model.messages[-1]
        assert 'Попередня кімната' not in model.messages[0]['content']
        await s.control({'type': 'camera_off'})
        await s.reply('Опиши кімнату', 0)
        reply = next(e for e in reversed(s.ws.events) if e['type'] == 'reply')
        assert 'не отримую свіжого кадру' in reply['text']
        assert 'Попередня кімната' not in reply['text']
        memory.close()
    asyncio.run(check())


def test_recognition_preserves_speech_source():
    class Speech:
        def transcribe(self, audio, **kwargs):
            return 'Що ти бачиш?'

    async def check():
        s = Session(Socket(), None, None, Speech())
        s.active = True
        received = []

        async def capture(text, direct, source):
            received.append((text, direct, source))

        s.text = capture
        await s.recognize(b'', True, 0)
        assert received == [('Що ти бачиш?', True, 'speech')]
    asyncio.run(check())
