from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from agents.models import AppSettings, BriefingIndexItem, BriefingQuality, MarketSnapshot, VideoAnalysis
from agents.paths import (
    briefing_english_path,
    briefing_german_path,
    briefing_metadata_path,
    briefing_path,
    report_day_dir,
)
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import write_json, write_text
from agents.utils import unwrap_markdown_response

logger = logging.getLogger(__name__)

AGENT_CHATTER_PATTERNS = [
    re.compile(r"\bi (?:now )?have (?:all the data|enough information) (?:i )?need\b", re.IGNORECASE),
    re.compile(r"\blet me (?:compile|write|translate|revise)\b", re.IGNORECASE),
    re.compile(r"\bi (?:can|will|am going to)(?: now)? (?:compile|write|translate|revise)\b", re.IGNORECASE),
    re.compile(r"\bhere(?:'s| is) the (?:briefing|analysis|translation|translated briefing)\b", re.IGNORECASE),
    re.compile(r"\bbased on the provided (?:markdown|briefing|data|information)\b", re.IGNORECASE),
    re.compile(r"\bich habe jetzt (?:alle daten|genug informationen)\b", re.IGNORECASE),
    re.compile(r"\blassen sie mich\b", re.IGNORECASE),
    re.compile(r"\bich (?:kann|werde)(?: jetzt)? (?:kompilieren|schreiben|uebersetzen|übersetzen)\b", re.IGNORECASE),
    re.compile(r"\bhier ist die (?:analyse|uebersetzung|übersetzung|zusammenfassung)\b", re.IGNORECASE),
]


def _default_agent_model(settings: AppSettings) -> str | None:
    model = settings.agent.model.strip()
    return model or None


def _section_for_analysis(analysis: VideoAnalysis) -> str:
    if analysis.watchlist_matches:
        return "WATCHLIST"
    tags = {tag.lower() for tag in analysis.topic_tags}
    if {"macro", "inflation", "rates"} & tags:
        return "MACRO"
    if {"commodities"} & tags:
        return "COMMODITIES"
    if {"equities", "earnings", "ai"} & tags or analysis.tickers:
        return "EQUITIES"
    return "MACRO"


def _normalize_markdown(markdown: str) -> str:
    normalized = markdown.strip()
    if not normalized:
        raise RuntimeError("Agent returned empty markdown")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def _is_agent_chatter_block(block: str) -> bool:
    flattened = " ".join(line.strip() for line in block.splitlines() if line.strip())
    if not flattened:
        return False
    return any(pattern.search(flattened) for pattern in AGENT_CHATTER_PATTERNS)


def _clean_public_markdown(raw_text: str, *, artifact_name: str, date_str: str) -> str:
    day_dir = report_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)
    write_text(day_dir / artifact_name, raw_text)

    cleaned = unwrap_markdown_response(raw_text).strip()
    blocks = [block.strip() for block in re.split(r"\n\s*\n", cleaned) if block.strip()]
    filtered_blocks = [block for block in blocks if not _is_agent_chatter_block(block)]
    if len(filtered_blocks) != len(blocks):
        logger.warning("Removed agent workflow chatter from %s for %s", artifact_name, date_str)
    return _normalize_markdown("\n\n".join(filtered_blocks))


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


def _serialize_analysis_summary(analysis: VideoAnalysis, section: str) -> dict[str, Any]:
    return {
        "video_id": analysis.video.video_id,
        "section": section,
        "channel_name": analysis.video.channel_name,
        "title": analysis.video.title,
        "summary": analysis.summary.strip(),
        "topic_tags": analysis.topic_tags[:8],
        "tickers": analysis.tickers[:10],
        "watchlist_matches": analysis.watchlist_matches[:6],
    }


def _related_analyses_map(analyses: list[VideoAnalysis]) -> dict[str, list[dict[str, Any]]]:
    section_by_video_id = {analysis.video.video_id: _section_for_analysis(analysis) for analysis in analyses}
    related: dict[str, list[dict[str, Any]]] = {}
    for analysis in analyses:
        current_tags = {tag.lower() for tag in analysis.topic_tags}
        current_tickers = {ticker.upper() for ticker in analysis.tickers}
        overlaps: list[tuple[int, dict[str, Any]]] = []
        for other in analyses:
            if other.video.video_id == analysis.video.video_id:
                continue
            other_tags = {tag.lower() for tag in other.topic_tags}
            other_tickers = {ticker.upper() for ticker in other.tickers}
            shared_tags = sorted(current_tags & other_tags)
            shared_tickers = sorted(current_tickers & other_tickers)
            score = len(shared_tags) + (len(shared_tickers) * 2)
            if score == 0:
                continue
            overlaps.append(
                (
                    score,
                    {
                        "video_id": other.video.video_id,
                        "channel_name": other.video.channel_name,
                        "title": other.video.title,
                        "section": section_by_video_id[other.video.video_id],
                        "shared_topic_tags": shared_tags,
                        "shared_tickers": shared_tickers,
                    },
                )
            )
        overlaps.sort(key=lambda item: (-item[0], item[1]["title"]))
        related[analysis.video.video_id] = [item for _, item in overlaps[:3]]
    return related


