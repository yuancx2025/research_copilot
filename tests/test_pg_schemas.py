"""L12: interrupted database test runs must not leave schemas behind forever."""
from tests.pg_schemas import MAX_AGE_S, drop_stale_schemas, new_schema_name, stale_schemas

NOW = 1_800_000_000


def test_new_names_carry_creation_time():
    name = new_schema_name(NOW)
    assert name.startswith(f"test_{NOW}_") and len(name) == len(f"test_{NOW}_") + 8


def test_selects_old_and_legacy_schemas_only():
    fresh = new_schema_name(NOW - 60)
    old = new_schema_name(NOW - MAX_AGE_S - 1)
    legacy = "test_7b70c97ce4d5"  # the schema actually left on the Neon test branch
    unrelated = ["public", "test_results", "testing_abc", "test_7b70c97ce4d"]
    assert stale_schemas([fresh, old, legacy, *unrelated], NOW) == sorted([old, legacy])


def test_drop_issues_cascade_for_stale_schemas_only():
    class Conn:
        def __init__(self, names):
            self.names, self.sql = names, []

        def execute(self, sql):
            self.sql.append(sql)
            return self

        def fetchall(self):
            return [(n,) for n in self.names]

    keep = new_schema_name(NOW)
    conn = Conn(["test_7b70c97ce4d5", keep])
    assert drop_stale_schemas(conn, NOW) == ["test_7b70c97ce4d5"]
    assert conn.sql[-1] == 'DROP SCHEMA "test_7b70c97ce4d5" CASCADE'
    assert not any(keep in s for s in conn.sql[1:])
