from fastapi.testclient import TestClient
import assistant.main as server
from assistant.memory import Memory
import base64
import numpy as np


def test_playback_module_is_served_as_javascript():
    # No lifespan is needed: this check must not open the user's memory database.
    client = TestClient(server.app)
    response = client.get('/static/playback.mjs')
    assert response.status_code == 200
    assert response.headers['content-type'].split(';')[0] in {'text/javascript', 'application/javascript'}
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_asr_comparison_checks_audio_and_protects_active_conversation(tmp_path, monkeypatch):
    paths = {name: tmp_path / name for name in ('small', 'turbo')}
    for path in paths.values():
        path.mkdir()
        (path / 'model.bin').touch()
    monkeypatch.setattr(server, 'ASR_PATHS', paths)
    monkeypatch.setattr(server, 'compare', lambda speech, audio, reference, **kwargs: [{'model': 'turbo', 'text': reference}])
    client = TestClient(server.app)
    origin = {'origin': 'http://testserver'}
    payload = {'audio': base64.b64encode(np.zeros(512, dtype='<f4').tobytes()).decode(), 'reference': 'Привіт'}
    result = client.post('/api/asr/compare', headers=origin, json=payload)
    assert result.status_code == 200
    assert result.json()['results'][0]['text'] == 'Привіт'
    assert client.post('/api/asr/compare', headers=origin, json={**payload, 'audio': 'invalid'}).status_code == 422
    monkeypatch.setattr(server, 'current', object())
    assert client.post('/api/asr/compare', headers=origin, json=payload).status_code == 409


def test_profile_editor_and_summary_deletion(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    memory = Memory(tmp_path / 'memory.sqlite3')
    memory.save_summary('test', 'Артем збирає робота.')
    memory.close()
    origin = {'origin': 'http://testserver'}
    with TestClient(server.app) as client:
        response = client.post('/api/profile', headers=origin, json={
            'name': 'Артем', 'address': 'Артеме', 'room': 'Стіл біля вікна', 'interests': 'Роботи'})
        assert response.status_code == 200
        assert len(response.json()) == 4
        assert all(f['kind'] == 'profile' for f in response.json())
        assert client.get('/api/summaries').json()
        fact_id = response.json()[0]['id']
        assert client.delete(f'/api/memory/{fact_id}', headers=origin).status_code == 200
        assert client.get('/api/summaries').json() == []
        assert client.post('/api/memory', headers=origin, json={'topic': ' ', 'text': 'тест'}).status_code == 422
        assert client.post('/api/profile', json={'name': 'Артем'}).status_code == 403


def test_websocket_memory_commands_and_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'DATA', tmp_path)
    with TestClient(server.app) as client:
        with client.websocket_connect('/ws', headers={'origin': 'http://testserver'}) as ws:
            assert ws.receive_json()['type'] == 'status'
            ws.send_json({'type': 'settings', 'voice': False})
            ws.send_json({'type': 'text', 'text': 'Запам’ятай інтереси: робототехніка'})
            for _ in range(10):
                event = ws.receive_json()
                if event['type'] == 'reply':
                    assert 'Запам’ятав' in event['text']
                    break
            else:
                raise AssertionError('No command response')
            assert len(client.get('/api/memory').json()) == 1
            ws.send_json({'type': 'stop'})
            while ws.receive_json()['type'] != 'stopped':
                pass
        assert server.current is None
