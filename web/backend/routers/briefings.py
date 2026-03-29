from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from agents.models import BriefingIndexItem, DailyClaimsManifest
from agents.paths import REPORTS_DIR, briefing_metadata_path, briefing_path, claims_manifest_path
from agents.storage import model_from_json, read_text

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


def _report_dirs() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted([path for path in REPORTS_DIR.iterdir() if path.is_dir()], reverse=True)


@router.get("")
def list_briefings() -> list[dict]:
    items: list[dict] = []
    for path in _report_dirs():
        metadata = model_from_json(briefing_metadata_path(path.name), BriefingIndexItem)
        if metadata is None:
            continue
        items.append(metadata.model_dump(mode="json"))
    return items


@router.get("/latest")
def latest_briefing() -> dict:
    dirs = _report_dirs()
    if not dirs:
        raise HTTPException(status_code=404, detail="No briefings available")
    return get_briefing(dirs[0].name)


@router.get("/{date_str}")
def get_briefing(date_str: str) -> dict:
    metadata = model_from_json(briefing_metadata_path(date_str), BriefingIndexItem)
    markdown = read_text(briefing_path(date_str))
    manifest = model_from_json(claims_manifest_path(date_str), DailyClaimsManifest)
    if not markdown:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return {
        "date": date_str,
        "markdown": markdown,
        "metadata": metadata.model_dump(mode="json") if metadata else None,
        "claims": manifest.model_dump(mode="json")["claims"] if manifest else [],
    }
