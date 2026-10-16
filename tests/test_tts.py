import io
import wave
import numpy as np
from assistant.tts import MultilingualVoice, spoken_text, text_language


def test_spoken_text_keeps_languages_case_and_punctuation():
    assert spoken_text('## **Bonjour**, Артеме! [OpenAI](https://openai.com)') == 'Bonjour, Артеме! OpenAI'
    assert spoken_text('<laugh>Привіт! `Bonjour` — déjà vu.') == 'Привіт! Bonjour — déjà vu.'


def test_multilingual_voice_is_offline_keeps_text_and_returns_pcm(monkeypatch):
    import supertonic
    calls = []

    class Engine:
        sample_rate = 44100

        def __init__(self, **kwargs):
            calls.append(kwargs)

        def get_voice_style(self, name):
            return name

        def synthesize(self, text, **kwargs):
            calls.append((text, kwargs))
            return np.array([[0.25, -0.25, 2.0]], dtype=np.float32), np.array([0.1])

    monkeypatch.setattr(supertonic, 'TTS', Engine)
    voice = MultilingualVoice()
    audio = voice.synthesize('**Bonjour**, déjà vu!', language='fr', voice='M3')
    assert calls[0]['auto_download'] is False
    assert calls[0]['intra_op_num_threads'] == 4
    assert calls[1][0] == 'Bonjour, déjà vu!'
    assert calls[1][1]['lang'] == 'fr' and calls[1][1]['voice_style'] == 'M3'
    with wave.open(io.BytesIO(audio)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 44100)
        assert np.frombuffer(wav.readframes(3), dtype='<i2').tolist() == [8191, -8191, 32767]
    voice.synthesize('Привіт! Я тебе слухаю.', language='auto')
    assert calls[-1][1]['lang'] == 'uk'


def test_language_routing_uses_text_and_keeps_unknown_fallback():
    assert text_language('Bonjour ! Je peux parler français.') == 'fr'
    assert text_language('Hello! I can speak English.') == 'en'
    assert text_language('Привет! Теперь я могу говорить по-русски.') == 'ru'
    assert text_language('42') == 'na'


def test_voice_selection_validated_and_forwarded_per_session():
    import asyncio
    from assistant.session import Session

    class Socket:
        async def send_json(self, data):
            pass

    class Speech:
        def synthesize(self, text, **kwargs):
            self.options = kwargs
            return b'wav'

    async def check():
        speech = Speech()
        session = Session(Socket(), None, None, speech)
        session.active = True
        await session.control({'type': 'settings', 'tts_voice': 'M4', 'tts_language': 'ru'})
        await session.speak('Привет!', 0)
        assert speech.options == dict(backend='supertonic', language='ru', voice='M4')
        try:
            await session.control({'type': 'settings', 'tts_language': 'bad'})
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid language accepted')
    asyncio.run(check())
