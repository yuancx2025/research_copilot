from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver
from functools import partial
from research_copilot.orchestrator.state import AgentState
from research_copilot.orchestrator.nodes import agent_node
from research_copilot.tools.base import SourceType
import logging

# CompiledGraph is the return type of StateGraph.compile()
# It's not directly importable, so we use Any for type hints
CompiledGraph = Any

logger = logging.getLogger(__name__)


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
            tools_condition, 
            {"tools": "tools", END: "extract_answer"}
        )
        agent_builder.add_edge("tools", "agent")
        agent_builder.add_edge("extract_answer", END)
        
        return agent_builder.compile(checkpointer=checkpointer)
    
    def extract_answer_with_citations(self, state: AgentState) -> Dict[str, Any]:
        """
        Extract final answer with citations from agent state.
        
        This method:
        1. Finds the final answer from AI messages
        2. Extracts citations from tool call results
        3. Formats result in standardized format
        
        Args:
            state: AgentState containing messages and question info
            
        Returns:
            Dictionary with final_answer and agent_answers
        """
        # Find final answer message (last AI message without tool calls)
        final_answer = "Unable to generate an answer."
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                # Handle Gemini's structured response format
                content = msg.content
                if isinstance(content, list):
                    # Extract text from Gemini's structured format
                    text_parts = [
                        item.get('text', '') 
                        for item in content 
                        if isinstance(item, dict) and 'text' in item
                    ]
                    final_answer = ' '.join(text_parts) if text_parts else str(content)
                elif isinstance(content, str):
                    final_answer = content
                else:
                    final_answer = str(content)
                break
        
        # Extract citations from tool calls and results
        citations = self._extract_citations_from_messages(state.get("messages", []))
        
        return {
            "final_answer": final_answer,
            "agent_answers": [{
                "index": state.get("question_index", 0),
                "question": state.get("question", ""),
                "answer": final_answer,
                "source": self.source_type.value,
                "citations": citations
            }]
        }
    
    def _extract_citations_from_messages(self, messages: List) -> List[dict]:
        """
        Extract citations from tool calls and their results.
        
        Improved implementation that:
        1. Tracks tool calls and their corresponding results
        2. Extracts source information from tool results
        3. Handles different tool result formats
        4. Creates structured citations
        
        Args:
            messages: List of messages from agent execution
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        tool_call_map = {}  # Map tool_call_id -> tool_call info
        
        # First pass: collect all tool calls
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_call_map[tool_call.get("id")] = {
                        "name": tool_call.get("name", ""),
                        "args": tool_call.get("args", {}),
                        "id": tool_call.get("id")
                    }
        
        # Second pass: extract citations from tool results
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", None)
                tool_call_info = tool_call_map.get(tool_call_id)
                
                if tool_call_info:
                    citation = self._parse_tool_result_to_citation(
                        tool_call_info["name"],
                        tool_call_info["args"],
                        msg.content
                    )
                    if citation:
                        citations.append(citation)
        
        return citations
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse tool result into a structured citation.
        
        This method should be overridden by subclasses for source-specific
        citation formatting.
        
        Args:
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
            tool_result: Result returned by the tool
            
        Returns:
            Citation dictionary or None if no citation can be extracted
        """
        # Default implementation - extract basic info
        # Subclasses should override for source-specific formatting
        
        # Handle string results (JSON strings)
        if isinstance(tool_result, str):
            try:
                import json
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Handle dict results
        if isinstance(tool_result, dict):
            # Try to extract common citation fields
            citation = {
                "source_type": self.source_type.value,
                "tool_name": tool_name,
                "url": tool_result.get("url") or tool_result.get("pdf_url") or tool_result.get("html_url"),
                "title": tool_result.get("title") or tool_result.get("name") or tool_name,
                "snippet": str(tool_result.get("content", ""))[:200] or str(tool_result.get("abstract", ""))[:200],
            }
            
            # Add source-specific metadata
            if "arxiv_id" in tool_result:
                citation["arxiv_id"] = tool_result["arxiv_id"]
            if "video_id" in tool_result:
                citation["video_id"] = tool_result["video_id"]
            if "repo" in tool_result:
                citation["repo"] = tool_result["repo"]
            
            # Only return if we have at least a URL or title
            if citation.get("url") or citation.get("title"):
                return citation
        
        # Handle list results (search results)
        elif isinstance(tool_result, list) and tool_result:
            # Return first result as primary citation
            return self._parse_tool_result_to_citation(tool_name, tool_args, tool_result[0])
        
        return None
    
    def format_result(self, answer: str, citations: List[dict]) -> Dict[str, Any]:
        """
        Format agent result in standardized format.
        
        Args:
            answer: The answer text
            citations: List of citation dictionaries
            
        Returns:
            Standardized result dictionary
        """
        return {
            "answer": answer,
            "citations": citations,
            "source": self.source_type.value
        }

