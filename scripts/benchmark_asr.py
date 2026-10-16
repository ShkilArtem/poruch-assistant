"""Compare ASR on supplied recordings, or explicitly labelled synthetic smoke samples."""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from faster_whisper.audio import decode_audio
from assistant.asr_check import compare
from assistant.speech import Speech


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, help='JSON list of {audio, reference}; audio paths relative to the manifest')
    parser.add_argument('--language', choices=['auto','uk','ru','fr'], default='auto')
    args = parser.parse_args()
    speech = Speech()
    if args.manifest:
        cases = [(entry['reference'], decode_audio(str(args.manifest.parent / entry['audio']), sampling_rate=16000))
                 for entry in json.loads(args.manifest.read_text(encoding='utf-8'))]
        origin = 'user-provided recordings'
    else:
        phrases = ['Я не питаю, чого ти боїшся. Я питаю, що ти бачиш.',
                   'Завтра о пів на восьму потрібно вийти з дому.',
                   'На столі лежать навушники, книжка та синя чашка.']
        cases = [(phrase, decode_audio(io.BytesIO(speech.synthesize(phrase, backend='piper')), sampling_rate=16000)) for phrase in phrases]
        origin = 'synthetic Piper voice; not evidence of accuracy on the user voice'
    report = {'origin': origin, 'cases': []}
    for reference, audio in cases:
        print('Comparing: ' + reference, flush=True)
        result = {'reference': reference, 'results': compare(speech, audio, reference, language=args.language)}
        report['cases'].append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    (ROOT / 'data' / 'asr-benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
