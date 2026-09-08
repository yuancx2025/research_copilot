from typing import Optional, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from research_copilot.runtime.base_agent import BaseAgent
from research_copilot.runtime.schemas import SourceType, BaseCitation
from research_copilot.sources.youtube.prompts import get_youtube_agent_prompt
from research_copilot.sources.youtube.citations import YouTubeCitation


class YouTubeAgent(BaseAgent):
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool]):
        super().__init__(SourceType.YOUTUBE, llm, tools)

    def get_system_prompt(self) -> str:
        return get_youtube_agent_prompt()

    def parse_citation(self, tool_name: str, tool_args: dict, tool_result: Any) -> Optional[BaseCitation]:
        if isinstance(tool_result, dict):
            if tool_name == "get_youtube_transcript" or "transcript" in tool_result:
                return None
            video_id = tool_result.get("video_id", "")
            if not video_id:
                return None
            title = tool_result.get("title", "")
            if title and (title.startswith("Transcript:") or (
                len(title) <= 15 and title.replace("_", "").replace("-", "").isalnum()
            )):
                return None
            try:
                return YouTubeCitation.from_tool_result(tool_result, self.source_type)
            except Exception:
                return None
        return None
