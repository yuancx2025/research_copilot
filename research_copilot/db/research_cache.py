import uuid
from typing import Dict, Optional, Any
from datetime import datetime


class ResearchCache:
    """
    Session-based cache for research queries and agent results.
    
    Prevents redundant API calls within the same session by caching
    query results, citations, and intermediate findings.
    """
    
    def __init__(self):
        """Initialize session cache."""
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for cache key (lowercase, strip whitespace)."""
        return query.lower().strip()
    
    def _make_key(self, query: str, agent_type: str) -> str:
        """Create cache key from query and agent type."""
        normalized_query = self._normalize_query(query)
        return f"{agent_type}:{normalized_query}"
    
    def get(self, query: str, agent_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached result for query and agent type.
        
        Args:
            query: Search query
            agent_type: Agent type ("arxiv", "youtube", "github", "web", "local")
        
        Returns:
            Cached result dictionary or None if not found
        """
        key = self._make_key(query, agent_type)
        return self.cache.get(key)
    
    def set(self, query: str, agent_type: str, result: Dict[str, Any]):
        """
        Store result in cache.
        
        Args:
            query: Search query
            agent_type: Agent type
            result: Result dictionary to cache
        """
        key = self._make_key(query, agent_type)
        self.cache[key] = {
            **result,
            "cached_at": datetime.now().isoformat(),
            "session_id": self.session_id
        }
    
    def clear(self):
        """Clear all cached results."""
        self.cache.clear()
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "cache_size": len(self.cache),
            "agent_types": list(set(key.split(':')[0] for key in self.cache.keys()))
        }
    
    def has(self, query: str, agent_type: str) -> bool:
        """Check if query+agent combination exists in cache."""
        key = self._make_key(query, agent_type)
        return key in self.cache

