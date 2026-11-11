"""H3: local citations must reflect evidence the answer used, not every search hit."""
import json

from langchain_core.messages import AIMessage, ToolMessage

from research_copilot.sources.local.agent import LocalRAGAgent
from research_copilot.sources.local.citations import mentioned_in


def _hit(source, parent_id, text="chunk text"):
    return {"content": text, "parent_id": parent_id, "source": source, "source_type": "local"}


def _parent(source, parent_id, text="full parent section"):
    return {"content": text, "parent_id": parent_id, "metadata": {"source": source, "parent_id": parent_id},
            "source_type": "local"}


def _run(answer, search_results, fetched=None):
    messages = [AIMessage(content="", tool_calls=[{"id": "s1", "name": "search_local_documents", "args": {"query": "q"}}]),
                ToolMessage(content=json.dumps(search_results), tool_call_id="s1")]
    if fetched is not None:
        messages += [AIMessage(content="", tool_calls=[{"id": "f1", "name": "retrieve_document_context",
                                                         "args": {"parent_ids": [p["parent_id"] for p in fetched]}}]),
                     ToolMessage(content=json.dumps(fetched), tool_call_id="f1")]
    messages.append(AIMessage(content=answer))
    out = LocalRAGAgent(llm=None, tools=[]).extract_answer_with_citations({"messages": messages, "question": "q"})
    return [(c["title"], c["metadata"]["evidence"]) for c in out["agent_answers"][0]["citations"]]


HITS = [_hit("alpha.pdf", "alpha_parent_0"), _hit("beta.pdf", "beta_parent_0"), _hit("gamma.pdf", "gamma_parent_0")]


def test_unused_search_hits_are_not_cited():
    """Before the fix all three hits were cited; the answer only used beta."""
    cited = _run("Beta explains it.\n\nSource: beta.pdf", HITS)
    assert cited == [("beta.pdf", "search_hit")]


def test_fetched_parent_is_cited_even_if_also_a_search_hit():
    cited = _run("Answer from the section.\n\nSource: alpha.pdf", HITS, fetched=[_parent("alpha.pdf", "alpha_parent_0")])
    assert cited == [("alpha.pdf", "fetched")]


def test_fetched_parents_count_without_being_named():
    cited = _run("Here is what the documents say.", HITS, fetched=[_parent("gamma.pdf", "gamma_parent_0")])
    assert cited == [("gamma.pdf", "fetched")]


def test_no_evidence_means_no_citation():
    assert _run("I could not find relevant information in the indexed documents.", HITS) == []


def test_error_results_never_become_citations():
    assert _run("Source: alpha.pdf", [{"error": "Search failed"}]) == []


def test_mention_matching():
    assert mentioned_in("Sources: [alpha.pdf], [beta.pdf]", "alpha.pdf")
    assert mentioned_in("see the transformer_notes document", "docs/transformer_notes.pdf")
    assert not mentioned_in("a b c", "a.pdf")  # short stems must match the full file name
