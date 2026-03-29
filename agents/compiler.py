from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from agents.models import AppSettings, BriefingIndexItem, VideoAnalysis
from agents.paths import briefing_metadata_path, briefing_path, report_day_dir
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

    lines = [
        f"# {settings.site.title}",
        "",
        settings.site.subtitle,
        "",
        f"*{date_str}*",
        "",
        "---",
        "",
    ]

    market_overview = "No channel data was available for this date yet."
    if analyses:
        market_overview = " ".join(
            analysis.summary for analysis in analyses[:3] if analysis.summary
        ).strip() or market_overview
    lines.extend(["## MARKET OVERVIEW", "", market_overview, ""])

    for section_name in ("EQUITIES", "MACRO", "COMMODITIES", "WATCHLIST"):
        items = sections.get(section_name, [])
        if not items:
            continue
        lines.extend([f"## {section_name}", ""])
        for analysis in items:
            lines.extend([f"### {analysis.video.title}", "", analysis.summary, ""])
            for opinion in analysis.opinions:
                lines.extend(
                    [
                        f"> \"{opinion.quote}\"",
                        f"> *{opinion.speaker}, [{analysis.video.channel_name}]({analysis.video.url})*",
                        "",
                    ]
                )
            for claim in analysis.claims:
                lines.extend([f"[[claim:{claim.id}|{claim.text}]]", ""])
            lines.extend([f"[Source video]({analysis.video.url})", ""])

    markdown = "\n".join(lines).strip() + "\n"
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
