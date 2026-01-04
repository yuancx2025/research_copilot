from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_web_agent_prompt
from research_copilot.agents.schemas import WebCitation, BaseCitation
from research_copilot.tools.base import SourceType
from research_copilot.tools.web_tools import WebToolkit

class WebAgent(BaseAgent):
    """
    Agent for web search and content extraction.
    
    Specialized in finding articles, tutorials, documentation, and web content.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        toolkit = WebToolkit(config)
        tools = toolkit.create_tools()
        super().__init__(SourceType.WEB, llm, tools)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for web search research."""
        return get_web_agent_prompt()
    
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse web tool results into validated WebCitation models.
        
        Extracts URLs, titles, and content snippets.
        Note: BaseAgent handles list iteration, so this only processes single items.
        """
        # Handle dict results
        if isinstance(tool_result, dict):
            url = tool_result.get("url", "")
            title = tool_result.get("title", "")
            # Only create citation if we have URL and valid title
            if url and title and len(title) > 5:
                return WebCitation.from_tool_result(tool_result, self.source_type)
        
        return None

