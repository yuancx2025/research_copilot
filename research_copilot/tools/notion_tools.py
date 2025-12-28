from typing import List, Dict, Optional, Any, Tuple
from langchain_core.tools import tool, BaseTool
from .base import BaseToolkit, SourceType
import logging
import asyncio
import requests

logger = logging.getLogger(__name__)


class NotionToolkit(BaseToolkit):
    """
    Tools for creating and managing Notion pages.
    
    Supports:
    - Creating Notion pages via MCP server (if configured)
    - Creating Notion pages via Direct API (fallback/default)
    - Appending blocks to existing pages
    - Formatting study plans as Notion content
    """
    
    # Notion is not a research source, but we need a source_type for BaseToolkit
    # We'll use a custom value that won't conflict
    source_type = SourceType.WEB  # Placeholder - Notion is not a research source type
    
    def __init__(self, config):
        self.config = config
        self.use_mcp = getattr(config, 'USE_NOTION_MCP', False)
        self.notion_api_key = getattr(config, 'NOTION_API_KEY', None)
        self.notion_base_url = "https://api.notion.com/v1"
        self.notion_version = "2022-06-28"
        self._mcp_adapter = None
        self._mcp_tools = None
        self._direct_api_tools = None
    
    def is_available(self) -> bool:
        """Notion tools available if MCP command is configured OR Direct API is configured."""
        mcp_configured = self.use_mcp and getattr(self.config, 'NOTION_MCP_COMMAND', None)
        direct_api_configured = self.notion_api_key and getattr(self.config, 'NOTION_PARENT_PAGE_ID', None)
        return mcp_configured or direct_api_configured
    
    def _validate_notion_api_config(self) -> Tuple[bool, Optional[str]]:
        """Check if Direct API config is valid.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.notion_api_key:
            return False, "NOTION_API_KEY not configured"
        
        parent_page_id = getattr(self.config, 'NOTION_PARENT_PAGE_ID', None)
        if not parent_page_id:
            return False, "NOTION_PARENT_PAGE_ID not configured"
        
        return True, None
    
    def _verify_parent_page_access(self, parent_page_id: str) -> Tuple[bool, Optional[str]]:
        """Verify that the parent page exists and is accessible.
        
        Returns:
            Tuple of (is_accessible, error_message)
        """
        headers = {
            "Authorization": f"Bearer {self.notion_api_key}",
            "Notion-Version": self.notion_version
        }
        
        try:
            response = requests.get(
                f"{self.notion_base_url}/pages/{parent_page_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return True, None
            elif response.status_code == 404:
                return False, f"Parent page not found (404). Check that the page ID is correct and the integration has access."
            elif response.status_code == 401:
                return False, f"Unauthorized (401). Check that NOTION_API_KEY is valid and has access to the parent page."
            elif response.status_code == 403:
                return False, f"Forbidden (403). The integration doesn't have access to the parent page. Share the page with your integration."
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                return False, f"Cannot access parent page: {error_msg}"
        except Exception as e:
            logger.warning(f"Could not verify parent page access: {e}")
            # Don't fail on verification error, just log it
            return True, None  # Assume accessible if we can't verify
    
    def _create_page_direct_api(
        self,
        parent_page_id: str,
        title: str,
        content_blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a Notion page using Direct REST API.
        
        Args:
            parent_page_id: Notion page ID to create under
            title: Page title
            content_blocks: List of content blocks (formatted for Notion)
        
        Returns:
            Dict with page creation result (page_id, url, etc.) or error
        """
        is_valid, error_msg = self._validate_notion_api_config()
        if not is_valid:
            return {"error": error_msg}
        
        # Validate and normalize parent_page_id
        # Notion page IDs can be provided with or without dashes
        # Extract UUID from URL if full URL provided
        original_parent_id = parent_page_id.strip()
        normalized_parent_id = original_parent_id
        
        
        if "notion.so" in normalized_parent_id:
            # Extract ID from URL: https://www.notion.so/PageName-abc123def456...
            # Notion URLs format: https://www.notion.so/PageName-UUID
            # The UUID is the last part after the final dash
            parts = normalized_parent_id.split("-")
            if len(parts) > 0:
                # Get the last part which should be the UUID
                normalized_parent_id = parts[-1]
                # Remove any query parameters or fragments
                normalized_parent_id = normalized_parent_id.split("?")[0].split("#")[0]
        
        # Ensure UUID format (add dashes if missing)
        normalized_parent_id = normalized_parent_id.replace("-", "")
        
        
        if len(normalized_parent_id) == 32:
            # Add dashes: 8-4-4-4-12
            normalized_parent_id = f"{normalized_parent_id[:8]}-{normalized_parent_id[8:12]}-{normalized_parent_id[12:16]}-{normalized_parent_id[16:20]}-{normalized_parent_id[20:]}"
        elif len(normalized_parent_id) < 32:
            return {
                "error": f"Invalid parent_page_id format: parent page ID is too short ({len(normalized_parent_id)} characters, expected 32).",
                "details": f"Provided ID: {original_parent_id[:50]}...\n\nA Notion page ID should be:\n- 32 hexadecimal characters (without dashes), OR\n- 36 characters with dashes (8-4-4-4-12 format), OR\n- A full Notion URL (https://www.notion.so/PageName-UUID)\n\nTo get your page ID:\n1. Open the Notion page\n2. Click 'Share' → 'Copy link'\n3. The UUID is the last part of the URL (after the final dash)"
            }
        
        if len(normalized_parent_id) != 36:
            return {
                "error": f"Invalid parent_page_id format: {original_parent_id[:50]}. Expected UUID format.",
                "details": f"Length: {len(normalized_parent_id)} (expected 36). Parent page ID should be a valid Notion UUID (32 hex chars without dashes, or 36 with dashes)"
            }
        
        
        # Verify parent page access (non-blocking - warn but don't fail)
        # Some integrations can create pages even if GET /pages/{id} fails
        is_accessible, access_error = self._verify_parent_page_access(normalized_parent_id)
        if not is_accessible:
            # Log warning but continue - creation might still work
            logger.warning(f"Parent page verification failed: {access_error}. Attempting creation anyway...")
            # Don't return error here - let the API call determine if it works
        
        # Validate blocks
        if not content_blocks:
            logger.warning("No content blocks provided - creating empty page")
        else:
            # Validate block structure
            for i, block in enumerate(content_blocks[:5]):  # Check first 5 blocks
                if not isinstance(block, dict) or "type" not in block:
                    logger.warning(f"Invalid block format at index {i}: {block}")
        
        headers = {
            "Authorization": f"Bearer {self.notion_api_key}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json"
        }
        
        # Notion API limit: max 100 blocks per request
        # Split blocks into chunks if needed
        MAX_BLOCKS_PER_REQUEST = 100
        initial_blocks = content_blocks[:MAX_BLOCKS_PER_REQUEST]
        remaining_blocks = content_blocks[MAX_BLOCKS_PER_REQUEST:]
        
        if len(content_blocks) > MAX_BLOCKS_PER_REQUEST:
            logger.info(f"Splitting {len(content_blocks)} blocks into chunks: {len(initial_blocks)} initial + {len(remaining_blocks)} remaining")
        
        # Build the page payload according to Notion API v1 format
        # The title needs to be in the properties field
        payload = {
            "parent": {
                "page_id": normalized_parent_id
            },
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            },
            "children": initial_blocks
        }
        
        try:
            # Log request details for debugging
            logger.info(f"Creating Notion page with parent_id: {parent_page_id[:8]}..., title: {title[:50]}..., blocks: {len(initial_blocks)} (of {len(content_blocks)} total)")
            
            response = requests.post(
                f"{self.notion_base_url}/pages",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # Log response status and details
            logger.info(f"Notion API response status: {response.status_code}")
            
            # Accept both 200 (OK) and 201 (Created) as success
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    page_id = data.get("id", "")
                    
                    if not page_id:
                        logger.error(f"No page_id in response: {data}")
                        return {
                            "error": "Notion API returned success but no page_id in response",
                            "response_data": str(data)[:500]
                        }
                    
                    # Construct URL from page ID (remove dashes for URL)
                    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
                    
                    # Append remaining blocks if any
                    if remaining_blocks:
                        logger.info(f"Appending {len(remaining_blocks)} remaining blocks to page {page_id}")
                        
                        # Split remaining blocks into chunks of 100
                        append_success = True
                        for i in range(0, len(remaining_blocks), MAX_BLOCKS_PER_REQUEST):
                            chunk = remaining_blocks[i:i + MAX_BLOCKS_PER_REQUEST]
                            append_result = self._append_blocks_direct_api(page_id, chunk)
                            if append_result.get("error"):
                                logger.error(f"Failed to append block chunk {i//MAX_BLOCKS_PER_REQUEST + 1}: {append_result.get('error')}")
                                append_success = False
                                # Continue appending other chunks even if one fails
                            else:
                                logger.info(f"Appended block chunk {i//MAX_BLOCKS_PER_REQUEST + 1} ({len(chunk)} blocks)")
                        
                        if not append_success:
                            logger.warning(f"Some blocks failed to append, but page was created: {page_url}")
                    
                    logger.info(f"Notion page created successfully: {page_id} -> {page_url}")
                    
                    return {
                        "page_id": page_id,
                        "url": page_url,
                        "page_url": page_url,  # Alias for compatibility
                        "error": None
                    }
                except ValueError as e:
                    # JSON decode error
                    logger.error(f"Failed to parse Notion API response as JSON: {e}")
                    logger.error(f"Response content: {response.text[:500]}")
                    return {
                        "error": f"Invalid JSON response from Notion API: {str(e)}",
                        "status_code": response.status_code,
                        "response_preview": response.text[:500]
                    }
            else:
                # Error response
                try:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("message", f"HTTP {response.status_code}")
                    error_code = error_data.get("code", "")
                    
                    logger.error(f"Notion API error: {error_message} (code: {error_code}, status: {response.status_code})")
                    logger.error(f"Full error response: {error_data}")
                    
                    # Provide helpful error message based on error code
                    if error_code == "object_not_found" and response.status_code == 404:
                        # This usually means the page isn't shared with the integration
                        detailed_error = (
                            f"Notion API error: {error_message}\n\n"
                            "This usually means:\n"
                            "1. The parent page ID is incorrect, OR\n"
                            "2. The parent page is not shared with your Notion integration\n\n"
                            "To fix:\n"
                            "1. Open your Notion page\n"
                            "2. Click the 'Share' button (top right)\n"
                            "3. Click 'Add people, emails, groups, or integrations'\n"
                            "4. Search for your integration name and add it\n"
                            "5. Make sure the page ID is correct (32 hex characters)\n\n"
                            f"Page ID used: {normalized_parent_id}"
                        )
                    elif error_code == "validation_error" and "children.length" in error_message:
                        # Block limit exceeded - this should be handled by chunking, but provide helpful message
                        detailed_error = (
                            f"Notion API error: {error_message}\n\n"
                            "The Notion API has a limit of 100 blocks per request. "
                            "This error should be handled automatically by splitting blocks into chunks. "
                            "If you see this, please report it as a bug."
                        )
                    else:
                        detailed_error = f"Notion API error: {error_message}"
                    
                    return {
                        "error": detailed_error,
                        "error_code": error_code,
                        "status_code": response.status_code,
                        "error_details": error_data,
                        "parent_page_id": normalized_parent_id
                    }
                except ValueError:
                    # Can't parse error JSON
                    logger.error(f"Notion API error (non-JSON): Status {response.status_code}, Content: {response.text[:500]}")
                    return {
                        "error": f"Notion API error: HTTP {response.status_code}",
                        "status_code": response.status_code,
                        "response_preview": response.text[:500]
                    }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create Notion page via Direct API: {e}", exc_info=True)
            return {"error": f"Failed to create Notion page: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error creating Notion page: {e}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}
    
    def _append_blocks_direct_api(
        self,
        block_id: str,
        children: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Append blocks to an existing Notion page using Direct REST API.
        
        Args:
            block_id: Notion block/page ID to append to
            children: List of child blocks to append
        
        Returns:
            Dict with result or error
        """
        is_valid, error_msg = self._validate_notion_api_config()
        if not is_valid:
            return {"error": error_msg}
        
        headers = {
            "Authorization": f"Bearer {self.notion_api_key}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json"
        }
        
        payload = {
            "children": children
        }
        
        try:
            response = requests.patch(
                f"{self.notion_base_url}/blocks/{block_id}/children",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return {"success": True, "error": None}
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get("message", f"HTTP {response.status_code}")
                return {"error": f"Notion API error: {error_message}"}
        except Exception as e:
            logger.error(f"Failed to append blocks via Direct API: {e}", exc_info=True)
            return {"error": f"Failed to append blocks: {str(e)}"}
    
    async def _init_mcp(self):
        """Initialize Notion MCP adapter via stdio if configured."""
        if self.use_mcp and not self._mcp_adapter:
            from .mcp.adapter import MCPToolAdapter
            
            command = getattr(self.config, 'NOTION_MCP_COMMAND', None)
            if not command:
                logger.error("NOTION_MCP_COMMAND not configured for Notion MCP")
                return
            
            args = getattr(self.config, 'NOTION_MCP_ARGS', [])
            
            # Prepare environment variables for the MCP server process
            env = {}
            if self.notion_api_key:
                env["NOTION_API_KEY"] = self.notion_api_key
            
            server_config = {
                "command": command,
                "args": args,
                "env": env
            }
            
            logger.info(f"Initializing Notion MCP with command: {' '.join(command + args)}")
            
            self._mcp_adapter = MCPToolAdapter(
                server_name="notion",
                server_config=server_config
            )
            try:
                connected = await self._mcp_adapter.connect()
                if connected:
                    self._mcp_tools = await self._mcp_adapter.create_langchain_tools()
                    logger.info(f"Notion MCP initialized with {len(self._mcp_tools)} tools")
                else:
                    logger.warning(f"Notion MCP connection failed")
                    self._mcp_adapter = None  # Reset on failure
            except Exception as e:
                logger.error(f"Notion MCP initialization error: {e}", exc_info=True)
                self._mcp_adapter = None
                raise  # Re-raise to provide more context
    
    async def _ensure_mcp_initialized(self):
        """Ensure MCP adapter is initialized (idempotent)."""
        if self.use_mcp and not self._mcp_tools:
            try:
                await self._init_mcp()
                if self._mcp_tools:
                    return True
            except Exception as e:
                logger.error(f"Failed to ensure MCP initialization: {e}")
        return False
    
    def create_tools(self) -> List[BaseTool]:
        """Create Notion tools, preferring MCP if available, falling back to Direct API."""
        # Try to initialize MCP synchronously if configured
        if self.use_mcp:
            try:
                # Check if we're in an async context
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an async context, we can't use run_until_complete
                    # In this case, MCP tools will be initialized lazily on first use
                    if not self._mcp_tools:
                        logger.warning(
                            "Notion MCP initialization deferred (async context detected). "
                            "Will initialize on first use or fall back to Direct API."
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
                logger.warning(f"Failed to initialize Notion MCP: {e}. Falling back to Direct API.")
        
        # Return MCP tools if available
        if self.use_mcp and self._mcp_tools:
            logger.info("Using Notion MCP tools")
            return self._mcp_tools
        
        # Fallback to Direct API tools
        if self._direct_api_tools is None:
            self._direct_api_tools = self._create_direct_api_tools()
        
        if self._direct_api_tools:
            logger.info("Using Notion Direct API tools")
            return self._direct_api_tools
        
        # Neither MCP nor Direct API is available
        logger.warning(
            "Notion tools not available. Configure either:\n"
            "  - MCP: USE_NOTION_MCP=true and NOTION_MCP_COMMAND\n"
            "  - Direct API: NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
        )
        return []
    
    def _create_direct_api_tools(self) -> List[BaseTool]:
        """Create LangChain tools for Direct API mode."""
        is_valid, error_msg = self._validate_notion_api_config()
        if not is_valid:
            logger.warning(f"Direct API not configured: {error_msg}")
            return []
        
        def create_notion_page(
            parent_page_id: str,
            title: str,
            content_blocks: List[Dict[str, Any]]
        ) -> Dict[str, Any]:
            """Create a Notion page using Direct API.
            
            Args:
                parent_page_id: Notion page ID to create under
                title: Page title
                content_blocks: List of content blocks (formatted for Notion)
            
            Returns:
                Dict with page creation result (page_id, url, etc.)
            """
            return self._create_page_direct_api(parent_page_id, title, content_blocks)
        
        # Create LangChain tool
        create_page_tool = tool("create_notion_page")(create_notion_page)
        return [create_page_tool]
    
    def get_create_page_tool(self) -> Optional[BaseTool]:
        """Get the create page tool from MCP tools."""
        if not self._mcp_tools:
            return None
        
        # Look for create page tool (could be notion-create-pages or similar)
        for tool in self._mcp_tools:
            if "create" in tool.name.lower() and "page" in tool.name.lower():
                return tool
        
        # Fallback: return first tool if no specific match
        return self._mcp_tools[0] if self._mcp_tools else None
    
    async def create_study_plan_page(
        self,
        parent_page_id: str,
        title: str,
        content_blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a Notion page for a study plan.
        
        Supports both MCP and Direct API modes. Tries MCP first if configured,
        otherwise falls back to Direct API.
        
        Args:
            parent_page_id: Notion page ID to create under
            title: Page title
            content_blocks: List of content blocks (formatted for Notion)
        
        Returns:
            Dict with page creation result (page_id, url, etc.)
        """
        # Try MCP mode first if configured
        if self.use_mcp:
            command = getattr(self.config, 'NOTION_MCP_COMMAND', None)
            if not command:
                logger.warning("USE_NOTION_MCP=true but NOTION_MCP_COMMAND not set. Falling back to Direct API.")
            else:
                # Try to initialize if not already done
                if not self._mcp_tools:
                    try:
                        initialized = await self._ensure_mcp_initialized()
                        if not initialized:
                            logger.warning("MCP initialization failed. Falling back to Direct API.")
                        else:
                            # MCP initialized successfully, use it
                            create_tool = self.get_create_page_tool()
                            if create_tool:
                                try:
                                    # Call the MCP tool with appropriate parameters
                                    result = create_tool.invoke({
                                        "parent_page_id": parent_page_id,
                                        "title": title,
                                        "content": content_blocks
                                    })
                                    return result
                                except Exception as e:
                                    logger.error(f"Failed to create Notion page via MCP: {e}", exc_info=True)
                                    logger.warning("Falling back to Direct API.")
                    except Exception as e:
                        logger.error(f"Exception during MCP initialization: {e}", exc_info=True)
                        logger.warning("Falling back to Direct API.")
                else:
                    # MCP tools already initialized, use them
                    create_tool = self.get_create_page_tool()
                    if create_tool:
                        try:
                            result = create_tool.invoke({
                                "parent_page_id": parent_page_id,
                                "title": title,
                                "content": content_blocks
                            })
                            return result
                        except Exception as e:
                            logger.error(f"Failed to create Notion page via MCP: {e}", exc_info=True)
                            logger.warning("Falling back to Direct API.")
        
        # Fallback to Direct API mode
        logger.info("Using Direct API to create Notion page")
        is_valid, error_msg = self._validate_notion_api_config()
        if not is_valid:
            # Provide helpful error message
            error_details = []
            if not self.notion_api_key:
                error_details.append("NOTION_API_KEY not set")
            if not getattr(self.config, 'NOTION_PARENT_PAGE_ID', None):
                error_details.append("NOTION_PARENT_PAGE_ID not set")
            
            return {
                "error": "Notion Direct API not configured",
                "details": "; ".join(error_details) if error_details else error_msg,
                "suggestion": (
                    "Configure either:\n"
                    "  - MCP: USE_NOTION_MCP=true and NOTION_MCP_COMMAND\n"
                    "  - Direct API: NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
                )
            }
        
        # Use Direct API
        result = self._create_page_direct_api(parent_page_id, title, content_blocks)
        return result

