import json
import httpx
from .config import MODEL, OLLAMA


class StructuredOutputError(RuntimeError):
    pass


class Ollama:
    def __init__(self, model=MODEL):
        self.model = model

    async def stream(self, messages, *, schema=None, tokens=220):
        options = {'num_ctx': 4096, 'num_predict': tokens, 'temperature': 0.2}
        if not schema and 'gemma-4-' in self.model.lower():
            options.update(temperature=1.0, top_p=0.95, top_k=64)
        elif not schema and 'qwen3.6' in self.model.lower():
            options.update(temperature=0.7, top_p=0.8, top_k=20)
        body = {'model': self.model, 'messages': messages, 'stream': True, 'think': False,
                'keep_alive': '15m', 'options': options}
        if schema:
            body['format'] = schema
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            async with client.stream('POST', OLLAMA + '/api/chat', json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        item = json.loads(line)
                        if item.get('error'):
                            raise RuntimeError(item['error'])
                        if schema and item.get('done_reason') == 'length':
                            raise StructuredOutputError('Модель досягла ліміту довжини відповіді')
                        yield item.get('message', {}).get('content', '')

    async def complete(self, messages, *, schema=None, tokens=200):
        if not schema:
            return ''.join([part async for part in self.stream(messages, tokens=tokens)])
        for attempt in range(2):
            try:
                response = ''.join([part async for part in self.stream(
                    messages, schema=schema, tokens=min(tokens * (2 ** attempt), 1200))])
                json.loads(response)
                return response
            except (json.JSONDecodeError, StructuredOutputError):
                if attempt:
                    raise StructuredOutputError('Модель не завершила опис кадру або запис пам’яті. Потрібна повторна спроба.') from None
                messages = [dict(message) for message in messages]
                messages.insert(0, {'role': 'system', 'content':
                    'Поверни лише завершений JSON за схемою. Значення роби короткими, без повторів і пояснень.'})

    async def health(self):
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                r = await client.get(OLLAMA + '/api/tags')
                r.raise_for_status()
                names = [m['name'] for m in r.json()['models']]
                placement = 'not_loaded'
                try:
                    loaded = await client.get(OLLAMA + '/api/ps')
                    loaded.raise_for_status()
                    for model in loaded.json().get('models', []):
                        if model.get('name') == self.model:
                            size, vram = model.get('size', 0), model.get('size_vram', 0)
                            placement = 'gpu' if size and vram >= size else 'mixed' if vram else 'cpu'
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    placement = 'unknown'
                labels = {'hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0': 'Gemma 4 12B · QAT Q4',
                          'hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS': 'Qwen3.6 35B-A3B · IQ3',
                          'qwen3.5:9b': 'Qwen3.5 9B · Q4'}
                return {'available': self.model in names, 'model': self.model, 'display_name': labels.get(self.model, self.model), 'installed': names,
                        'processor': placement}
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return {'available': False, 'model': self.model, 'error': str(exc)}
