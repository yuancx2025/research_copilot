from typing import Optional, Any
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_youtube_agent_prompt
from research_copilot.agents.schemas import YouTubeCitation, BaseCitation
from research_copilot.tools.base import SourceType
from research_copilot.tools.youtube_tools import YouTubeToolkit

class YouTubeAgent(BaseAgent):
    """
    Agent for searching YouTube videos and extracting educational content.
    
    Specialized in video tutorials, lectures, and educational content analysis.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        toolkit = YouTubeToolkit(config)
        tools = toolkit.create_tools()
        super().__init__(SourceType.YOUTUBE, llm, tools)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for YouTube video research."""
        return get_youtube_agent_prompt()
    
    def parse_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[BaseCitation]:
        """
        Parse YouTube tool results into validated YouTubeCitation models.
        
        Extracts video IDs, URLs, titles, channels, and timestamps.
        Note: BaseAgent handles list iteration, so this only processes single items.
        """
        # Handle dict results (transcript or single video)
        if isinstance(tool_result, dict):
            video_id = tool_result.get("video_id", "")
            if not video_id:
                return None
            
            # Skip transcript IDs (unreadable titles)
            title = tool_result.get("title", "")
            if title and (title.startswith("Transcript:") or (
                len(title) <= 15 and title.replace("_", "").replace("-", "").isalnum()
            )):
                return None
            
            # Regular video result
            try:
                citation = YouTubeCitation.from_tool_result(tool_result, self.source_type)
                return citation
            except Exception as e:
                return None
        
        return None

