from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Literal
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver
from functools import partial
from research_copilot.orchestrator.state import AgentState
from research_copilot.orchestrator.nodes import agent_node
from research_copilot.tools.base import SourceType
from research_copilot.agents.schemas import BaseCitation
import logging
import json

# CompiledGraph is the return type of StateGraph.compile()
# It's not directly importable, so we use Any for type hints
CompiledGraph = Any

logger = logging.getLogger(__name__)

# Maximum number of tool calls allowed per agent execution
MAX_TOOL_CALLS_PER_AGENT = 10

# Maximum number of citations to extract per agent (prevents citation explosion)
MAX_TOTAL_CITATIONS_PER_AGENT = 10


def should_continue_with_limit(state: AgentState) -> Literal["tools", "extract_answer"]:
    """
    Conditional routing function that enforces max tool call limit.
    
    Prevents infinite loops by limiting the number of tool calls.
    After MAX_TOOL_CALLS_PER_AGENT tool calls, forces extraction of answer.
    
    Args:
        state: AgentState containing messages
        
    Returns:
        "tools" if more tool calls are allowed and present, "extract_answer" otherwise
    """
    # Count total tool calls in the conversation
    tool_call_count = sum(
        1 for m in state.get("messages", [])
        if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls
    )
    
    # Enforce limit: if we've exceeded max tool calls, force extraction
    if tool_call_count >= MAX_TOOL_CALLS_PER_AGENT:
        logger.warning(
            f"Agent reached max tool call limit ({MAX_TOOL_CALLS_PER_AGENT}). "
            "Forcing answer extraction."
        )
        return "extract_answer"
    
    # Otherwise, check if last message has tool calls (same logic as tools_condition)
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
    
    # No tool calls, extract answer
    return "extract_answer"


