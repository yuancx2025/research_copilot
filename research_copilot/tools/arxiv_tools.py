from typing import List, Dict, Optional
from langchain_core.tools import tool, BaseTool
from langchain_community.document_loaders import ArxivLoader
from .base import BaseToolkit, SourceType, Citation
import arxiv
import logging

logger = logging.getLogger(__name__)

class ArxivToolkit(BaseToolkit):
    """Tools for searching and retrieving ArXiv papers."""
    
    source_type = SourceType.ARXIV
    
    def __init__(self, config):
        self.config = config
        self.max_results = getattr(config, 'MAX_ARXIV_RESULTS', 5)  # Reduced default from 10 to 5
    
    def is_available(self) -> bool:
        """ArXiv API is free and always available."""
        return True
    
    def _search_arxiv(
        self, 
        query: str, 
        max_results: int = 5,
        sort_by: str = "relevance"
    ) -> List[Dict]:
        """
        Search ArXiv for academic papers matching your query.
        
        Use this tool when looking for:
        - Academic research papers
        - Technical publications
        - Scientific studies
        - Preprints and recent research
        
        Args:
            query: Search query - supports ArXiv syntax like 'cat:cs.AI' for categories,
                   'au:lastname' for authors, or natural language
            max_results: Maximum papers to return (default: 5, recommended: 3-5 for focused results)
            sort_by: How to sort results. 
                - "relevance" (default): Best for general topic searches
                - "lastUpdatedDate": Best for finding recently updated papers
        
        Returns:
            List of papers with title, authors, abstract, and PDF link
        """
        try:
            sort_criterion = {
                "relevance": arxiv.SortCriterion.Relevance,
                "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate
            }.get(sort_by, arxiv.SortCriterion.Relevance)
            
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=min(max_results, self.max_results),
                sort_by=sort_criterion
            )
            
            results = []
            for paper in client.results(search):
                arxiv_id = paper.entry_id.split("/")[-1]
                results.append({
                    "arxiv_id": arxiv_id,
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:5]],  # Limit authors
                    "abstract": paper.summary[:1000],  # Truncate long abstracts
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "pdf_url": paper.pdf_url,
                    "categories": paper.categories[:3],
                    "primary_category": paper.primary_category,
                    "source_type": "arxiv"
                })
            
            return results if results else [{"message": "No papers found matching query"}]
        except Exception as e:
            logger.error(f"ArXiv search failed: {e}")
            return [{"error": f"ArXiv search failed: {str(e)}"}]
    
    def _get_paper_content(
        self, 
        arxiv_id: str
    ) -> Dict:
        """
        Retrieve the full content of an ArXiv paper.
        
        Use this after searching to get complete paper text for detailed analysis.
        
        Args:
            arxiv_id: ArXiv paper ID (e.g., '2301.00001' or '2301.00001v2')
        
        Returns:
            Full paper content with metadata
        """
        try:
            # Clean up arxiv_id if full URL provided
            if "arxiv.org" in arxiv_id:
                arxiv_id = arxiv_id.split("/")[-1]
            
            loader = ArxivLoader(
                query=arxiv_id,
                load_max_docs=1,
                load_all_available_meta=True
            )
            docs = loader.load()
            
            if not docs:
                return {"error": f"Paper {arxiv_id} not found"}
            
            doc = docs[0]
            return {
                "arxiv_id": arxiv_id,
                "title": doc.metadata.get("Title", "Unknown"),
                "authors": doc.metadata.get("Authors", ""),
                "content": doc.page_content[:20000],  # Limit content length
                "published": doc.metadata.get("Published", ""),
                "source_type": "arxiv",
                "url": f"https://arxiv.org/abs/{arxiv_id}"
            }
        except Exception as e:
            logger.error(f"Failed to load paper {arxiv_id}: {e}")
            return {"error": f"Failed to load paper: {str(e)}"}
    
    def _find_related_papers(
        self,
        arxiv_id: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Find papers related to a given ArXiv paper.
        
        Useful for literature review and finding connected research.
        
        Args:
            arxiv_id: Reference paper's ArXiv ID
            max_results: Maximum related papers to return
        
        Returns:
            List of related papers
        """
        try:
            # Get the reference paper first
            client = arxiv.Client()
            search = arxiv.Search(id_list=[arxiv_id])
            ref_paper = next(client.results(search), None)
            
            if not ref_paper:
                return [{"error": f"Paper {arxiv_id} not found"}]
            
            # Search using primary category and key title words
            title_words = [w for w in ref_paper.title.split() 
                          if len(w) > 4 and w.isalpha()][:3]
            query = f"cat:{ref_paper.primary_category} AND ({' OR '.join(title_words)})"
            
            related = self._search_arxiv(query, max_results + 1)
            # Filter out the original paper
            return [p for p in related if p.get("arxiv_id") != arxiv_id][:max_results]
        except Exception as e:
            logger.error(f"Related paper search failed: {e}")
            return [{"error": f"Related paper search failed: {str(e)}"}]
    
    def create_tools(self) -> List[BaseTool]:
        """Create ArXiv research tools."""
        return [
            tool("search_arxiv")(self._search_arxiv),
            tool("get_arxiv_paper")(self._get_paper_content),
            tool("find_related_papers")(self._find_related_papers)
        ]