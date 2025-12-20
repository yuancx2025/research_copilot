#!/usr/bin/env python3
"""
Manual test script for remote MCP tools (GitHub and Tavily).

This script allows interactive testing of remote MCP tools via terminal.

Usage:
    # Test remote GitHub MCP server
    python3 test_mcp_manual.py --github-only --github-url https://...
    
    # Test remote Tavily MCP server
    python3 test_mcp_manual.py --tavily-only --tavily-url https://...
    
    # Test both remote servers
    python3 test_mcp_manual.py --all --github-url https://... --tavily-url https://...
"""

import os
import sys
import asyncio
import argparse
import json
from typing import Dict, Any, Optional
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.github_tools import GitHubToolkit
from tools.web_tools import WebToolkit
from tools.mcp.adapter import MCPToolAdapter


def create_config(args: argparse.Namespace) -> Mock:
    """Create configuration based on command line arguments."""
    config = Mock()
    
    # MCP enablement
    config.USE_GITHUB_MCP = args.github or args.all
    config.USE_WEB_SEARCH_MCP = args.tavily or args.all
    
    # Remote MCP server URLs (required)
    config.GITHUB_MCP_SERVER_URL = args.github_url or os.getenv("GITHUB_MCP_SERVER_URL")
    config.WEB_SEARCH_MCP_SERVER_URL = args.tavily_url or os.getenv("WEB_SEARCH_MCP_SERVER_URL")
    config.MCP_SERVER_AUTH_TOKEN = args.auth_token or os.getenv("MCP_SERVER_AUTH_TOKEN")
    
    # API keys/tokens (for server-side use or fallback)
    config.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", args.github_token)
    config.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", args.tavily_key)
    config.MAX_WEB_RESULTS = 10
    config.MCP_CONNECTION_TIMEOUT = 30
    
    return config


