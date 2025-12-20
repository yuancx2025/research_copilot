"""
Tests for tools/youtube_tools.py - YouTube video tools
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from tools.youtube_tools import YouTubeToolkit
from tools.base import SourceType


class TestYouTubeToolkit:
    """Test YouTubeToolkit class"""
    
    def test_source_type(self):
        """Test that YouTubeToolkit has correct source type"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        assert toolkit.source_type == SourceType.YOUTUBE
    
    def test_is_available_without_api_key(self):
        """Test availability check without API key"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        
        with patch('youtube_transcript_api.YouTubeTranscriptApi'):
            toolkit = YouTubeToolkit(config)
            # Should be available for transcript extraction even without API key
            assert toolkit.is_available() is True
    
    def test_extract_video_id_from_url(self):
        """Test extracting video ID from various URL formats"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        # Test different URL formats
        assert toolkit._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert toolkit._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert toolkit._extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"  # Already an ID
    
    @patch('tools.youtube_tools.YouTubeToolkit.youtube_client')
    def test_search_youtube_without_api(self, mock_client):
        """Test YouTube search without API key"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        results = toolkit._search_youtube("python tutorial")
        
        assert len(results) == 1
        assert "message" in results[0] or "error" in results[0]
    
    @patch('youtube_transcript_api.YouTubeTranscriptApi')
    def test_get_transcript(self, mock_api):
        """Test getting YouTube transcript"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        # Mock transcript data
        mock_transcript_data = [
            {"text": "Hello", "start": 0.0, "duration": 1.0},
            {"text": "world", "start": 1.0, "duration": 1.0}
        ]
        
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_transcript_data
        mock_transcript.language_code = "en"
        
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript
        mock_api.list_transcripts.return_value = mock_transcript_list
        
        result = toolkit._get_youtube_transcript("dQw4w9WgXcQ")
        
        assert "transcript" in result
        assert "Hello world" in result["transcript"]
        assert result["source_type"] == "youtube"
        assert result["video_id"] == "dQw4w9WgXcQ"
    
    def test_get_video_segment(self):
        """Test getting specific video segment"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        # Mock the _get_youtube_transcript method
        toolkit._get_youtube_transcript = Mock(return_value={
            "segments": [
                {"text": "Segment 1", "start": 0.0, "duration": 5.0},
                {"text": "Segment 2", "start": 5.0, "duration": 5.0},
                {"text": "Segment 3", "start": 10.0, "duration": 5.0}
            ],
            "video_id": "test123"
        })
        
        result = toolkit._get_video_segment("test123", start_time=2.0, end_time=8.0)
        
        assert "content" in result
        assert result["start_time"] == 2.0
        assert result["end_time"] == 8.0
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        
        with patch('youtube_transcript_api.YouTubeTranscriptApi'):
            toolkit = YouTubeToolkit(config)
            tools = toolkit.create_tools()
            
            assert len(tools) == 3
            tool_names = [t.name for t in tools]
            assert "search_youtube" in tool_names
            assert "get_youtube_transcript" in tool_names
            assert "get_video_segment" in tool_names
    
    def test_error_handling(self):
        """Test error handling"""
        config = Mock()
        config.YOUTUBE_API_KEY = None
        toolkit = YouTubeToolkit(config)
        
        with patch('youtube_transcript_api.YouTubeTranscriptApi') as mock_api:
            mock_api.list_transcripts.side_effect = Exception("Transcript not available")
            
            result = toolkit._get_youtube_transcript("invalid_id")
            
            assert "error" in result

