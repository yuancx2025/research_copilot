from typing import Dict, Any, List, Optional
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_local_rag_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.local_tools import LocalToolkit
from research_copilot.orchestrator.state import AgentState
import json

class LocalRAGAgent(BaseAgent):
    """
    Agent for searching locally indexed documents.
    
    Maintains backward compatibility with existing document search functionality
    while providing structured citations and source tracking.
    """
    
    def __init__(self, llm: BaseChatModel, collection, config):
        toolkit = LocalToolkit(config, collection)
        tools = toolkit.create_tools()
        super().__init__(SourceType.LOCAL, llm, tools)
        self.collection = collection
    
    def get_system_prompt(self) -> str:
        """Return system prompt for local document search."""
        return get_local_rag_agent_prompt()
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse local document tool results into citations.
        
        Extracts document source paths and creates structured citations.
        """
        # Handle string results (JSON strings)
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                # If it's not JSON, might be a list string
                if tool_result.startswith('['):
                    try:
                        tool_result = eval(tool_result)  # Fallback for list strings
                    except:
                        return None
                else:
                    return None
        
        # Handle list results (search results)
        if isinstance(tool_result, list):
            citations = []
            seen_sources = set()
            
            for item in tool_result:
                if isinstance(item, dict):
                    source = item.get("source", "")
                    if source and source not in seen_sources:
                        seen_sources.add(source)
                        citation = {
                            "source_type": self.source_type.value,
                            "tool_name": tool_name,
                            "title": source.split("/")[-1] if "/" in source else source,  # Filename
                            "url": f"local://{source}",  # Local URI format
                            "snippet": item.get("content", "")[:200],
                            "metadata": {
                                "parent_id": item.get("parent_id", ""),
                                "source_path": source
                            }
                        }
                        citations.append(citation)
            
            # Return first citation if single, or create aggregate citation
            if len(citations) == 1:
                return citations[0]
            elif citations:
                # Aggregate multiple sources
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"{len(citations)} documents",
                    "url": "local://multiple",
                    "snippet": f"Found in {len(citations)} document(s)",
                    "metadata": {
                        "sources": [c["metadata"]["source_path"] for c in citations],
                        "count": len(citations)
                    }
                }
            return None
        
        # Handle dict results (single result)
        if isinstance(tool_result, dict):
            source = tool_result.get("source", "")
            if not source:
                return None
            
            return {
                "source_type": self.source_type.value,
                "tool_name": tool_name,
                "title": source.split("/")[-1] if "/" in source else source,
                "url": f"local://{source}",
                "snippet": tool_result.get("content", "")[:200],
                "metadata": {
                    "parent_id": tool_result.get("parent_id", ""),
                    "source_path": source
                }
            }
        
        return None

