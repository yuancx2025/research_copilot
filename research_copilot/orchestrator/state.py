from typing import List, Annotated, Dict, Any
from langgraph.graph import MessagesState

def accumulate_or_reset(existing: List[dict], new: List[dict]) -> List[dict]:
    if new and any(item.get('__reset__') for item in new):
        return []
    return existing + new

class State(MessagesState):
    """State for main agent graph with multi-agent orchestration support"""
    questionIsClear: bool = False
    conversation_summary: str = ""
    originalQuery: str = "" 
    rewrittenQuestions: List[str] = []
    agent_answers: Annotated[List[dict], accumulate_or_reset] = []
    
    research_intent: List[str] = []
    available_sources: List[str] = []
    agent_results: Dict[str, List[dict]] = {}
    citations: Annotated[List[dict], accumulate_or_reset] = []
    research_session_id: str = ""
    
    active_agents: List[str] = []
    routing_decision: Dict[str, Any] = {}
    aggregation_strategy: str = "concat"
    max_iterations: int = 3
    current_iteration: int = 0
    
    cache_enabled: bool = False
    cached_results: Dict[str, dict] = {}
    
    create_study_plan: bool = False
    notion_page_url: str = ""
    study_plan_data: Dict[str, Any] = {}
