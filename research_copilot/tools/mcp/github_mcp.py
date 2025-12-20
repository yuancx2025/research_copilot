from typing import List, Dict, Optional
from langchain_core.tools import tool, BaseTool
from .base import BaseToolkit, SourceType
import requests
import base64
import logging
import asyncio

logger = logging.getLogger(__name__)

class GitHubToolkit(BaseToolkit):
    """
    Tools for searching GitHub repositories and reading code.
    
    Supports two modes:
    1. MCP mode: Uses GitHub MCP server (recommended if available)
    2. Direct API mode: Uses GitHub REST API directly
    """
    
    source_type = SourceType.GITHUB
    
    def __init__(self, config):
        self.config = config
        self.use_mcp = getattr(config, 'USE_GITHUB_MCP', False)
        self.token = getattr(config, 'GITHUB_TOKEN', None)
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.base_url = "https://api.github.com"
        self._mcp_adapter = None
        self._mcp_tools = None
    
    def is_available(self) -> bool:
        """GitHub is available with or without token (rate limited without)."""
        return True
    
    async def _init_mcp(self):
        """Initialize MCP adapter if configured."""
        if self.use_mcp and not self._mcp_adapter:
            from .mcp.adapter import MCPToolAdapter
            
            self._mcp_adapter = MCPToolAdapter(
                server_name="github",
                server_config={
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": self.token} if self.token else None
                }
            )
            await self._mcp_adapter.connect()
            self._mcp_tools = await self._mcp_adapter.create_langchain_tools()
    
    def _search_repositories(
        self,
        query: str,
        max_results: int = 5,
        sort: str = "stars",
        language: Optional[str] = None
    ) -> List[Dict]:
        """
        Search GitHub for repositories.
        
        Use this to find relevant code repositories, libraries, and projects.
        
        Args:
            query: Search query - can include qualifiers like 'langchain agent'
            max_results: Maximum repos to return (default: 5)
            sort: Sort by 'stars', 'forks', 'updated', or 'best-match'
            language: Filter by language (e.g., 'python', 'typescript')
        
        Returns:
            List of repositories with descriptions and stats
        """
        try:
            search_query = query
            if language:
                search_query += f" language:{language}"
            
            params = {
                "q": search_query,
                "sort": sort if sort != "best-match" else None,
                "per_page": max_results
            }
            
            response = requests.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params={k: v for k, v in params.items() if v},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for repo in data.get("items", [])[:max_results]:
                results.append({
                    "full_name": repo["full_name"],
                    "description": repo.get("description", "")[:200],
                    "url": repo["html_url"],
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo.get("language"),
                    "topics": repo.get("topics", [])[:5],
                    "updated_at": repo["updated_at"][:10],
                    "source_type": "github"
                })
            
            return results if results else [{"message": "No repositories found"}]
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return [{"error": f"GitHub search failed: {str(e)}"}]
    
    def _get_readme(
        self,
        repo: str
    ) -> Dict:
        """
        Get the README content from a GitHub repository.
        
        READMEs contain project documentation, setup instructions, and examples.
        
        Args:
            repo: Repository in format 'owner/repo' (e.g., 'langchain-ai/langchain')
        
        Returns:
            README content in markdown format
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{repo}/readme",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            content = base64.b64decode(data["content"]).decode("utf-8")
            
            return {
                "repo": repo,
                "content": content[:15000],  # Limit size
                "path": data["path"],
                "url": data["html_url"],
                "source_type": "github"
            }
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"error": f"README not found for {repo}"}
            return {"error": f"Failed to get README: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to get README: {str(e)}"}
    
    def _get_file_content(
        self,
        repo: str,
        path: str,
        branch: str = "main"
    ) -> Dict:
        """
        Get content of a specific file from a repository.
        
        Use this to read source code, configuration files, or documentation.
        
        Args:
            repo: Repository in format 'owner/repo'
            path: File path within repository (e.g., 'src/main.py')
            branch: Branch name (default: 'main', try 'master' if not found)
        
        Returns:
            File content
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{repo}/contents/{path}",
                headers=self.headers,
                params={"ref": branch},
                timeout=10
            )
            
            # Try master branch if main fails
            if response.status_code == 404 and branch == "main":
                response = requests.get(
                    f"{self.base_url}/repos/{repo}/contents/{path}",
                    headers=self.headers,
                    params={"ref": "master"},
                    timeout=10
                )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("type") != "file":
                return {"error": f"'{path}' is a directory, not a file"}
            
            content = base64.b64decode(data["content"]).decode("utf-8")
            
            return {
                "repo": repo,
                "path": path,
                "content": content[:20000],  # Limit size
                "size": data["size"],
                "url": data["html_url"],
                "source_type": "github"
            }
        except Exception as e:
            return {"error": f"Failed to get file: {str(e)}"}
    
    def _get_repo_structure(
        self,
        repo: str,
        path: str = ""
    ) -> Dict:
        """
        Get the file/folder structure of a repository.
        
        Useful to understand project organization before reading specific files.
        
        Args:
            repo: Repository in format 'owner/repo'
            path: Starting path (empty for root)
        
        Returns:
            Directory listing with file types
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{repo}/contents/{path}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            items = response.json()
            
            # Handle single file response
            if isinstance(items, dict):
                return {"error": f"'{path}' is a file, not a directory"}
            
            structure = []
            for item in items:
                structure.append({
                    "name": item["name"],
                    "type": item["type"],
                    "path": item["path"],
                    "size": item.get("size", 0) if item["type"] == "file" else None
                })
            
            # Sort: directories first, then files
            structure.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"]))
            
            return {
                "repo": repo,
                "path": path or "/",
                "contents": structure,
                "source_type": "github"
            }
        except Exception as e:
            return {"error": f"Failed to get structure: {str(e)}"}
    
    def create_tools(self) -> List[BaseTool]:
        """Create GitHub research tools."""
        # If MCP is configured and initialized, prefer MCP tools
        if self.use_mcp and self._mcp_tools:
            return self._mcp_tools
        
        # Otherwise use direct API tools
        return [
            tool("search_github")(self._search_repositories),
            tool("get_github_readme")(self._get_readme),
            tool("get_github_file")(self._get_file_content),
            tool("get_repo_structure")(self._get_repo_structure)
        ]