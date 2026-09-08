from typing import List
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """State for an individual source-agent subgraph."""
    question: str = ""
    tool_calls_used: int = 0
    question_index: int = 0
    final_answer: str = ""
    agent_answers: List[dict] = []
    citations: List[dict] = []
    source: str = ""
