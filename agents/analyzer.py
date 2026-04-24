from __future__ import annotations

import asyncio
from datetime import date
import json
import logging
from pathlib import Path
import re
from typing import Any

from agents.charts import materialize_chart_markdown
from agents.config import load_pipeline_status, save_pipeline_status
from agents.config import effective_settings_path
from agents.model_selection import analysis_agent_model, capital_iq_agent_model
from agents.models import (
    AnalysisResearchTask,
    AppSettings,
    Claim,
    DailyClaimsManifest,
    Opinion,
    PipelineStatus,
    SourceVideo,
    SubAnalysis,
    VideoAnalysis,
)
from agents.paths import SKILLS_DIR, claims_manifest_path, raw_day_dir, report_asset_url, report_charts_dir, video_subtasks_dir
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import read_json, write_json, write_text
from agents.utils import COMMON_NON_TICKER_TOKENS, claim_id_from_text, extract_tickers, sentence_chunks

logger = logging.getLogger(__name__)


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


FALLBACK_TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
FALLBACK_TICKER_IGNORE = COMMON_NON_TICKER_TOKENS | {
    "AUF",
    "BEI",
    "EIN",
    "FOMO",
    "IST",
    "KEINE",
    "KRIEG",
    "MESSY",
    "OF",
    "ON",
    "SITS",
    "STEVE",
    "THERE",
    "UND",
    "VIDEO",
    "WHY",
    "ZUR",
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


def _watchlist_prompt_context(settings: AppSettings) -> str:
    items = []
    for stock in settings.watchlist.stocks:
        ticker = stock.ticker.strip().upper()
        if not ticker:
            continue
        label = ticker
        if stock.name.strip():
            label = f"{label} ({stock.name.strip()})"
        if stock.notes.strip():
            label = f"{label}: {stock.notes.strip()}"
        items.append(label)
    return "\n".join(f"- {item}" for item in items) if items else "No watchlist configured."


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
        watchlist_context=_watchlist_prompt_context(settings),
    )
    if retry_on_invalid_json:
        prompt += (
            "\n\nImportant: Return only one valid JSON object that exactly matches the requested schema. "
            "Do not add commentary, markdown fences, or prose before or after the JSON."
        )
    workspace = raw_day_dir(date_str) / "agent-analysis" / video.video_id
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=analysis_agent_model(settings),
    )
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
        SKILLS_DIR / "capital-iq-browser" / "navigation-notes.md",
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


def _watchlist_lookup(settings: AppSettings) -> dict[str, tuple[str, str]]:
    lookup: dict[str, tuple[str, str]] = {}
    for stock in settings.watchlist.stocks:
        ticker = stock.ticker.strip().upper()
        if not ticker:
            continue
        lookup[ticker] = (stock.name.strip(), stock.notes.strip())
    return lookup


def _watchlist_matches(settings: AppSettings, video: SourceVideo, payload: dict[str, Any]) -> list[str]:
    watchlist = _watchlist_lookup(settings)
    if not watchlist:
        return []

    payload_tickers = {
        ticker.strip().upper()
        for ticker in payload.get("tickers", [])
        if isinstance(ticker, str) and ticker.strip()
    }
    text_parts = [
        video.title,
        video.description,
        video.transcript[:20000],
        str(payload.get("summary", "")),
        " ".join(
            item.get("text", "")
            for item in payload.get("claims", [])
            if isinstance(item, dict) and item.get("text")
        ),
    ]
    combined_text = " ".join(part for part in text_parts if part).strip()
    combined_lower = combined_text.lower()
    inferred_tickers = set(extract_tickers(combined_text))

    matches: list[str] = []
    for ticker, (name, _) in watchlist.items():
        if ticker in payload_tickers or ticker in inferred_tickers:
            matches.append(ticker)
            continue
        if name and name.lower() in combined_lower:
            matches.append(ticker)
    return matches


def _watchlist_refresh_is_due(last_checked: str | None, target_date: str, refresh_days: int) -> bool:
    if not last_checked:
        return True
    try:
        current = date.fromisoformat(target_date)
        previous = date.fromisoformat(last_checked)
    except ValueError:
        return True
    return (current - previous).days >= max(refresh_days, 1)


def _task_targets_watchlist_ticker(task: AnalysisResearchTask, ticker: str) -> bool:
    task_tickers = extract_tickers(f"{task.topic} {task.goal}")
    return ticker in task_tickers


def _auto_watchlist_research_tasks(
    settings: AppSettings,
    watchlist_matches: list[str],
    pipeline_status: PipelineStatus,
    date_str: str,
) -> list[AnalysisResearchTask]:
    if not watchlist_matches or not _capital_iq_configured(settings):
        return []

    refresh_days = max(settings.watchlist.valuation_refresh_days, 1)
    watchlist = _watchlist_lookup(settings)
    tasks: list[AnalysisResearchTask] = []
    for ticker in watchlist_matches:
        if not _watchlist_refresh_is_due(pipeline_status.watchlist_valuation_checks.get(ticker), date_str, refresh_days):
            continue
        name, notes = watchlist.get(ticker, ("", ""))
        label = name or ticker
        goal = f"Use S&P Capital IQ to refresh price, scale, and valuation context for {ticker}."
        if notes:
            goal += f" Keep this angle in mind: {notes}"
        tasks.append(
            AnalysisResearchTask(
                task_type="sp_data_research",
                topic=f"{label} valuation refresh",
                goal=goal,
                priority="high",
            )
        )
    return tasks


