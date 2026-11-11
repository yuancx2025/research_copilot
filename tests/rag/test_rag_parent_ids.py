"""L10: parent ids for indexed sources must not collide (they are also parent-store file names)."""
import re
from pathlib import Path

from research_copilot.rag.chunker import Chunker, parent_id_prefix

COLLIDING_BEFORE = [
    ("2401.12345", "2401.67890"),  # every arXiv paper from one month shared the stem "2401"
    ("https://github.com/langchain-ai/langgraph", "https://github.com/someone/langgraph"),
    ("https://example.com/docs/index.html", "https://other.org/blog/index.html"),
]


def test_old_scheme_collided():
    for a, b in COLLIDING_BEFORE:
        assert Path(a).stem == Path(b).stem


def test_prefixes_are_unique_stable_and_filename_safe():
    for a, b in COLLIDING_BEFORE:
        assert parent_id_prefix(a) != parent_id_prefix(b)
        assert parent_id_prefix(a) == parent_id_prefix(a)
    for source in ("2401.12345", "https://x.org/a b?c=d", "", "///"):
        assert re.fullmatch(r"[A-Za-z0-9_-]+", parent_id_prefix(source))


def test_chunker_gives_two_arxiv_papers_distinct_parents():
    chunker = Chunker()
    text = "# Title\n\n" + "Body sentence about the method. " * 120
    a, _ = chunker.create_chunks_from_text(text, {"source_id": "2401.12345"})
    b, _ = chunker.create_chunks_from_text(text, {"source_id": "2401.67890"})
    ids_a, ids_b = {pid for pid, _ in a}, {pid for pid, _ in b}
    assert ids_a and ids_b and not ids_a & ids_b
    assert all(pid.startswith("2401-12345-") for pid in ids_a)
