from __future__ import annotations

from fastapi import APIRouter

from agents.config import load_settings, save_settings
from agents.models import AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> dict:
    return load_settings().model_dump(mode="json")


@router.put("")
def update_settings(payload: AppSettings) -> dict:
    save_settings(payload)
    return payload.model_dump(mode="json")
