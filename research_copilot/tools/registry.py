from typing import List, Dict, Optional, Type
from langchain_core.tools import BaseTool
from .base import BaseToolkit, SourceType
import logging
import asyncio

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Central registry for all research tools.
    
    Handles:
    - Tool registration and discovery
    - Conditional loading based on config
    - Unified access for the agent
    """
    
    _instance = None
    _toolkits: Dict[SourceType, BaseToolkit] = {}
    _tools_cache: Optional[List[BaseTool]] = None
    
    def __new__(cls):
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, toolkit: BaseToolkit) -> None:
        """Register a toolkit and initialize MCP if needed."""
        if toolkit.is_available():
            # Initialize MCP tools if toolkit uses MCP
            if hasattr(toolkit, 'use_mcp') and toolkit.use_mcp:
                self._initialize_mcp_tools(toolkit)
            
            self._toolkits[toolkit.source_type] = toolkit
            self._tools_cache = None  # Invalidate cache
            logger.info(f"Registered toolkit: {toolkit.source_type.value}")
        else:
            logger.warning(f"Toolkit {toolkit.source_type.value} not available (missing config?)")
    
    def _initialize_mcp_tools(self, toolkit: BaseToolkit) -> None:
        """Initialize MCP tools for a toolkit if it supports MCP."""
        try:
            # Check if toolkit has MCP initialization method
            if hasattr(toolkit, '_ensure_mcp_initialized'):
                # Try to initialize MCP synchronously
                try:
                    # Check if we're in an async context
                    try:
                        loop = asyncio.get_running_loop()
                        # If we're in an async context, defer initialization
                        logger.debug(
                            f"MCP initialization for {toolkit.source_type.value} "
                            "deferred (async context detected)"
                        )
                    except RuntimeError:
                        # No running loop, safe to create one
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_closed():
                                asyncio.run(toolkit._ensure_mcp_initialized())
                            else:
                                loop.run_until_complete(toolkit._ensure_mcp_initialized())
                        except RuntimeError:
                            asyncio.run(toolkit._ensure_mcp_initialized())
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize MCP for {toolkit.source_type.value}: {e}. "
                        "Will use direct API fallback."
                    )
        except Exception as e:
            logger.warning(f"Error during MCP initialization for {toolkit.source_type.value}: {e}")
    
    def get_toolkit(self, source_type: SourceType) -> Optional[BaseToolkit]:
        """Get a specific toolkit."""
        return self._toolkits.get(source_type)
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all tools from all registered toolkits."""
        if self._tools_cache is None:
            self._tools_cache = []
            for toolkit in self._toolkits.values():
                self._tools_cache.extend(toolkit.create_tools())
            logger.info(f"Loaded {len(self._tools_cache)} tools from {len(self._toolkits)} toolkits")
        return self._tools_cache
    
    def get_tools_for_sources(self, sources: List[SourceType]) -> List[BaseTool]:
        """Get tools only for specified sources."""
        tools = []
        for source in sources:
            toolkit = self._toolkits.get(source)
            if toolkit:
                tools.extend(toolkit.create_tools())
        return tools
    
    def list_available_sources(self) -> List[SourceType]:
        """List all available source types."""
        return list(self._toolkits.keys())
    
    def clear(self) -> None:
        """Clear all registrations (useful for testing)."""
        self._toolkits.clear()
        self._tools_cache = None


def initialize_registry(config) -> ToolRegistry:
    """
    Initialize the tool registry with all available toolkits.
    
    This is the main entry point - call once at startup.
    
    Includes comprehensive error handling:
    - Catches toolkit initialization failures
    - Logs warnings for unavailable toolkits
    - Ensures core functionality (local tools) always loads
    - Returns registry even if some toolkits fail
    
    Args:
        config: Configuration object with agent enablement flags
        
    Returns:
        Initialized ToolRegistry instance
        
    Raises:
        RuntimeError: If core local tools fail to initialize
    """
    from .local_tools import LocalToolkit
    from .arxiv_tools import ArxivToolkit
    from .youtube_tools import YouTubeToolkit
    from .github_tools import GitHubToolkit
    from .web_tools import WebToolkit
    
    registry = ToolRegistry()
    failed_toolkits = []
    
    # Always register local tools (core functionality) - this must succeed
    try:
        local_toolkit = LocalToolkit(config)
        registry.register(local_toolkit)
        logger.info("Core local tools registered successfully")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize local tools: {e}")
        raise RuntimeError(f"Core local tools initialization failed: {e}") from e
    
    # Register external source toolkits based on config
    # These are optional and failures are logged but don't stop initialization
    
    if getattr(config, 'ENABLE_ARXIV_AGENT', True):
        try:
            arxiv_toolkit = ArxivToolkit(config)
            registry.register(arxiv_toolkit)
        except Exception as e:
            failed_toolkits.append(("ArXiv", str(e)))
            logger.warning(f"Failed to initialize ArXiv toolkit: {e}")
    
    if getattr(config, 'ENABLE_YOUTUBE_AGENT', True):
        try:
            youtube_toolkit = YouTubeToolkit(config)
            registry.register(youtube_toolkit)
        except Exception as e:
            failed_toolkits.append(("YouTube", str(e)))
            logger.warning(f"Failed to initialize YouTube toolkit: {e}")
    
    if getattr(config, 'ENABLE_GITHUB_AGENT', True):
        try:
            github_toolkit = GitHubToolkit(config)
            registry.register(github_toolkit)
        except Exception as e:
            failed_toolkits.append(("GitHub", str(e)))
            logger.warning(f"Failed to initialize GitHub toolkit: {e}")
    
    if getattr(config, 'ENABLE_WEB_AGENT', True):
        try:
            web_toolkit = WebToolkit(config)
            registry.register(web_toolkit)
        except Exception as e:
            failed_toolkits.append(("Web", str(e)))
            logger.warning(f"Failed to initialize Web toolkit: {e}")
    
    # Log summary
    if failed_toolkits:
        logger.warning(
            f"Tool registry initialized with {len(failed_toolkits)} toolkit(s) failed: "
            f"{', '.join([name for name, _ in failed_toolkits])}"
        )
    else:
        logger.info("All configured toolkits registered successfully")
    
    return registry