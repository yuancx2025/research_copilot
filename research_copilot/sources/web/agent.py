from typing import Optional, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_agent import BaseAgent
from research_copilot.runtime.schemas import SourceType, BaseCitation
from research_copilot.sources.web.prompts import get_web_agent_prompt
from research_copilot.sources.web.citations import WebCitation


class WebAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool]):
        super().__init__(SourceType.WEB, llm, tools)

    def get_system_prompt(self) -> str:
        return get_web_agent_prompt()

    def parse_citation(self, tool_name: str, tool_args: dict, tool_result: Any) -> Optional[BaseCitation]:
        if isinstance(tool_result, dict):
            url = tool_result.get("url", "")
            title = tool_result.get("title", "")
            if url and title and len(title) > 5:
                return WebCitation.from_tool_result(tool_result, self.source_type)
        return None
