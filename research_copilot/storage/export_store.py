"""Small local submission ledger. Pending writes after a crash are ambiguous."""
import sqlite3
from pathlib import Path
from typing import Literal
from pydantic import BaseModel


class ExportResult(BaseModel):
    status: Literal['success', 'failure', 'unknown', 'pending']
    page_id: str | None = None
    url: str | None = None
    message: str = ''


PENDING = ExportResult(status='pending', message='Export is already in progress.')
STALE_UNKNOWN = ExportResult(
    status='unknown',
    message='Creation outcome unknown. Inspect Notion; this submission will not be retried automatically.',
)


class ExportStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS exports (key TEXT PRIMARY KEY, result TEXT NOT NULL)')

    def claim(self, key):
        with sqlite3.connect(self.path) as db:
            inserted = db.execute(
                'INSERT OR IGNORE INTO exports VALUES (?, ?)', (key, PENDING.model_dump_json())
            ).rowcount
            if inserted:
                return None
            raw = db.execute('SELECT result FROM exports WHERE key=?', (key,)).fetchone()[0]
            return ExportResult.model_validate_json(raw)

    def finish(self, key, result):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE exports SET result=? WHERE key=?', (result.model_dump_json(), key))
