"""
Tests for db/research_cache.py - Session-based research cache
"""
import pytest
from db.research_cache import ResearchCache


class TestResearchCache:
    """Test ResearchCache class"""
    
    @pytest.fixture
    def cache(self):
        """Create cache instance"""
        return ResearchCache()
    
    def test_cache_initialization(self, cache):
        """Test cache initializes correctly"""
        assert cache.cache == {}
        assert cache.session_id is not None
        assert cache.created_at is not None
    
    def test_set_and_get(self, cache):
        """Test setting and getting cached results"""
        query = "test query"
        agent_type = "arxiv"
        result = {
            "answer": "Test answer",
            "citations": [{"title": "Test"}]
        }
        
        cache.set(query, agent_type, result)
        retrieved = cache.get(query, agent_type)
        
        assert retrieved is not None
        assert retrieved["answer"] == "Test answer"
        assert "cached_at" in retrieved
        assert "session_id" in retrieved
    
    def test_get_nonexistent(self, cache):
        """Test getting nonexistent cache entry"""
        result = cache.get("nonexistent query", "arxiv")
        
        assert result is None
    
    def test_query_normalization(self, cache):
        """Test that queries are normalized for cache keys"""
        query1 = "Test Query"
        query2 = "  test query  "
        query3 = "TEST QUERY"
        
        result = {"answer": "test"}
        cache.set(query1, "arxiv", result)
        
        # All variations should retrieve the same cached result
        assert cache.get(query2, "arxiv") is not None
        assert cache.get(query3, "arxiv") is not None
    
    def test_has_method(self, cache):
        """Test has method"""
        query = "test query"
        agent_type = "youtube"
        
        assert cache.has(query, agent_type) is False
        
        cache.set(query, agent_type, {"answer": "test"})
        
        assert cache.has(query, agent_type) is True
    
    def test_clear(self, cache):
        """Test clearing cache"""
        cache.set("query1", "arxiv", {"answer": "test1"})
        cache.set("query2", "youtube", {"answer": "test2"})
        
        assert len(cache.cache) == 2
        
        cache.clear()
        
        assert len(cache.cache) == 0
        assert cache.session_id is not None  # New session ID generated
    
    def test_different_agents_same_query(self, cache):
        """Test that same query with different agents are cached separately"""
        query = "machine learning"
        result1 = {"answer": "arxiv answer"}
        result2 = {"answer": "youtube answer"}
        
        cache.set(query, "arxiv", result1)
        cache.set(query, "youtube", result2)
        
        assert len(cache.cache) == 2
        
        arxiv_result = cache.get(query, "arxiv")
        youtube_result = cache.get(query, "youtube")
        
        assert arxiv_result["answer"] == "arxiv answer"
        assert youtube_result["answer"] == "youtube answer"
    
    def test_get_stats(self, cache):
        """Test getting cache statistics"""
        cache.set("query1", "arxiv", {"answer": "test1"})
        cache.set("query2", "youtube", {"answer": "test2"})
        cache.set("query3", "arxiv", {"answer": "test3"})
        
        stats = cache.get_stats()
        
        assert stats["cache_size"] == 3
        assert stats["session_id"] == cache.session_id
        assert "created_at" in stats
        assert "arxiv" in stats["agent_types"]
        assert "youtube" in stats["agent_types"]
    
    def test_cache_preserves_original_data(self, cache):
        """Test that cached data preserves original structure"""
        original_result = {
            "answer": "Test answer",
            "citations": [{"title": "Paper 1"}, {"title": "Paper 2"}],
            "metadata": {"source": "arxiv"}
        }
        
        cache.set("test query", "arxiv", original_result)
        retrieved = cache.get("test query", "arxiv")
        
        assert retrieved["answer"] == original_result["answer"]
        assert len(retrieved["citations"]) == 2
        assert retrieved["metadata"] == original_result["metadata"]
        # Should have additional cache metadata
        assert "cached_at" in retrieved
        assert "session_id" in retrieved
    
    def test_case_insensitive_query(self, cache):
        """Test that queries are case-insensitive"""
        cache.set("Machine Learning", "arxiv", {"answer": "test"})
        
        assert cache.get("machine learning", "arxiv") is not None
        assert cache.get("MACHINE LEARNING", "arxiv") is not None
        assert cache.get("MaChInE lEaRnInG", "arxiv") is not None

