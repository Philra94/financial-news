from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.config import load_settings
from agents.models import DailyClaimsManifest
from agents.pipeline import enqueue_pipeline_run, load_pipeline_job
from agents.paths import RAW_DIR, claims_manifest_path
from agents.researcher import enqueue_research, load_job, load_research_result
from agents.storage import model_from_json

router = APIRouter(prefix="/api", tags=["research"])


class ResearchRequest(BaseModel):
    date: str


class PipelineRunRequest(BaseModel):
    date: str


def _find_claim_date(claim_id: str) -> str | None:
    if not RAW_DIR.exists():
        return None
    for path in sorted(RAW_DIR.iterdir(), reverse=True):
        manifest = model_from_json(claims_manifest_path(path.name), DailyClaimsManifest)
        if manifest and any(claim.id == claim_id for claim in manifest.claims):
            return path.name
    return None


def _find_claim(date_str: str, claim_id: str):
    manifest = model_from_json(claims_manifest_path(date_str), DailyClaimsManifest)
    if manifest is None:
        return None
    return next((claim for claim in manifest.claims if claim.id == claim_id), None)


@router.get("/claims")
def list_claims() -> list[dict]:
    claims: list[dict] = []
    if not RAW_DIR.exists():
        return claims

    for path in sorted(RAW_DIR.iterdir(), reverse=True):
        manifest = model_from_json(claims_manifest_path(path.name), DailyClaimsManifest)
        if not manifest:
            continue
        for claim in manifest.claims:
            payload = claim.model_dump(mode="json")
            payload["date"] = manifest.date
            claims.append(payload)
    return claims


@router.get("/claims/{date_str}")
def get_claims(date_str: str) -> dict:
    manifest = model_from_json(claims_manifest_path(date_str), DailyClaimsManifest)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Claims manifest not found")
    return manifest.model_dump(mode="json")


@router.get("/claims/{date_str}/{claim_id}")
def get_claim(date_str: str, claim_id: str) -> dict:
    claim = _find_claim(date_str, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    job = load_job(claim_id)
    result = load_research_result(date_str, claim_id)
    return {
        "date": date_str,
        "claim": claim.model_dump(mode="json"),
        "job": job.model_dump(mode="json") if job else None,
        "result": result.model_dump(mode="json") if result else None,
    }


@router.post("/research/{claim_id}")
def queue_research(claim_id: str, payload: ResearchRequest | None = None) -> dict:
    date_str = payload.date if payload else _find_claim_date(claim_id)
    if not date_str:
        raise HTTPException(status_code=404, detail="Claim not found")
    settings = load_settings()
    job = enqueue_research(settings, date_str, claim_id)
    return {"queued": True, "job": job.model_dump(mode="json")}


@router.get("/research/{claim_id}")
def get_research(claim_id: str) -> dict:
    job = load_job(claim_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    result = load_research_result(job.date, claim_id)
    return {
        "job": job.model_dump(mode="json"),
        "result": result.model_dump(mode="json") if result else None,
    }


@router.post("/run")
def queue_pipeline_run(payload: PipelineRunRequest) -> dict:
    job = enqueue_pipeline_run(payload.date)
    return {"queued": True, "job": job.model_dump(mode="json")}


@router.get("/run/{job_id}")
def get_pipeline_run(job_id: str) -> dict:
    job = load_pipeline_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Pipeline job not found")
    return {"job": job.model_dump(mode="json")}
