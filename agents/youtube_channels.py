from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


CHANNEL_ID_PREFIX = "UC"


@dataclass
class ResolvedYouTubeChannel:
    id: str
    name: str
    source_input: str
    url: str


def _extract_input_candidate(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValueError("Channel input is empty")
    return value


def _extract_channel_id_from_url(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel" and parts[1].startswith(CHANNEL_ID_PREFIX):
        return parts[1]
    return None


def normalize_channel_lookup(raw_value: str) -> tuple[str, str]:
    value = _extract_input_candidate(raw_value)
    if value.startswith(CHANNEL_ID_PREFIX):
        return ("channel_id", value)
    if value.startswith("@"):
        return ("handle", value)

    if "youtube.com" in value or "youtu.be" in value:
        parsed = urlparse(value)
        path = parsed.path or ""
        channel_id = _extract_channel_id_from_url(path)
        if channel_id:
            return ("channel_id", channel_id)
        parts = [part for part in path.split("/") if part]
        if parts and parts[0].startswith("@"):
            return ("handle", parts[0])
        if len(parts) >= 2 and parts[0] in {"user", "c"}:
            return ("search", parts[1])
        if parts:
            return ("search", parts[-1])
        query = parse_qs(parsed.query)
        if "channel" in query and query["channel"]:
            return ("search", query["channel"][0])
    return ("search", value)


def resolve_youtube_channel(youtube: object, raw_value: str) -> ResolvedYouTubeChannel:
    lookup_type, lookup_value = normalize_channel_lookup(raw_value)

    if lookup_type == "channel_id":
        response = youtube.channels().list(part="snippet", id=lookup_value).execute()
        items = response.get("items", [])
        if not items:
            raise ValueError(f"No YouTube channel found for '{raw_value}'")
        item = items[0]
        channel_id = item["id"]
        title = item.get("snippet", {}).get("title", channel_id)
        return ResolvedYouTubeChannel(
            id=channel_id,
            name=title,
            source_input=raw_value,
            url=f"https://www.youtube.com/channel/{channel_id}",
        )

    if lookup_type == "search":
        search_response = (
            youtube.search()
            .list(part="snippet", q=lookup_value, type="channel", maxResults=1)
            .execute()
        )
        items = search_response.get("items", [])
        if not items:
            raise ValueError(f"No YouTube channel found for '{raw_value}'")
        channel_id = items[0].get("snippet", {}).get("channelId") or items[0].get("id", {}).get("channelId")
        if not channel_id:
            raise ValueError(f"Could not resolve channel ID for '{raw_value}'")
        return resolve_youtube_channel(youtube, channel_id)

    handle_value = lookup_value.lstrip("@")
    search_response = (
        youtube.search()
        .list(part="snippet", q=f"@{handle_value}", type="channel", maxResults=5)
        .execute()
    )
    items = search_response.get("items", [])
    if not items:
        raise ValueError(f"No YouTube channel found for '{raw_value}'")

    exact_match = next(
        (
            item
            for item in items
            if (item.get("snippet", {}).get("channelTitle", "").replace(" ", "").lower() == handle_value.lower())
        ),
        items[0],
    )
    channel_id = exact_match.get("snippet", {}).get("channelId") or exact_match.get("id", {}).get("channelId")
    if not channel_id:
        raise ValueError(f"Could not resolve handle '{raw_value}'")
    return resolve_youtube_channel(youtube, channel_id)
