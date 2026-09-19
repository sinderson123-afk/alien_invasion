"""Small SQLite document store for the game's existing collection operations.

All modifying API requests run in one IMMEDIATE transaction, including uniqueness
checks and score maxima. No Google libraries or credentials are needed at runtime.
"""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

SERVER_TIMESTAMP = object()


class Query:
    DESCENDING = 'DESCENDING'


def _encode(value):
    if value is SERVER_TIMESTAMP:
        return datetime.now(timezone.utc).isoformat()
    raise TypeError(f'Unsupported stored value: {type(value)}')


class Client:
    def __init__(self, path=None):
        self.path = path or os.environ.get('DATABASE_PATH', '/var/lib/alien-invasion/game.sqlite3')
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._current = ContextVar('sqlite_connection', default=None)
        with self.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE IF NOT EXISTS documents (collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(collection, id))')
            for field in ('username', 'email'):
                conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS users_{field} ON documents(json_extract(data, '$.{field}')) WHERE collection='users'")

    @contextmanager
    def connection(self):
        current = self._current.get()
        if current is not None:
            yield current
            return
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            token = self._current.set(conn)
            try:
                yield
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                self._current.reset(token)

    def collection(self, name):
        return Collection(self, name)


class Snapshot:
    def __init__(self, reference, data):
        self.reference = reference
        self.id = reference.id
        self.exists = data is not None
        self._data = data

    def to_dict(self):
        return self._data.copy() if self.exists else None


class Document:
    def __init__(self, collection, identifier):
        self.collection = collection
        self.id = identifier

    def get(self):
        with self.collection.client.connection() as conn:
            row = conn.execute('SELECT data FROM documents WHERE collection=? AND id=?', (self.collection.name, self.id)).fetchone()
        return Snapshot(self, json.loads(row[0]) if row else None)

    def set(self, data):
        with self.collection.client.connection() as conn:
            conn.execute('INSERT INTO documents VALUES (?, ?, ?) ON CONFLICT(collection,id) DO UPDATE SET data=excluded.data', (self.collection.name, self.id, json.dumps(data, default=_encode)))

    def update(self, data):
        existing = self.get()
        if not existing.exists:
            raise KeyError(self.id)
        value = existing.to_dict()
        value.update(data)
        self.set(value)

    def delete(self):
        with self.collection.client.connection() as conn:
            conn.execute('DELETE FROM documents WHERE collection=? AND id=?', (self.collection.name, self.id))


class Collection:
    def __init__(self, client, name, filters=(), order=None, maximum=None):
        self.client, self.name = client, name
        self.filters, self.order, self.maximum = filters, order, maximum

    def document(self, identifier=None):
        return Document(self, identifier or uuid.uuid4().hex)

    def where(self, field, operator, value):
        if operator not in ('==', 'array_contains'):
            raise ValueError(operator)
        return Collection(self.client, self.name, self.filters + ((field, operator, value),), self.order, self.maximum)

    def limit(self, maximum):
        return Collection(self.client, self.name, self.filters, self.order, maximum)

    def order_by(self, field, direction=None):
        return Collection(self.client, self.name, self.filters, (field, direction), self.maximum)

    def get(self):
        with self.client.connection() as conn:
            rows = conn.execute('SELECT id, data FROM documents WHERE collection=? ORDER BY id', (self.name,)).fetchall()
        docs = [Snapshot(self.document(key), json.loads(value)) for key, value in rows]
        for field, operator, value in self.filters:
            docs = [doc for doc in docs if (doc._data.get(field) == value if operator == '==' else value in doc._data.get(field, []))]
        if self.order:
            field, direction = self.order
            docs.sort(key=lambda doc: doc._data.get(field, 0), reverse=direction == Query.DESCENDING)
        return docs if self.maximum is None else docs[:self.maximum]
