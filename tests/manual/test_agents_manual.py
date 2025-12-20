#!/usr/bin/env python3
"""
Manual testing script for agents with real LLM and APIs.

Usage:
    python test_agents_manual.py --agent arxiv --query "transformer neural networks"
    python test_agents_manual.py --agent youtube --video-id "dQw4w9WgXcQ"
    python test_agents_manual.py --agent github --query "langchain"
    python test_agents_manual.py --agent web --url "https://www.python.org"
    python test_agents_manual.py --agent local --query "machine learning"
"""
import os
import sys
import argparse
import uuid
from unittest.mock import Mock
import config

# Try to import LLM providers
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from agents.local_rag_agent import LocalRAGAgent
from agents.arxiv_agent import ArxivAgent
from agents.youtube_agent import YouTubeAgent
from agents.github_agent import GitHubAgent
from agents.web_agent import WebAgent
from orchestrator.state import AgentState


def create_config():
    """Create config with environment variables."""
    cfg = Mock()
    cfg.MAX_ARXIV_RESULTS = 5
    cfg.MAX_WEB_RESULTS = 5
    cfg.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    cfg.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
    cfg.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    cfg.USE_GITHUB_MCP = False
    cfg.USE_WEB_SEARCH_MCP = False
    cfg.ENABLE_ARXIV_AGENT = True
    cfg.ENABLE_YOUTUBE_AGENT = True
    cfg.ENABLE_GITHUB_AGENT = True
    cfg.ENABLE_WEB_AGENT = True
    return cfg


def test_agent(agent_name, query, llm, cfg, collection=None):
    """Test an agent with a real query."""
    print(f"\n{'='*60}")
    print(f"Testing {agent_name} Agent")
    print(f"{'='*60}")
    print(f"Query: {query}\n")
    
    try:
        # Create agent
        if agent_name == "local":
            if collection is None:
                from db.vector_db_manager import VectorDbManager
                vector_db = VectorDbManager()
                vector_db.create_collection(config.CHILD_COLLECTION)
                collection = vector_db.get_collection(config.CHILD_COLLECTION)
            agent = LocalRAGAgent(llm, collection, cfg)
        elif agent_name == "arxiv":
            agent = ArxivAgent(llm, cfg)
        elif agent_name == "youtube":
            agent = YouTubeAgent(llm, cfg)
        elif agent_name == "github":
            agent = GitHubAgent(llm, cfg)
        elif agent_name == "web":
            agent = WebAgent(llm, cfg)
        else:
            print(f"Unknown agent: {agent_name}")
            return
        
        # Create subgraph
        print("Creating agent subgraph...")
        subgraph = agent.create_agent_subgraph()
        print("✓ Subgraph created\n")
        
        # Create state
        state = AgentState(
            question=query,
            question_index=0,
            messages=[]
        )
        
        # Execute agent with proper config (required for checkpointer)
        thread_id = str(uuid.uuid4())
        graph_config = {"configurable": {"thread_id": thread_id}}
        
        print("Executing agent (this may take a while)...")
        result = subgraph.invoke(state, graph_config)
        
        # Display results
        print("\n" + "-"*60)
        print("RESULT:")
        print("-"*60)
        print(result.get("final_answer", "No answer generated"))
        
        # Display citations
        if result.get("agent_answers"):
            citations = result["agent_answers"][0].get("citations", [])
            if citations:
                print(f"\nCitations ({len(citations)}):")
                for i, cit in enumerate(citations[:5], 1):
                    print(f"  {i}. {cit.get('title', 'Unknown')}")
                    print(f"     {cit.get('url', 'No URL')}")
        
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n✗ Error: {error_msg}")
        
        # Provide helpful error messages
        if "Connection refused" in error_msg or "Errno 61" in error_msg:
            print("\n" + "="*60)
            print("⚠️  Ollama Connection Error")
            print("="*60)
            print("The Ollama server is not running or not accessible.")
            print("\nTo fix:")
            print("  1. Start Ollama: ollama serve")
            print("  2. Verify it's running: curl http://localhost:11434/api/tags")
            print("  3. Pull your model: ollama pull " + config.LLM_MODEL)
            print("\nOr use Gemini instead: --provider gemini")
            print("="*60 + "\n")
        elif "API key" in error_msg or "GOOGLE_API_KEY" in error_msg:
            print("\n" + "="*60)
            print("⚠️  Gemini API Key Error")
            print("="*60)
            print("The Google API key is not set or invalid.")
            print("\nTo fix:")
            print("  1. Get API key from: https://makersuite.google.com/app/apikey")
            print("  2. Set environment variable: export GOOGLE_API_KEY='your_key'")
            print("="*60 + "\n")
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            print("\n" + "="*60)
            print("⚠️  Model Not Found")
            print("="*60)
            print(f"The model '{config.LLM_MODEL}' is not available.")
            print(f"\nTo fix: ollama pull {config.LLM_MODEL}")
            print("="*60 + "\n")
        else:
            # Show full traceback for other errors
            import traceback
            traceback.print_exc()


