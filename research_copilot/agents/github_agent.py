from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_github_agent_prompt
from research_copilot.agents.schemas import GitHubCitation, BaseCitation
from research_copilot.tools.base import SourceType
from research_copilot.tools.github_tools import GitHubToolkit

class GitHubAgent(BaseAgent):
    """
    Agent for searching GitHub repositories and analyzing code.
    
    Specialized in code analysis, repository exploration, and technical documentation.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        toolkit = GitHubToolkit(config)
        tools = toolkit.create_tools()
        super().__init__(SourceType.GITHUB, llm, tools)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for GitHub repository research."""
        return get_github_agent_prompt()
    
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse GitHub tool results into validated GitHubCitation models.
        
        Extracts repository URLs, file paths, and code content.
        Note: BaseAgent handles list iteration, so this only processes single items.
        """
        # Handle dict results
        if isinstance(tool_result, dict):
            # Skip error results
            if "error" in tool_result:
                return None
            try:
                citation = GitHubCitation.from_tool_result(tool_result, self.source_type)
                return citation
            except Exception as e:
                return None
        
        return None

