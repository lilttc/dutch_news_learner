"""
YouTube ingestion - adapted from tai8bot for Dutch content.

Prefers Dutch (nl) transcripts. Uses youtube-transcript-api for subtitles
and YouTube Data API v3 for playlist metadata.
"""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Optional
import os


class YouTubeTranscriptFetcher:
    """Fetches transcripts from YouTube videos."""

    def __init__(self):
        self.api = YouTubeTranscriptApi()

    def fetch_transcript(
        self,
        video_id: str,
        preferred_languages: List[str] = None,
        include_metadata: bool = False,
    ) -> Optional[Dict]:
        """
        Fetch transcript for a video.

        Args:
            video_id: YouTube video ID
            preferred_languages: List of language codes to prefer (default: ['nl', 'nl-NL', 'en'])
            include_metadata: If True, returns dict with 'segments' and 'metadata' keys

        Returns:
            If include_metadata=False: List of transcript segments
            If include_metadata=True: Dict with 'segments' and 'metadata'
            None if no transcript available
        """
        if preferred_languages is None:
            preferred_languages = ["nl", "nl-NL", "en"]

        try:
            transcript_list = self.api.list(video_id)

            # Try to find preferred language (Dutch first)
            transcript_obj = None
            for transcript in transcript_list:
                if transcript.language_code in preferred_languages:
                    transcript_obj = transcript
                    break

            # Fallback: first available
            if transcript_obj is None:
                for transcript in transcript_list:
                    transcript_obj = transcript
                    break

            if transcript_obj:
                data = transcript_obj.fetch()
                segments = [
                    {
                        "text": segment.text,
                        "start": segment.start,
                        "duration": segment.duration,
                    }
                    for segment in data
                ]

                if include_metadata:
                    return {
                        "segments": segments,
                        "metadata": {
                            "language": transcript_obj.language,
                            "language_code": transcript_obj.language_code,
                            "is_generated": transcript_obj.is_generated,
                            "is_translatable": transcript_obj.is_translatable,
                        },
                    }

                return segments

            return None

        except Exception as e:
            print(f"Error fetching transcript for {video_id}: {e}")
            return None


class YouTubePlaylistFetcher:
    """Fetches video metadata from YouTube playlists."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with YouTube Data API key.

        Args:
            api_key: YouTube Data API v3 key. If None, reads from YOUTUBE_API_KEY env var
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "YouTube API key required. Set YOUTUBE_API_KEY env var or pass api_key parameter"
            )

        try:
            from googleapiclient.discovery import build

            self.youtube = build("youtube", "v3", developerKey=self.api_key)
        except ImportError:
            raise ImportError(
                "google-api-python-client required. Install with: pip install google-api-python-client"  # noqa: E501
            )

    def fetch_playlist_videos(
        self, playlist_id: str, max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch all videos from a playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum number of videos to fetch (None = all)

        Returns:
            List of dicts with video_id, title, description, published_at, position, thumbnail_url
        """
        videos = []
        next_page_token = None

        try:
            while True:
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=min(50, max_results) if max_results else 50,
                    pageToken=next_page_token,
                )
                response = request.execute()

                for item in response.get("items", []):
                    snippet = item["snippet"]
                    content_details = item["contentDetails"]

                    thumbnails = snippet.get("thumbnails", {})
                    thumbnail_url = None
                    for size in ["default", "medium", "high", "standard", "maxres"]:
                        if size in thumbnails:
                            thumbnail_url = thumbnails[size]["url"]
                            break

                    videos.append(
                        {
                            "video_id": content_details["videoId"],
                            "title": snippet["title"],
                            "description": snippet.get("description", ""),
                            "published_at": snippet["publishedAt"],
                            "position": snippet["position"],
                            "thumbnail_url": thumbnail_url or "",
                        }
                    )

                    if max_results and len(videos) >= max_results:
                        return videos

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            return videos

        except Exception as e:
            print(f"Error fetching playlist {playlist_id}: {e}")
            return []

    def fetch_video_details(self, video_id: str) -> Optional[Dict]:
        """Fetch detailed metadata for a single video."""
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics", id=video_id
            )
            response = request.execute()

            if not response.get("items"):
                return None

            item = response["items"][0]
            snippet = item["snippet"]
            content_details = item["contentDetails"]
            statistics = item.get("statistics", {})

            return {
                "video_id": video_id,
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "published_at": snippet["publishedAt"],
                "duration": content_details["duration"],
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "thumbnail_url": snippet["thumbnails"]["high"]["url"],
            }

        except Exception as e:
            print(f"Error fetching video details for {video_id}: {e}")
            return None
