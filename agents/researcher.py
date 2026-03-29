from __future__ import annotations

import asyncio
from pathlib import Path

from agents.models import AppSettings, DailyClaimsManifest, ResearchJob, ResearchResult
from agents.paths import (
    SKILLS_DIR,
    claims_manifest_path,
    job_path,
    research_result_json_path,
    research_result_path,
)
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import model_from_json, read_json, write_json, write_text
from agents.utils import utc_now


def load_claim_manifest(date_str: str) -> DailyClaimsManifest:
    manifest = model_from_json(claims_manifest_path(date_str), DailyClaimsManifest)
    return manifest or DailyClaimsManifest(date=date_str, claims=[])


def save_claim_manifest(manifest: DailyClaimsManifest) -> None:
    write_json(claims_manifest_path(manifest.date), manifest.model_dump(mode="json"))


def enqueue_research(settings: AppSettings, date_str: str, claim_id: str) -> ResearchJob:
    manifest = load_claim_manifest(date_str)
    claim = next((item for item in manifest.claims if item.id == claim_id), None)
    if claim is None:
        raise ValueError(f"Claim '{claim_id}' was not found for {date_str}")

    job = ResearchJob(
        claim_id=claim.id,
        date=date_str,
        claim_text=claim.text,
        source_video=claim.source_video_id,
        speaker=claim.speaker,
        status="queued",
        backend=settings.agent.backend,
        created_at=utc_now(),
    )
    claim.status = "queued"
    save_claim_manifest(manifest)
    write_json(job_path(claim.id), job.model_dump(mode="json"))
    return job


def load_job(claim_id: str) -> ResearchJob | None:
    return model_from_json(job_path(claim_id), ResearchJob)


def list_jobs() -> list[ResearchJob]:
    jobs: list[ResearchJob] = []
    for path in sorted(job_path("*").parent.glob("*.json")):
        job = model_from_json(path, ResearchJob)
        if job is not None:
            jobs.append(job)
    return jobs


def load_research_result(date_str: str, claim_id: str) -> ResearchResult | None:
    return model_from_json(research_result_json_path(date_str, claim_id), ResearchResult)


def _update_claim_status(date_str: str, claim_id: str, status: str, result_path: str | None = None) -> None:
    manifest = load_claim_manifest(date_str)
    for claim in manifest.claims:
        if claim.id == claim_id:
            claim.status = status  # type: ignore[assignment]
            if result_path:
                claim.research_result_path = result_path
            break
    save_claim_manifest(manifest)


def _skills() -> list[Path]:
    return [
        SKILLS_DIR / "browser" / "SKILL.md",
        SKILLS_DIR / "financial_data" / "SKILL.md",
        SKILLS_DIR / "news_search" / "SKILL.md",
    ]


async def process_job(settings: AppSettings, job: ResearchJob) -> ResearchResult:
    manifest = load_claim_manifest(job.date)
    claim = next((item for item in manifest.claims if item.id == job.claim_id), None)
    if claim is None:
        raise ValueError(f"Claim '{job.claim_id}' is missing from manifest")

    result_markdown_path = research_result_path(job.date, job.claim_id)
    workspace = result_markdown_path.parent
    workspace.mkdir(parents=True, exist_ok=True)

    job.status = "researching"
    job.started_at = utc_now()
    write_json(job_path(job.claim_id), job.model_dump(mode="json"))
    _update_claim_status(job.date, job.claim_id, "researching")

    prompt = render_prompt(
        "research_claim.md",
        claim=claim.text,
        speaker=claim.speaker,
        source_title=claim.source_title,
        source_url=claim.source_url,
    )
    runner = build_runner(job.backend, workspace, settings.agent.research_timeout_seconds)
    output = await runner.run(prompt, _skills())
    if not output:
        output = "# Claim\n\nNo output was returned by the selected agent."

    verdict = "mixed"
    lowered = output.lower()
    if "counter" in lowered and "supporting" not in lowered:
        verdict = "counter"
    elif "supporting" in lowered and "counter" not in lowered:
        verdict = "supporting"
    elif "support" not in lowered and "counter" not in lowered:
        verdict = "unknown"

    result = ResearchResult(
        claim_id=job.claim_id,
        date=job.date,
        verdict=verdict,
        summary=output.splitlines()[0].replace("#", "").strip() or "Research result",
        sources=[],
        markdown=output,
    )
    write_text(result_markdown_path, output)
    write_json(research_result_json_path(job.date, job.claim_id), result.model_dump(mode="json"))

    job.status = "completed"
    job.completed_at = utc_now()
    job.result_path = str(result_markdown_path)
    write_json(job_path(job.claim_id), job.model_dump(mode="json"))
    _update_claim_status(job.date, job.claim_id, "completed", str(result_markdown_path))
    return result


async def process_next_job(settings: AppSettings) -> ResearchJob | None:
    for job in list_jobs():
        if job.status != "queued":
            continue
        try:
            await process_job(settings, job)
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = utc_now()
            write_json(job_path(job.claim_id), job.model_dump(mode="json"))
            _update_claim_status(job.date, job.claim_id, "failed")
        return job
    return None


async def watch_jobs(settings: AppSettings, poll_interval: int = 2) -> None:
    while True:
        processed = await process_next_job(settings)
        if processed is None:
            await asyncio.sleep(poll_interval)


async def research_claim_now(settings: AppSettings, date_str: str, claim_id: str) -> ResearchResult:
    manifest = load_claim_manifest(date_str)
    claim = next((item for item in manifest.claims if item.id == claim_id), None)
    if claim is None:
        raise ValueError(f"Claim '{claim_id}' was not found")

    job = ResearchJob(
        claim_id=claim_id,
        date=date_str,
        claim_text=claim.text,
        source_video=claim.source_video_id,
        speaker=claim.speaker,
        status="queued",
        backend=settings.agent.backend,
        created_at=utc_now(),
    )
    write_json(job_path(job.claim_id), job.model_dump(mode="json"))
    try:
        return await process_job(settings, job)
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = utc_now()
        write_json(job_path(job.claim_id), job.model_dump(mode="json"))
        _update_claim_status(job.date, job.claim_id, "failed")
        raise
