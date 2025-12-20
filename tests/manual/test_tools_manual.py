#!/usr/bin/env python3
"""
Manual testing script for Research Copilot tools.

This script allows you to quickly test tools with real APIs.
Set environment variables for API keys (optional for most tools).

Usage:
    python test_tools_manual.py
    python test_tools_manual.py --tool arxiv
    python test_tools_manual.py --tool github --query "langchain"
"""
import os
import sys
import argparse
from unittest.mock import Mock

def create_config():
    """Create a mock config object with environment variables."""
    config = Mock()
    
    # ArXiv - no key needed
    config.MAX_ARXIV_RESULTS = 5
    config.ENABLE_ARXIV_AGENT = True
    
    # GitHub - optional token
    config.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    config.USE_GITHUB_MCP = False
    config.ENABLE_GITHUB_AGENT = True
    
    # YouTube - optional API key
    config.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
    config.ENABLE_YOUTUBE_AGENT = True
    
    # Web - optional Tavily key
    config.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    config.USE_WEB_SEARCH_MCP = False
    config.MAX_WEB_RESULTS = 5
    config.ENABLE_WEB_AGENT = True
    
    return config


def test_arxiv(config, query="transformer neural network"):
    """Test ArXiv tools."""
    print("\n" + "="*60)
    print("Testing ArXiv Tools")
    print("="*60)
    
    try:
        from tools.arxiv_tools import ArxivToolkit
        
        toolkit = ArxivToolkit(config)
        
        print(f"\n1. Searching ArXiv for: '{query}'")
        results = toolkit._search_arxiv(query, max_results=3)
        
        if results and "error" not in results[0]:
            print(f"   ✓ Found {len(results)} papers")
            for i, r in enumerate(results[:3], 1):
                print(f"   {i}. {r.get('title', 'Unknown')[:60]}...")
                print(f"      ID: {r.get('arxiv_id')}, Published: {r.get('published')}")
        else:
            print(f"   ✗ Error: {results[0].get('error', 'Unknown error')}")
        
        if results and "arxiv_id" in results[0]:
            print(f"\n2. Getting full content for paper: {results[0]['arxiv_id']}")
            paper = toolkit._get_paper_content(results[0]['arxiv_id'])
            if "error" not in paper:
                print(f"   ✓ Retrieved paper: {paper.get('title', 'Unknown')[:60]}...")
                print(f"   Content length: {len(paper.get('content', ''))} chars")
            else:
                print(f"   ✗ Error: {paper.get('error')}")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")


def test_github(config, query="langchain"):
    """Test GitHub tools."""
    print("\n" + "="*60)
    print("Testing GitHub Tools")
    print("="*60)
    
    try:
        from tools.github_tools import GitHubToolkit
        
        toolkit = GitHubToolkit(config)
        
        print(f"\n1. Searching GitHub for: '{query}'")
        results = toolkit._search_repositories(query, max_results=3)
        
        if results and "error" not in results[0]:
            print(f"   ✓ Found {len(results)} repositories")
            for i, r in enumerate(results[:3], 1):
                print(f"   {i}. {r.get('full_name')}")
                print(f"      Stars: {r.get('stars')}, Language: {r.get('language')}")
        else:
            print(f"   ✗ Error: {results[0].get('error', 'Unknown error')}")
        
        if results and "full_name" in results[0]:
            repo = results[0]['full_name']
            print(f"\n2. Getting README for: {repo}")
            readme = toolkit._get_readme(repo)
            if "error" not in readme:
                print(f"   ✓ Retrieved README ({len(readme.get('content', ''))} chars)")
            else:
                print(f"   ✗ Error: {readme.get('error')}")
            
            print(f"\n3. Getting repository structure for: {repo}")
            structure = toolkit._get_repo_structure(repo, "")
            if "error" not in structure:
                print(f"   ✓ Retrieved structure with {len(structure.get('contents', []))} items")
                for item in structure.get('contents', [])[:5]:
                    print(f"      - {item['name']} ({item['type']})")
            else:
                print(f"   ✗ Error: {structure.get('error')}")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")


