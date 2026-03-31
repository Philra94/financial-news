from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.discovery import build

from agents.models import AppSettings, SourceVideo, YouTubeChannel
from agents.paths import raw_day_dir
from agents.storage import read_json, write_json
from agents.transcriber import transcribe_source_video
from agents.youtube_channels import resolve_youtube_channel

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def _parse_published_at(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


def _parse_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = _DURATION_RE.fullmatch(value)
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds


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


def _video_details_map(youtube: object, video_ids: list[str]) -> dict[str, dict]:
    if not video_ids:
        return {}
    response = (
        youtube.videos()
        .list(
            part="snippet,contentDetails",
            id=",".join(video_ids),
            maxResults=len(video_ids),
        )
        .execute()
    )
    return {item["id"]: item for item in response.get("items", []) if item.get("id")}


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
        items = response.get("items", [])
        video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id", {}).get("videoId")]
        details_by_id = _video_details_map(youtube, video_ids)

        for item in items:
            search_snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            detail = details_by_id.get(video_id, {})
            detail_snippet = detail.get("snippet", {})
            snippet = detail_snippet or search_snippet
            video = SourceVideo(
                video_id=video_id,
                title=snippet.get("title") or search_snippet.get("title", "Untitled video"),
                channel_id=channel_id,
                channel_name=snippet.get("channelTitle") or search_snippet.get("channelTitle") or channel_name or channel.name,
                published_at=_parse_published_at(search_snippet["publishedAt"]),
                url=f"https://www.youtube.com/watch?v={video_id}",
                thumbnail_url=((search_snippet.get("thumbnails") or {}).get("high") or {}).get("url"),
                description=snippet.get("description") or search_snippet.get("description", ""),
                duration_seconds=_parse_duration_seconds((detail.get("contentDetails") or {}).get("duration")),
                default_audio_language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
            )
            video = transcribe_source_video(settings, date_str, video)
            videos.append(video)

    videos.sort(key=lambda video: video.published_at, reverse=True)
    write_json(day_dir / "videos.json", [video.model_dump(mode="json") for video in videos])
    return videos


def load_fetched_videos(date_str: str) -> list[SourceVideo]:
    payload = read_json(raw_day_dir(date_str) / "videos.json", default=[])
    return [SourceVideo.model_validate(item) for item in payload]
