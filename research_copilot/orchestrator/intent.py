"""Shared intent helpers: available sources and explicit Notion requests."""
import re

VALID_AGENTS = ("arxiv", "youtube", "github", "web", "local", "notion")
DEFAULT_AGENTS = ("arxiv", "youtube", "github", "web", "local")

# Product name, or "notion" tied to workspace/notes language — not "I have a notion that".
_NOTION_PRODUCT = re.compile(r"\bNotion\b")
_NOTION_WORKSPACE = re.compile(
    r"\bnotion\b.{0,32}\b(note|notes|page|pages|workspace|database|wiki|connect)\b"
    r"|\b(my|in|from|search|connect|open)\b.{0,24}\bnotion\b",
    re.I,
)


def explicit_notion_request(message: str) -> bool:
    text = message or ""
    return bool(_NOTION_PRODUCT.search(text) or _NOTION_WORKSPACE.search(text))


def available_agents(state) -> list[str]:
    requested = state.get("available_sources") if isinstance(state, dict) else None
    if not requested:
        return list(DEFAULT_AGENTS)
    return [name for name in requested if name in VALID_AGENTS]


def keyword_agents(query: str, available: list[str]) -> list[str]:
    query_lower = (query or "").lower()
    selected = []
    if any(term in query_lower for term in ("arxiv", "arxiv.org")):
        selected.append("arxiv")
    elif any(term in query_lower for term in ("paper", "research paper", "publication")):
        selected.append("arxiv")
    if any(term in query_lower for term in ("youtube", "youtu.be", "video", "tutorial", "lecture")):
        selected.append("youtube")
    if any(term in query_lower for term in ("github", "github.com", "code", "repository", "repo", "implementation")):
        selected.append("github")
    if any(term in query_lower for term in ("web", "article", "blog", "documentation", "website")):
        selected.append("web")
    if explicit_notion_request(query) and "notion" in available:
        selected.append("notion")
    selected = [name for name in selected if name in available]
    if not selected:
        return list(available)
    if "local" in available and "local" not in selected:
        selected.append("local")
    return selected


def ensure_notion(query: str, agents: list[str], available: list[str]) -> list[str]:
    if explicit_notion_request(query) and "notion" in available and "notion" not in agents:
        return [*agents, "notion"]
    return agents
