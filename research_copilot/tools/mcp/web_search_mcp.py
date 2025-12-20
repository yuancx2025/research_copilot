"""
Web Search MCP Server Wrapper for Tavily API.

This module provides a wrapper that can be used to create an MCP server
for web search using Tavily API. This allows web search tools to be exposed
via MCP protocol.

Usage:
    This can be run as a standalone MCP server:
    python -m tools.mcp.web_search_mcp
    
    Or integrated into the web_tools.py toolkit when USE_WEB_SEARCH_MCP=True
    and a custom MCP server path is configured.
"""

import os
import sys
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available. Install with: pip install mcp")


def create_tavily_mcp_server(api_key: Optional[str] = None) -> Optional[Any]:
    """
    Create an MCP server for Tavily web search.
    
    Args:
        api_key: Tavily API key (if None, reads from TAVILY_API_KEY env var)
        
    Returns:
        MCP Server instance if MCP SDK is available, None otherwise
    """
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not available. Cannot create MCP server.")
        return None
    
    api_key = api_key or os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("Tavily API key not provided. Set TAVILY_API_KEY environment variable.")
        return None
    
    # Import Tavily client
    try:
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key=api_key)
    except ImportError:
        logger.error("Tavily client not available. Install with: pip install tavily-python")
        return None
    
    # Create MCP server
    server = Server("web-search-tavily")
    
    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """List available web search tools."""
        return [
            Tool(
                name="web_search",
                description="Search the web using Tavily API. Returns relevant articles, tutorials, and web content.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10
                        },
                        "search_depth": {
                            "type": "string",
                            "description": "Search depth: 'basic' or 'advanced'",
                            "enum": ["basic", "advanced"],
                            "default": "advanced"
                        }
                    },
                    "required": ["query"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls."""
        if name == "web_search":
            query = arguments.get("query", "")
            max_results = arguments.get("max_results", 10)
            search_depth = arguments.get("search_depth", "advanced")
            
            try:
                # Call Tavily API
                response = tavily_client.search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth
                )
                
                # Format results
                results = []
                for result in response.get("results", [])[:max_results]:
                    result_text = f"Title: {result.get('title', 'N/A')}\n"
                    result_text += f"URL: {result.get('url', 'N/A')}\n"
                    result_text += f"Content: {result.get('content', '')[:500]}\n"
                    results.append(TextContent(type="text", text=result_text))
                
                if not results:
                    results.append(TextContent(
                        type="text",
                        text="No results found for the query."
                    ))
                
                return results
            except Exception as e:
                logger.error(f"Tavily search failed: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error: Web search failed - {str(e)}"
                )]
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    return server


def run_mcp_server():
    """Run the MCP server via stdio."""
    if not MCP_AVAILABLE:
        print("Error: MCP SDK not available. Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Error: TAVILY_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    server = create_tavily_mcp_server(api_key)
    if not server:
        print("Error: Failed to create MCP server", file=sys.stderr)
        sys.exit(1)
    
    # Run server via stdio
    import asyncio
    asyncio.run(stdio_server(server))


if __name__ == "__main__":
    run_mcp_server()

