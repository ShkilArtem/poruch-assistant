import asyncio
import numpy as np

from assistant.session import Session


class Socket:
    async def send_json(self, event):
        pass


class Segmenter:
    active = False

    def feed(self, audio):
        return [audio]

    def reset(self):
        pass


def test_hands_free_segments_are_direct_requests_and_button_mode_is_background():
    async def check():
        s = Session(Socket(), None, None, None)
        s.active = True
        s.segmenter = Segmenter()
        recognized = []

        async def capture(audio, direct, turn, epoch):
            recognized.append(direct)
            s.asr_busy = False

        s.recognize = capture
        await s.control({'type': 'settings', 'hands_free': True})
        await s.audio(np.zeros(1600, dtype='<f4').tobytes())
        await s.audio_task
        await s.control({'type': 'settings', 'hands_free': False})
        await s.audio(np.zeros(1600, dtype='<f4').tobytes())
        await s.audio_task
        assert recognized == [True, False]
        # Both modes suppress the assistant's own speaker.
        s.playing, s.hands_free = True, True
        await s.audio(np.zeros(1600, dtype='<f4').tobytes())
        assert recognized == [True, False]
        s.barge_in = True
        await s.audio(np.zeros(1600, dtype='<f4').tobytes())
        await s.audio_task
        assert recognized == [True, False, True]
    asyncio.run(check())


def test_turning_hands_free_off_while_transcribing_drops_automatic_reply():
    class Speech:
        def transcribe(self, audio, **kwargs):
            return 'Привіт'

    async def check():
        s = Session(Socket(), None, None, Speech())
        s.active = True
        await s.control({'type': 'settings', 'hands_free': True})
        epoch = s.input_epoch
        await s.control({'type': 'settings', 'hands_free': False})

        async def unexpected(*args, **kwargs):
            raise AssertionError('Stale speech triggered a reply')

        s.text = unexpected
        await s.recognize(b'', True, 0, epoch)
    asyncio.run(check())


def test_microphone_off_clears_unfinished_button_recording():
    async def check():
        s = Session(Socket(), None, None, None)
        s.ptt, s.asr_busy = True, True
        s.ptt_frames = [np.ones(10)]
        await s.control({'type': 'mic_off'})
        assert not s.ptt and not s.ptt_frames and not s.asr_busy
        assert s.input_epoch == 1
    asyncio.run(check())


def test_full_duplex_ignores_recent_own_voice_but_accepts_different_user_speech():
    class Speech:
        phrase = 'Бачу червону чашку на столі'

        def transcribe(self, audio, **kwargs):
            return self.phrase

    async def check():
        import time
        speech = Speech()
        s = Session(Socket(), None, None, speech)
        s.active, s.hands_free, s.barge_in = True, True, True
        s.spoken_fragments.append((time.monotonic(), speech.phrase))
        received = []

        async def capture(text, direct, source):
            received.append((text, direct))

        s.text = capture
        await s.recognize(b'', True, 0, s.input_epoch)
        assert not received
        speech.phrase = 'А тепер поясни, як працює пам’ять'
        await s.recognize(b'', True, 0, s.input_epoch)
        assert received == [(speech.phrase, True)]
    asyncio.run(check())


def test_ptt_waits_for_old_recognizer_cleanup_before_starting_new_one():
    async def check():
        s = Session(Socket(), None, None, None)
        s.active = True
        s.ptt_frames = [np.ones(512)]
        running = asyncio.Event()
        async def old():
            try:
                running.set()
                await asyncio.sleep(60)
            finally:
                s.asr_busy = False
        s.audio_task = asyncio.create_task(old())
        await running.wait()
        observed = []
        async def recognize(*args):
            observed.append((s.asr_busy, args[-1]))
        s.recognize = recognize
        await s.control({'type': 'ptt_end'})
        await s.audio_task
        assert observed == [(True, s.input_epoch)]
    asyncio.run(check())
