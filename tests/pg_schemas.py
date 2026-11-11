"""Naming and cleanup of throwaway Postgres schemas used by the database tests.

A session's schema is dropped in the fixture's ``finally``, which never runs
when the process is killed, so interrupted runs left schemas behind on the
test branch. Schema names now carry their creation time, and each session
drops test schemas older than ``MAX_AGE_S`` before creating its own. Names in
the old format (``test_`` + 12 hex characters) are no longer created, so any
that remain are leftovers and are dropped too.
"""
import re
import time
import uuid

MAX_AGE_S = 6 * 3600
_CURRENT = re.compile(r"^test_(\d{10})_[0-9a-f]{8}$")
_LEGACY = re.compile(r"^test_[0-9a-f]{12}$")


def new_schema_name(now: float | None = None) -> str:
    return f"test_{int(now if now is not None else time.time())}_{uuid.uuid4().hex[:8]}"


def stale_schemas(names, now: float | None = None, max_age_s: int = MAX_AGE_S) -> list[str]:
    """Test schemas safe to drop: old-format leftovers and current-format ones past ``max_age_s``."""
    now = now if now is not None else time.time()
    stale = []
    for name in names:
        match = _CURRENT.match(name)
        if (match and now - int(match.group(1)) > max_age_s) or _LEGACY.match(name):
            stale.append(name)
    return sorted(stale)


def drop_stale_schemas(conn, now: float | None = None) -> list[str]:
    rows = conn.execute(
        "select schema_name from information_schema.schemata where schema_name like 'test\\_%'").fetchall()
    dropped = stale_schemas([r[0] for r in rows], now)
    for name in dropped:
        conn.execute(f'DROP SCHEMA "{name}" CASCADE')
    return dropped
