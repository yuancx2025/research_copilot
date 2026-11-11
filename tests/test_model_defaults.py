"""L11: one default model, defined once."""
import re
from pathlib import Path

from research_copilot.config import settings
from research_copilot.config.defaults import DEFAULT_LLM_MODEL

PACKAGE = Path(__file__).resolve().parents[1] / "research_copilot"


def test_create_llm_falls_back_to_the_shared_default(monkeypatch):
    from research_copilot.core import rag_system
    monkeypatch.setattr(settings, "LLM_PROVIDER", "google", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", None, raising=False)
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-key-not-used", raising=False)
    llm = rag_system.create_llm()
    assert DEFAULT_LLM_MODEL in llm.model


def test_no_other_hard_coded_default_model_names():
    pattern = re.compile(r"""["'](gemini-[\w.-]+|qwen3:[\w.-]+)["']""")
    offenders = [
        f"{path.relative_to(PACKAGE)}: {match}"
        for path in PACKAGE.rglob("*.py")
        if path.name != "defaults.py" and "evals" not in path.parts
        for match in pattern.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
