from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_youtube_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.youtube_tools import YouTubeToolkit
import json

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
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse YouTube tool results into structured citations.
        
        Extracts video IDs, URLs, titles, channels, and timestamps.
        """
        # Handle string results
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                return None
        
        # Handle list results (search results)
        if isinstance(tool_result, list) and tool_result:
            video = tool_result[0]
            if isinstance(video, dict):
                video_id = video.get("video_id", "")
                if video_id:
                    return {
                        "source_type": self.source_type.value,
                        "tool_name": tool_name,
                        "title": video.get("title", "Unknown Video"),
                        "url": video.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                        "snippet": video.get("description", "")[:300],
                        "metadata": {
                            "video_id": video_id,
                            "channel": video.get("channel", ""),
                            "published_at": video.get("published_at", "")
                        }
                    }
            return None
        
        # Handle dict results (transcript or single video)
        if isinstance(tool_result, dict):
            video_id = tool_result.get("video_id", "")
            if not video_id:
                return None
            
            # Check if this is a transcript result
            if "transcript" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"Transcript: {video_id}",
                    "url": tool_result.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                    "snippet": tool_result.get("transcript", "")[:300],
                    "metadata": {
                        "video_id": video_id,
                        "transcript_type": tool_result.get("transcript_type", ""),
                        "language": tool_result.get("language", ""),
                        "segment_count": tool_result.get("segment_count", 0)
                    }
                }
            
            # Check if this is a segment result
            if "start_time" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"Video Segment: {video_id}",
                    "url": tool_result.get("timestamp_url", f"https://www.youtube.com/watch?v={video_id}&t={int(tool_result.get('start_time', 0))}"),
                    "snippet": tool_result.get("content", "")[:300],
                    "metadata": {
                        "video_id": video_id,
                        "start_time": tool_result.get("start_time"),
                        "end_time": tool_result.get("end_time")
                    }
                }
            
            # Regular video result
            return {
                "source_type": self.source_type.value,
                "tool_name": tool_name,
                "title": tool_result.get("title", "Unknown Video"),
                "url": tool_result.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                "snippet": tool_result.get("description", "")[:300] or tool_result.get("transcript", "")[:300],
                "metadata": {
                    "video_id": video_id,
                    "channel": tool_result.get("channel", ""),
                    "published_at": tool_result.get("published_at", "")
                }
            }
        
        return None

