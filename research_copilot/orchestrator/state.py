from typing import List, Annotated, Dict, Any
from langgraph.graph import MessagesState

def accumulate_or_reset(existing: List[dict], new: List[dict]) -> List[dict]:
    if new and any(item.get('__reset__') for item in new):
        return []
    return existing + new

class State(MessagesState):
    """State for main agent graph with multi-agent orchestration support"""
    # Existing fields
    questionIsClear: bool = False
    conversation_summary: str = ""
    originalQuery: str = "" 
    rewrittenQuestions: List[str] = []
    agent_answers: Annotated[List[dict], accumulate_or_reset] = []
    
    # Phase 1: Multi-agent orchestration fields
    research_intent: List[str] = []  # Which agents to invoke (e.g., ["arxiv", "youtube"])
    agent_results: Dict[str, List[dict]] = {}  # Results from each specialized agent
    citations: Annotated[List[dict], accumulate_or_reset] = []  # Unified citation tracking
    research_session_id: str = ""  # Session tracking
    
    # Phase 3: Orchestration control fields (needed for routing)
    active_agents: List[str] = []  # Track which agents are currently running
    routing_decision: Dict[str, Any] = {}  # Store orchestrator's routing logic and reasoning
    aggregation_strategy: str = "concat"  # How to merge multi-agent results: "concat", "synthesize", "hierarchical"
    max_iterations: int = 3  # Prevent infinite loops in agent routing
    current_iteration: int = 0  # Track routing depth/iteration count
    
    # Phase 4: Research cache support
    cache_enabled: bool = False  # Whether cache is enabled for this session
    cached_results: Dict[str, dict] = {}  # Cached agent results (agent_type -> result)
    
    # Phase 5: Notion agent support
    create_study_plan: bool = False  # Flag to trigger study plan creation
    notion_page_url: str = ""  # URL of created Notion page
    study_plan_data: Dict[str, Any] = {}  # Generated study plan structure

class AgentState(MessagesState):
    """State for individual agent subgraph"""
    question: str = ""
    question_index: int = 0
    final_answer: str = ""
    agent_answers: List[dict] = []
    citations: List[dict] = []  # Agent-specific citations
    source: str = ""  # Agent source type (e.g., "arxiv", "youtube")