#!/usr/bin/env python3
"""
Test script for MCP implementations (GitHub and Tavily).

This script:
1. Tests GitHub MCP connection and tool discovery
2. Tests Tavily MCP connection and tool discovery
3. Compares available tools between MCP and direct API modes
4. Shows what additional tools MCP servers provide
"""

import os
import sys
import asyncio
import logging
from unittest.mock import Mock

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.github_tools import GitHubToolkit
from tools.web_tools import WebToolkit
from tools.mcp.adapter import MCPToolAdapter


def create_test_config():
    """Create a test configuration."""
    config = Mock()
    
    # GitHub config
    config.USE_GITHUB_MCP = True
    config.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    
    # Web/Tavily config
    config.USE_WEB_SEARCH_MCP = True
    config.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    config.MAX_WEB_RESULTS = 10
    config.WEB_SEARCH_MCP_SERVER_PATH = None
    
    return config


async def test_github_mcp():
    """Test GitHub MCP implementation."""
    print("\n" + "="*80)
    print("TESTING GITHUB MCP IMPLEMENTATION")
    print("="*80)
    
    config = create_test_config()
    config.USE_GITHUB_MCP = True
    
    toolkit = GitHubToolkit(config)
    
    print(f"\nGitHub MCP Enabled: {toolkit.use_mcp}")
    print(f"GitHub Token Available: {bool(toolkit.token)}")
    
    # Test MCP initialization
    print("\n--- Initializing GitHub MCP ---")
    try:
        await toolkit._ensure_mcp_initialized()
        
        if toolkit._mcp_tools:
            print(f"✅ GitHub MCP initialized successfully!")
            print(f"   Found {len(toolkit._mcp_tools)} MCP tools:")
            for tool in toolkit._mcp_tools:
                print(f"   - {tool.name}: {tool.description[:80]}...")
            
            # Discover all available tools from MCP server
            print("\n--- Discovering all MCP tools ---")
            if toolkit._mcp_adapter:
                mcp_tools = await toolkit._mcp_adapter.discover_tools()
                print(f"   MCP server provides {len(mcp_tools)} tools:")
                for mcp_tool in mcp_tools:
                    print(f"   - {mcp_tool['name']}")
                    print(f"     Description: {mcp_tool.get('description', 'N/A')[:100]}")
                    if mcp_tool.get('input_schema'):
                        props = mcp_tool['input_schema'].get('properties', {})
                        if props:
                            print(f"     Parameters: {', '.join(props.keys())}")
        else:
            print("❌ GitHub MCP initialization failed (will use direct API)")
            print("   This is expected if:")
            print("   - Node.js/npx is not installed")
            print("   - @modelcontextprotocol/server-github package is not available")
            print("   - Network issues preventing npm package download")
    except Exception as e:
        print(f"❌ Error during GitHub MCP initialization: {e}")
        import traceback
        traceback.print_exc()
    
    # Compare with direct API tools
    print("\n--- Direct API Tools (Fallback) ---")
    direct_tools = [
        "search_github",
        "get_github_readme",
        "get_github_file",
        "get_repo_structure"
    ]
    print(f"   Basic tools: {len(direct_tools)}")
    for tool_name in direct_tools:
        print(f"   - {tool_name}")
    
    return toolkit


async def test_tavily_mcp():
    """Test Tavily MCP implementation."""
    print("\n" + "="*80)
    print("TESTING TAVILY MCP IMPLEMENTATION")
    print("="*80)
    
    config = create_test_config()
    config.USE_WEB_SEARCH_MCP = True
    
    toolkit = WebToolkit(config)
    
    print(f"\nWeb Search MCP Enabled: {toolkit.use_mcp}")
    print(f"Tavily API Key Available: {bool(toolkit.tavily_api_key)}")
    
    # Check MCP server config
    print("\n--- MCP Server Configuration ---")
    server_config = toolkit._get_mcp_server_config()
    if server_config:
        print(f"✅ MCP server config found:")
        print(f"   Command: {server_config.get('command')}")
        print(f"   Args: {server_config.get('args')}")
        print(f"   Has API Key: {bool(server_config.get('env', {}).get('TAVILY_API_KEY'))}")
    else:
        print("⚠️  No MCP server config (will use direct API)")
        print("   This happens when:")
        print("   - TAVILY_API_KEY is not set")
        print("   - Custom web_search_mcp.py wrapper is not found")
    
    # Test MCP initialization
    print("\n--- Initializing Tavily MCP ---")
    try:
        await toolkit._ensure_mcp_initialized()
        
        if toolkit._mcp_tools:
            print(f"✅ Tavily MCP initialized successfully!")
            print(f"   Found {len(toolkit._mcp_tools)} MCP tools:")
            for tool in toolkit._mcp_tools:
                print(f"   - {tool.name}: {tool.description[:80]}...")
            
            # Discover all available tools from MCP server
            print("\n--- Discovering all MCP tools ---")
            if toolkit._mcp_adapter:
                mcp_tools = await toolkit._mcp_adapter.discover_tools()
                print(f"   MCP server provides {len(mcp_tools)} tools:")
                for mcp_tool in mcp_tools:
                    print(f"   - {mcp_tool['name']}")
                    print(f"     Description: {mcp_tool.get('description', 'N/A')[:100]}")
                    if mcp_tool.get('input_schema'):
                        props = mcp_tool['input_schema'].get('properties', {})
                        if props:
                            print(f"     Parameters: {', '.join(props.keys())}")
        else:
            print("❌ Tavily MCP initialization failed (will use direct API)")
            print("   This is expected if:")
            print("   - TAVILY_API_KEY is not set")
            print("   - MCP server wrapper fails to start")
            print("   - Required dependencies (mcp, tavily-python) are not installed")
    except Exception as e:
        print(f"❌ Error during Tavily MCP initialization: {e}")
        import traceback
        traceback.print_exc()
    
    # Compare with direct API tools
    print("\n--- Direct API Tools (Fallback) ---")
    direct_tools = [
        "web_search",
        "extract_webpage",
        "search_docs",
        "extract_code"
    ]
    print(f"   Basic tools: {len(direct_tools)}")
    for tool_name in direct_tools:
        print(f"   - {tool_name}")
    
    return toolkit