def _serialize_analysis_for_prompt(analysis: VideoAnalysis, related_analyses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "video": {
            "video_id": analysis.video.video_id,
            "title": analysis.video.title,
            "channel_name": analysis.video.channel_name,
            "published_at": analysis.video.published_at.isoformat(),
            "url": analysis.video.url,
        },
        "summary": analysis.summary.strip(),
        "topic_tags": analysis.topic_tags[:8],
        "tickers": analysis.tickers[:10],
        "watchlist_matches": analysis.watchlist_matches[:6],
        "opinions": [
            {
                "quote": opinion.quote,
                "speaker": opinion.speaker,
            }
            for opinion in analysis.opinions[:3]
        ],
        "claims": [
            {
                "id": claim.id,
                "text": claim.text,
                "speaker": claim.speaker,
                "topic_tags": claim.topic_tags[:6],
                "tickers": claim.tickers[:8],
            }
            for claim in analysis.claims[:8]
        ],
        "sub_analyses": [
            {
                "task_type": sub_analysis.task_type,
                "topic": sub_analysis.topic,
                "goal": sub_analysis.goal,
                "priority": sub_analysis.priority,
                "markdown": sub_analysis.markdown.strip(),
            }
            for sub_analysis in analysis.sub_analyses
            if sub_analysis.markdown.strip()
        ],
        "sp_enrichment": analysis.sp_enrichment.strip(),
        "related_analyses": related_analyses,
    }


def _analysis_priority_key(analysis: VideoAnalysis) -> tuple[int, float]:
    return (0 if analysis.watchlist_matches else 1, -analysis.video.published_at.timestamp())


