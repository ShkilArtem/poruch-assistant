import asyncio
import json
import threading
import time

from assistant.memory import Memory
from assistant.session import Session
from assistant.streaming import speech_parts


class Socket:
    def __init__(self):
        self.events = []
        self.first_audio = asyncio.Event()

    async def send_json(self, data):
        self.events.append(data)
        if data['type'] == 'audio':
            self.first_audio.set()


class Speech:
    def synthesize(self, text, **kwargs):
        return text.encode()


def test_sentence_and_long_phrase_boundaries():
    assert speech_parts('Бачу на камері червоний квадрат без', first=True) == (['Бачу на камері червоний'], 'квадрат без')
    assert speech_parts('Число 3.14 і незавершена фраза') == ([], 'Число 3.14 і незавершена фраза')
    assert speech_parts('Привіт! Як справи? Хвіст') == (['Привіт!', 'Як справи?'], 'Хвіст')
    text = 'дуже довге речення ' * 40
    parts, tail = speech_parts(text, final=True)
    assert not tail and all(len(p) <= 180 for p in parts)
    assert ' '.join(parts) == text.strip()


def test_audio_arrives_before_model_finishes(tmp_path):
    async def check():
        socket = Socket()

        class Model:
            async def stream(self, messages):
                yield 'Привіт! '
                # Generation cannot finish until actual audio has been delivered.
                await asyncio.wait_for(socket.first_audio.wait(), timeout=3)
                assert not any(e['type'] == 'reply' for e in socket.events)
                yield 'Це продовження.'

        memory = Memory(tmp_path / 'm.db')
        s = Session(socket, Model(), memory, Speech())
        s.active, s.auto_memory = True, False
        await s.reply('Привіт', 0)
        kinds = [e['type'] for e in socket.events]
        assert kinds.index('audio') < kinds.index('reply')
        assert kinds.count('audio') == 2
        assert kinds.count('audio_start') == kinds.count('audio_end') == 1
        memory.close()
    asyncio.run(check())


def test_cancel_during_synthesis_drops_late_audio(tmp_path):
    async def check():
        started, release = threading.Event(), threading.Event()

        class SlowSpeech:
            def synthesize(self, text, **kwargs):
                started.set()
                release.wait(timeout=3)
                return b'old'

        class Model:
            async def stream(self, messages):
                yield 'Стара відповідь. '
                await asyncio.Event().wait()

        memory = Memory(tmp_path / 'm.db')
        s = Session(Socket(), Model(), memory, SlowSpeech())
        s.active, s.auto_memory = True, False
        s.task = asyncio.create_task(s.reply('Привіт', 0))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            await s.cancel_reply()
            release.set()
            await asyncio.sleep(0.05)
            assert not any(e['type'] == 'audio' for e in s.ws.events)
            assert s.ws.events[-1]['type'] == 'cancel'
        finally:
            release.set()
            memory.close()
    asyncio.run(check())


def test_major_events_survive_quiet_mode_and_duplicates_are_suppressed():
    class Model:
        event = {'scene': 'Людина біля столу', 'event': '', 'remark': '',
                 'significance': 'none', 'event_key': '', 'confidence': 1}
        async def complete(self, *args, **kwargs):
            return json.dumps(self.event)

    async def check():
        model = Model()
        s = Session(Socket(), model, None, Speech())
        s.active, s.voice_enabled = True, False
        s.frames.append((time.monotonic(), 'fake-frame'))
        await s.observe_once()
        assert not any(e['type'] == 'reply' for e in s.ws.events)
        model.event = {'scene': 'Людина махає рукою', 'event': 'Рух руки', 'remark': 'Бачу твій жест!',
                       'significance': 'minor', 'event_key': 'person:hand_motion', 'confidence': 0.99}
        s.changed = True
        await s.observe_once()
        assert not any(e['type'] == 'reply' for e in s.ws.events)
        model.event.update(significance='major', event='Людина вийшла', event_key='person:left', remark='Ти вийшов із кадру.')
        s.changed = True
        await s.observe_once()
        assert len([e for e in s.ws.events if e['type'] == 'reply']) == 1
        model.event.update(event='Тебе більше немає у кадрі')
        s.changed = True
        await s.observe_once()
        assert len([e for e in s.ws.events if e['type'] == 'reply']) == 1
        # Another real major transition is allowed immediately, without a global minute-long delay.
        model.event.update(event='Людина повернулася', event_key='person:entered', remark='Ти повернувся!')
        s.changed = True
        await s.observe_once()
        assert len([e for e in s.ws.events if e['type'] == 'reply']) == 2
        s.initiative = False
        model.event.update(event='Змінилася кімната', event_key='scene:changed')
        s.changed = True
        await s.observe_once()
        assert len([e for e in s.ws.events if e['type'] == 'reply']) == 2
    asyncio.run(check())


def test_camera_off_during_analysis_drops_comment():
    async def check():
        class Model:
            async def complete(self, *args, **kwargs):
                await s.control({'type': 'camera_off'})
                return json.dumps({'scene': 'Стара сцена', 'event': 'Рух', 'remark': 'Коментар'})

        s = Session(Socket(), Model(), None, Speech())
        s.active = True
        s.frames.append((time.monotonic(), 'frame'))
        await s.observe_once()
        assert not s.ws.events
    asyncio.run(check())


def test_uncertain_major_event_does_not_use_up_future_notification():
    class Model:
        confidence = 0.4

        async def complete(self, messages, **kwargs):
            assert messages[-1]['images'] == ['previous-frame', 'new-frame']
            return json.dumps({'scene': 'На столі чашка', 'event': 'З’явилася чашка',
                               'remark': '', 'significance': 'major',
                               'event_key': 'object:cup:added', 'confidence': self.confidence})

    async def check():
        model = Model()
        s = Session(Socket(), model, None, None)
        s.active, s.voice_enabled = True, False
        s.observation_reference = (time.monotonic() - 3, 'previous-frame')
        s.frames.append((time.monotonic(), 'new-frame'))
        await s.observe_once()
        assert not any(e['type'] == 'reply' for e in s.ws.events)
        s.observation_reference = (time.monotonic() - 3, 'previous-frame')
        model.confidence = 0.95
        s.changed = True
        await s.observe_once()
        assert len([e for e in s.ws.events if e['type'] == 'reply']) == 1
        assert next(e['text'] for e in s.ws.events if e['type'] == 'reply') == 'З’явилася чашка'
    asyncio.run(check())
