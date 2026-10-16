import asyncio
import time
import numpy as np

from assistant.asr_check import word_error_rate
from assistant.session import Session
from assistant.speech import Speech


class Socket:
    async def send_json(self, data):
        pass


def test_button_recording_keeps_first_samples_despite_echo_guard():
    async def check():
        s = Session(Socket(), None, None, None)
        s.active = True
        s.quiet_until = time.monotonic() + 0.35
        await s.control({'type': 'ptt_start'})
        samples = np.linspace(0, 1, 512, dtype='<f4')
        await s.audio(samples.tobytes())
        assert np.array_equal(s.ptt_frames[0], samples)
        assert s.quiet_until == 0
        await s.control({'type': 'playing', 'value': False, 'turn': s.turn})
        await s.audio(samples.tobytes())
        assert len(s.ptt_frames) == 2
    asyncio.run(check())


def test_recognition_uses_beam_five_without_prompt_injection(monkeypatch):
    import faster_whisper
    calls = []

    class Recognizer:
        def __init__(self, path, **kwargs):
            calls.append(('load', path, kwargs))

        def transcribe(self, audio, **kwargs):
            calls.append(('transcribe', kwargs))
            return [], None

    monkeypatch.setattr(faster_whisper, 'WhisperModel', Recognizer)
    speech = Speech(asr_model='turbo')
    speech.transcribe(np.zeros(1600, dtype=np.float32))
    assert calls[0][1].endswith('whisper-turbo')
    assert calls[0][2]['device'] == 'cpu'
    options = calls[1][1]
    assert options['language'] is None and options['beam_size'] == 5
    assert options['temperature'] == 0 and 'initial_prompt' not in options


def test_word_error_rate_normalizes_case_punctuation_and_apostrophes():
    assert word_error_rate('Моя пам’ять.', "МОЯ пам'ять!") == 0
    assert word_error_rate('Бачу синю чашку', 'Бачу сіру чашку') == 0.3333
    assert word_error_rate('Два слова', '') == 1


def test_parakeet_uses_local_cpu_transducer_and_fresh_stream(monkeypatch):
    import sherpa_onnx
    from types import SimpleNamespace
    calls, streams = [], []

    class Recognizer:
        def create_stream(self):
            stream = SimpleNamespace(result=SimpleNamespace(text=' Bonjour. '))
            stream.accept_waveform = lambda rate, audio: calls.append((rate, audio.dtype))
            streams.append(stream)
            return stream

        def decode_stream(self, stream):
            assert stream in streams

    def load(**kwargs):
        calls.append(kwargs)
        return Recognizer()

    monkeypatch.setattr(sherpa_onnx.OfflineRecognizer, 'from_transducer', load)
    speech = Speech(asr_model='parakeet')
    for _ in range(2):
        assert speech.transcribe(np.zeros(16000), language='fr') == 'Bonjour.'
    assert calls[0]['provider'] == 'cpu'
    assert calls[0]['encoder'].endswith('encoder.int8.onnx')
    assert len(streams) == 2 and streams[0] is not streams[1]
    assert calls[1] == (16000, np.dtype('float32'))


def test_asr_selection_is_used_for_next_voice_input():
    class Recognizer:
        def transcribe(self, audio, model, language):
            self.model = model
            self.language = language
            return ''

    async def check():
        recognizer = Recognizer()
        s = Session(Socket(), None, None, recognizer)
        s.active = True
        await s.control({'type': 'settings', 'asr_model': 'small'})
        await s.recognize(b'', False, 0)
        assert recognizer.model == 'small'
        await s.control({'type': 'settings', 'asr_model': 'turbo'})
        await s.recognize(b'', False, 0)
        assert recognizer.model == 'turbo'
        await s.control({'type': 'settings', 'asr_model': 'parakeet', 'asr_language': 'fr'})
        await s.recognize(b'', False, 0)
        assert recognizer.model == 'parakeet' and recognizer.language == 'fr'
    asyncio.run(check())
