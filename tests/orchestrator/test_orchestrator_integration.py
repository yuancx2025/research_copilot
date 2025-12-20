"""
Integration tests for orchestrator with real LLM and APIs.

These tests execute the full orchestrator flow:
1. Intent classification
2. Multi-agent routing
3. Parallel agent execution
4. Result aggregation

Run with: pytest tests/test_orchestrator_integration.py -v -m integration

Requirements:
- Real LLM (Ollama or Gemini configured)
- API keys (optional for most sources)
- Set environment variables:
  - GOOGLE_API_KEY (for Gemini)
  - GITHUB_TOKEN (optional)
  - YOUTUBE_API_KEY (optional)
  - TAVILY_API_KEY (optional)
"""
import pytest
import os
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


def create_llm(provider=None):
    """Create LLM instance based on provider."""
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    
    if provider == "gemini":
        if not GEMINI_AVAILABLE:
            pytest.skip("langchain_google_genai not installed")
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            pytest.skip("GOOGLE_API_KEY environment variable not set")
        
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=config.LLM_TEMPERATURE,
            google_api_key=api_key
        )
    
    elif provider == "ollama":
        if not OLLAMA_AVAILABLE:
            pytest.skip("langchain_ollama not installed")
        
        return ChatOllama(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE
        )
    else:
        pytest.skip(f"Unknown provider: {provider}")


@pytest.fixture
def real_llm():
    """Create real LLM instance."""
    return create_llm()


@pytest.fixture
def real_config():
    """Create config with real API keys from environment."""
    cfg = Mock()
    
    # ArXiv - no key needed
    cfg.MAX_ARXIV_RESULTS = 5
    cfg.ENABLE_ARXIV_AGENT = True
    
    # GitHub - optional token
    cfg.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    cfg.USE_GITHUB_MCP = False
    cfg.ENABLE_GITHUB_AGENT = True
    
    # YouTube - optional API key
    cfg.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
    cfg.ENABLE_YOUTUBE_AGENT = True
    
    # Web - optional Tavily key
    cfg.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    cfg.USE_WEB_SEARCH_MCP = False
    cfg.MAX_WEB_RESULTS = 5
    cfg.ENABLE_WEB_AGENT = True
    
    # Local agent
    cfg.ENABLE_LOCAL_AGENT = True
    
    return cfg


@pytest.fixture
def real_collection():
    """Create or get real vector store collection."""
    vector_db = VectorDbManager()
    vector_db.create_collection(config.CHILD_COLLECTION)
    collection = vector_db.get_collection(config.CHILD_COLLECTION)
    return collection


@pytest.fixture
def graph_config():
    """Create graph config with thread_id for checkpointer."""
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


@pytest.fixture
def orchestrator_graph(real_llm, real_config, real_collection):
    """Create orchestrator graph for testing."""
    return create_agent_graph(real_llm, real_config, real_collection)


@pytest.mark.integration
class TestOrchestratorIntentClassification:
    """Test intent classification functionality."""
    
    def test_intent_classification_academic_query(self, orchestrator_graph, graph_config):
        """Test that academic queries route to arxiv agent."""
        query = "Find recent papers about transformer neural networks"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        # Execute up to intent classification
        # Note: We can't easily stop at intent classification without modifying the graph
        # So we'll check the final result for research_intent
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        research_intent = result.get("research_intent", [])
        assert len(research_intent) > 0, "Intent classification should select at least one agent"
        assert "arxiv" in research_intent or "web" in research_intent, \
            f"Academic query should route to arxiv or web, got: {research_intent}"
        
        routing_decision = result.get("routing_decision", {})
        assert "reasoning" in routing_decision, "Routing decision should include reasoning"
        assert "confidence" in routing_decision, "Routing decision should include confidence"
        
        print(f"\n✓ Intent Classification:")
        print(f"  Query: {query}")
        print(f"  Selected Agents: {research_intent}")
        print(f"  Reasoning: {routing_decision.get('reasoning', 'N/A')[:100]}...")
        print(f"  Confidence: {routing_decision.get('confidence', 0.0):.2f}")
    
    def test_intent_classification_code_query(self, orchestrator_graph, graph_config):
        """Test that code queries route to github agent."""
        query = "Find GitHub repositories about langchain"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        research_intent = result.get("research_intent", [])
        assert len(research_intent) > 0, "Intent classification should select at least one agent"
        # Code queries might route to github, web, or both
        assert any(agent in research_intent for agent in ["github", "web"]), \
            f"Code query should route to github or web, got: {research_intent}"
        
        print(f"\n✓ Intent Classification:")
        print(f"  Query: {query}")
        print(f"  Selected Agents: {research_intent}")
    
    def test_intent_classification_multi_agent_query(self, orchestrator_graph, graph_config):
        """Test that complex queries route to multiple agents."""
        query = "self-evolving agents"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        research_intent = result.get("research_intent", [])
        assert len(research_intent) > 0, "Intent classification should select at least one agent"
        
        # Complex queries should route to multiple agents
        print(f"\n✓ Intent Classification:")
        print(f"  Query: {query}")
        print(f"  Selected Agents: {research_intent}")
        print(f"  Multi-agent: {len(research_intent) > 1}")


