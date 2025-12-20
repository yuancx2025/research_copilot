from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage, AIMessage
from .state import State, AgentState
from .schemas import QueryAnalysis, ResearchIntent
from .prompts import *

def analyze_chat_and_summarize(state: State, llm):
    if len(state["messages"]) < 4:
        return {"conversation_summary": ""}
    
    relevant_msgs = [
        msg for msg in state["messages"][:-1]
        if isinstance(msg, (HumanMessage, AIMessage))
        and not getattr(msg, "tool_calls", None)
    ]
    if not relevant_msgs:
        return {"conversation_summary": ""}

    summary_prompt = get_conversation_summary_prompt(relevant_msgs)
    # Gemini requires at least one non-system message, use HumanMessage instead of SystemMessage
    summary_response = llm.with_config(temperature=0.2).invoke([HumanMessage(content=summary_prompt)])
    return {"conversation_summary": summary_response.content, "agent_answers": [{"__reset__": True}]}

def analyze_and_rewrite_query(state: State, llm):
    last_message = state["messages"][-1]
    conversation_summary = state.get("conversation_summary", "")

    prompt = get_query_analysis_prompt(last_message.content, conversation_summary)

    llm_with_structure = llm.with_config(temperature=0.1).with_structured_output(QueryAnalysis)
    # Gemini requires at least one non-system message, use HumanMessage instead of SystemMessage
    response = llm_with_structure.invoke([HumanMessage(content=prompt)])

    if response.is_clear:
        delete_all = [
            RemoveMessage(id=m.id)
            for m in state["messages"]
            if not isinstance(m, SystemMessage)
        ]
        return {
            "questionIsClear": True,
            "messages": delete_all,
            "originalQuery": last_message.content,
            "rewrittenQuestions": response.questions
        }
    else:
        clarification = response.clarification_needed or "I need more information to understand your question."
        return {
            "questionIsClear": False,
            "messages": [AIMessage(content=clarification)]
        }

def classify_research_intent(state: State, llm) -> Dict[str, Any]:
    """
    Analyzes query to determine which specialized agents to invoke.
    
    Uses LLM with structured output to classify research intent.
    Returns state update with research_intent and routing_decision.
    """
    query = state.get("originalQuery", "")
    if not query:
        # Fallback: try to get from rewritten questions or messages
        if state.get("rewrittenQuestions"):
            query = state["rewrittenQuestions"][0]
        elif state["messages"]:
            last_msg = state["messages"][-1]
            if isinstance(last_msg, HumanMessage):
                query = last_msg.content
    
    if not query:
        # Default fallback
        return {
            "research_intent": ["local", "web"],
            "routing_decision": {
                "reasoning": "No query found, defaulting to local and web agents",
                "confidence": 0.5
            },
            "active_agents": ["local", "web"]
        }
    
    conversation_summary = state.get("conversation_summary", "")
    prompt = get_intent_classification_prompt(query, conversation_summary)
    
    try:
        llm_with_structure = llm.with_config(temperature=0.1).with_structured_output(ResearchIntent)
        # Gemini requires at least one non-system message, use HumanMessage instead of SystemMessage
        intent = llm_with_structure.invoke([HumanMessage(content=prompt)])
        
        # Validate agent names (filter invalid ones)
        valid_agents = ["arxiv", "youtube", "github", "web", "local"]
        filtered_agents = [a for a in intent.agents if a in valid_agents]
        
        # Default fallback if no valid agents
        if not filtered_agents:
            filtered_agents = ["local", "web"]
            intent.reasoning = f"Invalid agents selected: {intent.agents}. Defaulting to local and web."
            intent.confidence = 0.5
        
        return {
            "research_intent": filtered_agents,
            "routing_decision": {
                "reasoning": intent.reasoning,
                "confidence": intent.confidence,
                "suggested_queries": intent.suggested_queries or {}
            },
            "active_agents": filtered_agents
        }
    except Exception as e:
        # Error handling: default to safe fallback
        print(f"Error in intent classification: {e}")
        return {
            "research_intent": ["local", "web"],
            "routing_decision": {
                "reasoning": f"Intent classification failed: {str(e)}. Defaulting to local and web agents.",
                "confidence": 0.5
            },
            "active_agents": ["local", "web"]
        }

def human_input_node(state: State):
    return {}

