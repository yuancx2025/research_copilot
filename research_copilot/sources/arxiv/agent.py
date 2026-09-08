from typing import Optional, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_agent import BaseAgent
from research_copilot.runtime.schemas import SourceType, BaseCitation
from research_copilot.sources.arxiv.prompts import get_arxiv_agent_prompt
from research_copilot.sources.arxiv.citations import ArxivCitation


class ArxivAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool]):
        super().__init__(SourceType.ARXIV, llm, tools)

    def get_system_prompt(self) -> str:
        return get_arxiv_agent_prompt()

    def parse_citation(self, tool_name: str, tool_args: dict, tool_result: Any) -> Optional[BaseCitation]:
        if isinstance(tool_result, dict):
            if tool_result.get("error") or tool_result.get("message"):
                return None
            return ArxivCitation.from_tool_result(tool_result, self.source_type)
        return None
