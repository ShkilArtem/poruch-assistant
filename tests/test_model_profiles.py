import asyncio
import json
import httpx
from assistant.llm import Ollama


def test_model_profiles_keep_json_conservative_and_hide_reasoning(monkeypatch):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text=json.dumps({'message': {'content': 'Bonjour!'}, 'done': True}) + '\n')

    client = httpx.AsyncClient
    monkeypatch.setattr('assistant.llm.httpx.AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(handle)))

    async def check():
        for model, schema in [('hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0', None),
                              ('hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS', None),
                              ('hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0', {'type': 'object'})]:
            assert ''.join([part async for part in Ollama(model).stream([{'role': 'user', 'content': 'Bonjour'}], schema=schema)]) == 'Bonjour!'
    asyncio.run(check())
    assert requests[0]['options']['temperature'] == 1.0 and requests[0]['options']['top_k'] == 64
    assert requests[1]['options']['temperature'] == 0.7
    assert requests[2]['options']['temperature'] == 0.2 and requests[2]['format'] == {'type': 'object'}
    assert all(request['think'] is False and request['stream'] is True for request in requests)
