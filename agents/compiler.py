from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime

from agents.models import AppSettings, BriefingIndexItem, VideoAnalysis
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


def _section_for_analysis(analysis: VideoAnalysis) -> str:
    tags = {tag.lower() for tag in analysis.topic_tags}
    if {"macro", "inflation", "rates"} & tags:
        return "MACRO"
    if {"equities", "earnings", "ai"} & tags:
        return "EQUITIES"
    if {"commodities"} & tags:
        return "COMMODITIES"
    return "WATCHLIST"


def _normalize_markdown(markdown: str) -> str:
    normalized = markdown.strip()
    if not normalized:
        raise RuntimeError("Agent returned empty markdown")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def _translate_briefing_to_german(settings: AppSettings, markdown: str, date_str: str) -> str:
    workspace = report_day_dir(date_str) / "agent-translate"
    prompt = render_prompt("translate_briefing_german.md", markdown=markdown)
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    translated = unwrap_markdown_response(asyncio.run(runner.run(prompt, [])))
    return _normalize_markdown(translated)


def compile_briefing(settings: AppSettings, analyses: list[VideoAnalysis], date_str: str) -> str:
    day_dir = report_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    sections: dict[str, list[VideoAnalysis]] = defaultdict(list)
    for analysis in analyses:
        sections[_section_for_analysis(analysis)].append(analysis)

    market_overview = "No channel data was available for this date yet."
    if analyses:
        market_overview = " ".join(
            analysis.summary for analysis in analyses[:3] if analysis.summary
        ).strip() or market_overview

    structured_payload = {
        "date": date_str,
        "subtitle": settings.site.subtitle,
        "market_overview": market_overview,
        "sections": {
            section: [analysis.model_dump(mode="json") for analysis in items]
            for section, items in sections.items()
        },
    }
    prompt = render_prompt(
        "compile_briefing.md",
        date=date_str,
        title=settings.site.title,
        payload=json.dumps(structured_payload, indent=2),
    )
    workspace = day_dir / "agent-compile"
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    english_markdown = _normalize_markdown(unwrap_markdown_response(asyncio.run(runner.run(prompt, []))))
    german_markdown = _translate_briefing_to_german(settings, english_markdown, date_str)

    write_text(briefing_english_path(date_str), english_markdown)
    write_text(briefing_german_path(date_str), german_markdown)
    write_text(briefing_path(date_str), german_markdown)

    item = BriefingIndexItem(
        date=date_str,
        title=settings.site.title,
        summary=market_overview[:240],
        claim_count=sum(len(analysis.claims) for analysis in analyses),
        updated_at=max((analysis.video.published_at for analysis in analyses), default=None)
        or datetime.now(UTC),
    )
    write_json(briefing_metadata_path(date_str), item.model_dump(mode="json"))
    return german_markdown
