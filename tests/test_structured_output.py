import asyncio
import json

import httpx
import pytest
from assistant.llm import Ollama, StructuredOutputError
from assistant.schemas import Observation


def test_truncated_observation_retries_with_larger_budget(monkeypatch):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            item = {'message': {'content': '{"scene":"обірваний'}, 'done': True, 'done_reason': 'length'}
        else:
            item = {'message': {'content': json.dumps({'scene': 'Кімната', 'event': '', 'remark': ''})},
                    'done': True, 'done_reason': 'stop'}
        return httpx.Response(200, text=json.dumps(item) + '\n')

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))

    async def check():
        text = await Ollama().complete([{'role': 'user', 'content': 'Опиши кадр'}],
                                       schema=Observation.model_json_schema(), tokens=512)
        assert Observation.model_validate_json(text).scene == 'Кімната'
    asyncio.run(check())
    assert [body['options']['num_predict'] for body in requests] == [512, 1024]


def test_malformed_json_has_bounded_retry_and_readable_error():
    class Model(Ollama):
        def __init__(self):
            self.calls = 0

        async def stream(self, *args, **kwargs):
            self.calls += 1
            yield '{"scene":"незавершений опис'

    async def check():
        model = Model()
        with pytest.raises(StructuredOutputError, match='Модель не завершила'):
            await model.complete([], schema=Observation.model_json_schema())
        assert model.calls == 2
    asyncio.run(check())
