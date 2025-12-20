from typing import Optional, Dict
from abc import ABC, abstractmethod
from pathlib import Path
import arxiv
import yt_dlp
import requests
from bs4 import BeautifulSoup
from research_copilot.config import settings as config
class BaseSourceIndexer(ABC):
    """Base class for source-specific indexers."""
    
    @abstractmethod
    def fetch_content(self, source_id: str) -> Optional[str]:
        """Fetch content from source."""
        pass
    
    @abstractmethod
    def get_metadata(self, source_id: str) -> Dict:
        """Get source-specific metadata."""
        pass


class ArxivIndexer(BaseSourceIndexer):
    """Indexer for ArXiv papers."""
    
    def fetch_content(self, paper_id: str) -> Optional[str]:
        """
        Fetch ArXiv paper and convert to text.
        
        Args:
            paper_id: ArXiv paper ID (e.g., "2301.00001" or "2301.00001v1")
        
        Returns:
            Paper content as markdown text, or None if failed
        """
        try:
            # Remove 'arxiv:' prefix if present
            paper_id = paper_id.replace('arxiv:', '').replace('arXiv:', '')
            
            # Search for paper
            search = arxiv.Search(id_list=[paper_id])
            paper = next(search.results(), None)
            
            if not paper:
                print(f"Paper {paper_id} not found on ArXiv")
                return None
            
            # Download PDF and convert to text
            # Note: This requires pdf processing - for now return abstract + metadata
            # Full implementation would use pdf_to_markdown utility
            content = f"# {paper.title}\n\n"
            content += f"**Authors:** {', '.join([author.name for author in paper.authors])}\n\n"
            content += f"**Published:** {paper.published}\n\n"
            content += f"**Abstract:**\n\n{paper.summary}\n\n"
            content += f"**ArXiv ID:** {paper.entry_id}\n\n"
            content += f"**PDF URL:** {paper.pdf_url}\n\n"
            
            # Note: Full PDF text extraction would require additional processing
            # For Phase 4, we index metadata + abstract
            # Full PDF indexing can be added later
            
            return content
        except Exception as e:
            print(f"Error fetching ArXiv paper {paper_id}: {e}")
            return None
    
    def get_metadata(self, paper_id: str) -> Dict:
        """Get ArXiv paper metadata."""
        try:
            paper_id = paper_id.replace('arxiv:', '').replace('arXiv:', '')
            search = arxiv.Search(id_list=[paper_id])
            paper = next(search.results(), None)
            
            if paper:
                return {
                    "source_id": paper_id,
                    "title": paper.title,
                    "authors": [author.name for author in paper.authors],
                    "published": paper.published.isoformat() if paper.published else None,
                    "arxiv_url": paper.entry_id,
                    "pdf_url": paper.pdf_url,
                }
        except Exception as e:
            print(f"Error getting ArXiv metadata: {e}")
        
        return {"source_id": paper_id}


class YouTubeIndexer(BaseSourceIndexer):
    """Indexer for YouTube videos."""
    
    def fetch_content(self, video_id: str) -> Optional[str]:
        """
        Extract transcript from YouTube video.
        
        Args:
            video_id: YouTube video ID or URL
        
        Returns:
            Video transcript as text, or None if failed
        """
        try:
            # Extract video ID from URL if needed
            if 'youtube.com' in video_id or 'youtu.be' in video_id:
                # Extract ID from URL
                if 'v=' in video_id:
                    video_id = video_id.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in video_id:
                    video_id = video_id.split('youtu.be/')[1].split('?')[0]
            
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'skip_download': True,
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                
                # Try to get transcript
                transcript = ""
                if 'subtitles' in info:
                    # Extract transcript from subtitles
                    # This is simplified - full implementation would parse subtitle files
                    transcript = f"Video: {info.get('title', '')}\n\n"
                    transcript += f"Description: {info.get('description', '')}\n\n"
                
                return transcript if transcript else None
        except Exception as e:
            print(f"Error extracting YouTube transcript {video_id}: {e}")
            return None
    
    def get_metadata(self, video_id: str) -> Dict:
        """Get YouTube video metadata."""
        try:
            if 'youtube.com' in video_id or 'youtu.be' in video_id:
                if 'v=' in video_id:
                    video_id = video_id.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in video_id:
                    video_id = video_id.split('youtu.be/')[1].split('?')[0]
            
            ydl_opts = {'skip_download': True, 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return {
                    "source_id": video_id,
                    "title": info.get('title', ''),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": info.get('duration', 0),
                    "uploader": info.get('uploader', ''),
                }
        except Exception as e:
            print(f"Error getting YouTube metadata: {e}")
        
        return {"source_id": video_id}


class GitHubIndexer(BaseSourceIndexer):
    """Indexer for GitHub repositories."""
    
    def fetch_content(self, repo_url: str) -> Optional[str]:
        """
        Fetch README and documentation from GitHub repo.
        
        Args:
            repo_url: GitHub repository URL
        
        Returns:
            Repository documentation as text, or None if failed
        """
        try:
            # Parse GitHub URL
            if 'github.com' not in repo_url:
                return None
            
            parts = repo_url.replace('https://github.com/', '').replace('http://github.com/', '').split('/')
            if len(parts) < 2:
                return None
            
            owner, repo = parts[0], parts[1]
            
            # Fetch README
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
            readme_alt = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            
            content = f"# {repo}\n\n"
            content += f"**Repository:** {repo_url}\n\n"
            
            # Try main branch first, then master
            for url in [readme_url, readme_alt]:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        content += "## README\n\n" + response.text + "\n\n"
                        break
                except:
                    continue
            
            return content
        except Exception as e:
            print(f"Error fetching GitHub repo {repo_url}: {e}")
            return None
    
    def get_metadata(self, repo_url: str) -> Dict:
        """Get GitHub repository metadata."""
        try:
            if 'github.com' not in repo_url:
                return {"source_id": repo_url}
            
            parts = repo_url.replace('https://github.com/', '').replace('http://github.com/', '').split('/')
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                return {
                    "source_id": repo_url,
                    "owner": owner,
                    "repo": repo,
                    "url": repo_url,
                }
        except Exception as e:
            print(f"Error getting GitHub metadata: {e}")
        
        return {"source_id": repo_url}


class WebIndexer(BaseSourceIndexer):
    """Indexer for web articles."""
    
    def fetch_content(self, url: str) -> Optional[str]:
        """
        Scrape web article content.
        
        Args:
            url: Web page URL
        
        Returns:
            Article content as text, or None if failed
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text
            title = soup.find('title')
            title_text = title.get_text() if title else ""
            
            # Try to find main content
            article = soup.find('article') or soup.find('main') or soup.find('body')
            text = article.get_text() if article else soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            content = f"# {title_text}\n\n"
            content += f"**URL:** {url}\n\n"
            content += text
            
            return content
        except Exception as e:
            print(f"Error scraping web page {url}: {e}")
            return None
    
    def get_metadata(self, url: str) -> Dict:
        """Get web page metadata."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.find('title')
            title_text = title.get_text() if title else ""
            
            return {
                "source_id": url,
                "title": title_text,
                "url": url,
            }
        except Exception as e:
            print(f"Error getting web metadata: {e}")
        
        return {"source_id": url}

