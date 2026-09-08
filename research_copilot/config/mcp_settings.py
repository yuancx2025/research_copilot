"""Single configuration source shared by local and GCP settings."""
import os
from research_copilot.tools.mcp.config import normalize_command

USE_GITHUB_MCP = os.getenv('USE_GITHUB_MCP', 'false').lower() == 'true'
USE_WEB_SEARCH_MCP = os.getenv('USE_WEB_SEARCH_MCP', 'false').lower() == 'true'
NOTION_BACKEND = os.getenv('NOTION_BACKEND', 'disabled').lower()
if NOTION_BACKEND not in {'disabled', 'rest', 'mcp'}:
    raise ValueError('NOTION_BACKEND must be disabled, rest, or mcp')
USE_NOTION_MCP = NOTION_BACKEND == 'mcp'
NOTION_MCP_URL = 'https://mcp.notion.com/mcp'
OAUTH_BASE_URL = os.getenv('OAUTH_BASE_URL', 'http://127.0.0.1:7860').rstrip('/')
OAUTH_TIMEOUT = 300

def _command(prefix, default):
    command = os.getenv(prefix + '_MCP_COMMAND', default)
    args = [a for a in os.getenv(prefix + '_MCP_ARGS', '').split(',') if a]
    return normalize_command(command, args) if command else (None, [])

GITHUB_MCP_COMMAND, GITHUB_MCP_ARGS = _command('GITHUB', 'npx,-y,@modelcontextprotocol/server-github')
WEB_SEARCH_MCP_COMMAND, WEB_SEARCH_MCP_ARGS = _command('WEB_SEARCH', '')