def test_youtube(config, video_id=None):
    """Test YouTube tools."""
    print("\n" + "="*60)
    print("Testing YouTube Tools")
    print("="*60)
    
    try:
        from tools.youtube_tools import YouTubeToolkit
        
        toolkit = YouTubeToolkit(config)
        
        # Use a known working video ID if none provided
        if video_id is None:
            video_id = "kqtD5dpn9C8"  # Python tutorial with transcripts
            print(f"   Using default test video: {video_id}")
        
        print(f"\n1. Getting transcript for video: {video_id}")
        result = toolkit._get_youtube_transcript(video_id)
        
        if "error" not in result:
            print(f"   ✓ Retrieved transcript")
            print(f"   Type: {result.get('transcript_type')}")
            print(f"   Language: {result.get('language')}")
            print(f"   Length: {len(result.get('transcript', ''))} chars")
            print(f"   Preview: {result.get('transcript', '')[:100]}...")
        else:
            print(f"   ✗ Error: {result.get('error')}")
            print(f"   Note: Video may not have transcripts enabled")
        
        if config.YOUTUBE_API_KEY:
            print(f"\n2. Searching YouTube for: 'python tutorial'")
            results = toolkit._search_youtube("python tutorial", max_results=3)
            if results and "error" not in results[0]:
                print(f"   ✓ Found {len(results)} videos")
                for i, r in enumerate(results[:3], 1):
                    print(f"   {i}. {r.get('title', 'Unknown')[:60]}...")
            else:
                print(f"   ✗ Error: {results[0].get('error', 'Unknown error')}")
        else:
            print(f"\n2. Skipping search (YOUTUBE_API_KEY not set)")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")


def test_web(config, url="https://www.python.org"):
    """Test web tools."""
    print("\n" + "="*60)
    print("Testing Web Tools")
    print("="*60)
    
    try:
        from tools.web_tools import WebToolkit
        
        toolkit = WebToolkit(config)
        
        print(f"\n1. Extracting content from: {url}")
        result = toolkit._extract_webpage_content(url)
        
        if "error" not in result:
            print(f"   ✓ Extracted content")
            print(f"   Title: {result.get('title', 'Unknown')}")
            print(f"   Length: {len(result.get('content', ''))} chars")
            print(f"   Words: {result.get('word_count', 0)}")
            print(f"   Preview: {result.get('content', '')[:100]}...")
        else:
            print(f"   ✗ Error: {result.get('error')}")
        
        if config.TAVILY_API_KEY:
            print(f"\n2. Searching web for: 'python programming'")
            results = toolkit._web_search("python programming", max_results=3)
            if results and "error" not in results[0]:
                print(f"   ✓ Found {len(results)} results")
                for i, r in enumerate(results[:3], 1):
                    print(f"   {i}. {r.get('title', 'Unknown')[:60]}...")
                    print(f"      URL: {r.get('url', '')[:50]}...")
            else:
                print(f"   ✗ Error: {results[0].get('error', 'Unknown error')}")
        else:
            print(f"\n2. Skipping search (TAVILY_API_KEY not set)")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")


def test_registry(config):
    """Test tool registry."""
    print("\n" + "="*60)
    print("Testing Tool Registry")
    print("="*60)
    
    try:
        from tools.registry import initialize_registry
        from tools.base import SourceType
        
        registry = initialize_registry(config)
        
        available_sources = registry.list_available_sources()
        print(f"\n✓ Registry initialized")
        print(f"   Available sources: {[s.value for s in available_sources]}")
        
        tools = registry.get_all_tools()
        print(f"   Total tools: {len(tools)}")
        print(f"   Tool names: {[t.name for t in tools[:10]]}")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test Research Copilot tools manually")
    parser.add_argument("--tool", choices=["arxiv", "github", "youtube", "web", "registry", "all"],
                       default="all", help="Which tool to test")
    parser.add_argument("--query", default=None, help="Search query")
    parser.add_argument("--video-id", default="dQw4w9WgXcQ", help="YouTube video ID")
    parser.add_argument("--url", default="https://www.python.org", help="URL to extract")
    
    args = parser.parse_args()
    
    config = create_config()
    
    print("="*60)
    print("Research Copilot Tools - Manual Testing")
    print("="*60)
    print("\nNote: Some tools require API keys (set as environment variables)")
    print("      Most tools work without keys but may have rate limits\n")
    
    if args.tool == "all":
        test_arxiv(config, args.query or "transformer neural network")
        test_github(config, args.query or "langchain")
        test_youtube(config, args.video_id)
        test_web(config, args.url)
        test_registry(config)
    elif args.tool == "arxiv":
        test_arxiv(config, args.query or "transformer neural network")
    elif args.tool == "github":
        test_github(config, args.query or "langchain")
    elif args.tool == "youtube":
        test_youtube(config, args.video_id)
    elif args.tool == "web":
        test_web(config, args.url)
    elif args.tool == "registry":
        test_registry(config)
    
    print("\n" + "="*60)
    print("Testing Complete!")
    print("="*60)


if __name__ == "__main__":
    main()

