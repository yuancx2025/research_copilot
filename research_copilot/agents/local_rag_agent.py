from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_local_rag_agent_prompt
from research_copilot.agents.schemas import LocalCitation, BaseCitation
from research_copilot.tools.base import SourceType
from research_copilot.tools.local_tools import LocalToolkit

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
    
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse local document tool results into validated LocalCitation models.
        
        Extracts document source paths and creates structured citations.
        Note: BaseAgent handles list iteration, so this only processes single items.
        """
        # Handle dict results (single result)
        if isinstance(tool_result, dict):
            return LocalCitation.from_tool_result(tool_result, self.source_type)
        
        return None

