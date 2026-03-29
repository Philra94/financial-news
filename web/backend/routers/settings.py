from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.config import load_settings, save_settings
from agents.google_search import search_google
from agents.models import AppSettings
from agents.youtube_channels import ChannelResolutionError, resolve_youtube_channel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ResolveChannelRequest(BaseModel):
    api_key: str
    channel_input: str


class TestGoogleSearchRequest(BaseModel):
    api_key: str = ""
    fallback_api_key: str = ""
    engine_id: str
    query: str = "financial markets"


@router.get("")
def get_settings() -> dict:
    return load_settings().model_dump(mode="json")


@router.put("")
def update_settings(payload: AppSettings) -> dict:
    save_settings(payload)
    return payload.model_dump(mode="json")


@router.post("/resolve-channel")
def resolve_channel(payload: ResolveChannelRequest) -> dict:
    try:
        youtube = build("youtube", "v3", developerKey=payload.api_key)
        resolved = resolve_youtube_channel(youtube, payload.channel_input)
    except ChannelResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": resolved.id,
        "name": resolved.name,
        "source_input": resolved.source_input,
        "url": resolved.url,
    }


@router.post("/test-google-search")
def test_google_search(payload: TestGoogleSearchRequest) -> dict:
    settings = load_settings()
    settings.google_search.api_key = payload.api_key
    settings.google_search.engine_id = payload.engine_id
    settings.youtube.api_key = payload.fallback_api_key
    try:
        results = search_google(payload.query, settings, num_results=3)
    except HttpError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "results": [item.model_dump(mode="json") for item in results],
    }
