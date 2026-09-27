"""Convert service objects into the JSON shapes the frontend renders."""
from typing import Any, Dict, List


def _is_placeholder_youtube_title(title: str) -> bool:
    lowered = title.lower()
    compact = title.replace("_", "").replace("-", "")
    return lowered.startswith("transcript:") or (len(title) <= 15 and compact.isalnum())


def _authors(value) -> List[str]:
    if isinstance(value, str):
        return [a.strip() for a in value.split(",") if a.strip()]
    if isinstance(value, list):
        return [str(a) for a in value if a]
    return []


def present_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
    metadata = citation.get("metadata") or {}
    return {
        "source_type": str(citation.get("source_type") or "unknown"),
        "title": (citation.get("title") or "Untitled").strip(),
        "url": citation.get("url") or "",
        "snippet": citation.get("snippet") or "",
        "authors": _authors(citation.get("authors")),
        "date": citation.get("date") or citation.get("published") or citation.get("published_at"),
        "channel": citation.get("channel"),
        "repo": citation.get("repo") or metadata.get("full_name") or None,
    }


def present_citations(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    presented = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        item = present_citation(citation)
        if item["source_type"] == "youtube" and _is_placeholder_youtube_title(item["title"]):
            continue
        presented.append(item)
    return presented


def present_sources(agent_results: Dict[str, list]) -> Dict[str, int]:
    return {source: len(results or []) for source, results in (agent_results or {}).items()}


def present_record(record, service) -> Dict[str, Any]:
    citations = present_citations(record.citations)
    return {
        "query": record.query,
        "answer": record.answer,
        "citations": citations,
        "sources": present_sources(record.agent_results),
        "needs_clarification": record.needs_clarification,
        "can_preview_plan": service.can_preview(record),
        "generation": record.generation,
    }


def present_event(event: Dict[str, Any], service) -> Dict[str, Any]:
    if event.get("type") == "result":
        return {"type": "result", **present_record(event["record"], service)}
    return event


def present_draft(draft) -> Dict[str, Any]:
    return {"draft_id": draft.draft_id, "title": draft.plan.title, "markdown": draft.markdown}


def present_export(result) -> Dict[str, Any]:
    return {**result.model_dump(), "retryable": result.status == "failure"}
