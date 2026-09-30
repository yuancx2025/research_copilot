"""Export submission ledger in PostgreSQL. Pending writes after a crash are ambiguous.

Each submission is claimed atomically before Notion is called, so a repeated
submission returns the recorded outcome instead of writing again. An
``unknown`` outcome is never retried automatically.
"""
import sqlite3
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from research_copilot.db.models import ExportRow, StudyPlanDraftRow


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


def _result(row) -> ExportResult:
    return ExportResult(status=row.status, page_id=row.page_id, url=row.url, message=row.message or '')


class PostgresExportLedger:
    def __init__(self, db):
        self.db = db

    async def claim(self, key: str, draft_id: Optional[str] = None,
                    destination: Optional[str] = None) -> Optional[ExportResult]:
        """Record a pending submission. Returns None if claimed, else the existing outcome."""
        draft = select(StudyPlanDraftRow.id).where(StudyPlanDraftRow.id == draft_id).scalar_subquery()
        statement = insert(ExportRow).values(
            idempotency_key=key, draft_id=draft, destination=destination,
            status=PENDING.status, message=PENDING.message,
        ).on_conflict_do_nothing(index_elements=['idempotency_key']).returning(ExportRow.id)
        async with self.db.transaction() as session:
            inserted = (await session.execute(statement)).scalar()
            if inserted is not None:
                return None
            row = await session.scalar(select(ExportRow).where(ExportRow.idempotency_key == key))
            return _result(row)

    async def finish(self, key: str, result: ExportResult):
        async with self.db.transaction() as session:
            await session.execute(update(ExportRow).where(ExportRow.idempotency_key == key).values(
                status=result.status, page_id=result.page_id, url=result.url, message=result.message))

    async def get(self, key: str) -> Optional[ExportResult]:
        async with self.db.session() as session:
            row = await session.scalar(select(ExportRow).where(ExportRow.idempotency_key == key))
            return _result(row) if row else None


def read_sqlite_ledger(path: Path):
    """Rows of the legacy ``exports(key, result)`` table; pending rows become unknown."""
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
        rows = db.execute('SELECT key, result FROM exports').fetchall()
    for key, raw in rows:
        result = ExportResult.model_validate_json(raw)
        yield key, STALE_UNKNOWN if result.status == 'pending' else result


async def import_sqlite_ledger(path: Path, db) -> tuple[int, int]:
    """Copy legacy export keys and outcomes; existing keys are left untouched."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'No export ledger at {path}.')
    imported = skipped = 0
    async with db.transaction() as session:
        for key, result in read_sqlite_ledger(path):
            statement = insert(ExportRow).values(
                idempotency_key=key, status=result.status, page_id=result.page_id, url=result.url,
                message=result.message, legacy=True,
            ).on_conflict_do_nothing(index_elements=['idempotency_key']).returning(ExportRow.id)
            if (await session.execute(statement)).scalar() is None:
                skipped += 1
            else:
                imported += 1
    return imported, skipped
