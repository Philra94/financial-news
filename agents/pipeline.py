from __future__ import annotations

from datetime import UTC, datetime

from agents.analyzer import analyze_videos
from agents.compiler import compile_briefing
from agents.config import load_pipeline_status, save_pipeline_status
from agents.fetcher import fetch_latest_videos
from agents.models import AppSettings, PipelineJob
from agents.paths import pipeline_job_path
from agents.storage import model_from_json, write_json
from agents.utils import utc_now


def run_daily_pipeline(settings: AppSettings, date_str: str) -> None:
    videos = fetch_latest_videos(settings, date_str)
    analyses = analyze_videos(settings, videos, date_str)
    compile_briefing(settings, analyses, date_str)

    status = load_pipeline_status()
    status.last_run_at = datetime.now(UTC)
    status.last_run_date = date_str
    status.last_error = None
    save_pipeline_status(status)


def enqueue_pipeline_run(date_str: str) -> PipelineJob:
    job_id = f"pipeline-{date_str}"
    job = PipelineJob(id=job_id, date=date_str, status="queued", created_at=utc_now())
    write_json(pipeline_job_path(job_id), job.model_dump(mode="json"))
    return job


def load_pipeline_job(job_id: str) -> PipelineJob | None:
    return model_from_json(pipeline_job_path(job_id), PipelineJob)


def list_pipeline_jobs() -> list[PipelineJob]:
    jobs: list[PipelineJob] = []
    for path in sorted(pipeline_job_path("*").parent.glob("pipeline-*.json"), reverse=True):
        job = model_from_json(path, PipelineJob)
        if job is not None:
            jobs.append(job)
    return jobs


def process_next_pipeline_job(settings: AppSettings) -> PipelineJob | None:
    for job in list_pipeline_jobs():
        if job.status != "queued":
            continue
        status = load_pipeline_status()
        status.active_pipeline_job_id = job.id
        save_pipeline_status(status)
        try:
            job.status = "running"
            job.started_at = utc_now()
            write_json(pipeline_job_path(job.id), job.model_dump(mode="json"))
            run_daily_pipeline(settings, job.date)
            job.status = "completed"
            job.completed_at = utc_now()
            write_json(pipeline_job_path(job.id), job.model_dump(mode="json"))
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = utc_now()
            write_json(pipeline_job_path(job.id), job.model_dump(mode="json"))
            status = load_pipeline_status()
            status.last_error = str(exc)
            save_pipeline_status(status)
        finally:
            status = load_pipeline_status()
            status.active_pipeline_job_id = None
            save_pipeline_status(status)
        return job
    return None