async def test_mcp_adapter_directly():
    """Test MCP adapter directly to see what tools are available."""
    print("\n" + "="*80)
    print("TESTING MCP ADAPTER DIRECTLY")
    print("="*80)
    
    # Test GitHub MCP server
    print("\n--- GitHub MCP Server ---")
    github_token = os.getenv("GITHUB_TOKEN", None)
    if github_token:
        try:
            adapter = MCPToolAdapter(
                server_name="github",
                server_config={
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": github_token}
                }
            )
            
            print("   Attempting to connect...")
            connected = await adapter.connect()
            
            if connected:
                print("   ✅ Connected successfully!")
                tools = await adapter.discover_tools()
                print(f"   📦 Discovered {len(tools)} tools:")
                for tool_info in tools:
                    print(f"      • {tool_info['name']}")
                    print(f"        {tool_info.get('description', 'No description')[:100]}")
            else:
                print("   ❌ Connection failed")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print("   ⚠️  GITHUB_TOKEN not set, skipping GitHub MCP test")
    
    # Test Tavily MCP server (our custom wrapper)
    print("\n--- Tavily MCP Server (Custom Wrapper) ---")
    tavily_key = os.getenv("TAVILY_API_KEY", None)
    if tavily_key:
        try:
            import os
            wrapper_path = os.path.join(
                os.path.dirname(__file__),
                "tools",
                "mcp",
                "web_search_mcp.py"
            )
            
            if os.path.exists(wrapper_path):
                adapter = MCPToolAdapter(
                    server_name="tavily",
                    server_config={
                        "command": "python",
                        "args": [wrapper_path],
                        "env": {"TAVILY_API_KEY": tavily_key}
                    }
                )
                
                print("   Attempting to connect...")
                connected = await adapter.connect()
                
                if connected:
                    print("   ✅ Connected successfully!")
                    tools = await adapter.discover_tools()
                    print(f"   📦 Discovered {len(tools)} tools:")
                    for tool_info in tools:
                        print(f"      • {tool_info['name']}")
                        print(f"        {tool_info.get('description', 'No description')[:100]}")
                else:
                    print("   ❌ Connection failed")
            else:
                print(f"   ⚠️  MCP wrapper not found at: {wrapper_path}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⚠️  TAVILY_API_KEY not set, skipping Tavily MCP test")


def print_summary():
    """Print summary of MCP vs Direct API."""
    print("\n" + "="*80)
    print("SUMMARY: MCP vs DIRECT API")
    print("="*80)
    
    print("\n📌 Key Points:")
    print("   1. MCP servers are LOCAL processes (not remote)")
    print("      - GitHub: Runs via npx (@modelcontextprotocol/server-github)")
    print("      - Tavily: Runs via Python (our custom wrapper)")
    print("   2. MCP servers communicate via stdio (standard input/output)")
    print("   3. Tools are DISCOVERED dynamically from MCP servers")
    print("   4. MCP servers can provide MORE tools than our basic implementations")
    
    print("\n🔧 GitHub MCP Server:")
    print("   - Official server: @modelcontextprotocol/server-github")
    print("   - Provides: All tools exposed by the GitHub MCP server")
    print("   - May include: search_repositories, get_file_contents, create_issue, etc.")
    print("   - Our basic tools: search_github, get_github_readme, get_github_file, get_repo_structure")
    
    print("\n🔧 Tavily MCP Server:")
    print("   - Custom wrapper: tools/mcp/web_search_mcp.py")
    print("   - Provides: web_search tool (can be extended)")
    print("   - Our basic tools: web_search, extract_webpage, search_docs, extract_code")
    
    print("\n✅ Benefits of MCP:")
    print("   - Automatic tool discovery (no need to manually define all tools)")
    print("   - Standardized interface across different services")
    print("   - Easy to add new tools (just update the MCP server)")
    print("   - Better error handling and connection management")
    
    print("\n⚠️  Requirements:")
    print("   - GitHub MCP: Node.js/npx installed, network access for npm")
    print("   - Tavily MCP: Python, mcp package, tavily-python package")
    print("   - Both require API keys/tokens for authentication")


async def main():
    """Main test function."""
    print("\n" + "="*80)
    print("MCP IMPLEMENTATION TEST SUITE")
    print("="*80)
    print("\nThis script tests:")
    print("  1. GitHub MCP integration")
    print("  2. Tavily MCP integration")
    print("  3. Tool discovery and comparison")
    print("\nNote: Some tests may fail if:")
    print("  - Required dependencies are not installed")
    print("  - API keys/tokens are not set")
    print("  - Network access is unavailable")
    
    # Test GitHub MCP
    await test_github_mcp()
    
    # Test Tavily MCP
    await test_tavily_mcp()
    
    # Test MCP adapter directly
    await test_mcp_adapter_directly()
    
    # Print summary
    print_summary()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

