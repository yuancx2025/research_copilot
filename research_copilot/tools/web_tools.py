from typing import List, Dict, Optional, Any
from langchain_core.tools import tool, BaseTool
from .base import BaseToolkit, SourceType
import requests
from bs4 import BeautifulSoup
import logging
import asyncio

logger = logging.getLogger(__name__)

class WebToolkit(BaseToolkit):
    """
    Tools for web search and content extraction.
    
    Supports:
    - Web search (requires external API like Tavily or MCP)
    - Webpage content extraction
    - Documentation site search
    - Code extraction from web pages
    """
    
    source_type = SourceType.WEB
    
    def __init__(self, config):
        self.config = config
        self.tavily_api_key = getattr(config, 'TAVILY_API_KEY', None)
        self.use_mcp = getattr(config, 'USE_WEB_SEARCH_MCP', False)
        self.max_results = getattr(config, 'MAX_WEB_RESULTS', 10)
        self._tavily = None
        self._mcp_adapter = None
        self._mcp_tools = None
        
        # Initialize Tavily if API key provided
        if self.tavily_api_key:
            try:
                # Use the new langchain-tavily package
                from langchain_tavily import TavilySearchResults
                self._tavily = TavilySearchResults(
                    max_results=self.max_results,
                    api_key=self.tavily_api_key,
                    # Note: search_depth, include_answer, include_raw_content might not be supported
                    # Check TavilySearchResults API documentation for exact parameters
                )
            except ImportError:
                # Fallback to deprecated version if new package not installed
                try:
                    from langchain_community.tools.tavily_search import TavilySearchResults
                    logger.warning(
                        "Using deprecated TavilySearchResults from langchain-community. "
                        "Install langchain-tavily for the updated version: pip install langchain-tavily"
                    )
                    self._tavily = TavilySearchResults(
                        max_results=self.max_results,
                        search_depth="advanced",
                        include_answer=True,
                        include_raw_content=True,
                        tavily_api_key=self.tavily_api_key
                    )
                except ImportError:
                    logger.warning(
                        "Tavily search unavailable. Install langchain-tavily: pip install langchain-tavily"
                    )
    
    def is_available(self) -> bool:
        """Web tools available if Tavily API key or MCP command is configured."""
        mcp_configured = self.use_mcp and getattr(self.config, 'WEB_SEARCH_MCP_COMMAND', None)
        return bool(self.tavily_api_key or mcp_configured)
    
    async def _init_mcp(self):
        """Initialize local MCP adapter via stdio for web search if configured."""
        if self.use_mcp and not self._mcp_adapter:
            from .mcp.adapter import MCPToolAdapter
            
            command = getattr(self.config, 'WEB_SEARCH_MCP_COMMAND', None)
            if not command:
                logger.error("WEB_SEARCH_MCP_COMMAND not configured for local MCP")
                return
            
            args = getattr(self.config, 'WEB_SEARCH_MCP_ARGS', [])
            
            # Prepare environment variables for the MCP server process
            env = {}
            if self.tavily_api_key:
                env["TAVILY_API_KEY"] = self.tavily_api_key
            
            server_config = {
                "command": command,
                "args": args,
                "env": env
            }
            
            self._mcp_adapter = MCPToolAdapter(
                server_name="web_search",
                server_config=server_config
            )
            connected = await self._mcp_adapter.connect()
            if connected:
                self._mcp_tools = await self._mcp_adapter.create_langchain_tools()
                logger.info(f"Web search MCP initialized with {len(self._mcp_tools)} tools")
            else:
                logger.warning("Web search MCP connection failed, will fall back to direct API")
    
    async def _ensure_mcp_initialized(self):
        """Ensure MCP adapter is initialized (idempotent)."""
        if self.use_mcp and not self._mcp_tools:
            await self._init_mcp()
            if self._mcp_tools:
                return True
        return False
    
    def _web_search(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "general"
    ) -> List[Dict]:
        """
        Search the web for information.
        
        Use this to find articles, tutorials, documentation, and general web content.
        
        Args:
            query: Search query
            max_results: Maximum results to return (default: 10)
            search_type: 'general', 'news', 'academic', or 'tutorial'
        
        Returns:
            List of search results with titles, URLs, and snippets
        """
        if not self._tavily:
            return [{
                "error": "Web search API not configured. Set TAVILY_API_KEY or configure WEB_SEARCH_MCP_COMMAND",
                "message": "Configure Tavily API key or set WEB_SEARCH_MCP_COMMAND for local MCP server"
            }]
        
        try:
            # Enhance query based on search type
            enhanced_query = query
            if search_type == "news":
                enhanced_query = f"{query} news latest"
            elif search_type == "academic":
                enhanced_query = f"{query} research paper study"
            elif search_type == "tutorial":
                enhanced_query = f"{query} tutorial guide how to"
            
            results = self._tavily.invoke({"query": enhanced_query})
            
            formatted_results = []
            for r in results[:max_results]:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],  # Limit snippet length
                    "score": r.get("score", 0),
                    "source_type": "web"
                })
            
            return formatted_results if formatted_results else [{"message": "No results found"}]
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return [{"error": f"Web search failed: {str(e)}"}]
    
    def _extract_webpage_content(
        self,
        url: str,
        extract_type: str = "article"
    ) -> Dict:
        """
        Extract content from a webpage.
        
        Use this to get full text content from articles, blog posts, and documentation.
        
        Args:
            url: URL to extract content from
            extract_type: 'article' (smart extraction), 'full' (all text), or 'structured' (with headings)
        
        Returns:
            Extracted content with metadata
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script, style, and navigation elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
            
            if extract_type == "article":
                # Try to find main article content
                article = (soup.find("article") or 
                          soup.find("main") or 
                          soup.find("div", {"class": "content"}) or
                          soup.find("div", {"id": "content"}))
                if article:
                    text = article.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)
            elif extract_type == "structured":
                # Extract with structure preserved
                result = {
                    "title": soup.title.string if soup.title else "",
                    "headings": [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])],
                    "paragraphs": [p.get_text(strip=True) for p in soup.find_all("p") 
                                  if len(p.get_text(strip=True)) > 50],
                    "code_blocks": [code.get_text() for code in soup.find_all("code") 
                                   if len(code.get_text()) > 20]
                }
                return {
                    "url": url,
                    "structured_content": result,
                    "source_type": "web"
                }
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            clean_text = "\n".join(lines)
            
            return {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "content": clean_text[:15000],  # Limit content length
                "word_count": len(clean_text.split()),
                "source_type": "web"
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to fetch URL: {str(e)}"}
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return {"error": f"Failed to extract content: {str(e)}"}
    
    def _search_documentation(
        self,
        library_name: str,
        query: str
    ) -> List[Dict]:
        """
        Search documentation for a specific library/framework.
        
        Use this to find official documentation and API references.
        
        Args:
            library_name: Name of the library (e.g., 'langchain', 'pytorch', 'react')
            query: What to search for in the docs
        
        Returns:
            Relevant documentation sections
        """
        # Known documentation sites
        doc_sites = {
            "langchain": "site:python.langchain.com",
            "pytorch": "site:pytorch.org/docs",
            "tensorflow": "site:tensorflow.org/api_docs",
            "huggingface": "site:huggingface.co/docs",
            "openai": "site:platform.openai.com/docs",
            "fastapi": "site:fastapi.tiangolo.com",
            "react": "site:react.dev",
            "nextjs": "site:nextjs.org/docs",
            "django": "site:docs.djangoproject.com",
            "flask": "site:flask.palletsprojects.com"
        }
        
        site_filter = doc_sites.get(library_name.lower(), f"site:{library_name}.com")
        full_query = f"{site_filter} {query}"
        
        return self._web_search(full_query, max_results=5, search_type="general")
    
    def _extract_code_from_url(
        self,
        url: str
    ) -> Dict:
        """
        Extract code snippets from a webpage (e.g., tutorials, docs).
        
        Use this to get code examples from tutorial pages or documentation.
        
        Args:
            url: URL containing code
        
        Returns:
            Extracted code blocks with language detection
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            code_blocks = []
            for code in soup.find_all(["code", "pre"]):
                code_text = code.get_text(strip=True)
                if len(code_text) > 20:  # Filter out small inline code
                    # Try to detect language from class
                    classes = code.get("class", [])
                    language = "unknown"
                    for cls in classes:
                        if isinstance(cls, str):
                            if "language-" in cls:
                                language = cls.replace("language-", "")
                                break
                            elif cls in ["python", "javascript", "typescript", "java", "cpp", "rust", "go"]:
                                language = cls
                                break
                    
                    code_blocks.append({
                        "language": language,
                        "code": code_text[:5000]  # Limit code block size
                    })
            
            return {
                "url": url,
                "code_blocks": code_blocks[:10],  # Limit to 10 blocks
                "source_type": "web"
            }
        except Exception as e:
            logger.error(f"Code extraction failed: {e}")
            return {"error": f"Failed to extract code: {str(e)}"}
    
    def create_tools(self) -> List[BaseTool]:
        """Create web research tools, preferring MCP if available."""
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
                            "Web search MCP initialization deferred (async context detected). "
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
                logger.warning(f"Failed to initialize web search MCP: {e}. Falling back to direct API.")
        
        # Return MCP tools if available, otherwise API tools
        if self.use_mcp and self._mcp_tools:
            return self._mcp_tools
        
        # Fallback to direct API tools
        return [
            tool("web_search")(self._web_search),
            tool("extract_webpage")(self._extract_webpage_content),
            tool("search_docs")(self._search_documentation),
            tool("extract_code")(self._extract_code_from_url)
        ]
