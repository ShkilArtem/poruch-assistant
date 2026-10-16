"""Local multilingual synthesis and conservative text cleanup."""
import io
import re
import wave
from functools import lru_cache
import numpy as np
from .config import TTS_PATH, TTS_LANGUAGES


@lru_cache(maxsize=1)
def language_identifier():
    from langid.langid import LanguageIdentifier, model
    identifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
    identifier.set_languages([lang for lang in TTS_LANGUAGES if lang != 'auto'])
    return identifier


def text_language(text):
    if len(re.findall(r'[^\W\d_]', text)) < 3:
        return 'na'
    if re.search('[іїєґІЇЄҐ]', text):
        return 'uk'
    language, confidence = language_identifier().classify(text)
    return language if confidence >= 0.6 else 'na'


def spoken_text(text):
    text = re.sub(r'```[^\n]*\n([\s\S]*?)```', r'\1', text)
    text = re.sub(r'!?\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'(?m)^\s*(?:#{1,6}\s+|[-*+]\s+)', '', text)
    text = re.sub(r'[*_`~]', '', text)
    # Model expression tags are not user speech; do not execute generated markup.
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()


class MultilingualVoice:
    def __init__(self):
        from supertonic import TTS
        language_identifier()
        self.engine = TTS(model='supertonic-3', model_dir=TTS_PATH, auto_download=False,
                          intra_op_num_threads=4, inter_op_num_threads=1)
        self.styles = {name: self.engine.get_voice_style(name) for name in ('M1', 'M2', 'M3', 'M4', 'M5')}

    def synthesize(self, text, language='auto', voice='M1'):
        if language not in TTS_LANGUAGES or voice not in self.styles:
            raise ValueError('Невідомий голос або мова озвучування')
        text = spoken_text(text)
        output = io.BytesIO()
        if text:
            samples, _ = self.engine.synthesize(text, voice_style=self.styles[voice],
                                                lang=text_language(text) if language == 'auto' else language,
                                                total_steps=8, speed=1.0)
        else:
            samples = np.zeros(int(self.engine.sample_rate * 0.04), dtype=np.float32)
        pcm = (np.clip(np.asarray(samples).reshape(-1), -1, 1) * 32767).astype('<i2')
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.engine.sample_rate)
            wav.writeframes(pcm.tobytes())
        return output.getvalue()
