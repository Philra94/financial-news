from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from agents.analyzer import analyze_videos, load_analyses
from agents.compiler import compile_briefing
from agents.config import load_pipeline_status, load_settings, save_pipeline_status
from agents.fetcher import fetch_latest_videos, load_fetched_videos
from agents.paths import SETTINGS_PATH, ensure_directories
from agents.researcher import (
    enqueue_research,
    list_jobs,
    load_research_result,
    process_next_job,
    research_claim_now,
    watch_jobs,
)

app = typer.Typer(help="Local agentic financial news workflow.")
console = Console()


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


@app.command()
def fetch(date: str = typer.Option(None, help="Target date in YYYY-MM-DD format.")) -> None:
    ensure_directories()
    settings = load_settings()
    target_date = date or _today()
    videos = fetch_latest_videos(settings, target_date)
    console.print(f"Fetched {len(videos)} videos for {target_date}.")


@app.command()
def analyze(date: str = typer.Option(None, help="Target date in YYYY-MM-DD format.")) -> None:
    settings = load_settings()
    target_date = date or _today()
    videos = load_fetched_videos(target_date)
    analyses = analyze_videos(settings, videos, target_date)
    console.print(f"Analyzed {len(analyses)} videos for {target_date}.")


@app.command("compile")
def compile_cmd(date: str = typer.Option(None, help="Target date in YYYY-MM-DD format.")) -> None:
    settings = load_settings()
    target_date = date or _today()
    analyses = load_analyses(target_date)
    markdown = compile_briefing(settings, analyses, target_date)
    console.print(f"Compiled briefing for {target_date} ({len(markdown)} chars).")


@app.command()
def run(date: str = typer.Option(None, help="Target date in YYYY-MM-DD format.")) -> None:
    settings = load_settings()
    target_date = date or _today()
    videos = fetch_latest_videos(settings, target_date)
    analyses = analyze_videos(settings, videos, target_date)
    compile_briefing(settings, analyses, target_date)

    status = load_pipeline_status()
    status.last_run_at = datetime.now(UTC)
    status.last_run_date = target_date
    status.last_error = None
    save_pipeline_status(status)
    console.print(f"Daily pipeline completed for {target_date}.")


@app.command()
def research(
    claim: str = typer.Option(..., "--claim", help="Claim ID to research."),
    date: str = typer.Option(..., help="Date that contains the claim."),
) -> None:
    settings = load_settings()
    result = asyncio.run(research_claim_now(settings, date, claim))
    console.print(result.markdown)


@app.command()
def worker(
    watch: bool = typer.Option(True, "--watch/--once", help="Continuously watch the jobs queue."),
    poll_interval: int = typer.Option(2, help="Polling interval in seconds."),
) -> None:
    settings = load_settings()
    status = load_pipeline_status()
    status.worker_running = True
    save_pipeline_status(status)
    try:
        if watch:
            asyncio.run(watch_jobs(settings, poll_interval=poll_interval))
        else:
            asyncio.run(process_next_job(settings))
    finally:
        status = load_pipeline_status()
        status.worker_running = False
        save_pipeline_status(status)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    uvicorn.run("web.backend.main:app", host=host, port=port, reload=False)


@app.command()
def status() -> None:
    pipeline_status = load_pipeline_status()
    table = Table(title="Financial News Status")
    table.add_column("Item")
    table.add_column("Value")
    table.add_row("Last run date", pipeline_status.last_run_date or "-")
    table.add_row("Last run at", pipeline_status.last_run_at.isoformat() if pipeline_status.last_run_at else "-")
    table.add_row("Worker running", "yes" if pipeline_status.worker_running else "no")
    table.add_row("Jobs queued", str(sum(1 for job in list_jobs() if job.status == "queued")))
    console.print(table)


@app.command()
def config() -> None:
    ensure_directories()
    payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    console.print_json(data=payload)


@app.command("queue")
def queue_job(
    claim: str = typer.Option(..., "--claim", help="Claim ID to queue."),
    date: str = typer.Option(..., help="Date that contains the claim."),
) -> None:
    settings = load_settings()
    job = enqueue_research(settings, date, claim)
    console.print(f"Queued research job {job.claim_id}.")


@app.command("result")
def result_cmd(
    claim: str = typer.Option(..., "--claim", help="Claim ID to inspect."),
    date: str = typer.Option(..., help="Date that contains the claim."),
) -> None:
    result = load_research_result(date, claim)
    if result is None:
        console.print(f"No research result found for {claim} on {date}.", style="red")
        raise typer.Exit(code=1)
    console.print(result.markdown)


if __name__ == "__main__":
    app()
