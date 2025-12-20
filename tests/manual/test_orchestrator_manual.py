#!/usr/bin/env python3
"""
Manual testing script for orchestrator with real LLM and APIs.

Tests the full orchestrator flow:
1. Intent classification
2. Multi-agent routing
3. Parallel agent execution
4. Result aggregation

Usage:
    python test_orchestrator_manual.py --query "self-evolving agents"
    python test_orchestrator_manual.py --query "transformer neural networks" --provider gemini
    python test_orchestrator_manual.py --query "how to implement transformers" --provider ollama
"""
import os
import sys
import argparse
import uuid
from unittest.mock import Mock
import config
from langchain_core.messages import HumanMessage

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

from orchestrator.graph import create_agent_graph
from orchestrator.state import State
from db.vector_db_manager import VectorDbManager


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
    cfg.ENABLE_LOCAL_AGENT = True
    return cfg


def test_orchestrator(query, llm, cfg, collection=None):
    """Test the orchestrator with a real query."""
    print(f"\n{'='*70}")
    print(f"Testing Orchestrator")
    print(f"{'='*70}")
    print(f"Query: {query}\n")
    
    try:
        # Create vector collection if needed
        if collection is None:
            print("Creating vector collection...")
            vector_db = VectorDbManager()
            vector_db.create_collection(config.CHILD_COLLECTION)
            collection = vector_db.get_collection(config.CHILD_COLLECTION)
            print("✓ Collection created\n")
        
        # Create orchestrator graph
        print("Creating orchestrator graph...")
        orchestrator_graph = create_agent_graph(llm, cfg, collection)
        print("✓ Orchestrator graph created\n")
        
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        # Execute orchestrator with proper config (required for checkpointer)
        thread_id = str(uuid.uuid4())
        graph_config = {"configurable": {"thread_id": thread_id}}
        
        print("Executing orchestrator (this may take a while)...")
        print("  - Intent classification...")
        print("  - Routing to agents...")
        print("  - Executing agents in parallel...")
        print("  - Aggregating results...\n")
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        # Display results
        print("\n" + "="*70)
        print("ORCHESTRATOR RESULTS")
        print("="*70)
        
        # Show intent classification
        research_intent = result.get("research_intent", [])
        routing_decision = result.get("routing_decision", {})
        
        print(f"\n📋 Intent Classification:")
        print(f"   Selected Agents: {', '.join(research_intent) if research_intent else 'None'}")
        if routing_decision:
            print(f"   Reasoning: {routing_decision.get('reasoning', 'N/A')}")
            print(f"   Confidence: {routing_decision.get('confidence', 0.0):.2f}")
        
        # Show agent results
        agent_results = result.get("agent_results", {})
        if agent_results:
            print(f"\n🤖 Agent Results:")
            for source, answers in agent_results.items():
                print(f"   {source}: {len(answers)} answer(s)")
                for ans in answers[:1]:  # Show first answer per source
                    answer_preview = ans.get("answer", "")[:100]
                    print(f"      Preview: {answer_preview}...")
        
        # Show final answer
        messages = result.get("messages", [])
        if messages:
            final_answer = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            print(f"\n💬 Final Answer:")
            print(f"   {final_answer[:500]}{'...' if len(final_answer) > 500 else ''}")
        
        # Show citations
        citations = result.get("citations", [])
        agent_answers = result.get("agent_answers", [])
        
        # Collect citations from agent_answers as well
        all_citations = list(citations)
        for answer in agent_answers:
            answer_citations = answer.get("citations", [])
            if answer_citations:
                all_citations.extend(answer_citations)
        
        # Deduplicate citations
        seen = set()
        unique_citations = []
        for cit in all_citations:
            cit_key = (cit.get("url", ""), cit.get("title", ""))
            if cit_key not in seen and cit_key[0]:
                seen.add(cit_key)
                unique_citations.append(cit)
        
        if unique_citations:
            print(f"\n📚 Citations ({len(unique_citations)}):")
            for i, cit in enumerate(unique_citations[:10], 1):  # Show first 10
                print(f"   {i}. {cit.get('title', 'Unknown')}")
                print(f"      Source: {cit.get('source_type', 'unknown')}")
                print(f"      URL: {cit.get('url', 'No URL')}")
        
        print("\n" + "="*70)
        print("✓ Orchestrator test completed successfully!")
        print("="*70 + "\n")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n✗ Error: {error_msg}")
        
        # Provide helpful error messages
        if "Connection refused" in error_msg or "Errno 61" in error_msg:
            print("\n" + "="*70)
            print("⚠️  Ollama Connection Error")
            print("="*70)
            print("The Ollama server is not running or not accessible.")
            print("\nTo fix:")
            print("  1. Start Ollama: ollama serve")
            print("  2. Verify it's running: curl http://localhost:11434/api/tags")
            print("  3. Pull your model: ollama pull " + config.LLM_MODEL)
            print("\nOr use Gemini instead: --provider gemini")
            print("="*70 + "\n")
        elif "API key" in error_msg or "GOOGLE_API_KEY" in error_msg:
            print("\n" + "="*70)
            print("⚠️  Gemini API Key Error")
            print("="*70)
            print("The Google API key is not set or invalid.")
            print("\nTo fix:")
            print("  1. Get API key from: https://makersuite.google.com/app/apikey")
            print("  2. Set environment variable: export GOOGLE_API_KEY='your_key'")
            print("="*70 + "\n")
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            print("\n" + "="*70)
            print("⚠️  Model Not Found")
            print("="*70)
            print(f"The model '{config.LLM_MODEL}' is not available.")
            print(f"\nTo fix: ollama pull {config.LLM_MODEL}")
            print("="*70 + "\n")
        else:
            # Show full traceback for other errors
            import traceback
            traceback.print_exc()
        
        return None


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
    parser = argparse.ArgumentParser(description="Test orchestrator with real LLM and APIs")
    parser.add_argument(
        "--query",
        default="self-evolving agents",
        help="Query/question for the orchestrator"
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
        print("\n" + "="*70)
        print("⚠️  ERROR: Gemini provider not available!")
        print("="*70)
        print("\nInstall with: pip install langchain-google-genai")
        print("Set API key: export GOOGLE_API_KEY='your_key'")
        print("="*70 + "\n")
        sys.exit(1)
    
    if args.provider == "ollama" and not OLLAMA_AVAILABLE:
        print("\n" + "="*70)
        print("⚠️  ERROR: Ollama provider not available!")
        print("="*70)
        print("\nInstall with: pip install langchain-ollama")
        print("="*70 + "\n")
        sys.exit(1)
    
    # Check if Ollama is running (only for Ollama provider)
    if args.provider == "ollama" and not args.skip_ollama_check:
        print("Checking Ollama server...")
        if not check_ollama_running():
            print("\n" + "="*70)
            print("⚠️  ERROR: Ollama server is not running!")
            print("="*70)
            print("\nTo start Ollama:")
            print("  1. Install Ollama: https://ollama.ai")
            print("  2. Start the server: ollama serve")
            print("  3. Pull your model: ollama pull " + (args.model or config.LLM_MODEL))
            print("\nOr skip this check with: --skip-ollama-check")
            print("="*70 + "\n")
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
    
    # Run test
    test_orchestrator(args.query, llm, cfg)


if __name__ == "__main__":
    main()

