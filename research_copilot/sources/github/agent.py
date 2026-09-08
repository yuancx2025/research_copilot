from typing import Optional, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_agent import BaseAgent
from research_copilot.runtime.schemas import SourceType, BaseCitation
from research_copilot.sources.github.prompts import get_github_agent_prompt
from research_copilot.sources.github.citations import GitHubCitation


class GitHubAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool]):
        super().__init__(SourceType.GITHUB, llm, tools)

    def get_system_prompt(self) -> str:
        return get_github_agent_prompt()

    def parse_citation(self, tool_name: str, tool_args: dict, tool_result: Any) -> Optional[BaseCitation]:
        if isinstance(tool_result, dict):
            if "error" in tool_result:
                return None
            try:
                return GitHubCitation.from_tool_result(tool_result, self.source_type)
            except Exception:
                return None
        return None
