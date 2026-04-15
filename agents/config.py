from __future__ import annotations

from typing import Any

from agents.models import AppSettings, PipelineStatus
from agents.paths import PIPELINE_STATUS_PATH, SETTINGS_LOCAL_PATH, SETTINGS_PATH, ensure_directories
from agents.storage import model_from_json, write_model


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
            continue
        merged[key] = value
    return merged


def effective_settings_path() -> str:
    ensure_directories()
    if SETTINGS_LOCAL_PATH.exists():
        return str(SETTINGS_LOCAL_PATH)
    return str(SETTINGS_PATH)


def load_settings() -> AppSettings:
    ensure_directories()
    base_settings = model_from_json(SETTINGS_PATH, AppSettings)
    if base_settings is None:
        base_settings = AppSettings()
        save_settings(base_settings)

    local_settings = model_from_json(SETTINGS_LOCAL_PATH, AppSettings)
    if local_settings is None:
        return base_settings

    merged = _deep_merge(
        base_settings.model_dump(mode="python"),
        local_settings.model_dump(mode="python", exclude_unset=True),
    )
    return AppSettings.model_validate(merged)


def save_settings(settings: AppSettings) -> None:
    ensure_directories()
    write_model(SETTINGS_PATH, settings)


def load_pipeline_status() -> PipelineStatus:
    ensure_directories()
    status = model_from_json(PIPELINE_STATUS_PATH, PipelineStatus)
    if status is None:
        status = PipelineStatus()
        save_pipeline_status(status)
    return status


def save_pipeline_status(status: PipelineStatus) -> None:
    ensure_directories()
    write_model(PIPELINE_STATUS_PATH, status)
