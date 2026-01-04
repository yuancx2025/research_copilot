from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_arxiv_agent_prompt
from research_copilot.agents.schemas import ArxivCitation, BaseCitation
from research_copilot.tools.base import SourceType
from research_copilot.tools.arxiv_tools import ArxivToolkit

class ArxivAgent(BaseAgent):
    """
    Agent for searching and analyzing ArXiv academic papers.
    
    Specialized in academic research, paper analysis, and literature review.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        toolkit = ArxivToolkit(config)
        tools = toolkit.create_tools()
        super().__init__(SourceType.ARXIV, llm, tools)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for ArXiv paper research."""
        return get_arxiv_agent_prompt()
    
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse ArXiv tool results into validated ArxivCitation models.
        
        Extracts ArXiv IDs, titles, authors, and publication dates.
        Note: BaseAgent handles list iteration, so this only processes single items.
        """
        # Handle dict results (single paper)
        if isinstance(tool_result, dict):
            if tool_result.get("error") or tool_result.get("message"):
                return None
            return ArxivCitation.from_tool_result(tool_result, self.source_type)
        
        return None