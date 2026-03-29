from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime

from agents.models import AppSettings, BriefingIndexItem, VideoAnalysis
from agents.paths import briefing_metadata_path, briefing_path, report_day_dir
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import write_json, write_text


def _section_for_analysis(analysis: VideoAnalysis) -> str:
    tags = {tag.lower() for tag in analysis.topic_tags}
    if {"macro", "inflation", "rates"} & tags:
        return "MACRO"
    if {"equities", "earnings", "ai"} & tags:
        return "EQUITIES"
    if {"commodities"} & tags:
        return "COMMODITIES"
    return "WATCHLIST"


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
    markdown = asyncio.run(runner.run(prompt, []))
    if not markdown.strip():
        raise RuntimeError("Compile agent returned empty markdown")
    if not markdown.endswith("\n"):
        markdown += "\n"
    write_text(briefing_path(date_str), markdown)

    item = BriefingIndexItem(
        date=date_str,
        title=settings.site.title,
        summary=market_overview[:240],
        claim_count=sum(len(analysis.claims) for analysis in analyses),
        updated_at=max((analysis.video.published_at for analysis in analyses), default=None)
        or datetime.now(UTC),
    )
    write_json(briefing_metadata_path(date_str), item.model_dump(mode="json"))
    return markdown
