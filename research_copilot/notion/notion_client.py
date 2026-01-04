"""
Pure HTTP/REST client for Notion API.

Handles all HTTP operations with Notion API. No rendering or layout knowledge.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import requests

logger = logging.getLogger(__name__)

# Notion API constants
NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MAX_BLOCKS_PER_REQUEST = 100


def _validate_notion_api_config(config) -> Tuple[bool, Optional[str]]:
    """Check if Direct API config is valid."""
    notion_api_key = getattr(config, 'NOTION_API_KEY', None)
    parent_page_id = getattr(config, 'NOTION_PARENT_PAGE_ID', None)
    
    if not notion_api_key:
        return False, "NOTION_API_KEY not configured"
    if not parent_page_id:
        return False, "NOTION_PARENT_PAGE_ID not configured"
    
    return True, None


def _normalize_page_id(page_id: str) -> Tuple[str, Optional[str]]:
    """Normalize Notion page ID to UUID format."""
    original_id = page_id.strip()
    normalized_id = original_id
    
    if "notion.so" in normalized_id:
        parts = normalized_id.split("-")
        if len(parts) > 0:
            normalized_id = parts[-1].split("?")[0].split("#")[0]
    
    normalized_id = normalized_id.replace("-", "")
    
    if len(normalized_id) == 32:
        normalized_id = f"{normalized_id[:8]}-{normalized_id[8:12]}-{normalized_id[12:16]}-{normalized_id[16:20]}-{normalized_id[20:]}"
    elif len(normalized_id) < 32:
        return None, f"Invalid parent_page_id format: too short ({len(normalized_id)} characters, expected 32)"
    
    if len(normalized_id) != 36:
        return None, f"Invalid parent_page_id format: expected UUID format (got {len(normalized_id)} chars)"
    
    return normalized_id, None


def append_blocks(block_id: str, children: List[Dict[str, Any]], notion_api_key: str) -> Dict[str, Any]:
    """
    Append blocks to an existing Notion page using Direct REST API.
    
    Args:
        block_id: Notion block/page ID
        children: List of block dictionaries to append
        notion_api_key: Notion API key
        
    Returns:
        Dict with success/error status
    """
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    payload = {"children": children}
    
    try:
        response = requests.patch(
            f"{NOTION_BASE_URL}/blocks/{block_id}/children",
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


def create_page(
    parent_page_id: str,
    title: str,
    children_blocks: List[Dict[str, Any]],
    config
) -> Dict[str, Any]:
    """
    Create a Notion page with blocks.
    
    Pure HTTP client - accepts blocks, not study plan dict.
    
    Args:
        parent_page_id: Notion page ID to create under
        title: Page title
        children_blocks: List of Notion block dictionaries
        config: Configuration object with NOTION_API_KEY
        
    Returns:
        Dict with page_id, url, error (if any)
    """
    is_valid, error_msg = _validate_notion_api_config(config)
    if not is_valid:
        return {"error": error_msg}
    
    notion_api_key = getattr(config, 'NOTION_API_KEY', None)
    
    # Normalize parent page ID
    normalized_parent_id, id_error = _normalize_page_id(parent_page_id)
    if id_error:
        return {"error": id_error}
    
    # Split blocks into chunks if needed
    initial_blocks = children_blocks[:MAX_BLOCKS_PER_REQUEST]
    remaining_blocks = children_blocks[MAX_BLOCKS_PER_REQUEST:]
    
    if len(children_blocks) > MAX_BLOCKS_PER_REQUEST:
        logger.info(f"Splitting {len(children_blocks)} blocks into chunks: {len(initial_blocks)} initial + {len(remaining_blocks)} remaining")
    
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    payload = {
        "parent": {"page_id": normalized_parent_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        },
        "children": initial_blocks
    }
    
    try:
        logger.info(f"Creating Notion page with parent_id: {parent_page_id[:8]}..., title: {title[:50]}...")
        
        response = requests.post(
            f"{NOTION_BASE_URL}/pages",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            try:
                data = response.json()
                page_id = data.get("id", "")
                
                if not page_id:
                    return {
                        "error": "Notion API returned success but no page_id in response",
                        "response_data": str(data)[:500]
                    }
                
                page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
                
                # Append remaining blocks if any
                if remaining_blocks:
                    logger.info(f"Appending {len(remaining_blocks)} remaining blocks to page {page_id}")
                    for i in range(0, len(remaining_blocks), MAX_BLOCKS_PER_REQUEST):
                        chunk = remaining_blocks[i:i + MAX_BLOCKS_PER_REQUEST]
                        append_result = append_blocks(page_id, chunk, notion_api_key)
                        if append_result.get("error"):
                            logger.error(f"Failed to append block chunk {i//MAX_BLOCKS_PER_REQUEST + 1}: {append_result.get('error')}")
                
                logger.info(f"Notion page created successfully: {page_id} -> {page_url}")
                
                return {
                    "page_id": page_id,
                    "url": page_url,
                    "page_url": page_url,
                    "error": None
                }
            except ValueError as e:
                logger.error(f"Failed to parse Notion API response as JSON: {e}")
                return {
                    "error": f"Invalid JSON response from Notion API: {str(e)}",
                    "status_code": response.status_code,
                    "response_preview": response.text[:500]
                }
        else:
            try:
                error_data = response.json() if response.content else {}
                error_message = error_data.get("message", f"HTTP {response.status_code}")
                error_code = error_data.get("code", "")
                
                logger.error(f"Notion API error: {error_message} (code: {error_code}, status: {response.status_code})")
                
                if error_code == "object_not_found" and response.status_code == 404:
                    detailed_error = (
                        f"Notion API error: {error_message}\n\n"
                        "This usually means:\n"
                        "1. The parent page ID is incorrect, OR\n"
                        "2. The parent page is not shared with your Notion integration\n\n"
                        f"Page ID used: {normalized_parent_id}"
                    )
                else:
                    detailed_error = f"Notion API error: {error_message}"
                
                return {
                    "error": detailed_error,
                    "error_code": error_code,
                    "status_code": response.status_code
                }
            except ValueError:
                logger.error(f"Notion API error (non-JSON): Status {response.status_code}")
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