def agent_node(state: AgentState, llm_with_tools, system_prompt: str = None):
    """
    Agent node that processes questions with tools.
    
    Args:
        state: AgentState with question and messages
        llm_with_tools: LLM instance bound with tools
        system_prompt: Optional custom system prompt (defaults to RAG agent prompt)
    """
    # Use custom system prompt if provided, otherwise use default
    if system_prompt is None:
        system_prompt = get_rag_agent_system_prompt()
    
    sys_msg = SystemMessage(content=system_prompt)
    
    if not state.get("messages"):
        human_msg = HumanMessage(content=state["question"])
        response = llm_with_tools.invoke([sys_msg] + [human_msg])
        return {"messages": [human_msg, response]}
    
    return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}

def extract_final_answer(state: AgentState):
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            res = {
                "final_answer": msg.content,
                "agent_answers": [{
                    "index": state["question_index"],
                    "question": state["question"],
                    "answer": msg.content
                }]
            }
            return res
    return {
        "final_answer": "Unable to generate an answer.",
        "agent_answers": [{
            "index": state["question_index"],
            "question": state["question"],
            "answer": "Unable to generate an answer."
        }]
    }


def aggregate_responses(state: State, llm):
    """
    Aggregate responses from multiple agents and synthesize into unified answer.
    
    Handles:
    - Multiple agent results with different sources
    - Citation merging and deduplication
    - Multi-source synthesis
    - Cached results integration
    - Error handling for empty results and agent failures
    """
    agent_answers = state.get("agent_answers", [])
    
    # Merge cached results if available
    cached_results = state.get("cached_results", {})
    if cached_results:
        # Convert cached results to agent_answers format
        for agent_type, cached_result in cached_results.items():
            if isinstance(cached_result, dict) and "answer" in cached_result:
                agent_answers.append({
                    "source": agent_type,
                    "answer": cached_result.get("answer", ""),
                    "citations": cached_result.get("citations", []),
                    "cached": True  # Mark as cached
                })
    
    # Error handling: no agent answers
    if not agent_answers:
        error_msg = (
            "I apologize, but I was unable to retrieve information from any of the selected sources. "
            "This could be due to:\n"
            "- Network or API issues\n"
            "- No relevant content found\n"
            "- Agent execution failures\n\n"
            "Please try rephrasing your query or selecting different sources."
        )
        return {"messages": [AIMessage(content=error_msg)]}
    
    # Organize agent results by source for tracking
    agent_results = {}
    successful_sources = []
    failed_sources = []
    
    for answer in agent_answers:
        source = answer.get("source", "unknown")
        answer_text = answer.get("answer", "")
        
        # Track successful vs failed agents
        if answer_text and answer_text.lower() not in [
            "unable to generate an answer.",
            "no information found",
            "error"
        ]:
            successful_sources.append(source)
            if source not in agent_results:
                agent_results[source] = []
            agent_results[source].append(answer)
        else:
            failed_sources.append(source)
    
    # Error handling: all agents failed
    if not agent_results:
        error_msg = (
            "I apologize, but all selected agents failed to retrieve information. "
            "This could indicate:\n"
            "- API connectivity issues\n"
            "- Invalid query format\n"
            "- No matching content available\n\n"
            "Please try rephrasing your query or check your API configurations."
        )
        return {"messages": [AIMessage(content=error_msg)]}
    
    # Log failed agents for debugging
    if failed_sources:
        print(f"⚠ Warning: Some agents failed to generate answers: {failed_sources}")
    
    # Collect all citations from all agents
    all_citations = []
    seen_citations = set()  # For deduplication
    
    for answer in agent_answers:
        citations = answer.get("citations", [])
        if isinstance(citations, list):
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                # Create unique key for deduplication (URL + title)
                citation_key = (
                    citation.get("url", ""),
                    citation.get("title", "")
                )
                if citation_key not in seen_citations and citation_key[0]:  # Only add if URL exists
                    seen_citations.add(citation_key)
                    all_citations.append(citation)
    
    # Prepare source info for aggregation prompt
    sources = list(agent_results.keys())
    source_info = {"sources": sources}
    
    # Create aggregation prompt with multi-source support
    aggregation_prompt = get_aggregation_prompt(
        state.get("originalQuery", ""),
        agent_answers,
        source_info=source_info
    )
    
    # Synthesize response
    # Gemini requires at least one non-system message, use HumanMessage instead of SystemMessage
    synthesis_response = llm.invoke([HumanMessage(content=aggregation_prompt)])
    
    # Update state with agent results and citations
    return {
        "messages": [AIMessage(content=synthesis_response.content)],
        "agent_results": agent_results,
        "citations": all_citations
    }