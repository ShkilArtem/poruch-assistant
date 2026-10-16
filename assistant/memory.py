import re
import sqlite3
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Memory:
    """Local facts and bounded summaries; raw conversations/media are never stored."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.revision = 0
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('''CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY, topic TEXT NOT NULL UNIQUE,
            text TEXT NOT NULL, source TEXT NOT NULL, updated TEXT NOT NULL)''')
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(facts)')}
        for name, definition in [('kind', "TEXT NOT NULL DEFAULT 'fact'"),
                                 ('confidence', 'REAL NOT NULL DEFAULT 1.0'),
                                 ('active', 'INTEGER NOT NULL DEFAULT 1')]:
            if name not in columns:
                self.db.execute(f'ALTER TABLE facts ADD COLUMN {name} {definition}')
        self.db.execute('''CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY, session_id TEXT NOT NULL UNIQUE,
            text TEXT NOT NULL, source TEXT NOT NULL, updated TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.7, active INTEGER NOT NULL DEFAULT 1)''')
        self.db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(category UNINDEXED, record_id UNINDEXED, text)')
        self._reindex()
        self.db.commit()

    def _reindex(self):
        self.db.execute('DELETE FROM memory_search')
        self.db.execute("INSERT INTO memory_search SELECT 'fact', id, topic || ' ' || text FROM facts WHERE active=1")
        self.db.execute("INSERT INTO memory_search SELECT 'summary', id, text FROM summaries WHERE active=1")

    def all(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM facts ORDER BY updated DESC')]

    def summaries(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM summaries ORDER BY updated DESC LIMIT 50')]

    def put(self, topic, text, source, *, kind='fact', confidence=1.0, active=True):
        topic, text = topic.strip()[:80], text.strip()[:500]
        if not topic or not text or kind not in {'fact', 'profile', 'task'}:
            raise ValueError('Потрібні тема, текст і коректний тип запису')
        existing = self.db.execute('SELECT * FROM facts WHERE topic=?', (topic,)).fetchone()
        with self.db:
            if existing and (existing['text'] != text or bool(existing['active']) != active):
                self.db.execute('DELETE FROM summaries')
            self.db.execute('''INSERT INTO facts(topic,text,source,updated,kind,confidence,active) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(topic) DO UPDATE SET text=excluded.text, source=excluded.source,
                updated=excluded.updated,kind=excluded.kind,confidence=excluded.confidence,active=excluded.active''',
                (topic, text, source[:1000], utcnow(), kind, max(0, min(1, confidence)), int(active)))
            self._reindex()
        if existing and (existing['text'] != text or bool(existing['active']) != active):
            self.revision += 1

    def save_summary(self, session_id, text):
        if not text.strip():
            with self.db:
                self.db.execute('DELETE FROM summaries WHERE session_id=?', (session_id,))
                self._reindex()
            return
        with self.db:
            self.db.execute('''INSERT INTO summaries(session_id,text,source,updated) VALUES(?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET text=excluded.text,updated=excluded.updated''',
                (session_id, text.strip()[:1800], 'Автоматичний підсумок прямих звернень', utcnow()))
            self.db.execute('DELETE FROM summaries WHERE id NOT IN (SELECT id FROM summaries ORDER BY updated DESC LIMIT 50)')
            self._reindex()

    def delete(self, fact_id):
        with self.db:
            self.db.execute('DELETE FROM facts WHERE id=?', (fact_id,))
            # Paraphrases cannot reliably be removed with literal string matching.
            self.db.execute('DELETE FROM summaries')
            self._reindex()
        self.revision += 1
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def delete_summary(self, summary_id):
        with self.db:
            self.db.execute('DELETE FROM summaries WHERE id=?', (summary_id,))
            self._reindex()
        self.revision += 1
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def context(self, query, limit=3000):
        words = re.findall(r'\w+', query.lower())[:24]
        ranked = []
        if words:
            match = ' OR '.join('"' + word + '"*' for word in words)
            ranked = list(self.db.execute('SELECT category, record_id FROM memory_search WHERE memory_search MATCH ? ORDER BY rank LIMIT 12', (match,)))
        facts = [f for f in self.all() if f['active']]
        positions = {(r['category'], r['record_id']): i for i, r in enumerate(ranked)}
        facts.sort(key=lambda f: (f['kind'] != 'profile', positions.get(('fact', f['id']), 99)))
        lines = [f"[{f['kind']}; впевненість {f['confidence']:.1f}] {f['topic']}: {f['text']}" for f in facts]
        summaries = {s['id']: s for s in self.summaries()}
        for record in ranked:
            if record['category'] == 'summary' and record['record_id'] in summaries:
                lines.append('Підсумок (може бути неточним): ' + summaries[record['record_id']]['text'])
        return '\n'.join(lines)[:limit]

    def close(self):
        self.db.close()
