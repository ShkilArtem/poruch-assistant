import io
import json
import threading
import wave
from collections import deque
import numpy as np
from .config import ASR_MODEL, ASR_PATHS, VOICE


class Speech:
    def __init__(self, asr_model=ASR_MODEL):
        self.recognizer = None
        if asr_model not in ASR_PATHS:
            raise ValueError('Невідома модель ASR: ' + asr_model)
        self.asr_model = asr_model
        self.loaded_asr_model = None
        self.voice = None
        self.multilingual_voice = None
        self.asr_lock = threading.Lock()
        self.tts_lock = threading.Lock()

    def _load_voice(self):
        if self.voice is None:
            import onnxruntime as ort
            from piper import PiperVoice
            from piper.config import PiperConfig
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            self.voice = PiperVoice(
                config=PiperConfig.from_dict(json.loads(VOICE.with_suffix('.onnx.json').read_text(encoding='utf-8'))),
                session=ort.InferenceSession(str(VOICE), sess_options=options, providers=['CPUExecutionProvider']))

    def warmup(self):
        with self.tts_lock:
            self._load_multilingual_voice()
            self.multilingual_voice.synthesize('Привіт! Я готовий до розмови.', language='uk')

    def _load_multilingual_voice(self):
        if self.multilingual_voice is None:
            from .tts import MultilingualVoice
            self.multilingual_voice = MultilingualVoice()

    def transcribe(self, audio, model=None, language='auto'):
        model = model or self.asr_model
        if model not in ASR_PATHS:
            raise ValueError('Невідома модель ASR')
        if language not in ('auto', 'uk', 'ru', 'fr'):
            raise ValueError('Невідома мова ASR')
        with self.asr_lock:
            if self.recognizer is None or self.loaded_asr_model != model:
                self.recognizer = None
                if model == 'parakeet':
                    import sherpa_onnx
                    path = ASR_PATHS[model]
                    self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                        encoder=str(path / 'encoder.int8.onnx'), decoder=str(path / 'decoder.int8.onnx'),
                        joiner=str(path / 'joiner.int8.onnx'), tokens=str(path / 'tokens.txt'),
                        num_threads=4, provider='cpu', decoding_method='greedy_search',
                        model_type='nemo_transducer')
                else:
                    from faster_whisper import WhisperModel
                    self.recognizer = WhisperModel(str(ASR_PATHS[model]), device='cpu',
                                                  compute_type='int8', cpu_threads=4, local_files_only=True)
                self.loaded_asr_model = model
            if model == 'parakeet':
                stream = self.recognizer.create_stream()
                stream.accept_waveform(16000, np.asarray(audio, dtype=np.float32))
                self.recognizer.decode_stream(stream)
                return stream.result.text.strip()
            segments, _ = self.recognizer.transcribe(
                audio, language=None if language == 'auto' else language, beam_size=5, temperature=0.0, condition_on_previous_text=False,
                vad_filter=True, no_speech_threshold=0.6)
            return ' '.join(s.text.strip() for s in segments if s.avg_logprob > -1.0).strip()

    def synthesize(self, text, backend='supertonic', language='auto', voice='M1'):
        from piper import SynthesisConfig
        with self.tts_lock:
            if backend == 'supertonic':
                self._load_multilingual_voice()
                return self.multilingual_voice.synthesize(text, language=language, voice=voice)
            if backend != 'piper':
                raise ValueError('Невідомий рушій озвучування')
            self._load_voice()
            # This Ukrainian character-based voice has lowercase letters and ASCII apostrophe only.
            text = text.lower().replace('’', "'").replace('ʼ', "'").replace('`', "'")
            text = text.replace('—', '-').replace('–', '-').replace('…', '...')
            text = text.replace('«', '').replace('»', '').replace('“', '').replace('”', '').replace('"', '')
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                self.voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(speaker_id=1))
            return output.getvalue()


class Segmenter:
    """Streaming Silero from faster-whisper's bundled ONNX, 512 samples at 16 kHz."""
    def __init__(self):
        from faster_whisper.vad import get_vad_model
        self.model = get_vad_model()
        self.reset()

    def reset(self):
        self.pending = np.empty(0, dtype=np.float32)
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.pre = deque(maxlen=8)
        self.frames = []
        self.silence = 0
        self.voiced = 0
        self.active = False

    def feed(self, samples):
        self.pending = np.concatenate((self.pending, samples))
        completed = []
        while len(self.pending) >= 512:
            frame, self.pending = self.pending[:512], self.pending[512:]
            # The bundled model callable owns ONNX invocation; recurrent state stays per session.
            probability, self.h, self.c = self.model.session.run(None, {
                'input': np.concatenate((self.context, frame.reshape(1, -1)), axis=1),
                'h': self.h, 'c': self.c})
            self.context = frame[-64:].reshape(1, -1)
            voiced = float(np.asarray(probability).ravel()[0]) >= 0.5
            if voiced and not self.active:
                self.frames = list(self.pre)
                self.active = True
            if self.active:
                self.frames.append(frame.copy())
                self.voiced += int(voiced)
                self.silence = 0 if voiced else self.silence + 1
                if self.silence >= 22 or len(self.frames) >= 625:
                    if self.voiced >= 5:
                        completed.append(np.concatenate(self.frames))
                    self.frames, self.silence, self.voiced, self.active = [], 0, 0, False
                    self.pre.clear()
            else:
                self.pre.append(frame.copy())
        return completed
