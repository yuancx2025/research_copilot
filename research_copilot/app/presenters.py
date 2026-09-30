"""Convert service objects into the JSON shapes the frontend renders."""
from typing import Any, Dict, List, Optional


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


def present_result(run, service) -> Dict[str, Any]:
    data = run.result or {}
    return {
        "run_id": run.id,
        "query": run.query,
        "answer": data.get("answer", ""),
        "citations": present_citations(data.get("citations", [])),
        "sources": present_sources(data.get("agent_results", {})),
        "needs_clarification": run.needs_clarification,
        "can_preview_plan": service.can_preview(run),
        "generation": run.connection_generation,
    }


def present_run(run, service, last_seq: Optional[int] = None) -> Dict[str, Any]:
    return {
        "id": run.id,
        "conversation_id": run.conversation_id,
        "request_id": run.request_id,
        "status": run.status,
        "query": run.query,
        "retry_of_run_id": run.retry_of_run_id,
        "error": run.error,
        "last_seq": last_seq or 0,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "result": present_result(run, service) if run.result else None,
    }


def present_message(message) -> Dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "clarification": message.clarification,
        "run_id": message.run_id,
        "request_id": message.request_id,
        "created_at": message.created_at,
    }


def present_conversation(conversation) -> Dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


def present_draft(draft, service) -> Dict[str, Any]:
    return {
        "draft_id": draft.id,
        "run_id": draft.run_id,
        "title": draft.title,
        "markdown": draft.markdown,
        "exportable": service.draft_exportable(draft),
    }


def present_conversation_detail(detail, service) -> Dict[str, Any]:
    conversation, messages, runs, drafts, last_seq = detail
    return {
        **present_conversation(conversation),
        "messages": [present_message(m) for m in messages],
        "runs": [present_run(r, service, last_seq.get(r.id)) for r in runs],
        "drafts": [present_draft(d, service) for d in drafts],
    }


def present_export(result) -> Dict[str, Any]:
    return {**result.model_dump(), "retryable": result.status == "failure"}