async def test_github_mcp_tools(config: Mock) -> None:
    """Test GitHub MCP tools interactively."""
    print("\n" + "="*80)
    print("GITHUB MCP TOOLS TEST")
    print("="*80)
    
    toolkit = GitHubToolkit(config)
    
    print(f"\nConfiguration:")
    print(f"  MCP Enabled: {toolkit.use_mcp}")
    if toolkit.use_mcp:
        print(f"  Remote URL: {getattr(config, 'GITHUB_MCP_SERVER_URL', 'N/A')}")
    print(f"  GitHub Token: {'Set' if toolkit.token else 'Not set (rate limited)'}")
    
    # Initialize MCP
    if toolkit.use_mcp:
        print("\n--- Initializing GitHub MCP ---")
        try:
            await toolkit._ensure_mcp_initialized()
            if toolkit._mcp_tools:
                print(f"✅ MCP initialized successfully!")
                print(f"   Found {len(toolkit._mcp_tools)} tools:")
                for tool in toolkit._mcp_tools:
                    print(f"   - {tool.name}")
            else:
                print("❌ MCP initialization failed, using direct API")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Get tools
    tools = toolkit.create_tools()
    print(f"\n--- Available Tools ({len(tools)}) ---")
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool.name}")
        print(f"   {tool.description[:100]}...")
    
    # Interactive testing
    print("\n" + "-"*80)
    print("INTERACTIVE TESTING")
    print("-"*80)
    print("Available commands:")
    print("  search <query>              - Search GitHub repositories")
    print("  readme <owner/repo>         - Get README from repository")
    print("  file <owner/repo> <path>    - Get file content")
    print("  structure <owner/repo>      - Get repository structure")
    print("  list                        - List all available tools")
    print("  discover                    - Discover MCP tools")
    print("  quit                        - Exit")
    
    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue
            
            if cmd == "quit":
                break
            elif cmd == "list":
                print("\nAvailable tools:")
                for i, tool in enumerate(tools, 1):
                    print(f"{i}. {tool.name}")
            elif cmd == "discover" and toolkit.use_mcp and toolkit._mcp_adapter:
                print("\nDiscovering MCP tools...")
                mcp_tools = await toolkit._mcp_adapter.discover_tools()
                print(f"Found {len(mcp_tools)} tools:")
                for tool_info in mcp_tools:
                    print(f"  - {tool_info['name']}")
                    print(f"    {tool_info.get('description', 'N/A')[:80]}")
            elif cmd.startswith("search "):
                query = cmd[7:].strip()
                if not query:
                    print("Usage: search <query>")
                    continue
                print(f"\nSearching for: {query}")
                # Find search tool
                search_tool = next((t for t in tools if "search" in t.name.lower()), None)
                if search_tool:
                    try:
                        result = search_tool.invoke({"query": query, "max_results": 5})
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Search tool not found")
            elif cmd.startswith("readme "):
                repo = cmd[7:].strip()
                if not repo:
                    print("Usage: readme <owner/repo>")
                    continue
                print(f"\nGetting README for: {repo}")
                readme_tool = next((t for t in tools if "readme" in t.name.lower()), None)
                if readme_tool:
                    try:
                        result = readme_tool.invoke({"repo": repo})
                        print(json.dumps(result, indent=2)[:1000])  # Limit output
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("README tool not found")
            elif cmd.startswith("file "):
                parts = cmd[5:].strip().split(" ", 1)
                if len(parts) != 2:
                    print("Usage: file <owner/repo> <path>")
                    continue
                repo, path = parts
                print(f"\nGetting file {path} from {repo}")
                file_tool = next((t for t in tools if "file" in t.name.lower()), None)
                if file_tool:
                    try:
                        result = file_tool.invoke({"repo": repo, "path": path})
                        print(json.dumps(result, indent=2)[:2000])  # Limit output
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("File tool not found")
            elif cmd.startswith("structure "):
                repo = cmd[10:].strip()
                if not repo:
                    print("Usage: structure <owner/repo>")
                    continue
                print(f"\nGetting structure for: {repo}")
                structure_tool = next((t for t in tools if "structure" in t.name.lower()), None)
                if structure_tool:
                    try:
                        result = structure_tool.invoke({"repo": repo})
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Structure tool not found")
            else:
                print("Unknown command. Type 'quit' to exit.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


async def test_tavily_mcp_tools(config: Mock) -> None:
    """Test Tavily MCP tools interactively."""
    print("\n" + "="*80)
    print("TAVILY/WEB SEARCH MCP TOOLS TEST")
    print("="*80)
    
    toolkit = WebToolkit(config)
    
    print(f"\nConfiguration:")
    print(f"  MCP Enabled: {toolkit.use_mcp}")
    if toolkit.use_mcp:
        print(f"  Remote URL: {getattr(config, 'WEB_SEARCH_MCP_SERVER_URL', 'N/A')}")
    print(f"  Tavily API Key: {'Set' if toolkit.tavily_api_key else 'Not set'}")
    
    # Initialize MCP
    if toolkit.use_mcp:
        print("\n--- Initializing Web Search MCP ---")
        try:
            await toolkit._ensure_mcp_initialized()
            if toolkit._mcp_tools:
                print(f"✅ MCP initialized successfully!")
                print(f"   Found {len(toolkit._mcp_tools)} tools:")
                for tool in toolkit._mcp_tools:
                    print(f"   - {tool.name}")
            else:
                print("❌ MCP initialization failed, using direct API")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Get tools
    tools = toolkit.create_tools()
    print(f"\n--- Available Tools ({len(tools)}) ---")
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool.name}")
        print(f"   {tool.description[:100]}...")
    
    # Interactive testing
    print("\n" + "-"*80)
    print("INTERACTIVE TESTING")
    print("-"*80)
    print("Available commands:")
    print("  search <query>              - Search the web")
    print("  extract <url>               - Extract webpage content")
    print("  docs <library> <query>      - Search documentation")
    print("  code <url>                  - Extract code from URL")
    print("  list                        - List all available tools")
    print("  discover                    - Discover MCP tools")
    print("  quit                        - Exit")
    
    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue
            
            if cmd == "quit":
                break
            elif cmd == "list":
                print("\nAvailable tools:")
                for i, tool in enumerate(tools, 1):
                    print(f"{i}. {tool.name}")
            elif cmd == "discover" and toolkit.use_mcp and toolkit._mcp_adapter:
                print("\nDiscovering MCP tools...")
                mcp_tools = await toolkit._mcp_adapter.discover_tools()
                print(f"Found {len(mcp_tools)} tools:")
                for tool_info in mcp_tools:
                    print(f"  - {tool_info['name']}")
                    print(f"    {tool_info.get('description', 'N/A')[:80]}")
            elif cmd.startswith("search "):
                query = cmd[7:].strip()
                if not query:
                    print("Usage: search <query>")
                    continue
                print(f"\nSearching for: {query}")
                search_tool = next((t for t in tools if "search" in t.name.lower() and "doc" not in t.name.lower()), None)
                if search_tool:
                    try:
                        result = search_tool.invoke({"query": query, "max_results": 5})
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Search tool not found")
            elif cmd.startswith("extract "):
                url = cmd[8:].strip()
                if not url:
                    print("Usage: extract <url>")
                    continue
                print(f"\nExtracting content from: {url}")
                extract_tool = next((t for t in tools if "extract" in t.name.lower()), None)
                if extract_tool:
                    try:
                        result = extract_tool.invoke({"url": url})
                        print(json.dumps(result, indent=2)[:2000])  # Limit output
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Extract tool not found")
            elif cmd.startswith("docs "):
                parts = cmd[5:].strip().split(" ", 1)
                if len(parts) != 2:
                    print("Usage: docs <library> <query>")
                    continue
                library, query = parts
                print(f"\nSearching {library} docs for: {query}")
                docs_tool = next((t for t in tools if "doc" in t.name.lower()), None)
                if docs_tool:
                    try:
                        result = docs_tool.invoke({"library_name": library, "query": query})
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Docs search tool not found")
            elif cmd.startswith("code "):
                url = cmd[5:].strip()
                if not url:
                    print("Usage: code <url>")
                    continue
                print(f"\nExtracting code from: {url}")
                code_tool = next((t for t in tools if "code" in t.name.lower()), None)
                if code_tool:
                    try:
                        result = code_tool.invoke({"url": url})
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    print("Code extraction tool not found")
            else:
                print("Unknown command. Type 'quit' to exit.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


async def test_mcp_adapter_directly(config: Mock) -> None:
    """Test MCP adapter directly."""
    print("\n" + "="*80)
    print("MCP ADAPTER DIRECT TEST (Remote Only)")
    print("="*80)
    
    # Test GitHub MCP
    if config.USE_GITHUB_MCP:
        print("\n--- Testing GitHub MCP Adapter ---")
        server_url = getattr(config, 'GITHUB_MCP_SERVER_URL')
        if not server_url:
            print("❌ GITHUB_MCP_SERVER_URL not configured")
        else:
            headers = {}
            auth_token = getattr(config, 'MCP_SERVER_AUTH_TOKEN')
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            server_config = {
                "url": server_url,
                "headers": headers,
                "timeout": 30
            }
            
            adapter = MCPToolAdapter("github", server_config)
            connected = await adapter.connect()
            if connected:
                print("✅ Connected!")
                tools = await adapter.discover_tools()
                print(f"   Discovered {len(tools)} tools:")
                for tool_info in tools:
                    print(f"   - {tool_info['name']}")
            else:
                print("❌ Connection failed")
    
    # Test Tavily MCP
    if config.USE_WEB_SEARCH_MCP:
        print("\n--- Testing Tavily MCP Adapter ---")
        server_url = getattr(config, 'WEB_SEARCH_MCP_SERVER_URL')
        if not server_url:
            print("❌ WEB_SEARCH_MCP_SERVER_URL not configured")
        else:
            headers = {}
            auth_token = getattr(config, 'MCP_SERVER_AUTH_TOKEN')
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            if config.TAVILY_API_KEY:
                headers["X-Tavily-API-Key"] = config.TAVILY_API_KEY
            
            server_config = {
                "url": server_url,
                "headers": headers,
                "timeout": 30
            }
            
            adapter = MCPToolAdapter("tavily", server_config)
            connected = await adapter.connect()
            if connected:
                print("✅ Connected!")
                tools = await adapter.discover_tools()
                print(f"   Discovered {len(tools)} tools:")
                for tool_info in tools:
                    print(f"   - {tool_info['name']}")
            else:
                print("❌ Connection failed")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Manual test script for remote MCP tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test GitHub MCP
  python3 test_mcp_manual.py --github-only --github-url https://mcp-github.example.com/sse
  
  # Test Tavily MCP
  python3 test_mcp_manual.py --tavily-only --tavily-url https://mcp-tavily.example.com/sse
  
  # Test both
  python3 test_mcp_manual.py --all --github-url https://... --tavily-url https://...
  
  # Use environment variables
  export GITHUB_MCP_SERVER_URL="https://..."
  export WEB_SEARCH_MCP_SERVER_URL="https://..."
  python3 test_mcp_manual.py --all
        """
    )
    
    # Test selection
    parser.add_argument("--github-only", action="store_true", help="Test only GitHub MCP")
    parser.add_argument("--tavily-only", action="store_true", help="Test only Tavily MCP")
    parser.add_argument("--all", action="store_true", help="Test both (default)")
    parser.add_argument("--adapter", action="store_true", help="Test adapter directly")
    
    # Remote server URLs (required)
    parser.add_argument("--github-url", type=str, help="GitHub MCP server URL (or use GITHUB_MCP_SERVER_URL env)")
    parser.add_argument("--tavily-url", type=str, help="Tavily MCP server URL (or use WEB_SEARCH_MCP_SERVER_URL env)")
    parser.add_argument("--auth-token", type=str, help="Authentication token (or use MCP_SERVER_AUTH_TOKEN env)")
    
    # API keys (can also use environment variables)
    parser.add_argument("--github-token", type=str, help="GitHub token (or use GITHUB_TOKEN env)")
    parser.add_argument("--tavily-key", type=str, help="Tavily API key (or use TAVILY_API_KEY env)")
    
    args = parser.parse_args()
    
    # Determine what to test
    if args.github_only:
        args.github = True
        args.tavily = False
    elif args.tavily_only:
        args.github = False
        args.tavily = True
    else:
        args.github = True
        args.tavily = True
    
    # Validate required URLs
    if args.github and not (args.github_url or os.getenv("GITHUB_MCP_SERVER_URL")):
        parser.error("--github-url or GITHUB_MCP_SERVER_URL environment variable is required")
    if args.tavily and not (args.tavily_url or os.getenv("WEB_SEARCH_MCP_SERVER_URL")):
        parser.error("--tavily-url or WEB_SEARCH_MCP_SERVER_URL environment variable is required")
    
    # Create config
    config = create_config(args)
    
    # Run tests
    async def run_tests():
        if args.adapter:
            await test_mcp_adapter_directly(config)
        else:
            if args.github:
                await test_github_mcp_tools(config)
            if args.tavily:
                await test_tavily_mcp_tools(config)
    
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