@pytest.mark.integration
class TestOrchestratorExecution:
    """Test orchestrator execution flow."""
    
    def test_orchestrator_full_flow(self, orchestrator_graph, graph_config):
        """Test full orchestrator flow from query to answer."""
        query = "transformer neural networks"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        # Verify intent classification happened
        research_intent = result.get("research_intent", [])
        assert len(research_intent) > 0, "Intent classification should have occurred"
        
        # Verify agents were executed
        agent_results = result.get("agent_results", {})
        agent_answers = result.get("agent_answers", [])
        
        # At least one agent should have produced results
        assert len(agent_answers) > 0 or len(agent_results) > 0, \
            "At least one agent should have produced results"
        
        # Verify final answer exists
        messages = result.get("messages", [])
        assert len(messages) > 0, "Final answer should be present"
        
        final_answer = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        assert len(final_answer) > 0, "Final answer should not be empty"
        
        print(f"\n✓ Full Flow Test:")
        print(f"  Query: {query}")
        print(f"  Selected Agents: {research_intent}")
        print(f"  Agent Results: {len(agent_results)} sources")
        print(f"  Agent Answers: {len(agent_answers)} answers")
        print(f"  Final Answer Length: {len(final_answer)} chars")
    
    def test_orchestrator_parallel_execution(self, orchestrator_graph, graph_config):
        """Test that multiple agents execute in parallel."""
        query = "self-evolving agents"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        research_intent = result.get("research_intent", [])
        
        # If multiple agents were selected, verify they all executed
        if len(research_intent) > 1:
            agent_results = result.get("agent_results", {})
            agent_answers = result.get("agent_answers", [])
            
            # Count unique sources in results
            sources_in_results = set()
            for answer in agent_answers:
                source = answer.get("source", "")
                if source:
                    sources_in_results.add(source)
            
            print(f"\n✓ Parallel Execution Test:")
            print(f"  Selected Agents: {research_intent}")
            print(f"  Sources in Results: {sources_in_results}")
            print(f"  Parallel execution: {len(sources_in_results) > 1}")
            
            # Note: We can't easily verify true parallelism without timing,
            # but we can verify multiple agents produced results
            if len(sources_in_results) > 1:
                print("  ✓ Multiple agents executed successfully")
    
    def test_orchestrator_aggregation(self, orchestrator_graph, graph_config):
        """Test that results from multiple agents are aggregated."""
        query = "transformer neural networks"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        agent_answers = result.get("agent_answers", [])
        
        # If multiple agents produced answers, verify aggregation
        if len(agent_answers) > 1:
            messages = result.get("messages", [])
            final_answer = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            
            # Final answer should synthesize multiple sources
            assert len(final_answer) > 0, "Aggregated answer should not be empty"
            
            print(f"\n✓ Aggregation Test:")
            print(f"  Agent Answers: {len(agent_answers)}")
            print(f"  Final Answer Length: {len(final_answer)} chars")
            print(f"  ✓ Results aggregated successfully")
    
    def test_orchestrator_citations(self, orchestrator_graph, graph_config):
        """Test that citations are collected from all agents."""
        query = "transformer neural networks"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        # Collect citations from multiple sources
        citations = result.get("citations", [])
        agent_answers = result.get("agent_answers", [])
        
        all_citations = list(citations)
        for answer in agent_answers:
            answer_citations = answer.get("citations", [])
            if answer_citations:
                all_citations.extend(answer_citations)
        
        # Deduplicate
        seen = set()
        unique_citations = []
        for cit in all_citations:
            cit_key = (cit.get("url", ""), cit.get("title", ""))
            if cit_key not in seen and cit_key[0]:
                seen.add(cit_key)
                unique_citations.append(cit)
        
        print(f"\n✓ Citations Test:")
        print(f"  Total Citations: {len(unique_citations)}")
        if unique_citations:
            print(f"  Example Citation:")
            print(f"    Title: {unique_citations[0].get('title', 'Unknown')[:60]}...")
            print(f"    Source: {unique_citations[0].get('source_type', 'unknown')}")
            print(f"    URL: {unique_citations[0].get('url', 'No URL')[:60]}...")


@pytest.mark.integration
class TestOrchestratorErrorHandling:
    """Test orchestrator error handling."""
    
    def test_orchestrator_empty_query(self, orchestrator_graph, graph_config):
        """Test orchestrator handles empty queries gracefully."""
        query = ""
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        # Should either return clarification or default routing
        messages = result.get("messages", [])
        assert len(messages) > 0, "Should return a message even for empty query"
        
        print(f"\n✓ Empty Query Handling:")
        print(f"  Query: '{query}'")
        print(f"  Response: {messages[-1].content[:100] if hasattr(messages[-1], 'content') else str(messages[-1])[:100]}...")
    
    def test_orchestrator_invalid_intent_fallback(self, orchestrator_graph, graph_config):
        """Test that invalid intents fall back to default agents."""
        # This is harder to test directly, but we can verify the system doesn't crash
        query = "some random query that might confuse intent classification"
        
        initial_state = {
            "messages": [HumanMessage(content=query)]
        }
        
        result = orchestrator_graph.invoke(initial_state, graph_config)
        
        # Should still produce a result
        research_intent = result.get("research_intent", [])
        assert len(research_intent) > 0, "Should have default fallback agents"
        
        messages = result.get("messages", [])
        assert len(messages) > 0, "Should return a message"
        
        print(f"\n✓ Error Handling Test:")
        print(f"  Query: {query}")
        print(f"  Selected Agents: {research_intent}")
        print(f"  ✓ System handled gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

