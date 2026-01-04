"""
LLM-Based Reranker for Multi-Source Content

Uses LLM for reranking, optimized for heterogeneous content
(GitHub code, YouTube transcripts, web articles, ArXiv papers, local documents).
"""
from typing import List, Tuple, Optional
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
import json
from research_copilot.config import settings as config


def _extract_text_from_content(content) -> str:
    """
    Extract plain text from LLM response content.
    
    Handles:
    - Strings (returned as-is)
    - Lists of content blocks from Gemini: [{'type': 'text', 'text': '...', 'extras': {...}}]
    - Single dict content blocks
    - Other types (converted via str())
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if 'text' in item:
                    text_parts.append(item['text'])
                elif 'content' in item:
                    text_parts.append(item['content'])
            elif isinstance(item, str):
                text_parts.append(item)
            elif item is not None:
                text_parts.append(str(item))
        return " ".join(text_parts)
    elif isinstance(content, dict):
        if 'text' in content:
            return content['text']
        elif 'content' in content:
            return content['content']
        return str(content)
    else:
        return str(content) if content else ""


class Reranker:
    """
    LLM-based reranker optimized for multi-source content.
    
    Uses LLM to score query-document relevance, considering:
    - Document content
    - Source type (GitHub, YouTube, Web, ArXiv, Local)
    - Contextual understanding across different formats
    """
    
    def __init__(self, llm: BaseChatModel, top_k: int = 5, batch_size: int = 5):
        """
        Initialize LLM reranker.
        
        Args:
            llm: LLM instance (e.g., ChatOllama)
            top_k: Default number of documents to return
            batch_size: Number of documents to score in one LLM call
        """
        self.llm = llm
        self.top_k = top_k
        self.batch_size = batch_size
    
    def rerank(self, query: str, documents: List[Document], top_k: Optional[int] = None) -> List[Tuple[Document, float]]:
        """
        Rerank documents using LLM scoring.
        
        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of top documents to return
        
        Returns:
            List of tuples (document, relevance_score) sorted by score (descending)
        """
        if not documents:
            return []
        
        if not self.llm:
            # Fallback: return documents with dummy scores
            return [(doc, 1.0) for doc in documents[:top_k or self.top_k]]
        
        top_k = top_k or self.top_k
        
        # Score documents in batches
        scored_docs = []
        
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batch_scores = self._score_batch(query, batch)
            scored_docs.extend(zip(batch, batch_scores))
        
        # Sort by score (descending)
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k
        return scored_docs[:top_k]
    
    def _score_batch(self, query: str, documents: List[Document]) -> List[float]:
        """
        Score a batch of documents using LLM.
        
        Args:
            query: Search query
            documents: Batch of documents to score
        
        Returns:
            List of relevance scores (0.0 to 1.0)
        """
        # Create scoring prompt
        prompt = self._create_scoring_prompt(query, documents)
        
        try:
            # Use LLM to score
            response = self.llm.invoke([
                SystemMessage(content=self._get_system_prompt()), 
                HumanMessage(content=prompt)
            ])
            
            # Parse response (extract text content first to handle Gemini's format)
            response_text = _extract_text_from_content(response.content)
            scores = self._parse_scores(response_text, len(documents))
            return scores
        except Exception as e:
            print(f"Error scoring batch with LLM: {e}")
            # Fallback: return equal scores
            return [0.5] * len(documents)
    
    def _create_scoring_prompt(self, query: str, documents: List[Document]) -> str:
        """Create prompt for scoring documents"""
        prompt = f"""Rate the relevance of each document to the query on a scale of 0.0 to 1.0.

Query: {query}

Documents to score:
"""
        for i, doc in enumerate(documents):
            source_type = doc.metadata.get("source_type", "unknown")
            source = doc.metadata.get("source", "unknown")
            content_preview = doc.page_content[:500]  # Limit content length
            
            prompt += f"""
Document {i+1}:
- Source Type: {source_type}
- Source: {source}
- Content: {content_preview}...
"""
        
        prompt += """
Rate each document's relevance to the query. Consider:
1. How well the document answers the query
2. The quality and relevance of the content
3. The source type's appropriateness for the query (e.g., GitHub code for programming questions, YouTube for tutorials, ArXiv for research)

Respond with a JSON array of scores, one per document, in order:
[0.85, 0.60, 0.90, ...]

Only return the JSON array, nothing else.
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for reranking"""
        return """You are a document relevance scorer. Your task is to rate how relevant each document is to a given query.

Consider:
- Semantic relevance: Does the document address the query?
- Source type: Is the source type appropriate? (e.g., GitHub code for programming questions, YouTube for tutorials, ArXiv for research papers)
- Content quality: Is the content clear and informative?

Return scores as a JSON array of floats between 0.0 and 1.0, where:
- 1.0 = Perfectly relevant and answers the query
- 0.7-0.9 = Highly relevant
- 0.4-0.6 = Moderately relevant
- 0.1-0.3 = Somewhat relevant
- 0.0 = Not relevant"""
    
    def _parse_scores(self, response: str, expected_count: int) -> List[float]:
        """Parse scores from LLM response"""
        try:
            # Try to extract JSON array
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith("```"):
                lines = response.split("\n")
                # Find the JSON part
                json_start = None
                json_end = None
                for i, line in enumerate(lines):
                    if line.strip().startswith("[") or line.strip().startswith("{"):
                        json_start = i
                        break
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().endswith("]") or lines[i].strip().endswith("}"):
                        json_end = i + 1
                        break
                if json_start is not None and json_end is not None:
                    response = "\n".join(lines[json_start:json_end])
            
            # Extract JSON array if embedded in text
            if "[" in response and "]" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                response = response[start:end]
            
            # Parse JSON
            scores = json.loads(response)
            
            # Validate
            if not isinstance(scores, list):
                scores = [scores]
            
            # Ensure correct length
            while len(scores) < expected_count:
                scores.append(0.5)  # Default score
            
            scores = scores[:expected_count]
            
            # Normalize to 0.0-1.0 range
            scores = [max(0.0, min(1.0, float(s))) for s in scores]
            
            return scores
        except Exception as e:
            print(f"Error parsing scores: {e}")
            print(f"Response was: {response[:200]}")
            # Fallback: return default scores
            return [0.5] * expected_count
    
    def is_available(self) -> bool:
        """Check if reranker is available"""
        return self.llm is not None