class BaseAgent(ABC):
    """
    Abstract base class for all specialized research agents.
    
    Provides common interface for:
    - Agent subgraph creation
    - Tool management and LLM binding
    - Standardized result format with citations
    - Citation extraction from tool calls
    """
    
    def __init__(self, source_type: SourceType, llm: BaseChatModel, tools: List[BaseTool]):
        self.source_type = source_type
        self.llm = llm
        self.tools = tools

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return agent-specific system prompt."""
        pass
    
    @abstractmethod
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse tool result into a validated Citation model, should be overridden
        
        Args:
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
            tool_result: Result returned by the tool
            
        Returns:
            Citation model instance or None if no citation can be extracted
        """
        pass
    
    def create_agent_subgraph(self) -> CompiledGraph:
        """
        Create a compiled agent subgraph with tools.
        
        Returns:
            Compiled LangGraph subgraph ready for execution
        """
        llm_with_tools = self.llm.bind_tools(self.tools)
        tool_node = ToolNode(self.tools)
        
        checkpointer = InMemorySaver()
        
        # Create agent-specific node with custom system prompt
        agent_node_func = partial(
            agent_node, 
            llm_with_tools=llm_with_tools,
            system_prompt=self.get_system_prompt()
        )
        
        agent_builder = StateGraph(AgentState)
        agent_builder.add_node("agent", agent_node_func)
        agent_builder.add_node("tools", tool_node)
        agent_builder.add_node("extract_answer", self.extract_answer_with_citations)
        
        agent_builder.add_edge(START, "agent")
        agent_builder.add_conditional_edges(
            "agent", 
            should_continue_with_limit, 
            {"tools": "tools", "extract_answer": "extract_answer"}
        )
        agent_builder.add_edge("tools", "agent")
        agent_builder.add_edge("extract_answer", END)
        
        return agent_builder.compile(checkpointer=checkpointer)
    
    def extract_answer_with_citations(self, state: AgentState) -> Dict[str, Any]:
        """
        Extract final answer and citations from agent state.
        
        Simplified implementation that:
        1. Finds the final answer from AI messages
        2. Extracts citations from tool results using parse_citation
        3. Returns validated Citation models
        
        Args:
            state: AgentState containing messages and question info
            
        Returns:
            Dictionary with final_answer and agent_answers
        """
        # Find final answer message (last AI message without tool calls)
        final_answer = "Unable to generate an answer."
        messages = state.get("messages", [])
        for msg in reversed(messages):
            tool_calls = getattr(msg, "tool_calls", None)
            has_no_tool_calls = tool_calls is None or tool_calls == []
            if isinstance(msg, AIMessage) and has_no_tool_calls:
                # Handle Gemini's structured response format
                content = getattr(msg, 'content', None)
                if content:
                    if isinstance(content, list):
                        # Extract text from Gemini's structured response format
                        text_parts = [
                            item.get('text', '') 
                            for item in content 
                            if isinstance(item, dict) and 'text' in item
                        ]
                        final_answer = ' '.join(text_parts) if text_parts else str(content)
                    elif isinstance(content, str):
                        final_answer = content.strip() if content.strip() else None
                    else:
                        final_answer = str(content)
                    
                    if final_answer:
                        break
        
        # Extract citations from tool calls and results
        citations = []
        tool_call_map = {}  # Map tool_call_id -> tool_call info
        
        # Collect all tool calls
        messages = state.get("messages", [])
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_call_map[tool_call.get("id")] = {
                        "name": tool_call.get("name", ""),
                        "args": tool_call.get("args", {})
                    }
        
        # Extract citations from tool results using parse_citation
        # Handle lists in one place: iterate through list items (up to cap of 10)
        MAX_CITATIONS_PER_TOOL_RESULT = 10
        seen_keys = set()  # For deduplication
        total_citations_added = 0  # Track total citations to enforce global limit
        
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", None)
                tool_call_info = tool_call_map.get(tool_call_id)
                
                if tool_call_info:
                    # Parse tool result - try JSON parsing, but keep as string if it fails
                    tool_result = msg.content
                    if isinstance(tool_result, str):
                        try:
                            tool_result = json.loads(tool_result)
                        except (json.JSONDecodeError, ValueError):
                            # Not JSON - keep as string and let parse_citation decide
                            pass
                    
                    # Handle lists: iterate through items (up to cap)
                    if isinstance(tool_result, list):
                        for item in tool_result[:MAX_CITATIONS_PER_TOOL_RESULT]:
                            # Stop if we've hit the total citation limit
                            if total_citations_added >= MAX_TOTAL_CITATIONS_PER_AGENT:
                                logger.info(
                                    f"Reached maximum citation limit ({MAX_TOTAL_CITATIONS_PER_AGENT}) "
                                    f"for {self.source_type.value} agent. Stopping citation extraction."
                                )
                                break
                            
                            try:
                                citation = self.parse_citation(
                                    tool_call_info["name"],
                                    tool_call_info["args"],
                                    item
                                )
                                if citation:
                                    # Deduplicate using stable key
                                    dedup_key = citation.get_deduplication_key()
                                    if dedup_key and dedup_key not in seen_keys:
                                        seen_keys.add(dedup_key)
                                        citations.append(citation)
                                        total_citations_added += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse citation from {tool_call_info['name']}: {e}. "
                                    "Skipping this citation."
                                )
                                continue
                    else:
                        # Handle single item (dict, string, or other)
                        # Stop if we've hit the total citation limit
                        if total_citations_added >= MAX_TOTAL_CITATIONS_PER_AGENT:
                            logger.info(
                                f"Reached maximum citation limit ({MAX_TOTAL_CITATIONS_PER_AGENT}) "
                                f"for {self.source_type.value} agent."
                            )
                        else:
                            try:
                                citation = self.parse_citation(
                                    tool_call_info["name"],
                                    tool_call_info["args"],
                                    tool_result
                                )
                                if citation:
                                    # Deduplicate using stable key
                                    dedup_key = citation.get_deduplication_key()
                                    if dedup_key and dedup_key not in seen_keys:
                                        seen_keys.add(dedup_key)
                                        citations.append(citation)
                                        total_citations_added += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse citation from {tool_call_info['name']}: {e}. "
                                    "Skipping this citation."
                            )
        
        # Convert Pydantic models to dicts for backward compatibility
        citations_dict = [citation.to_dict() for citation in citations]
        
        # If no answer found but we have citations, generate a summary from citations
        if final_answer == "Unable to generate an answer." and citations_dict:
            # Generate a summary from the citations
            citation_summaries = []
            for cit in citations_dict[:5]:  # Use first 5 citations
                if self.source_type == SourceType.YOUTUBE:
                    title = cit.get("title", "")
                    if title:
                        citation_summaries.append(f"Video: {title}")
                elif self.source_type == SourceType.GITHUB:
                    repo = cit.get("repository", "") or cit.get("url", "")
                    if repo:
                        citation_summaries.append(f"Repository: {repo}")
                elif self.source_type == SourceType.ARXIV:
                    title = cit.get("title", "")
                    if title:
                        citation_summaries.append(f"Paper: {title}")
                elif self.source_type == SourceType.WEB:
                    title = cit.get("title", "")
                    url = cit.get("url", "")
                    if title:
                        citation_summaries.append(f"{title}")
            
            if citation_summaries:
                final_answer = f"Found {len(citations_dict)} relevant result(s). " + " ".join(citation_summaries[:3])
        
        return {
            "final_answer": final_answer,
            "agent_answers": [{
                "index": state.get("question_index", 0),
                "question": state.get("question", ""),
                "answer": final_answer,
                "source": self.source_type.value,
                "citations": citations_dict
            }]
        }

