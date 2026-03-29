from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

from agents.models import AppSettings, SourceVideo, YouTubeChannel
from agents.paths import raw_day_dir, transcript_path
from agents.storage import read_json, write_json, write_text
from agents.youtube_channels import resolve_youtube_channel

TRANSCRIPT_LANGUAGES = ("en", "de")


def _parse_published_at(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


def _fetch_transcript(video_id: str) -> str:
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            transcript = api.fetch(video_id, languages=TRANSCRIPT_LANGUAGES)
        else:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=TRANSCRIPT_LANGUAGES)
    except Exception:
        return ""

    parts: list[str] = []
    for chunk in transcript:
        text = chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", "")
        if text:
            parts.append(text.strip())
    return " ".join(part for part in parts if part)


def _timezone(settings: AppSettings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.schedule.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _published_window(
    settings: AppSettings, date_str: str, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    tz = _timezone(settings)
    target_date = datetime.fromisoformat(date_str).date()
    start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)

    now_utc = now or datetime.now(UTC)
    now_local = now_utc.astimezone(tz)
    if target_date == now_local.date():
        lookback_start = now_local - timedelta(hours=settings.youtube.lookback_hours)
        return max(start_local, lookback_start).astimezone(UTC), now_utc

    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _persist_transcript(date_str: str, video: SourceVideo) -> None:
    if not video.transcript.strip():
        return
    write_text(transcript_path(date_str, video.video_id), video.transcript.rstrip() + "\n")


def _resolved_fetch_channel(youtube: object, channel: YouTubeChannel) -> tuple[str, str]:
    # Trust saved UC... ids first so daily runs never drift because of source input re-resolution.
    if channel.id.startswith("UC"):
        return channel.id, channel.name

    if channel.source_input:
        resolved = resolve_youtube_channel(youtube, channel.source_input)
        return resolved.id, resolved.name

    raise ValueError(
        f"Channel '{channel.name}' does not have a valid saved YouTube channel ID. "
        "Please re-check it in Settings."
    )


def fetch_latest_videos(settings: AppSettings, date_str: str) -> list[SourceVideo]:
    day_dir = raw_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    if not settings.youtube.api_key or not settings.youtube.channels:
        write_json(day_dir / "videos.json", [])
        return []

    youtube = build("youtube", "v3", developerKey=settings.youtube.api_key)
    published_after, published_before = _published_window(settings, date_str)
    videos: list[SourceVideo] = []

    for channel in settings.youtube.channels:
        channel_id, channel_name = _resolved_fetch_channel(youtube, channel)
        response = (
            youtube.search()
            .list(
                part="snippet",
                channelId=channel_id,
                order="date",
                publishedAfter=published_after.isoformat(),
                publishedBefore=published_before.isoformat(),
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
                channel_id=channel_id,
                channel_name=snippet.get("channelTitle") or channel_name or channel.name,
                published_at=_parse_published_at(snippet["publishedAt"]),
                url=f"https://www.youtube.com/watch?v={video_id}",
                transcript=_fetch_transcript(video_id),
                thumbnail_url=((snippet.get("thumbnails") or {}).get("high") or {}).get("url"),
                description=snippet.get("description", ""),
            )
            videos.append(video)
            _persist_transcript(date_str, video)

    videos.sort(key=lambda video: video.published_at, reverse=True)
    write_json(day_dir / "videos.json", [video.model_dump(mode="json") for video in videos])
    return videos


def load_fetched_videos(date_str: str) -> list[SourceVideo]:
    payload = read_json(raw_day_dir(date_str) / "videos.json", default=[])
    return [SourceVideo.model_validate(item) for item in payload]