def create_llm(provider="gemini", model=None, temperature=None):
    """Create LLM instance based on provider."""
    if provider == "gemini":
        if not GEMINI_AVAILABLE:
            raise ImportError("langchain_google_genai not installed. Install with: pip install langchain-google-genai")
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        temp = temperature if temperature is not None else config.LLM_TEMPERATURE
        
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temp,
            google_api_key=api_key
        )
    
    elif provider == "ollama":
        if not OLLAMA_AVAILABLE:   
            raise ImportError("langchain_ollama not installed. Install with: pip install langchain-ollama")
        
        model_name = model or config.LLM_MODEL
        temp = temperature if temperature is not None else config.LLM_TEMPERATURE
        
        return ChatOllama(
            model=model_name,
            temperature=temp
        )
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini' or 'ollama'")


def check_ollama_running():
    """Check if Ollama server is running."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Test agents with real LLM and APIs")
    parser.add_argument(
        "--agent",
        choices=["local", "arxiv", "youtube", "github", "web"],
        required=True,
        help="Which agent to test"
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Query/question for the agent"
    )
    parser.add_argument(
        "--video-id",
        default="dQw4w9WgXcQ",
        help="YouTube video ID (for youtube agent)"
    )
    parser.add_argument(
        "--url",
        default="https://www.python.org",
        help="URL to extract (for web agent)"
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "ollama"],
        default="gemini",
        help="LLM provider to use (default: gemini)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (overrides default for provider)"
    )
    parser.add_argument(
        "--skip-ollama-check",
        action="store_true",
        help="Skip Ollama server check (only for Ollama provider)"
    )
    
    args = parser.parse_args()
    
    # Check provider availability
    if args.provider == "gemini" and not GEMINI_AVAILABLE:
        print("\n" + "="*60)
        print("⚠️  ERROR: Gemini provider not available!")
        print("="*60)
        print("\nInstall with: pip install langchain-google-genai")
        print("Set API key: export GOOGLE_API_KEY='your_key'")
        print("="*60 + "\n")
        sys.exit(1)
    
    if args.provider == "ollama" and not OLLAMA_AVAILABLE:
        print("\n" + "="*60)
        print("⚠️  ERROR: Ollama provider not available!")
        print("="*60)
        print("\nInstall with: pip install langchain-ollama")
        print("="*60 + "\n")
        sys.exit(1)
    
    # Check if Ollama is running (only for Ollama provider)
    if args.provider == "ollama" and not args.skip_ollama_check:
        print("Checking Ollama server...")
        if not check_ollama_running():
            print("\n" + "="*60)
            print("⚠️  ERROR: Ollama server is not running!")
            print("="*60)
            print("\nTo start Ollama:")
            print("  1. Install Ollama: https://ollama.ai")
            print("  2. Start the server: ollama serve")
            print("  3. Pull your model: ollama pull " + (args.model or config.LLM_MODEL))
            print("\nOr skip this check with: --skip-ollama-check")
            print("="*60 + "\n")
            sys.exit(1)
        print("✓ Ollama server is running\n")
    
    # Create LLM
    print(f"Initializing LLM ({args.provider})...")
    try:
        llm = create_llm(
            provider=args.provider,
            model=args.model,
            temperature=config.LLM_TEMPERATURE
        )
        model_name = args.model or (os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if args.provider == "gemini" else config.LLM_MODEL)
        print(f"✓ LLM initialized: {model_name} ({args.provider})\n")
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        if args.provider == "gemini":
            print("\nMake sure:")
            print("  1. GOOGLE_API_KEY environment variable is set")
            print("  2. API key is valid")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Failed to initialize LLM: {e}")
        if args.provider == "ollama":
            print("\nMake sure:")
            print(f"  1. Ollama is running (ollama serve)")
            print(f"  2. Model is pulled: ollama pull {args.model or config.LLM_MODEL}")
        sys.exit(1)
    
    # Create config
    cfg = create_config()
    
    # Default queries
    default_queries = {
        "local": "What is machine learning?",
        "arxiv": "Find recent papers about transformer neural networks",
        "youtube": f"Get transcript from video {args.video_id} and summarize it",
        "github": "Find GitHub repositories about langchain",
        "web": f"Extract and summarize content from {args.url}"
    }
    
    query = args.query or default_queries.get(args.agent, "Test query")
    
    # Run test
    test_agent(args.agent, query, llm, cfg)


if __name__ == "__main__":
    main()