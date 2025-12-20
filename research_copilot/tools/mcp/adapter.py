from typing import List, Dict, Any, Optional, Callable
from langchain_core.tools import tool, BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class MCPToolAdapter:
    """
    Adapts remote MCP server tools to LangChain tools.
    
    This adapter:
    1. Connects to remote MCP servers via SSE (Server-Sent Events)
    2. Discovers available tools
    3. Wraps them as LangChain-compatible tools
    """
    
    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        self.server_name = server_name
        self.server_config = server_config
        self.session = None
        self._tools_cache: Optional[List[BaseTool]] = None
    
    async def connect(self) -> bool:
        """Connect to the remote MCP server via SSE."""
        return await self._connect_sse()
    
    async def _connect_sse(self) -> bool:
        """Connect to remote MCP server via SSE (Server-Sent Events)."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            
            url = self.server_config.get("url")
            if not url:
                logger.error(f"SSE transport requires 'url' in server_config for {self.server_name}")
                return False
            
            headers = self.server_config.get("headers", {})
            timeout = self.server_config.get("timeout", 30)
            
            # Connect via SSE
            async with sse_client(url, headers=headers, timeout=timeout) as (read, write):
                self.session = ClientSession(read, write)
                await self.session.__aenter__()
                await self.session.initialize()
            
            logger.info(f"Connected to remote MCP server: {self.server_name} at {url}")
            return True
        except ImportError:
            logger.error(
                f"SSE client not available. Install MCP SDK with SSE support: "
                f"pip install mcp[sse]"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to remote MCP server {self.server_name}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
    
    async def discover_tools(self) -> List[Dict]:
        """Discover available tools from the MCP server."""
        if not self.session:
            await self.connect()
        
        if not self.session:
            return []
        
        try:
            tools_result = await self.session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema
                }
                for t in tools_result.tools
            ]
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            return []
    
    def _create_tool_function(self, tool_name: str) -> Callable:
        """Create a sync wrapper for an async MCP tool call."""
        
        async def async_call(**kwargs) -> Dict:
            if not self.session:
                return {"error": f"Not connected to {self.server_name}"}
            
            try:
                result = await self.session.call_tool(tool_name, kwargs)
                # Parse MCP result
                if hasattr(result, 'content'):
                    content = result.content
                    if isinstance(content, list) and len(content) > 0:
                        return {"result": content[0].text if hasattr(content[0], 'text') else str(content[0])}
                return {"result": str(result)}
            except Exception as e:
                return {"error": f"Tool call failed: {str(e)}"}
        
        def sync_call(**kwargs) -> Dict:
            """Synchronous wrapper for async MCP call."""
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(async_call(**kwargs))
        
        return sync_call
    
    def _schema_to_pydantic(self, schema: Dict) -> type:
        """Convert JSON schema to Pydantic model for structured tools."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        for name, prop in properties.items():
            field_type = str  # Default
            if prop.get("type") == "integer":
                field_type = int
            elif prop.get("type") == "boolean":
                field_type = bool
            elif prop.get("type") == "array":
                field_type = list
            
            default = ... if name in required else None
            fields[name] = (field_type, Field(default=default, description=prop.get("description", "")))
        
        return create_model("ToolInput", **fields)
    
    async def create_langchain_tools(self) -> List[BaseTool]:
        """Convert all MCP tools to LangChain tools."""
        if self._tools_cache:
            return self._tools_cache
        
        mcp_tools = await self.discover_tools()
        langchain_tools = []
        
        for mcp_tool in mcp_tools:
            try:
                # Create the tool function
                tool_func = self._create_tool_function(mcp_tool["name"])
                
                # Create structured tool with proper schema
                if mcp_tool.get("input_schema"):
                    args_schema = self._schema_to_pydantic(mcp_tool["input_schema"])
                    lc_tool = StructuredTool.from_function(
                        func=tool_func,
                        name=f"{self.server_name}_{mcp_tool['name']}",
                        description=mcp_tool.get("description", ""),
                        args_schema=args_schema
                    )
                else:
                    lc_tool = tool(f"{self.server_name}_{mcp_tool['name']}")(tool_func)
                
                langchain_tools.append(lc_tool)
                logger.info(f"Wrapped MCP tool: {mcp_tool['name']}")
            except Exception as e:
                logger.error(f"Failed to wrap tool {mcp_tool['name']}: {e}")
        
        self._tools_cache = langchain_tools
        return langchain_tools