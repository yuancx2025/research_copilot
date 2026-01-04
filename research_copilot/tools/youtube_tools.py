from typing import List, Dict, Optional
from langchain_core.tools import tool, BaseTool
from .base import BaseToolkit, SourceType
import logging
import re

logger = logging.getLogger(__name__)

class YouTubeToolkit(BaseToolkit):
    """
    Tools for searching YouTube and extracting video transcripts.
    
    This toolkit provides direct API access:
    1. Transcript extraction is the PRIMARY VALUE for research (not available via most MCPs)
    2. youtube-transcript-api works reliably without API keys for transcript extraction
    3. Video search requires YouTube API key but users can provide URLs directly
    4. Fewer dependencies and more reliable for the core use case
    
    Available Tools:
    - search_youtube: Find educational videos by keywords and content type
    - get_youtube_transcript: Extract full transcript from videos (works without API key)
    - get_video_segment: Get transcript for specific time ranges
    
    Key Features:
    - Transcript extraction works without YouTube API key
    - Supports both manual and auto-generated captions
    - Robust API compatibility (works with multiple youtube-transcript-api versions)
    - Direct video URL support (bypass search if URL provided)
    """
    
    source_type = SourceType.YOUTUBE
    
    def __init__(self, config):
        self.config = config
        self.api_key = getattr(config, 'YOUTUBE_API_KEY', None)
        self._youtube_client = None
    
    @property
    def youtube_client(self):
        """Lazy load YouTube API client."""
        if self._youtube_client is None and self.api_key:
            try:
                from googleapiclient.discovery import build
                self._youtube_client = build('youtube', 'v3', developerKey=self.api_key)
            except ImportError:
                logger.warning("google-api-python-client not installed")
            except Exception as e:
                raise
        return self._youtube_client
    
    def is_available(self) -> bool:
        """Transcript API works without keys; search needs API key."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            return True
        except ImportError:
            logger.warning("youtube-transcript-api not installed")
            return False
    
    def _extract_video_id(self, url_or_id: str) -> str:
        """Extract video ID from URL or return as-is if already an ID."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return url_or_id
    
    def _search_youtube(
        self,
        query: str,
        max_results: int = 5,
        content_type: str = "any"
    ) -> List[Dict]:
        """
        Search YouTube for educational videos.
        
        Use this to find tutorials, lectures, explanations, and educational content
        on any topic. Best for discovering relevant video content before extracting
        transcripts.
        
        Args:
            query: Search query - use natural language or keywords (e.g., "Python tutorial", "machine learning explained")
            max_results: Maximum number of videos to return (default: 5, max: 10)
            content_type: Filter by content type:
                - "any": All video types (default)
                - "tutorial": How-to guides and tutorials
                - "lecture": Academic lectures and courses
                - "explanation": Concept explanations and introductions
        
        Returns:
            List of videos with metadata:
            - title: Video title
            - video_id: YouTube video ID (use for transcript extraction)
            - channel: Channel name
            - description: Video description
            - url: Full YouTube URL
            - published_at: Publication date
        
        Note:
            - Requires YouTube API key (YOUTUBE_API_KEY config)
            - If API key not configured, returns search URL suggestion
            - Prefers videos with closed captions for transcript availability
        """
        if not self.youtube_client:
            # Fallback: return search URL suggestion
            return [{
                "message": "YouTube API not configured. Search manually:",
                "search_url": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
                "tip": "Provide a video URL or ID to get_youtube_transcript for transcript extraction"
            }]
        
        try:
            # Enhance query based on content type
            enhanced_query = query
            if content_type == "tutorial":
                enhanced_query = f"{query} tutorial how to guide"
            elif content_type == "lecture":
                enhanced_query = f"{query} lecture course university"
            elif content_type == "explanation":
                enhanced_query = f"{query} explained introduction"
            
            request = self.youtube_client.search().list(
                part="snippet",
                q=enhanced_query,
                type="video",
                maxResults=max_results,
                relevanceLanguage="en",
                videoCaption="closedCaption"  # Prefer captioned videos
            )
            response = request.execute()
            
            results = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                video_id = item["id"]["videoId"]
                results.append({
                    "video_id": video_id,
                    "title": snippet["title"],
                    "channel": snippet["channelTitle"],
                    "description": snippet["description"][:300],
                    "published_at": snippet["publishedAt"][:10],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_type": "youtube"
                })
            
            return results if results else [{"message": "No videos found"}]
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return [{"error": f"YouTube search failed: {str(e)}"}]
    
    def _get_youtube_transcript(
        self,
        video_id_or_url: str,
        languages: List[str] = None
    ) -> Dict:
        """
        Extract full transcript from a YouTube video.
        
        This is the PRIMARY tool for research - transcripts contain the actual
        educational content from videos. Works without API keys using the 
        youtube-transcript-api library.
        
        Use this for:
        - Getting spoken content from tutorials and lectures
        - Analyzing video explanations and demonstrations
        - Extracting step-by-step instructions
        - Finding specific information discussed in videos
        
        Args:
            video_id_or_url: YouTube video ID (e.g., "dQw4w9WgXcQ") or full URL
                           (e.g., "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            languages: Preferred languages for transcript (default: ['en', 'en-US', 'en-GB'])
                      Try multiple language codes if primary is unavailable
        
        Returns:
            Dict containing:
            - video_id: Extracted video ID
            - title: Video title (if available)
            - transcript: Full transcript text (all segments concatenated)
            - segments: List of transcript segments with timestamps
                       Each segment: {text, start, duration}
            - language: Language code of retrieved transcript
            - is_generated: Whether transcript is auto-generated or manual
            - source_type: "youtube"
        
        Robust API Detection:
            - Automatically handles both old and new youtube-transcript-api versions
            - Strategy 1: Try NEW API (v1.2.3+) with direct fetch() method
            - Strategy 2: Fallback to OLD API with list() and find_transcript()
            - Maximizes compatibility across different environments
        
        Error handling:
            - Returns {"error": "..."} if transcript unavailable
            - Common issues: No captions, video deleted, age-restricted content
            - Requires youtube-transcript-api package: pip install youtube-transcript-api
        
        Note:
            - Works independently of YouTube API key
            - Automatic captions (auto-generated) work for most videos
            - Manual captions provide better quality when available
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            video_id = self._extract_video_id(video_id_or_url)
            languages = languages or ['en', 'en-US', 'en-GB']
            
            # Robust API detection: Try NEW API first, fallback to OLD API
            # This approach is more reliable than hasattr() checks
            
            # Strategy 1: Try NEW API (v1.2.3+) - direct fetch() method
            try:
                ytt_api = YouTubeTranscriptApi()
                fetched = ytt_api.fetch(video_id, languages=languages)
                
                # Extract transcript text from snippets
                full_text_parts = []
                segments = []
                
                for snippet in fetched.snippets:
                    text = snippet.text.replace("\n", " ").strip()
                    full_text_parts.append(text)
                    segments.append({
                        "text": text,
                        "start": round(snippet.start, 1),
                        "duration": round(snippet.duration, 1)
                    })
                
                full_text = " ".join(full_text_parts)
                
                return {
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "transcript": full_text,
                    "transcript_type": "auto-generated" if fetched.is_generated else "manual",
                    "language": fetched.language,
                    "language_code": fetched.language_code,
                    "segment_count": len(segments),
                    "segments": segments[:50],  # Limit segments in response
                    "source_type": "youtube"
                }
            except (AttributeError, TypeError) as e:
                # NEW API not available or incompatible signature
                logger.debug(f"NEW API not available, trying OLD API: {e}")
                pass
            except Exception as e:
                # NEW API available but failed - try OLD API as fallback
                logger.debug(f"NEW API failed, trying OLD API: {e}")
                pass
            
            # Strategy 2: Fallback to OLD API - list() and find_transcript() methods
            try:
                ytt_api = YouTubeTranscriptApi()
                transcript_list = ytt_api.list(video_id)
                
                # Try to find transcript in preferred languages
                transcript = transcript_list.find_transcript(languages)
                
                # Fetch the actual transcript data
                fetched = transcript.fetch()
                
                # Extract text from snippets
                full_text_parts = []
                segments = []
                
                for snippet in fetched.snippets:
                    text = snippet.text.replace("\n", " ").strip()
                    full_text_parts.append(text)
                    segments.append({
                        "text": text,
                        "start": round(snippet.start, 1),
                        "duration": round(snippet.duration, 1)
                    })
                
                full_text = " ".join(full_text_parts)
                
                return {
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "transcript": full_text,
                    "transcript_type": "auto-generated" if transcript.is_generated else "manual",
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "segment_count": len(segments),
                    "segments": segments[:50],
                    "source_type": "youtube"
                }
            except Exception as e:
                logger.error(f"OLD API also failed for {video_id}: {e}")
                return {"error": f"Failed to get transcript with both API versions: {str(e)}"}
                    
        except ImportError:
            return {"error": "youtube-transcript-api not installed. Install with: pip install youtube-transcript-api"}
        except Exception as e:
            logger.error(f"Transcript extraction failed for {video_id_or_url}: {e}")
            return {"error": f"Failed to get transcript: {str(e)}"}
    
    def _get_video_segment(
        self,
        video_id_or_url: str,
        start_time: float,
        end_time: float
    ) -> Dict:
        """
        Get transcript for a specific time segment of a video.
        
        Use this when you know which part of a video contains relevant information,
        or when user asks about content at specific timestamps.
        
        Useful for:
        - Extracting specific sections user references
        - Getting content from timestamp ranges
        - Analyzing particular demonstrations or explanations
        - Reducing content when full transcript is too long
        
        Args:
            video_id_or_url: YouTube video ID or full URL
            start_time: Start time in seconds (e.g., 120 for 2:00)
            end_time: End time in seconds (e.g., 300 for 5:00)
        
        Returns:
            Dict containing:
            - video_id: Extracted video ID
            - start_time: Requested start time (seconds)
            - end_time: Requested end time (seconds)
            - content: Transcript text for the time range
            - timestamp_url: Direct URL to video at start_time
            - source_type: "youtube"
        
        Note:
            - Internally uses _get_youtube_transcript then filters by time
            - Returns only segments that fall within the time range
            - Generates clickable timestamp URL for easy video navigation
        """
        try:
            result = self._get_youtube_transcript(video_id_or_url)
            
            if "error" in result:
                return result
            
            # Filter segments to time range
            segment_text_parts = []
            for seg in result.get("segments", []):
                seg_start = seg["start"]
                seg_end = seg_start + seg["duration"]
                
                # Include if segment overlaps with requested range
                if seg_end >= start_time and seg_start <= end_time:
                    segment_text_parts.append(seg["text"])
            
            return {
                "video_id": self._extract_video_id(video_id_or_url),
                "start_time": start_time,
                "end_time": end_time,
                "content": " ".join(segment_text_parts),
                "timestamp_url": f"https://www.youtube.com/watch?v={self._extract_video_id(video_id_or_url)}&t={int(start_time)}",
                "source_type": "youtube"
            }
        except Exception as e:
            return {"error": f"Failed to get segment: {str(e)}"}
    
    def create_tools(self) -> List[BaseTool]:
        """Create YouTube research tools."""
        return [
            tool("search_youtube")(self._search_youtube),
            tool("get_youtube_transcript")(self._get_youtube_transcript),
            tool("get_video_segment")(self._get_video_segment)
        ]