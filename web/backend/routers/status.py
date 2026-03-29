from __future__ import annotations

from fastapi import APIRouter

from agents.config import load_pipeline_status
from agents.researcher import list_jobs

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("")
def get_status() -> dict:
    pipeline_status = load_pipeline_status()
    jobs = list_jobs()
    return {
        "pipeline": pipeline_status.model_dump(mode="json"),
        "jobs": {
            "queued": sum(1 for job in jobs if job.status == "queued"),
            "researching": sum(1 for job in jobs if job.status == "researching"),
            "completed": sum(1 for job in jobs if job.status == "completed"),
            "failed": sum(1 for job in jobs if job.status == "failed"),
        },
    }
