from pathlib import Path
import shutil
from research_copilot.config import settings as config
from research_copilot.utils.pdf_converter import pdfs_to_markdowns
from research_copilot.rag.indexer import Indexer
from research_copilot.rag.source_indexers import ArxivIndexer, YouTubeIndexer, GitHubIndexer, WebIndexer

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize indexer
        self.indexer = Indexer(
            rag_system.vector_db,
            rag_system.parent_store,
            rag_system.chunker
        )
        
        # Initialize source indexers
        self.arxiv_indexer = ArxivIndexer()
        self.youtube_indexer = YouTubeIndexer()
        self.github_indexer = GitHubIndexer()
        self.web_indexer = WebIndexer()
        
    def add_documents(self, document_paths, progress_callback=None):
        """Add local documents (PDF/MD) to the knowledge base."""
        if not document_paths:
            return 0, 0
            
        document_paths = [document_paths] if isinstance(document_paths, str) else document_paths
        document_paths = [p for p in document_paths if p and Path(p).suffix.lower() in [".pdf", ".md"]]
        
        if not document_paths:
            return 0, 0
        
        collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
        added = 0
        skipped = 0
            
        for i, doc_path in enumerate(document_paths):
            if progress_callback:
                progress_callback((i + 1) / len(document_paths), f"Processing {Path(doc_path).name}")
                
            doc_name = Path(doc_path).stem
            md_path = self.markdown_dir / f"{doc_name}.md"
            
            if md_path.exists():
                skipped += 1
                continue
                
            try:            
                if Path(doc_path).suffix.lower() == ".md":
                    shutil.copy(doc_path, md_path)
                else:
                    pdfs_to_markdowns(str(doc_path), overwrite=False)
                
                # Use indexer to index document
                if self.indexer.index_document(md_path, collection, source_type="local"):
                    added += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"Error processing {doc_path}: {e}")
                skipped += 1
            
        return added, skipped
    
    def index_from_arxiv(self, paper_id: str) -> bool:
        """
        Index an ArXiv paper.
        
        Args:
            paper_id: ArXiv paper ID (e.g., "2301.00001")
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            content = self.arxiv_indexer.fetch_content(paper_id)
            if not content:
                return False
            
            metadata = self.arxiv_indexer.get_metadata(paper_id)
            metadata["source_type"] = "arxiv"
            
            collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
            return self.indexer.index_text(content, collection, source_type="arxiv", source_metadata=metadata)
        except Exception as e:
            print(f"Error indexing ArXiv paper {paper_id}: {e}")
            return False
    
    def index_from_youtube(self, video_id: str) -> bool:
        """
        Index a YouTube video transcript.
        
        Args:
            video_id: YouTube video ID or URL
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            content = self.youtube_indexer.fetch_content(video_id)
            if not content:
                return False
            
            metadata = self.youtube_indexer.get_metadata(video_id)
            metadata["source_type"] = "youtube"
            
            collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
            return self.indexer.index_text(content, collection, source_type="youtube", source_metadata=metadata)
        except Exception as e:
            print(f"Error indexing YouTube video {video_id}: {e}")
            return False
    
    def index_from_github(self, repo_url: str) -> bool:
        """
        Index a GitHub repository (README and docs).
        
        Args:
            repo_url: GitHub repository URL
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            content = self.github_indexer.fetch_content(repo_url)
            if not content:
                return False
            
            metadata = self.github_indexer.get_metadata(repo_url)
            metadata["source_type"] = "github"
            
            collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
            return self.indexer.index_text(content, collection, source_type="github", source_metadata=metadata)
        except Exception as e:
            print(f"Error indexing GitHub repo {repo_url}: {e}")
            return False
    
    def index_from_web(self, url: str) -> bool:
        """
        Index a web article.
        
        Args:
            url: Web page URL
        
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            content = self.web_indexer.fetch_content(url)
            if not content:
                return False
            
            metadata = self.web_indexer.get_metadata(url)
            metadata["source_type"] = "web"
            
            collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
            return self.indexer.index_text(content, collection, source_type="web", source_metadata=metadata)
        except Exception as e:
            print(f"Error indexing web page {url}: {e}")
            return False
    
    def get_markdown_files(self):
        if not self.markdown_dir.exists():
            return []
        return sorted([p.name.replace(".md", ".pdf") for p in self.markdown_dir.glob("*.md")])
    
    def clear_all(self):
        if self.markdown_dir.exists():
            shutil.rmtree(self.markdown_dir)
            self.markdown_dir.mkdir(parents=True, exist_ok=True)
        
        self.rag_system.parent_store.clear_store()
        self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)
        self.rag_system.vector_db.create_collection(self.rag_system.collection_name)