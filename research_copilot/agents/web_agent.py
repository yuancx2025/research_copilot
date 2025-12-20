from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_web_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.web_tools import WebToolkit
import json

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
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse web tool results into structured citations.
        
        Extracts URLs, titles, and content snippets.
        """
        # Handle string results
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                return None
        
        # Handle list results (search results)
        if isinstance(tool_result, list) and tool_result:
            result = tool_result[0]
            if isinstance(result, dict):
                url = result.get("url", "")
                if url:
                    return {
                        "source_type": self.source_type.value,
                        "tool_name": tool_name,
                        "title": result.get("title", "Unknown Page"),
                        "url": url,
                        "snippet": result.get("content", "")[:300],
                        "metadata": {
                            "score": result.get("score", 0),
                            "domain": url.split("/")[2] if "/" in url else ""
                        }
                    }
            return None
        
        # Handle dict results
        if isinstance(tool_result, dict):
            url = tool_result.get("url", "")
            if not url:
                return None
            
            # Check if this is structured content
            if "structured_content" in tool_result:
                structured = tool_result["structured_content"]
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": structured.get("title", "Unknown Page"),
                    "url": url,
                    "snippet": " ".join(structured.get("paragraphs", [])[:3])[:300],
                    "metadata": {
                        "headings": structured.get("headings", []),
                        "code_blocks": len(structured.get("code_blocks", []))
                    }
                }
            
            # Check if this is code extraction result
            if "code_blocks" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"Code Examples: {url.split('/')[-1]}",
                    "url": url,
                    "snippet": f"Extracted {len(tool_result.get('code_blocks', []))} code blocks",
                    "metadata": {
                        "code_blocks": tool_result.get("code_blocks", []),
                        "url": url
                    }
                }
            
            # Regular webpage content
            return {
                "source_type": self.source_type.value,
                "tool_name": tool_name,
                "title": tool_result.get("title", url.split("/")[-1]),
                "url": url,
                "snippet": tool_result.get("content", "")[:300],
                "metadata": {
                    "word_count": tool_result.get("word_count", 0),
                    "domain": url.split("/")[2] if "/" in url else ""
                }
            }
        
        return None

