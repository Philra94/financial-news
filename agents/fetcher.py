from __future__ import annotations

from datetime import UTC, datetime, timedelta

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

from agents.models import AppSettings, SourceVideo
from agents.paths import raw_day_dir
from agents.storage import read_json, write_json


def _parse_published_at(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


def _fetch_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception:
        return ""
    return " ".join(chunk["text"].strip() for chunk in transcript if chunk.get("text"))


def fetch_latest_videos(settings: AppSettings, date_str: str) -> list[SourceVideo]:
    day_dir = raw_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    if not settings.youtube.api_key or not settings.youtube.channels:
        write_json(day_dir / "videos.json", [])
        return []

    youtube = build("youtube", "v3", developerKey=settings.youtube.api_key)
    published_after = (datetime.now(UTC) - timedelta(hours=settings.youtube.lookback_hours)).isoformat()
    videos: list[SourceVideo] = []

    for channel in settings.youtube.channels:
        response = (
            youtube.search()
            .list(
                part="snippet",
                channelId=channel.id,
                order="date",
                publishedAfter=published_after,
                maxResults=settings.youtube.max_videos_per_channel,
                type="video",
            )
            .execute()
        )
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            video = SourceVideo(
                video_id=video_id,
                title=snippet.get("title", "Untitled video"),
                channel_id=channel.id,
                channel_name=snippet.get("channelTitle") or channel.name,
                published_at=_parse_published_at(snippet["publishedAt"]),
                url=f"https://www.youtube.com/watch?v={video_id}",
                transcript=_fetch_transcript(video_id),
                thumbnail_url=((snippet.get("thumbnails") or {}).get("high") or {}).get("url"),
                description=snippet.get("description", ""),
            )
            videos.append(video)

    videos.sort(key=lambda video: video.published_at, reverse=True)
    write_json(day_dir / "videos.json", [video.model_dump(mode="json") for video in videos])
    return videos


def load_fetched_videos(date_str: str) -> list[SourceVideo]:
    payload = read_json(raw_day_dir(date_str) / "videos.json", default=[])
    return [SourceVideo.model_validate(item) for item in payload]
