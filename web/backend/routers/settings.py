from __future__ import annotations

from googleapiclient.discovery import build
from fastapi import APIRouter
from pydantic import BaseModel

from agents.config import load_settings, save_settings
from agents.models import AppSettings
from agents.youtube_channels import resolve_youtube_channel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ResolveChannelRequest(BaseModel):
    api_key: str
    channel_input: str


@router.get("")
def get_settings() -> dict:
    return load_settings().model_dump(mode="json")


@router.put("")
def update_settings(payload: AppSettings) -> dict:
    save_settings(payload)
    return payload.model_dump(mode="json")


@router.post("/resolve-channel")
def resolve_channel(payload: ResolveChannelRequest) -> dict:
    youtube = build("youtube", "v3", developerKey=payload.api_key)
    resolved = resolve_youtube_channel(youtube, payload.channel_input)
    return {
        "id": resolved.id,
        "name": resolved.name,
        "source_input": resolved.source_input,
        "url": resolved.url,
    }
