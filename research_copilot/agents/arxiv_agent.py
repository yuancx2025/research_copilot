from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_arxiv_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.arxiv_tools import ArxivToolkit
import json

class ArxivAgent(BaseAgent):
    """
    Agent for searching and analyzing ArXiv academic papers.
    
    Specialized in academic research, paper analysis, and literature review.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        toolkit = ArxivToolkit(config)
        tools = toolkit.create_tools()
        super().__init__(SourceType.ARXIV, llm, tools)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for ArXiv paper research."""
        return get_arxiv_agent_prompt()
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse ArXiv tool results into structured citations.
        
        Extracts ArXiv IDs, titles, authors, and publication dates.
        """
        # Handle string results
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                return None
        
        # Handle list results (search results)
        if isinstance(tool_result, list) and tool_result:
            # Use first result as primary citation
            paper = tool_result[0]
            if isinstance(paper, dict):
                arxiv_id = paper.get("arxiv_id", "")
                if arxiv_id:
                    return {
                        "source_type": self.source_type.value,
                        "tool_name": tool_name,
                        "title": paper.get("title", "Unknown Paper"),
                        "url": paper.get("pdf_url", f"https://arxiv.org/abs/{arxiv_id}"),
                        "authors": paper.get("authors", []),
                        "date": paper.get("published", ""),
                        "snippet": paper.get("abstract", "")[:300],
                        "metadata": {
                            "arxiv_id": arxiv_id,
                            "categories": paper.get("categories", []),
                            "primary_category": paper.get("primary_category", "")
                        }
                    }
            return None
        
        # Handle dict results (single paper)
        if isinstance(tool_result, dict):
            arxiv_id = tool_result.get("arxiv_id", "")
            if not arxiv_id:
                return None
            
            return {
                "source_type": self.source_type.value,
                "tool_name": tool_name,
                "title": tool_result.get("title", "Unknown Paper"),
                "url": tool_result.get("url") or tool_result.get("pdf_url") or f"https://arxiv.org/abs/{arxiv_id}",
                "authors": tool_result.get("authors", []),
                "date": tool_result.get("published", ""),
                "snippet": tool_result.get("abstract", "")[:300] or tool_result.get("content", "")[:300],
                "metadata": {
                    "arxiv_id": arxiv_id,
                    "categories": tool_result.get("categories", []),
                    "primary_category": tool_result.get("primary_category", "")
                }
            }
        
        return None

