from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage, AIMessage
from .state import State, AgentState
from .schemas import QueryAnalysis, ResearchIntent
from .prompts import *
from research_copilot.core.llm_utils import extract_content_as_string
import logging

logger = logging.getLogger(__name__)


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
    summary_text = extract_content_as_string(summary_response)
    return {"conversation_summary": summary_text, "agent_answers": [{"__reset__": True}]}

def analyze_and_rewrite_query(state: State, llm):
    # Skip analysis if creating study plan - data already in state
    if state.get("create_study_plan", False):
        # Preserve messages and state for Notion agent
        return {
            "questionIsClear": True,  # Allow routing to proceed
            "messages": state.get("messages", []),  # Keep original messages
            "originalQuery": state.get("originalQuery", ""),
            "rewrittenQuestions": state.get("rewrittenQuestions", [])
        }
    
    last_message = state["messages"][-1]
    conversation_summary = state.get("conversation_summary", "")

    prompt = get_query_analysis_prompt(last_message.content, conversation_summary)

    try:
        llm_with_structure = llm.with_config(temperature=0.1).with_structured_output(QueryAnalysis)
        # Gemini requires at least one non-system message, use HumanMessage instead of SystemMessage
        response = llm_with_structure.invoke([HumanMessage(content=prompt)])
        
        # Handle case where structured output returns None (Gemini 3 issue)
        if response is None:
            # Fallback: treat as clear and use original query
            return {
                "questionIsClear": True,
                "messages": [],
                "originalQuery": last_message.content,
                "rewrittenQuestions": [last_message.content]
            }
        
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
                "rewrittenQuestions": response.questions if hasattr(response, 'questions') else [last_message.content]
            }
        else:
            clarification = (response.clarification_needed if hasattr(response, 'clarification_needed') else None) or "I need more information to understand your question."
            return {
                "questionIsClear": False,
                "messages": [AIMessage(content=clarification)]
            }
    except Exception as e:
        # Fallback on any error: treat as clear and use original query
        logger.warning(f"Error in query analysis: {e}. Treating query as clear.")
        return {
            "questionIsClear": True,
            "messages": [],
            "originalQuery": last_message.content,
            "rewrittenQuestions": [last_message.content]
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
        
        # Handle case where structured output returns None (Gemini 3 issue)
        if intent is None:
            # Fallback: analyze query text to determine agents
            query_lower = query.lower()
            selected_agents = []
            
            # Check for explicit source mentions (case-insensitive)
            if any(term in query_lower for term in ["arxiv", "arxiv.org"]):
                selected_agents.append("arxiv")
            elif any(term in query_lower for term in ["paper", "research paper", "publication", "research"]):
                selected_agents.append("arxiv")
            
            if any(term in query_lower for term in ["youtube", "youtu.be", "video", "tutorial", "lecture"]):
                selected_agents.append("youtube")
            
            if any(term in query_lower for term in ["github", "github.com", "code", "repository", "repo", "implementation"]):
                selected_agents.append("github")
            
            if any(term in query_lower for term in ["web", "article", "blog", "documentation", "website"]):
                selected_agents.append("web")
            
            # If query explicitly mentions sources, use only those; otherwise include all
            if not selected_agents:
                # No explicit mentions, include all sources
                selected_agents = ["arxiv", "youtube", "github", "web", "local"]
            else:
                # Add local for RAG search, but don't add web if not explicitly mentioned
                if "local" not in selected_agents:
                    selected_agents.append("local")
            
            return {
                "research_intent": selected_agents,
                "routing_decision": {
                    "reasoning": f"Structured output returned None. Analyzed query keywords to select agents: {', '.join(selected_agents)}",
                    "confidence": 0.7
                },
                "active_agents": selected_agents
            }
        
        # Validate agent names (filter invalid ones)
        valid_agents = ["arxiv", "youtube", "github", "web", "local"]
        filtered_agents = [a for a in (intent.agents if hasattr(intent, 'agents') and intent.agents else []) if a in valid_agents]
        
        # Default fallback if no valid agents
        if not filtered_agents:
            # Analyze query to determine agents
            query_lower = query.lower()
            if any(term in query_lower for term in ["arxiv", "arxiv.org"]):
                filtered_agents.append("arxiv")
            elif any(term in query_lower for term in ["paper", "research paper", "publication", "research"]):
                filtered_agents.append("arxiv")
            
            if any(term in query_lower for term in ["youtube", "youtu.be", "video", "tutorial", "lecture"]):
                filtered_agents.append("youtube")
            
            if any(term in query_lower for term in ["github", "github.com", "code", "repository", "repo", "implementation"]):
                filtered_agents.append("github")
            
            if any(term in query_lower for term in ["web", "article", "blog", "documentation", "website"]):
                filtered_agents.append("web")
            
            # If still no agents found, include all
            if not filtered_agents:
                filtered_agents = ["arxiv", "youtube", "github", "web", "local"]
            else:
                # Add local for RAG search
                if "local" not in filtered_agents:
                    filtered_agents.append("local")
        
        return {
            "research_intent": filtered_agents,
            "routing_decision": {
                "reasoning": (intent.reasoning if hasattr(intent, 'reasoning') else "Selected agents based on query analysis"),
                "confidence": (intent.confidence if hasattr(intent, 'confidence') else 0.7),
                "suggested_queries": (intent.suggested_queries if hasattr(intent, 'suggested_queries') and intent.suggested_queries else {})
            },
            "active_agents": filtered_agents
        }
    except Exception as e:
        # Error handling: default to safe fallback with keyword analysis
        logger.warning(f"Error in intent classification: {e}")
        query_lower = query.lower()
        fallback_agents = []
        
        # Analyze query keywords - prioritize explicit mentions
        if any(term in query_lower for term in ["arxiv", "arxiv.org"]):
            fallback_agents.append("arxiv")
        elif any(term in query_lower for term in ["paper", "research paper", "publication", "research"]):
            fallback_agents.append("arxiv")
        
        if any(term in query_lower for term in ["youtube", "youtu.be", "video", "tutorial", "lecture"]):
            fallback_agents.append("youtube")
        
        if any(term in query_lower for term in ["github", "github.com", "code", "repository", "repo", "implementation"]):
            fallback_agents.append("github")
        
        if any(term in query_lower for term in ["web", "article", "blog", "documentation", "website"]):
            fallback_agents.append("web")
        
        # If no explicit mentions, include all sources
        if not fallback_agents:
            fallback_agents = ["arxiv", "youtube", "github", "web", "local"]
        else:
            # Add local for RAG search
            if "local" not in fallback_agents:
                fallback_agents.append("local")
        
        return {
            "research_intent": fallback_agents,
            "routing_decision": {
                "reasoning": f"Intent classification failed: {str(e)}. Analyzed query keywords to select agents: {', '.join(fallback_agents)}",
                "confidence": 0.6
            },
            "active_agents": fallback_agents
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
            # Extract text properly (handles Gemini's list format)
            answer_text = extract_content_as_string(msg.content)
            res = {
                "final_answer": answer_text,
                "agent_answers": [{
                    "index": state["question_index"],
                    "question": state["question"],
                    "answer": answer_text
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
    # Special case: if create_study_plan is True, we might not have agent_answers
    # (research was done previously, we're just creating the study plan)
    if not agent_answers:
        if state.get("create_study_plan", False):
            # Study plan creation mode - research data already in state
            # Just pass through to allow Notion agent to proceed
            return {
                "messages": state.get("messages", []),
                "agent_results": state.get("agent_results", {}),
                "citations": state.get("citations", [])
            }
        
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
    
    # Collect all citations from all agents, filtering for relevance
    all_citations = []
    seen_citations = set()  # For deduplication
    original_query = state.get("originalQuery", "").lower()
    
    def is_citation_relevant(citation: dict, answer_text: str, query: str) -> bool:
        """
        Check if a citation is relevant by:
        1. Checking if it's mentioned in the answer text
        2. Checking if it matches the query topic
        3. Being permissive - if agent was invoked, include citations unless clearly irrelevant
        """
        if not citation:
            return False
        
        title = citation.get("title", "").lower()
        url = citation.get("url", "").lower()
        snippet = citation.get("snippet", "").lower()
        answer_lower = answer_text.lower()
        
        # Skip transcript IDs (YouTube)
        if citation.get("source_type") == "youtube":
            if title.startswith("transcript:") or (
                len(title) <= 15 and 
                title.replace("_", "").replace("-", "").isalnum()
            ):
                return False
        
        # Check if citation is mentioned in answer (title, URL, or arxiv ID)
        arxiv_id = citation.get("metadata", {}).get("arxiv_id", "")
        if arxiv_id:
            arxiv_id_lower = arxiv_id.lower()
            if arxiv_id_lower in answer_lower or f"arxiv:{arxiv_id_lower}" in answer_lower:
                return True
        
        # Check if title appears in answer (more lenient - just 1 keyword match)
        if title and len(title) > 10:
            # Extract key words from title (3+ chars)
            title_words = [w for w in title.split() if len(w) >= 3]
            if title_words:
                # Check if at least 1 key word from title appears in answer (relaxed from 2)
                matches = sum(1 for word in title_words[:5] if word in answer_lower)
                if matches >= 1:
                    return True
        
        # Check URL in answer
        if url and url in answer_lower:
            return True
        
        # If citation not mentioned, check query relevance as fallback (more lenient)
        if query:
            query_words = [w for w in query.split() if len(w) >= 3]  # Lower threshold from 4 to 3
            if query_words:
                # Check if citation title/snippet contains query terms (1 match instead of 2)
                citation_text = f"{title} {snippet}"
                query_matches = sum(1 for word in query_words[:5] if word in citation_text)
                if query_matches >= 1:  # Relaxed from 2 to 1
                    return True
        
        # More permissive: if citation has a valid URL and title, include it
        # This ensures citations from invoked agents are included even if not explicitly mentioned
        if url and title and len(title) > 5:
            # Only exclude if clearly irrelevant (contains common irrelevant terms)
            irrelevant_terms = ["error", "not found", "404", "invalid"]
            if not any(term in title for term in irrelevant_terms):
                return True
        
        return False
    
    for answer in agent_answers:
        citations = answer.get("citations", [])
        source = answer.get("source", "unknown")
        answer_text = answer.get("answer", "")
        
        if isinstance(citations, list):
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                
                # Filter: only include citations that are relevant
                if not is_citation_relevant(citation, answer_text, original_query):
                    continue
                
                # Create unique key for deduplication (normalize URL and title)
                citation_url = citation.get("url", "").strip()
                citation_title = citation.get("title", "").strip()
                
                # Normalize URL (remove trailing slashes, fragments, but preserve query params for YouTube)
                if citation_url:
                    # For YouTube URLs, preserve the video ID in query params
                    if "youtube.com/watch" in citation_url or "youtu.be/" in citation_url:
                        import re
                        # Extract video ID from YouTube URL
                        youtube_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', citation_url)
                        if youtube_match:
                            video_id = youtube_match.group(1)
                            citation_url = f"https://www.youtube.com/watch?v={video_id}"
                        else:
                            # If no video ID found, keep original URL
                            citation_url = citation_url.rstrip('/').split('#')[0]
                    else:
                        # For other URLs, remove query params and fragments
                        citation_url = citation_url.rstrip('/').split('#')[0].split('?')[0]
                        # Normalize ArXiv URLs: pdf/abs URLs point to same paper
                        # Convert pdf URLs to abs URLs and remove version suffix for consistent deduplication
                        if "arxiv.org" in citation_url:
                            # Extract arxiv ID from URL (handles both pdf and abs URLs)
                            import re
                            arxiv_match = re.search(r'arxiv\.org/(?:pdf|abs|html)/([\d.]+)(?:v\d+)?', citation_url)
                            if arxiv_match:
                                arxiv_id = arxiv_match.group(1)  # Base ID without version
                                citation_url = f"https://arxiv.org/abs/{arxiv_id}"
                
                citation_key = (citation_url.lower(), citation_title.lower())
                
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
    
    # Extract text content properly (handles Gemini's list format)
    final_answer_text = extract_content_as_string(synthesis_response)
    
    # Update state with agent results and citations
    return {
        "messages": [AIMessage(content=final_answer_text)],
        "agent_results": agent_results,
        "citations": all_citations
    }