def _merge_research_tasks(
    primary_tasks: list[AnalysisResearchTask],
    secondary_tasks: list[AnalysisResearchTask],
    *,
    limit: int = 3,
) -> list[AnalysisResearchTask]:
    merged: list[AnalysisResearchTask] = []
    seen: set[tuple[str, str, str]] = set()
    for task in primary_tasks + secondary_tasks:
        key = (task.task_type, task.topic.strip().lower(), task.goal.strip().lower())
        if key in seen:
            continue
        merged.append(task)
        seen.add(key)
        if len(merged) >= limit:
            break
    return merged


def _should_run_task(settings: AppSettings, task: AnalysisResearchTask) -> bool:
    if task.task_type == "sp_data_research":
        return _capital_iq_configured(settings)
    return False


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "task"


def _materialize_subanalysis_charts(markdown: str, date_str: str, video_id: str, task_index: int, slug: str) -> str:
    if "```chart-spec" not in markdown:
        return markdown
    try:
        return materialize_chart_markdown(
            markdown,
            report_charts_dir(date_str),
            report_asset_url(date_str, "assets", "charts"),
            f"{video_id}-{task_index:02d}-{slug}",
        )
    except Exception:
        logger.exception("Chart materialization failed for %s task %s", video_id, task_index)
        return markdown


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
        settings_path=effective_settings_path(),
    )
    slug = _slugify(task.topic)
    workspace = video_subtasks_dir(date_str, video.video_id) / f"{task_index:02d}-{slug}"
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=capital_iq_agent_model(settings),
    )
    markdown = (await runner.run(prompt, _sp_research_skills())).strip()
    markdown = _materialize_subanalysis_charts(markdown, date_str, video.video_id, task_index, slug)
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
    pipeline_status = load_pipeline_status()
    pipeline_status_dirty = False

    for video in videos:
        if not _has_analysis_material(video):
            continue
        try:
            payload = asyncio.run(_agent_analysis(settings, video, date_str))
        except Exception:
            logger.exception("Agent analysis failed for %s; using fallback payload", video.video_id)
            payload = _fallback_analysis_payload(video)
        if not payload:
            logger.warning("Agent analysis returned empty payload for %s; using fallback payload", video.video_id)
            payload = _fallback_analysis_payload(video)
        watchlist_matches = _watchlist_matches(settings, video, payload)
        research_tasks = _merge_research_tasks(
            _auto_watchlist_research_tasks(settings, watchlist_matches, pipeline_status, date_str),
            _planned_research_tasks(payload),
        )
        sub_analyses: list[SubAnalysis] = []
        completed_watchlist_checks: set[str] = set()
        for index, task in enumerate(research_tasks, start=1):
            if not _should_run_task(settings, task):
                continue
            try:
                sub_analysis = asyncio.run(_run_research_subtask(settings, video, date_str, payload, task, index))
            except Exception:
                logger.exception(
                    "Research subtask failed for %s task %s (%s); continuing without enrichment",
                    video.video_id,
                    index,
                    task.topic,
                )
                continue
            sub_analyses.append(sub_analysis)
            if sub_analysis.markdown.strip():
                for ticker in watchlist_matches:
                    if _task_targets_watchlist_ticker(task, ticker):
                        completed_watchlist_checks.add(ticker)
        sp_enrichment = "\n\n".join(
            analysis.markdown for analysis in sub_analyses if analysis.task_type == "sp_data_research" and analysis.markdown
        ).strip()
        for ticker in completed_watchlist_checks:
            pipeline_status.watchlist_valuation_checks[ticker] = date_str
            pipeline_status_dirty = True
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
            watchlist_matches=watchlist_matches,
            research_tasks=research_tasks,
            sub_analyses=sub_analyses,
            sp_enrichment=sp_enrichment,
            opinions=opinions,
            claims=claims,
        )
        analyses.append(analysis)

    if pipeline_status_dirty:
        save_pipeline_status(pipeline_status)
    write_json(day_dir / "analysis.json", [item.model_dump(mode="json") for item in analyses])
    manifest = DailyClaimsManifest(date=date_str, claims=all_claims)
    write_json(claims_manifest_path(date_str), manifest.model_dump(mode="json"))
    return analyses


def load_analyses(date_str: str) -> list[VideoAnalysis]:
    payload = read_json(raw_day_dir(date_str) / "analysis.json", default=[])
    return [VideoAnalysis.model_validate(item) for item in payload]