def _build_synthesis_hints(settings: AppSettings, analyses: list[VideoAnalysis]) -> list[str]:
    tag_counts: dict[str, int] = defaultdict(int)
    ticker_counts: dict[str, int] = defaultdict(int)
    for analysis in analyses:
        for tag in {item.lower() for item in analysis.topic_tags}:
            tag_counts[tag] += 1
        for ticker in {item.upper() for item in analysis.tickers}:
            ticker_counts[ticker] += 1
    hints: list[str] = []
    repeated_tags = [tag for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0])) if count > 1]
    repeated_tickers = [
        ticker
        for ticker, count in sorted(ticker_counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 1
    ]
    if repeated_tags:
        hints.append(f"Recurring themes across sources: {', '.join(repeated_tags[:5])}.")
    if repeated_tickers:
        hints.append(f"Recurring tickers across sources: {', '.join(repeated_tickers[:6])}.")
    watchlist_hits = sorted({ticker for analysis in analyses for ticker in analysis.watchlist_matches})
    if watchlist_hits:
        hints.append(f"Configured watchlist names mentioned in today's coverage: {', '.join(watchlist_hits[:6])}.")
    elif settings.watchlist.stocks:
        configured = [stock.ticker.strip().upper() for stock in settings.watchlist.stocks if stock.ticker.strip()]
        if configured:
            hints.append(f"Configured watchlist for editorial emphasis: {', '.join(configured[:8])}.")
    if len(analyses) > 1:
        hints.append("Merge overlapping coverage into a single coherent angle instead of repeating each channel in sequence.")
    return hints


def _build_market_overview_inputs(analyses: list[VideoAnalysis]) -> list[dict[str, Any]]:
    return [
        _serialize_analysis_summary(analysis, _section_for_analysis(analysis))
        for analysis in sorted(analyses, key=_analysis_priority_key)[:5]
        if analysis.summary.strip()
    ]


def _serialize_market_snapshot(snapshot: MarketSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "summary": snapshot.summary.strip(),
        "chart_url": snapshot.chart_url,
        "indices": [
            {
                "label": item.label,
                "symbol": item.symbol,
                "daily_change_percent": item.daily_change_percent,
                "closing_level": item.closing_level,
                "currency": item.currency,
                "as_of": item.as_of,
                "session_label": item.session_label,
                "note": item.note,
            }
            for item in snapshot.indices
        ],
    }


def _build_compiler_payload(
    settings: AppSettings, analyses: list[VideoAnalysis], date_str: str, market_snapshot: MarketSnapshot | None = None
) -> tuple[dict[str, Any], str]:
    sections: dict[str, list[VideoAnalysis]] = defaultdict(list)
    ordered_analyses = sorted(analyses, key=_analysis_priority_key)
    for analysis in ordered_analyses:
        sections[_section_for_analysis(analysis)].append(analysis)

    market_overview = "No channel data was available for this date yet."
    overview_inputs = _build_market_overview_inputs(ordered_analyses)
    if overview_inputs:
        market_overview = " ".join(item["summary"] for item in overview_inputs[:3]).strip() or market_overview

    related_map = _related_analyses_map(ordered_analyses)
    structured_payload = {
        "date": date_str,
        "title": settings.site.title,
        "subtitle": settings.site.subtitle,
        "market_overview_seed": market_overview,
        "market_overview_inputs": overview_inputs,
        "market_snapshot": _serialize_market_snapshot(market_snapshot),
        "synthesis_hints": _build_synthesis_hints(settings, ordered_analyses),
        "watchlist": [
            {
                "ticker": stock.ticker.strip().upper(),
                "name": stock.name.strip(),
                "notes": stock.notes.strip(),
            }
            for stock in settings.watchlist.stocks
            if stock.ticker.strip()
        ],
        "sections": {
            section: [
                _serialize_analysis_for_prompt(analysis, related_map.get(analysis.video.video_id, []))
                for analysis in items
            ]
            for section, items in sections.items()
        },
    }
    return structured_payload, market_overview


def _inject_market_snapshot(markdown: str, market_snapshot: MarketSnapshot | None) -> str:
    if market_snapshot is None or not market_snapshot.markdown.strip():
        return markdown
    if "## MARKET SNAPSHOT" in markdown:
        return markdown

    lines = markdown.strip().splitlines()
    insertion_lines = ["", market_snapshot.markdown.strip(), ""]
    for index, line in enumerate(lines):
        if line.strip() == "---":
            lines[index + 1 : index + 1] = insertion_lines
            return _normalize_markdown("\n".join(lines))
    return _normalize_markdown("\n".join([markdown.strip(), "", market_snapshot.markdown.strip()]))


def _generate_briefing(settings: AppSettings, payload: dict[str, Any], date_str: str) -> str:
    prompt = render_prompt(
        "compile_briefing.md",
        date=date_str,
        title=settings.site.title,
        payload=json.dumps(payload, indent=2),
    )
    workspace = report_day_dir(date_str) / "agent-compile"
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=_default_agent_model(settings),
    )
    raw_text = asyncio.run(runner.run(prompt, []))
    return _clean_public_markdown(raw_text, artifact_name="briefing.en.raw.md", date_str=date_str)


def _review_briefing(settings: AppSettings, payload: dict[str, Any], markdown: str, date_str: str) -> dict[str, Any] | None:
    prompt = render_prompt(
        "review_briefing.md",
        date=date_str,
        title=settings.site.title,
        payload=json.dumps(payload, indent=2),
        markdown=markdown,
    )
    workspace = report_day_dir(date_str) / "agent-review"
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=_default_agent_model(settings),
    )
    review_text = asyncio.run(runner.run(prompt, []))
    try:
        return _parse_json_block(review_text)
    except Exception:
        logger.warning("Reviewer returned invalid JSON; skipping revision loop", exc_info=True)
        return None


def _revise_briefing(
    settings: AppSettings,
    payload: dict[str, Any],
    draft_markdown: str,
    review_payload: dict[str, Any],
    date_str: str,
) -> str:
    instructions = review_payload.get("revision_instructions") or []
    if not instructions:
        return draft_markdown
    revision_prompt = (
        render_prompt(
            "compile_briefing.md",
            date=date_str,
            title=settings.site.title,
            payload=json.dumps(payload, indent=2),
        )
        + "\n\nRevise the existing draft below using the editor feedback."
        + "\nReturn markdown only."
        + "\n\nCurrent draft:\n"
        + draft_markdown
        + "\n\nEditor feedback:\n"
        + "\n".join(f"- {instruction}" for instruction in instructions)
    )
    workspace = report_day_dir(date_str) / "agent-revise"
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=_default_agent_model(settings),
    )
    revised = asyncio.run(runner.run(revision_prompt, []))
    return _clean_public_markdown(revised, artifact_name="briefing.revised.raw.md", date_str=date_str)


