"""Shared intent helpers: available sources and explicit Notion requests."""
import re

# A request for the user's *own* Notion workspace, not any mention of the word or the product.
# "Notion versus Obsidian" and "Notion of convergence" must not match: matching forces a Notion
# search after the LLM routes, and with Notion disconnected the request is refused outright.
_NOTION_WORKSPACE = re.compile(
    r"\b(?:my|our)\s+(?:own\s+)?notion\b"                                   # my Notion, our Notion
    r"|\b(?:in|from|inside|within|search|open|connect|check)\s+(?:my\s+|our\s+)?notion\b"  # in Notion, search my Notion
    r"|\bnotion\s+(?:notes?|pages?|workspaces?|databases?|wikis?|docs?)\b",  # Notion notes, Notion page
    re.I,
)


def explicit_notion_request(message: str) -> bool:
    """True when the message asks for the user's own Notion content."""
    return bool(_NOTION_WORKSPACE.search(message or ""))


def available_agents(state) -> list[str]:
    requested = state.get("available_sources") if isinstance(state, dict) else None
    if not requested:
        return ["local", "web"]
    return list(requested)


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
