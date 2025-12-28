from typing import List, Dict, Any, Optional, Callable
from langchain_core.tools import tool, BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class MCPToolAdapter:
    """
    Adapts local MCP server tools to LangChain tools.
    
    This adapter connects to local MCP servers via stdio (standard input/output).
    MCP servers are spawned as child processes and communicate via stdin/stdout.
    
    Configuration:
    - command: List[str] - Command to execute (e.g., ["npx", "-y", "@modelcontextprotocol/server-github"])
    - args: List[str] - Additional arguments for the command (optional)
    - env: Dict[str, str] - Environment variables to pass to the process (optional)
    """
    
    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        self.server_name = server_name
        self.server_config = server_config
        self._client_session = None  # MCP client session
        self._transport_context = None  # Store transport context manager to keep connection alive
        self._tools_cache: Optional[List[BaseTool]] = None
        # Keep session reference for backward compatibility
        self.session = None  # Will be set to _client_session
    
    async def connect(self) -> bool:
        """Connect to the local MCP server via stdio."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client
            
            command = self.server_config.get("command")
            if not command:
                logger.error(f"stdio transport requires 'command' in server_config for {self.server_name}")
                return False
            
            args = self.server_config.get("args", [])
            env = self.server_config.get("env", {})
            
            # Connect via stdio and keep the connection alive
            self._transport_context = stdio_client(command, args, env=env)
            read, write = await self._transport_context.__aenter__()
            
            # Create client session
            self._client_session = ClientSession(read, write)
            await self._client_session.__aenter__()
            await self._client_session.initialize()
            
            # Set session for backward compatibility
            self.session = self._client_session
            
            logger.info(
                f"Connected to MCP server via stdio: {self.server_name} "
                f"(command: {' '.join(command + args)})"
            )
            return True
        except ImportError as e:
            logger.error(
                f"stdio client not available. Install MCP SDK: "
                f"pip install mcp. Error: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.server_name} via stdio: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self._client_session:
            try:
                await self._client_session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing client session: {e}")
            self._client_session = None
        
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            self.session = None
        
        if self._transport_context:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing transport context: {e}")
            self._transport_context = None
    
    async def discover_tools(self) -> List[Dict]:
        """Discover available tools from the MCP server."""
        if not self._client_session and not self.session:
            await self.connect()
        
        session = self._client_session or self.session
        if not session:
            return []
        
        try:
            tools_result = await session.list_tools()
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
            session = self._client_session or self.session
            if not session:
                return {"error": f"Not connected to {self.server_name}"}
            
            try:
                result = await session.call_tool(tool_name, kwargs)
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
        """Convert all MCP tools to LangChain tools.
        
        Tries to use langchain-mcp-adapters' tool creation utilities if available,
        otherwise falls back to custom implementation.
        """
        if self._tools_cache:
            return self._tools_cache
        
        # Try to use langchain-mcp-adapters for tool creation
        try:
            from langchain_mcp_adapters import create_mcp_tools
            
            session = self._client_session or self.session
            if not session:
                await self.connect()
                session = self._client_session or self.session
            
            if session:
                # Use official library to create tools
                official_tools = await create_mcp_tools(session)
                
                # Apply server name prefixing for backward compatibility
                prefixed_tools = []
                for lc_tool in official_tools:
                    # Rename tool with server prefix
                    original_name = lc_tool.name
                    prefixed_name = f"{self.server_name}_{original_name}"
                    
                    # Create new tool with prefixed name
                    if hasattr(lc_tool, 'args_schema') and lc_tool.args_schema:
                        prefixed_tool = StructuredTool.from_function(
                            func=lc_tool.func,
                            name=prefixed_name,
                            description=lc_tool.description,
                            args_schema=lc_tool.args_schema
                        )
                    else:
                        prefixed_tool = tool(prefixed_name)(lc_tool.func)
                    
                    prefixed_tools.append(prefixed_tool)
                    logger.info(f"Wrapped MCP tool using langchain-mcp-adapters: {original_name} -> {prefixed_name}")
                
                self._tools_cache = prefixed_tools
                return prefixed_tools
        except ImportError:
            logger.debug("langchain-mcp-adapters tool creation not available, using custom implementation")
        except Exception as e:
            logger.warning(f"Failed to use langchain-mcp-adapters for tool creation: {e}, falling back to custom")
        
        # Fallback to custom implementation
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