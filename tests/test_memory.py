import asyncio
import json
import sqlite3

from assistant.memory import Memory
from assistant.session import Session


class Socket:
    def __init__(self):
        self.events = []

    async def send_json(self, data):
        self.events.append(data)


def test_migrate_existing_database(tmp_path):
    path = tmp_path / 'old.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE facts(id INTEGER PRIMARY KEY, topic TEXT UNIQUE, text TEXT, source TEXT, updated TEXT)')
    db.execute("INSERT INTO facts VALUES(1,'ім’я','Артем','користувач','2026-10-16')")
    db.commit()
    db.close()
    memory = Memory(path)
    assert memory.all()[0]['confidence'] == 1
    assert memory.all()[0]['kind'] == 'fact'
    assert 'Артем' in memory.context('ім’я')
    memory.close()


def test_summary_persistence_search_and_forgetting(tmp_path):
    path = tmp_path / 'memory.db'
    memory = Memory(path)
    memory.put('інтереси', 'Люблю роботів', 'явна команда')
    memory.save_summary('session', 'Планує зібрати робота з камерою.')
    memory.close()
    memory = Memory(path)
    assert 'камерою' in memory.context('камер')
    memory.delete(memory.all()[0]['id'])
    assert not memory.summaries()
    assert not memory.context('робот')
    assert not list(memory.db.execute('SELECT * FROM memory_search'))
    memory.close()


def test_correction_clears_summaries_and_inactive_facts_are_excluded(tmp_path):
    memory = Memory(tmp_path / 'm.db')
    memory.put('ім’я', 'Артем', 'знайомство', kind='profile')
    memory.save_summary('session', 'Користувача звати Артем.')
    memory.put('ім’я', 'Тарас', 'уточнення', kind='profile')
    assert not memory.summaries()
    assert 'Артем' not in memory.context('ім’я')
    memory.put('проєкт', 'Зібрати робота', 'вручну', kind='task', active=False)
    assert 'Зібрати' not in memory.context('проєкт')
    memory.close()


def test_commands_need_no_model_and_clear_old_context(tmp_path):
    memory = Memory(tmp_path / 'm.db')
    session = Session(Socket(), None, memory, None)
    assert 'Запам’ятав' in session.memory_command('Запам’ятай інтереси: робототехніка')
    assert 'робототехніка' in session.memory_command('Що ти про мене знаєш?')
    session.history = [{'role': 'user', 'content': 'робототехніка'}]
    session.summary_pending = ['робототехніка']
    memory.save_summary('session', 'Любить робототехніку')
    assert 'видалено' in session.memory_command('Забудь інтереси')
    assert not session.history and not session.summary_pending
    assert not memory.all() and not memory.summaries()
    memory.put('хобі 1', 'роботи', 'user')
    memory.put('хобі 2', 'шахи', 'user')
    assert 'кілька' in session.memory_command('Забудь хобі')
    assert len(memory.all()) == 2
    memory.close()


def test_summary_cannot_restore_deleted_memory(tmp_path):
    async def check():
        memory = Memory(tmp_path / 'm.db')
        memory.put('ім’я', 'Артем', 'user')

        class Model:
            async def complete(self, *args, **kwargs):
                memory.delete(memory.all()[0]['id'])
                return json.dumps({'text': 'Користувача звати Артем.'})

        session = Session(Socket(), Model(), memory, None)
        session.active = True
        session.summary_pending = ['Мене звати Артем']
        await session.summarize()
        assert not memory.summaries()
        memory.close()
    asyncio.run(check())


def test_four_turns_create_one_rolling_summary(tmp_path):
    class Model:
        async def stream(self, *args, **kwargs):
            yield 'Гаразд.'

        async def complete(self, *args, **kwargs):
            if 'facts' in kwargs['schema']['properties']:
                return '{"facts": []}'
            return json.dumps({'text': 'Обговорювали складання робота.'})

    async def check():
        memory = Memory(tmp_path / 'm.db')
        session = Session(Socket(), Model(), memory, None)
        session.active, session.voice_enabled = True, False
        for _ in range(8):
            await session.reply('Як зібрати робота?', session.turn)
        assert len(memory.summaries()) == 1
        assert len(session.history) == 8
        assert not session.summary_pending
        assert 'складання' in memory.context('робот')
        await session.stop()
        assert not session.history
        memory.close()
    asyncio.run(check())
