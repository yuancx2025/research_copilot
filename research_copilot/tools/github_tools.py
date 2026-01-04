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
        """Initialize local MCP adapter via stdio if configured."""
        if self.use_mcp and not self._mcp_adapter:
            from .mcp.adapter import MCPToolAdapter
            
            command = getattr(self.config, 'GITHUB_MCP_COMMAND', None)
            if not command:
                logger.error("GITHUB_MCP_COMMAND not configured for local MCP")
                return
            
            args = getattr(self.config, 'GITHUB_MCP_ARGS', [])
            
            # Prepare environment variables for the MCP server process
            env = {}
            if self.token:
                env["GITHUB_TOKEN"] = self.token
            
            server_config = {
                "command": command,
                "args": args,
                "env": env
            }
            
            self._mcp_adapter = MCPToolAdapter(
                server_name="github",
                server_config=server_config
            )
            connected = await self._mcp_adapter.connect()
            if connected:
                self._mcp_tools = await self._mcp_adapter.create_langchain_tools()
                logger.info(f"GitHub MCP initialized with {len(self._mcp_tools)} tools")
            else:
                logger.warning("GitHub MCP connection failed, will fall back to direct API")
    
    async def _ensure_mcp_initialized(self):
        """Ensure MCP adapter is initialized (idempotent)."""
        if self.use_mcp and not self._mcp_tools:
            await self._init_mcp()
            if self._mcp_tools:
                return True
        return False
    
    def _search_repositories(
        self,
        query: str,
        max_results: int = 5,
        sort: str = "stars",
        language: Optional[str] = None
    ) -> List[Dict]:
        """
        Search GitHub repositories.
        
        Args:
            query: Search query
            max_results: Maximum repos to return
            sort: Sort by 'stars', 'forks', 'updated', or 'best-match'
            language: Filter by programming language
        
        Returns:
            List of repository metadata
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
                params={k: v for k, v in params.items() if v}
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            if not isinstance(data, dict):
                return [{"error": f"Invalid response format: expected dict, got {type(data)}"}]
            
            items = data.get("items", [])
            if not isinstance(items, list):
                return [{"error": f"Invalid items format: expected list, got {type(items)}"}]
            
            for repo in items[:max_results]:
                # Validate repo is a dict
                if not isinstance(repo, dict):
                    continue
                
                updated_at = repo.get("updated_at")
                if updated_at:
                    updated_at = updated_at[:10]
                else:
                    updated_at = ""
                
                results.append({
                    "full_name": repo.get("full_name", ""),
                    "description": repo.get("description", "")[:200],
                    "url": repo.get("html_url", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language"),
                    "topics": repo.get("topics", [])[:5],
                    "updated_at": updated_at,
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
        """Create GitHub research tools, preferring MCP if available."""
        # Try to initialize MCP synchronously if configured
        if self.use_mcp:
            try:
                # Check if we're in an async context
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an async context, we can't use run_until_complete
                    # In this case, MCP tools will be initialized lazily on first use
                    # or we'll fall back to direct API
                    if not self._mcp_tools:
                        logger.warning(
                            "GitHub MCP initialization deferred (async context detected). "
                            "Will use direct API for now."
                        )
                except RuntimeError:
                    # No running loop, safe to create one
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            asyncio.run(self._ensure_mcp_initialized())
                        else:
                            loop.run_until_complete(self._ensure_mcp_initialized())
                    except RuntimeError:
                        asyncio.run(self._ensure_mcp_initialized())
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub MCP: {e}. Falling back to direct API.")
        
        # Return MCP tools if available, otherwise API tools
        if self.use_mcp and self._mcp_tools:
            return self._mcp_tools
        
        # Fallback to direct API tools
        return [
            tool("search_github")(self._search_repositories),
            tool("get_github_readme")(self._get_readme),
            tool("get_github_file")(self._get_file_content),
            tool("get_repo_structure")(self._get_repo_structure)
        ]