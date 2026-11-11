"""M6: parent loading keeps the retrieval order and tolerates a missing id."""
import pytest

from research_copilot.storage.parent_store import ParentStoreManager


@pytest.fixture
def store(tmp_path):
    s = ParentStoreManager(store_path=tmp_path / "parents")
    for pid in ("zeta_parent_0", "alpha_parent_0", "mid_parent_0"):
        s.save(pid, f"content of {pid}", {"source": f"{pid}.pdf"})
    return s


def test_load_many_preserves_requested_order(store):
    ids = ["zeta_parent_0", "alpha_parent_0", "mid_parent_0"]
    assert [p["parent_id"] for p in store.load_many(ids)] == ids  # previously sorted alphabetically


def test_load_many_deduplicates_keeping_first_position(store):
    got = store.load_many(["mid_parent_0", "zeta_parent_0", "mid_parent_0"])
    assert [p["parent_id"] for p in got] == ["mid_parent_0", "zeta_parent_0"]


def test_missing_id_is_skipped_not_fatal(store, caplog):
    got = store.load_many(["alpha_parent_0", "gone_parent_9", "zeta_parent_0"])
    assert [p["parent_id"] for p in got] == ["alpha_parent_0", "zeta_parent_0"]
    assert "gone_parent_9" in caplog.text


def test_corrupt_parent_still_raises(store, tmp_path):
    (tmp_path / "parents" / "bad_parent_0.json").write_text("{not json")
    with pytest.raises(ValueError):
        store.load_many(["alpha_parent_0", "bad_parent_0"])
