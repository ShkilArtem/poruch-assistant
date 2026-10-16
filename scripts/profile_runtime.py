"""Measure local Ollama latency; no user conversations are used."""
import argparse
import json
import time
from urllib.parse import urlparse
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:11435')
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--model', default='qwen3.5:9b')
    args = parser.parse_args()
    results = []
    with httpx.Client(base_url=args.url, trust_env=False, timeout=180) as client:
        for _ in range(args.runs):
            started = time.monotonic()
            first = None
            content = ''
            with client.stream('POST', '/api/chat', json={
                'model': args.model, 'stream': True, 'keep_alive': '15m',
                'messages': [{'role': 'user', 'content': 'Привіт! Представся одним коротким реченням українською.'}],
                'options': {'num_ctx': 4096, 'num_predict': 64, 'temperature': 0.2}}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    item = json.loads(line)
                    if item.get('error'):
                        raise RuntimeError(item['error'])
                    chunk = item.get('message', {}).get('content', '')
                    if chunk and first is None:
                        first = round(time.monotonic() - started, 3)
                    content += chunk
                    if item.get('done'):
                        duration = item.get('eval_duration', 0) / 1e9
                        record = {'first_token_seconds': first, 'total_seconds': round(time.monotonic() - started, 3),
                                  'tokens_per_second': round(item.get('eval_count', 0) / duration, 2) if duration else None,
                                  'load_seconds': round(item.get('load_duration', 0) / 1e9, 3), 'text': content}
                        results.append(record)
                        print(json.dumps(record, ensure_ascii=False), flush=True)
        report = {'url': args.url, 'runs': results, 'loaded_models': client.get('/api/ps').json()}
    target = Path(__file__).resolve().parent.parent / 'data' / f'performance-{urlparse(args.url).port}.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
