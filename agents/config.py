from __future__ import annotations

from agents.models import AppSettings, PipelineStatus
from agents.paths import PIPELINE_STATUS_PATH, SETTINGS_PATH, ensure_directories
from agents.storage import model_from_json, write_model


def load_settings() -> AppSettings:
    ensure_directories()
    settings = model_from_json(SETTINGS_PATH, AppSettings)
    if settings is None:
        settings = AppSettings()
        save_settings(settings)
    return settings


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
