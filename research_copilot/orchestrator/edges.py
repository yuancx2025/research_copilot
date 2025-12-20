from typing import Literal, List, Optional
from langgraph.types import Send
from .state import State, AgentState
from research_copilot.config import settings as config
def route_after_rewrite(state: State) -> Literal["human_input", "process_question"]:
    if not state.get("questionIsClear", False):
        return "human_input"
    else:
        return [
                Send("process_question", {"question": query, "question_index": idx, "messages": []})
                for idx, query in enumerate(state["rewrittenQuestions"])
            ]


def route_to_agents(state: State) -> List[Send]:
    """
    Routes to appropriate agent subgraphs based on research_intent.
    
    Creates Send objects for parallel agent execution.
    Returns list of Send objects, one per agent to invoke.
    
    Error handling:
    - Empty research_intent: defaults to ["local", "web"]
    - Invalid agent names: filtered out with warning
    - No query: returns empty list (will be handled downstream)
    
    Args:
        state: Current graph state with research_intent field
        
    Returns:
        List of Send objects targeting agent nodes for parallel execution
    """
    research_intent = state.get("research_intent", [])
    
    # Error handling: empty research_intent
    if not research_intent:
        print("⚠ Warning: Empty research_intent, defaulting to ['local', 'web']")
        research_intent = ["local", "web"]
    
    # Get query from rewritten questions or original query
    query = ""
    if state.get("rewrittenQuestions"):
        query = state["rewrittenQuestions"][0]
    elif state.get("originalQuery"):
        query = state["originalQuery"]
    else:
        # Fallback: try to get from messages
        if state.get("messages"):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, 'content'):
                query = last_msg.content
    
    if not query:
        # No query available - this should not happen, but handle gracefully
        print("⚠ Warning: No query found for agent routing")
        return []
    
    # Map intent names to agent node names
    intent_to_agent = {
        "arxiv": "arxiv_agent",
        "youtube": "youtube_agent",
        "github": "github_agent",
        "web": "web_agent",
        "local": "local_agent"
    }
    
    # Check cache if enabled
    cache_enabled = state.get("cache_enabled", False) and getattr(config, 'ENABLE_RESEARCH_CACHE', False)
    cached_results = state.get("cached_results", {})
    
    # Create Send objects for each agent in research_intent
    sends = []
    invalid_intents = []
    cache_hits = []
    
    for intent in research_intent:
        agent_name = intent_to_agent.get(intent)
        if agent_name:
            # Check cache first if enabled
            cache_key = f"{intent}:{query.lower().strip()}"
            if cache_enabled and cache_key in cached_results:
                cache_hits.append(intent)
                # Skip creating Send for cached results - they'll be added in aggregate
                continue
            
            # Create AgentState for the agent subgraph
            agent_state = {
                "question": query,
                "question_index": 0,
                "messages": [],
                "source": intent  # Store source type for citation tracking
            }
            sends.append(Send(agent_name, agent_state))
        else:
            # Invalid agent name, track for warning
            invalid_intents.append(intent)
    
    # Log cache hits
    if cache_hits:
        print(f"✓ Cache hits for agents: {cache_hits}")
    
    # Error handling: invalid agent names
    if invalid_intents:
        print(f"⚠ Warning: Invalid agent intents filtered out: {invalid_intents}")
    
    # Error handling: no valid agents to route to
    if not sends:
        print("⚠ Warning: No valid agents to route to, defaulting to ['local', 'web']")
        # Fallback to local and web agents
        for intent in ["local", "web"]:
            agent_name = intent_to_agent[intent]
            agent_state = {
                "question": query,
                "question_index": 0,
                "messages": [],
                "source": intent
            }
            sends.append(Send(agent_name, agent_state))
    
    return sends