from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


CHANNEL_ID_PREFIX = "UC"


@dataclass
class ResolvedYouTubeChannel:
    id: str
    name: str
    source_input: str
    url: str


class ChannelResolutionError(ValueError):
    """Raised when a YouTube channel input cannot be resolved exactly."""


def _extract_input_candidate(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ChannelResolutionError("Channel input is empty.")
    return value


def _extract_channel_id_from_url(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel" and parts[1].startswith(CHANNEL_ID_PREFIX):
        return parts[1]
    return None


def _extract_handle_from_url(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0].startswith("@"):
        return parts[0]
    return None


def normalize_channel_lookup(raw_value: str) -> tuple[str, str]:
    value = _extract_input_candidate(raw_value)
    if value.startswith(CHANNEL_ID_PREFIX):
        return ("channel_id", value)
    if value.startswith("@"):
        return ("handle", value)

    if "youtube.com" in value or "youtu.be" in value:
        parsed = urlparse(value)
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        if "youtu.be" in host:
            raise ChannelResolutionError(
                "Video short URLs are not supported. Paste a channel URL like "
                "'https://www.youtube.com/@name' or 'https://www.youtube.com/channel/UC...'."
            )

        channel_id = _extract_channel_id_from_url(path)
        if channel_id:
            return ("channel_id", channel_id)

        handle = _extract_handle_from_url(path)
        if handle:
            return ("handle", handle)

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"user", "c"}:
            raise ChannelResolutionError(
                "Legacy '/user/' and '/c/' URLs are ambiguous here. Please paste the channel's "
                "'/@handle' URL or '/channel/UC...' URL instead."
            )

        raise ChannelResolutionError(
            "Unsupported YouTube URL. Please paste a channel URL like "
            "'https://www.youtube.com/@name' or 'https://www.youtube.com/channel/UC...'."
        )

    raise ChannelResolutionError(
        "Unsupported input. Paste a YouTube channel URL, a direct @handle, or a UC... channel ID."
    )


def _resolve_channel_by_id(youtube: object, channel_id: str, source_input: str) -> ResolvedYouTubeChannel:
    response = youtube.channels().list(part="snippet", id=channel_id).execute()
    items = response.get("items", [])
    if not items:
        raise ChannelResolutionError(f"No YouTube channel found for '{source_input}'.")
    item = items[0]
    resolved_id = item["id"]
    title = item.get("snippet", {}).get("title", resolved_id)
    return ResolvedYouTubeChannel(
        id=resolved_id,
        name=title,
        source_input=source_input,
        url=f"https://www.youtube.com/channel/{resolved_id}",
    )


def resolve_youtube_channel(youtube: object, raw_value: str) -> ResolvedYouTubeChannel:
    lookup_type, lookup_value = normalize_channel_lookup(raw_value)

    if lookup_type == "channel_id":
        return _resolve_channel_by_id(youtube, lookup_value, raw_value)

    handle_value = lookup_value if lookup_value.startswith("@") else f"@{lookup_value}"
    response = youtube.channels().list(part="snippet", forHandle=handle_value).execute()
    items = response.get("items", [])
    if not items:
        raise ChannelResolutionError(
            f"No exact YouTube channel was found for '{raw_value}'. "
            "Paste a valid /@handle or /channel/UC... URL."
        )
    item = items[0]
    return ResolvedYouTubeChannel(
        id=item["id"],
        name=item.get("snippet", {}).get("title", item["id"]),
        source_input=raw_value,
        url=f"https://www.youtube.com/channel/{item['id']}",
    )
