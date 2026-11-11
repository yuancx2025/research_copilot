from typing import Optional, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_agent import BaseAgent
from research_copilot.runtime.schemas import SourceType, BaseCitation
from research_copilot.sources.local.prompts import get_local_rag_agent_prompt
from research_copilot.sources.local.citations import LocalCitation, select_local_citations

PARENT_TOOL = "retrieve_document_context"


class LocalRAGAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool]):
        super().__init__(SourceType.LOCAL, llm, tools)

    def get_system_prompt(self) -> str:
        return get_local_rag_agent_prompt()

    def parse_citation(self, tool_name: str, tool_args: dict, tool_result: Any) -> Optional[BaseCitation]:
        if not isinstance(tool_result, dict) or "error" in tool_result:
            return None
        if tool_name == PARENT_TOOL:
            return LocalCitation.from_parent(tool_result, self.source_type)
        return LocalCitation.from_tool_result(tool_result, self.source_type)

    def select_citations(self, answer: str, citations: List[BaseCitation]) -> List[BaseCitation]:
        return select_local_citations(answer, [c for c in citations if isinstance(c, LocalCitation)])