def _summary_from_markdown(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "*", "-", "|", "![", "```")):
            continue
        return stripped[:240]
    return fallback[:240]


def _fallback_briefing_markdown(
    settings: AppSettings, analyses: list[VideoAnalysis], date_str: str, market_snapshot: MarketSnapshot | None = None
) -> str:
    lines = [
        f"# {settings.site.title}",
        f"**{date_str} | {settings.site.subtitle}**",
        "",
        "---",
        "",
    ]
    if market_snapshot and market_snapshot.markdown.strip():
        lines.extend([market_snapshot.markdown.strip(), "", ""])
    lines.extend(["## MARKET OVERVIEW", ""])
    summaries = [analysis.summary.strip() for analysis in analyses if analysis.summary.strip()]
    if summaries:
        for summary in summaries[:3]:
            lines.append(f"- {summary}")
    else:
        lines.append("No channel data was available for this date yet.")

    section_labels = ("EQUITIES", "MACRO", "COMMODITIES", "WATCHLIST")
    grouped: dict[str, list[VideoAnalysis]] = defaultdict(list)
    for analysis in analyses:
        grouped[_section_for_analysis(analysis)].append(analysis)

    for section in section_labels:
        items = grouped.get(section, [])
        if not items:
            continue
        lines.extend(["", "---", "", f"## {section}", ""])
        for analysis in items:
            lines.append(f"### {analysis.video.channel_name}: {analysis.video.title}")
            lines.append(analysis.summary.strip() or "No summary available.")
            if analysis.sp_enrichment.strip():
                lines.extend(["", analysis.sp_enrichment.strip()])
            lines.append("")

    return _normalize_markdown("\n".join(lines))


def _translate_briefing_to_german(settings: AppSettings, markdown: str, date_str: str) -> str:
    workspace = report_day_dir(date_str) / "agent-translate"
    prompt = render_prompt("translate_briefing_german.md", markdown=markdown)
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=_default_agent_model(settings),
    )
    translated = asyncio.run(runner.run(prompt, []))
    return _clean_public_markdown(translated, artifact_name="briefing.de.raw.md", date_str=date_str)


def compile_briefing(
    settings: AppSettings, analyses: list[VideoAnalysis], date_str: str, market_snapshot: MarketSnapshot | None = None
) -> str:
    day_dir = report_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    structured_payload, market_overview = _build_compiler_payload(settings, analyses, date_str, market_snapshot)
    quality: BriefingQuality = "full"
    try:
        english_markdown = _generate_briefing(settings, structured_payload, date_str)
        review_payload = _review_briefing(settings, structured_payload, english_markdown, date_str)
        if review_payload and not review_payload.get("approved", False):
            logger.info(
                "Reviewer requested revisions for %s: %s",
                date_str,
                review_payload.get("summary", "No summary provided"),
            )
            try:
                english_markdown = _revise_briefing(settings, structured_payload, english_markdown, review_payload, date_str)
            except Exception:
                logger.exception("Revision pass failed for %s; keeping original draft", date_str)
        english_markdown = _inject_market_snapshot(english_markdown, market_snapshot)
    except Exception:
        logger.exception("Compiler agent failed for %s; using fallback briefing", date_str)
        quality = "fallback"
        english_markdown = _fallback_briefing_markdown(settings, analyses, date_str, market_snapshot)
    try:
        german_markdown = _translate_briefing_to_german(settings, english_markdown, date_str)
    except Exception:
        logger.exception("German translation failed for %s; using English fallback", date_str)
        quality = "fallback"
        german_markdown = english_markdown

    write_text(briefing_english_path(date_str), english_markdown)
    write_text(briefing_german_path(date_str), german_markdown)
    write_text(briefing_path(date_str), german_markdown)

    item = BriefingIndexItem(
        date=date_str,
        title=settings.site.title,
        summary=_summary_from_markdown(english_markdown, market_overview),
        claim_count=sum(len(analysis.claims) for analysis in analyses),
        source_count=len(analyses),
        quality=quality,
        updated_at=max((analysis.video.published_at for analysis in analyses), default=None)
        or datetime.now(UTC),
    )
    write_json(briefing_metadata_path(date_str), item.model_dump(mode="json"))
    return german_markdown
