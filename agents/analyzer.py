from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
from typing import Any

from agents.models import (
    AnalysisResearchTask,
    AppSettings,
    Claim,
    DailyClaimsManifest,
    Opinion,
    SourceVideo,
    SubAnalysis,
    VideoAnalysis,
)
from agents.paths import SETTINGS_PATH, SKILLS_DIR, claims_manifest_path, raw_day_dir, video_subtasks_dir
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import read_json, write_json, write_text
from agents.utils import claim_id_from_text, extract_tickers


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


async def _agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, Any]:
    prompt = render_prompt(
        "analyze_transcript.md",
        title=video.title,
        channel=video.channel_name,
        transcript=video.transcript[:16000],
    )
    workspace = raw_day_dir(date_str) / "agent-analysis" / video.video_id
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    text = await runner.run(prompt, [])
    return _parse_json_block(text)


def _sp_research_skills() -> list[Path]:
    return [
        SKILLS_DIR / "browser" / "SKILL.md",
        SKILLS_DIR / "capital-iq-browser" / "SKILL.md",
        SKILLS_DIR / "editorial-graphs" / "SKILL.md",
    ]


def _planned_research_tasks(payload: dict[str, Any]) -> list[AnalysisResearchTask]:
    tasks: list[AnalysisResearchTask] = []
    for item in payload.get("research_tasks", [])[:3]:
        try:
            task = AnalysisResearchTask.model_validate(item)
        except Exception:
            continue
        if task.task_type != "sp_data_research":
            continue
        tasks.append(task)
    return tasks


def _capital_iq_configured(settings: AppSettings) -> bool:
    return bool(settings.capital_iq.username.strip() and settings.capital_iq.password.strip())


def _should_run_task(settings: AppSettings, task: AnalysisResearchTask) -> bool:
    if task.task_type == "sp_data_research":
        return _capital_iq_configured(settings)
    return False


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "task"


async def _run_sp_data_subtask(
    settings: AppSettings,
    video: SourceVideo,
    date_str: str,
    payload: dict[str, Any],
    task: AnalysisResearchTask,
    task_index: int,
) -> SubAnalysis:
    prompt = render_prompt(
        "research_sp_data.md",
        title=video.title,
        channel=video.channel_name,
        summary=payload.get("summary", ""),
        tickers=", ".join(payload.get("tickers", [])),
        topic_tags=", ".join(payload.get("topic_tags", [])),
        topic=task.topic,
        goal=task.goal,
        priority=task.priority,
        transcript=video.transcript[:12000],
        settings_path=str(SETTINGS_PATH),
    )
    slug = _slugify(task.topic)
    workspace = video_subtasks_dir(date_str, video.video_id) / f"{task_index:02d}-{slug}"
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    markdown = (await runner.run(prompt, _sp_research_skills())).strip()
    result_path = workspace / "analysis.md"
    write_text(result_path, markdown.rstrip() + "\n" if markdown else "")
    return SubAnalysis(
        task_type=task.task_type,
        topic=task.topic,
        goal=task.goal,
        priority=task.priority,
        markdown=markdown,
        result_path=str(result_path),
    )


async def _run_research_subtask(
    settings: AppSettings,
    video: SourceVideo,
    date_str: str,
    payload: dict[str, Any],
    task: AnalysisResearchTask,
    task_index: int,
) -> SubAnalysis:
    if task.task_type == "sp_data_research":
        return await _run_sp_data_subtask(settings, video, date_str, payload, task, task_index)
    raise ValueError(f"Unsupported research task type: {task.task_type}")


def analyze_videos(settings: AppSettings, videos: list[SourceVideo], date_str: str) -> list[VideoAnalysis]:
    day_dir = raw_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    analyses: list[VideoAnalysis] = []
    all_claims: list[Claim] = []

    for video in videos:
        if not video.transcript.strip():
            continue
        payload = asyncio.run(_agent_analysis(settings, video, date_str))
        if not payload:
            raise RuntimeError(f"Agent analysis returned no payload for video {video.video_id}")
        research_tasks = _planned_research_tasks(payload)
        sub_analyses: list[SubAnalysis] = []
        for index, task in enumerate(research_tasks, start=1):
            if not _should_run_task(settings, task):
                continue
            sub_analyses.append(asyncio.run(_run_research_subtask(settings, video, date_str, payload, task, index)))
        sp_enrichment = "\n\n".join(
            analysis.markdown for analysis in sub_analyses if analysis.task_type == "sp_data_research" and analysis.markdown
        ).strip()
        opinions = [
            Opinion(
                quote=item["quote"],
                speaker=item.get("speaker") or video.channel_name,
                source_video_id=video.video_id,
                source_url=video.url,
            )
            for item in payload.get("opinions", [])
            if item.get("quote")
        ]
        claims = []
        for item in payload.get("claims", []):
            text = item.get("text", "").strip()
            if not text:
                continue
            claim = Claim(
                id=claim_id_from_text(f"{video.video_id}:{text}"),
                text=text,
                speaker=item.get("speaker") or video.channel_name,
                source_video_id=video.video_id,
                source_url=video.url,
                source_title=video.title,
                topic_tags=item.get("topic_tags") or payload.get("topic_tags", []),
                tickers=item.get("tickers") or extract_tickers(text),
            )
            claims.append(claim)
            all_claims.append(claim)
        analysis = VideoAnalysis(
            video=video,
            summary=payload.get("summary", ""),
            topic_tags=payload.get("topic_tags", []),
            tickers=payload.get("tickers", []),
            research_tasks=research_tasks,
            sub_analyses=sub_analyses,
            sp_enrichment=sp_enrichment,
            opinions=opinions,
            claims=claims,
        )
        analyses.append(analysis)

    write_json(day_dir / "analysis.json", [item.model_dump(mode="json") for item in analyses])
    manifest = DailyClaimsManifest(date=date_str, claims=all_claims)
    write_json(claims_manifest_path(date_str), manifest.model_dump(mode="json"))
    return analyses


def load_analyses(date_str: str) -> list[VideoAnalysis]:
    payload = read_json(raw_day_dir(date_str) / "analysis.json", default=[])
    return [VideoAnalysis.model_validate(item) for item in payload]
