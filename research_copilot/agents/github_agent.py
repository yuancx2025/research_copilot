from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_github_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.github_tools import GitHubToolkit
import json

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
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse GitHub tool results into structured citations.
        
        Extracts repository URLs, file paths, and code content.
        """
        # Handle string results
        if isinstance(tool_result, str):
            try:
                tool_result = json.loads(tool_result)
            except (json.JSONDecodeError, ValueError):
                return None
        
        # Handle list results (search results)
        if isinstance(tool_result, list) and tool_result:
            repo = tool_result[0]
            if isinstance(repo, dict):
                repo_url = repo.get("url", "")
                if repo_url:
                    return {
                        "source_type": self.source_type.value,
                        "tool_name": tool_name,
                        "title": repo.get("full_name", "Unknown Repository"),
                        "url": repo_url,
                        "snippet": repo.get("description", "")[:300],
                        "metadata": {
                            "full_name": repo.get("full_name", ""),
                            "stars": repo.get("stars", 0),
                            "language": repo.get("language", ""),
                            "topics": repo.get("topics", [])
                        }
                    }
            return None
        
        # Handle dict results
        if isinstance(tool_result, dict):
            # Check if this is a README result
            if "repo" in tool_result and "content" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"README: {tool_result.get('repo', '')}",
                    "url": tool_result.get("url", ""),
                    "snippet": tool_result.get("content", "")[:300],
                    "metadata": {
                        "repo": tool_result.get("repo", ""),
                        "path": tool_result.get("path", "README.md")
                    }
                }
            
            # Check if this is a file result
            if "repo" in tool_result and "path" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"{tool_result.get('repo', '')}/{tool_result.get('path', '')}",
                    "url": tool_result.get("url", ""),
                    "snippet": tool_result.get("content", "")[:500],
                    "metadata": {
                        "repo": tool_result.get("repo", ""),
                        "path": tool_result.get("path", ""),
                        "size": tool_result.get("size", 0)
                    }
                }
            
            # Check if this is a structure result
            if "repo" in tool_result and "contents" in tool_result:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": f"Structure: {tool_result.get('repo', '')}",
                    "url": f"https://github.com/{tool_result.get('repo', '')}",
                    "snippet": f"Repository structure with {len(tool_result.get('contents', []))} items",
                    "metadata": {
                        "repo": tool_result.get("repo", ""),
                        "path": tool_result.get("path", ""),
                        "item_count": len(tool_result.get("contents", []))
                    }
                }
            
            # Regular repository result
            repo_url = tool_result.get("url", "")
            if repo_url:
                return {
                    "source_type": self.source_type.value,
                    "tool_name": tool_name,
                    "title": tool_result.get("full_name", "Unknown Repository"),
                    "url": repo_url,
                    "snippet": tool_result.get("description", "")[:300],
                    "metadata": {
                        "full_name": tool_result.get("full_name", ""),
                        "stars": tool_result.get("stars", 0),
                        "language": tool_result.get("language", ""),
                        "topics": tool_result.get("topics", [])
                    }
                }
        
        return None

