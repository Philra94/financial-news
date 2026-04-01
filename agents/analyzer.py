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
from agents.utils import claim_id_from_text, extract_tickers, sentence_chunks


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


FALLBACK_TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
FALLBACK_TICKER_IGNORE = {
    "ARE",
    "BACK",
    "BEI",
    "BUILT",
    "CRAZY",
    "DOWN",
    "EAST",
    "EIN",
    "FOMO",
    "GOING",
    "HERE",
    "IM",
    "IN",
    "IRAN",
    "IS",
    "IST",
    "JOIN",
    "KEINE",
    "KRIEG",
    "MESSY",
    "OF",
    "ON",
    "REAL",
    "SITS",
    "STEVE",
    "THERE",
    "TRUMP",
    "UND",
    "VIDEO",
    "WHY",
    "ZUR",
    "AUF",
}


def _analysis_source_material(video: SourceVideo) -> tuple[str, str]:
    if video.transcript.strip():
        return "transcript", video.transcript[:16000]

    metadata_parts = [
        "No transcript was available for this video. Use only the metadata below.",
        f"Title: {video.title}",
        f"Channel: {video.channel_name}",
        f"Description: {video.description.strip() or 'No description provided.'}",
    ]
    if video.transcription_error:
        metadata_parts.append(f"Transcription error: {video.transcription_error}")
    return "metadata-only", "\n".join(metadata_parts)


def _has_analysis_material(video: SourceVideo) -> bool:
    return bool(video.transcript.strip() or video.title.strip() or video.description.strip())


def _clean_metadata_text(value: str) -> str:
    text = re.sub(r"https?://\S+", "", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_transcript_text(value: str) -> str:
    text = re.sub(r"https?://\S+", "", value)
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _topic_tags_from_text(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    if any(keyword in lowered for keyword in ("inflation", "rates", "fed", "ecb", "treasury", "bond", "macro")):
        tags.append("macro")
    if any(
        keyword in lowered
        for keyword in ("stock", "stocks", "shares", "equity", "equities", "earnings", "wall street", "analyst", "s&p", "nasdaq", "dow", "ai", "nvidia", "microsoft", "apple", "tesla", "marvell")
    ):
        tags.append("equities")
    if any(keyword in lowered for keyword in ("oil", "gold", "copper", "wti", "brent", "commodity", "commodities")):
        tags.append("commodities")
    return tags


def _fallback_tickers(text: str) -> list[str]:
    tickers = {
        token
        for token in FALLBACK_TICKER_PATTERN.findall(text)
        if token not in FALLBACK_TICKER_IGNORE
    }
    company_hints = {
        "nvidia": "NVDA",
        "microsoft": "MSFT",
        "apple": "AAPL",
        "tesla": "TSLA",
        "marvell": "MRVL",
        "nike": "NKE",
        "micron": "MU",
        "palo alto": "PANW",
        "servicenow": "NOW",
        "eli lilly": "LLY",
        "biogen": "BIIB",
        "unilever": "UL",
        "mccormick": "MKC",
    }
    lowered = text.lower()
    for company, ticker in company_hints.items():
        if company in lowered:
            tickers.add(ticker)
    return sorted(tickers)


def _fallback_summary_from_transcript(transcript: str) -> str:
    cleaned = _clean_transcript_text(transcript)
    chunks = [
        chunk
        for chunk in sentence_chunks(cleaned)
        if len(chunk) >= 45 and not chunk.lower().startswith(("so,", "okay,", "alright", "guten morgen"))
    ]
    selected = chunks[:3] or sentence_chunks(cleaned)[:2]
    summary = " ".join(selected).strip() if selected else cleaned[:420]
    return summary[:520].strip()


def _fallback_analysis_payload(video: SourceVideo) -> dict[str, Any]:
    if video.transcript.strip():
        transcript = _clean_transcript_text(video.transcript)
        summary = _fallback_summary_from_transcript(transcript)
        topic_source = transcript[:5000]
        return {
            "summary": summary or "A transcript-backed market update was available.",
            "topic_tags": _topic_tags_from_text(topic_source),
            "tickers": _fallback_tickers(topic_source),
            "research_tasks": [],
            "opinions": [],
            "claims": [],
        }

    headline = _clean_metadata_text(video.title)
    description = _clean_metadata_text(video.description)
    summary = headline or "A channel update was available without transcript text."
    if description:
        summary = f"{summary} {description[:280]}".strip()
    topic_source = f"{headline} {description}".strip()
    return {
        "summary": summary,
        "topic_tags": _topic_tags_from_text(topic_source),
        "tickers": _fallback_tickers(topic_source),
        "research_tasks": [],
        "opinions": [],
        "claims": [],
    }


async def _agent_analysis(
    settings: AppSettings, video: SourceVideo, date_str: str, *, retry_on_invalid_json: bool = True
) -> dict[str, Any]:
    source_mode, source_material = _analysis_source_material(video)
    prompt = render_prompt(
        "analyze_transcript.md",
        title=video.title,
        channel=video.channel_name,
        source_mode=source_mode,
        source_material=source_material,
    )
    if retry_on_invalid_json:
        prompt += (
            "\n\nImportant: Return only one valid JSON object that exactly matches the requested schema. "
            "Do not add commentary, markdown fences, or prose before or after the JSON."
        )
    workspace = raw_day_dir(date_str) / "agent-analysis" / video.video_id
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    text = await runner.run(prompt, [])
    try:
        return _parse_json_block(text)
    except Exception:
        if not retry_on_invalid_json:
            raise
        retry_prompt = (
            prompt
            + "\n\nYour previous response did not contain valid JSON. Retry now and respond with JSON only."
        )
        retry_text = await runner.run(retry_prompt, [])
        return _parse_json_block(retry_text)


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
        if not _has_analysis_material(video):
            continue
        try:
            payload = asyncio.run(_agent_analysis(settings, video, date_str))
        except Exception:
            payload = _fallback_analysis_payload(video)
        if not payload:
            payload = _fallback_analysis_payload(video)
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
