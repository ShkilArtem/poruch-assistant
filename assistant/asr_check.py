"""ASR comparison on the same samples, without persisting recordings."""
import re
import time
import logging


def words(text):
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", text.casefold().replace('’', "'").replace('ʼ', "'"))


def word_error_rate(reference, hypothesis):
    expected, actual = words(reference), words(hypothesis)
    if not expected:
        return None
    row = list(range(len(actual) + 1))
    for i, left in enumerate(expected, 1):
        updated = [i]
        for j, right in enumerate(actual, 1):
            updated.append(min(updated[-1] + 1, row[j] + 1, row[j - 1] + (left != right)))
        row = updated
    return round(row[-1] / len(expected), 4)


def compare(speech, audio, reference, models=('small', 'turbo', 'parakeet'), language='auto'):
    result = []
    for model in models:
        logging.getLogger(__name__).info('Comparing ASR: %s', model)
        # First pass includes loading; second measures this clip with the model already loaded.
        started = time.monotonic()
        speech.transcribe(audio, model=model, language=language)
        load_and_first = time.monotonic() - started
        started = time.monotonic()
        text = speech.transcribe(audio, model=model, language=language)
        result.append({'model': model, 'text': text, 'wer': word_error_rate(reference, text),
                       'warm_seconds': round(time.monotonic() - started, 3),
                       'load_and_first_seconds': round(load_and_first, 3)})
    return result
