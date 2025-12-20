#!/usr/bin/env python3
"""
Script to verify all imports in research_copilot package work correctly.
This tests that the restructured package can be imported without errors.
"""
import sys
import os

# Add project root to path
project_root = '/Users/yuanwenbo/Desktop/project'
sys.path.insert(0, project_root)

def test_import(module_path, description):
    """Test importing a module and report success/failure"""
    try:
        exec(f"from {module_path}")
        print(f"✓ {description}")
        return True
    except ImportError as e:
        print(f"✗ {description}")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"⚠ {description} (non-import error)")
        print(f"  Error: {type(e).__name__}: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing Research Copilot Package Imports")
    print("=" * 60)
    
    success_count = 0
    failure_count = 0
    
    # Test main package
    tests = [
        # Main package
        ("research_copilot import __version__", "Main package __init__"),
        
        # Config
        ("research_copilot.config.settings import MARKDOWN_DIR", "Config settings"),
        
        # Storage layer
        ("research_copilot.storage import VectorDbManager", "Storage: VectorDbManager"),
        ("research_copilot.storage import ParentStoreManager", "Storage: ParentStoreManager"),
        ("research_copilot.storage import ResearchCache", "Storage: ResearchCache"),
        
        # Core modules
        ("research_copilot.core.rag_system import RAGSystem", "Core: RAGSystem"),
        ("research_copilot.core.document_manager import DocumentManager", "Core: DocumentManager"),
        ("research_copilot.core.chat_interface import ChatInterface", "Core: ChatInterface"),
        
        # Agents
        ("research_copilot.agents.base_agent import BaseAgent", "Agents: BaseAgent"),
        ("research_copilot.agents.local_rag_agent import LocalRAGAgent", "Agents: LocalRAGAgent"),
        ("research_copilot.agents.arxiv_agent import ArxivAgent", "Agents: ArxivAgent"),
        ("research_copilot.agents.youtube_agent import YouTubeAgent", "Agents: YouTubeAgent"),
        ("research_copilot.agents.github_agent import GitHubAgent", "Agents: GitHubAgent"),
        ("research_copilot.agents.web_agent import WebAgent", "Agents: WebAgent"),
        
        # Orchestrator
        ("research_copilot.orchestrator.graph import create_agent_graph", "Orchestrator: graph"),
        ("research_copilot.orchestrator.state import State, AgentState", "Orchestrator: state"),
        ("research_copilot.orchestrator.nodes import agent_node", "Orchestrator: nodes"),
        ("research_copilot.orchestrator.edges import should_continue", "Orchestrator: edges"),
        
        # RAG
        ("research_copilot.rag import Chunker", "RAG: Chunker"),
        ("research_copilot.rag import Indexer", "RAG: Indexer"),
        ("research_copilot.rag import Retriever", "RAG: Retriever"),
        ("research_copilot.rag import Reranker", "RAG: Reranker"),
        
        # Tools
        ("research_copilot.tools.base import SourceType", "Tools: base"),
        ("research_copilot.tools.registry import initialize_registry", "Tools: registry"),
        ("research_copilot.tools.arxiv_tools import ArxivToolkit", "Tools: ArxivToolkit"),
        ("research_copilot.tools.youtube_tools import YouTubeToolkit", "Tools: YouTubeToolkit"),
        ("research_copilot.tools.github_tools import GitHubToolkit", "Tools: GitHubToolkit"),
        ("research_copilot.tools.web_tools import WebToolkit", "Tools: WebToolkit"),
        ("research_copilot.tools.local_tools import LocalToolkit", "Tools: LocalToolkit"),
        
        # UI
        ("research_copilot.ui.css import custom_css", "UI: css"),
        ("research_copilot.ui.gradio_app import create_gradio_ui", "UI: gradio_app"),
        
        # App
        ("research_copilot.app.main import main", "App: main"),
        ("research_copilot.app.gradio_app import create_gradio_ui", "App: gradio_app"),
    ]
    
    for import_stmt, description in tests:
        if test_import(import_stmt, description):
            success_count += 1
        else:
            failure_count += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {success_count} passed, {failure_count} failed")
    print("=" * 60)
    
    if failure_count > 0:
        print("\n⚠️  Some imports failed. Check the errors above.")
        return 1
    else:
        print("\n✅ All imports successful!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
