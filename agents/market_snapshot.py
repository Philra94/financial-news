from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import re

from agents.charts import BarComparisonSpec, ChartPoint, render_chart_svg
from agents.config import effective_settings_path
from agents.model_selection import capital_iq_agent_model
from agents.models import AppSettings, MarketSnapshot, MarketSnapshotIndex
from agents.paths import (
    SKILLS_DIR,
    market_snapshot_path,
    report_asset_url,
    report_charts_dir,
    report_day_dir,
)
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import write_json, write_text

logger = logging.getLogger(__name__)

DEFAULT_INDEX_ORDER = [
    "S&P 500",
    "Nasdaq 100",
    "DAX",
    "Euro Stoxx 50",
    "Nikkei 225",
]
EXTERNAL_SOURCE_PATTERN = re.compile(
    r"\b(yahoo|investing(?:\.com)?|marketwatch|google finance|tradingview|reuters|bloomberg|stooq)\b",
    re.IGNORECASE,
)
def _snapshot_skills() -> list[Path]:
    return [
        SKILLS_DIR / "browser" / "SKILL.md",
        SKILLS_DIR / "capital-iq-browser" / "SKILL.md",
        SKILLS_DIR / "capital-iq-browser" / "navigation-notes.md",
    ]


def _parse_json_block(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in market snapshot response")
    return json.loads(text[start : end + 1])


def _normalize_snapshot_payload(payload: dict) -> dict:
    normalized = dict(payload)
    normalized["summary"] = (normalized.get("summary") or "").strip()
    raw_indices = normalized.get("indices")
    if not isinstance(raw_indices, list):
        return normalized

    indices: list[dict] = []
    for item in raw_indices:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        for key in ("label", "symbol", "currency", "as_of", "session_label", "note"):
            normalized_item[key] = (normalized_item.get(key) or "").strip()
        if normalized_item.get("daily_change_percent") is not None and not normalized_item["session_label"]:
            normalized_item["session_label"] = "latest visible session"
        indices.append(normalized_item)
    normalized["indices"] = indices
    return normalized


def _normalize_indices(snapshot: MarketSnapshot) -> MarketSnapshot:
    lookup = {item.label.lower(): item for item in snapshot.indices}
    indices: list[MarketSnapshotIndex] = []
    for label in DEFAULT_INDEX_ORDER:
        item = lookup.get(label.lower())
        if item is None:
            item = MarketSnapshotIndex(label=label, note="Unavailable for this run.")
        indices.append(item)
    snapshot.indices = indices
    return snapshot


def _validate_capital_iq_only(snapshot: MarketSnapshot) -> None:
    text_parts = [snapshot.summary]
    for item in snapshot.indices:
        text_parts.extend([item.note, item.session_label, item.as_of, item.symbol])
        if item.daily_change_percent is not None and not item.session_label.strip():
            raise ValueError(f"Market snapshot index '{item.label}' is missing session context")
    combined = "\n".join(part for part in text_parts if part)
    match = EXTERNAL_SOURCE_PATTERN.search(combined)
    if match:
        raise ValueError(f"External market source leaked into Capital IQ snapshot: {match.group(0)}")


def _snapshot_chart(snapshot: MarketSnapshot, date_str: str) -> tuple[str | None, str | None]:
    available = [item for item in snapshot.indices if item.daily_change_percent is not None]
    if not available:
        return None, None
    chart_dir = report_charts_dir(date_str)
    chart_path = chart_dir / "market-snapshot.svg"
    spec = BarComparisonSpec(
        title="Global equity indices split on the latest session",
        label_suffix="%",
        caption="Source: S&P Capital IQ. Daily percentage move for the latest visible session.",
        highlight="S&P 500",
        data=[
            ChartPoint(label=item.label, value=item.daily_change_percent or 0.0)
            for item in available
        ],
    )
    write_text(chart_path, render_chart_svg(spec))
    return str(chart_path), report_asset_url(date_str, "assets", "charts", chart_path.name)


def _format_level(value: float | None, currency: str) -> str:
    if value is None:
        return ""
    if abs(value) >= 1000:
        formatted = f"{value:,.2f}"
    else:
        formatted = f"{value:.2f}"
    return f" at {formatted} {currency}".rstrip()


def _build_snapshot_markdown(snapshot: MarketSnapshot) -> str:
    lines = ["## MARKET SNAPSHOT", ""]
    for item in snapshot.indices:
        if item.daily_change_percent is None:
            lines.append(f"- `{item.label}`: unavailable.")
            continue
        sign = "+" if item.daily_change_percent > 0 else ""
        suffix = _format_level(item.closing_level, item.currency)
        session = f" ({item.session_label})" if item.session_label else ""
        note = f" {item.note.strip()}" if item.note.strip() else ""
        lines.append(
            f"- `{item.label}`: {sign}{item.daily_change_percent:.2f}%{suffix}{session}.{note}".strip()
        )
    if snapshot.chart_url:
        lines.extend(["", f"![Global equity indices split on the latest session]({snapshot.chart_url})"])
        lines.extend(["", "*Source: S&P Capital IQ. Daily percentage move for the latest visible session.*"])
    if snapshot.summary.strip():
        lines.extend(["", f"- {snapshot.summary.strip()}"])
    return "\n".join(lines).strip()


def _fallback_snapshot(date_str: str, message: str) -> MarketSnapshot:
    snapshot = MarketSnapshot(
        date=date_str,
        summary="",
        indices=[MarketSnapshotIndex(label=label, note="Unavailable for this run.") for label in DEFAULT_INDEX_ORDER],
    )
    snapshot.markdown = "\n".join(
        [
            "## MARKET SNAPSHOT",
            "",
            f"- {message}",
        ]
    )
    return snapshot


def build_market_snapshot(settings: AppSettings, date_str: str) -> MarketSnapshot:
    day_dir = report_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    if not (settings.capital_iq.username.strip() and settings.capital_iq.password.strip()):
        snapshot = _fallback_snapshot(date_str, "Capital IQ credentials were not configured for this run.")
        write_json(market_snapshot_path(date_str), snapshot.model_dump(mode="json"))
        return snapshot

    prompt = render_prompt(
        "market_snapshot.md",
        date=date_str,
        settings_path=effective_settings_path(),
        indices="\n".join(f"- {label}" for label in DEFAULT_INDEX_ORDER),
    )
    workspace = day_dir / "agent-market-snapshot"
    runner = build_runner(
        settings.agent.backend,
        workspace,
        settings.agent.research_timeout_seconds,
        model=capital_iq_agent_model(settings),
    )
    text = ""
    try:
        text = asyncio.run(runner.run(prompt, _snapshot_skills()))
        write_text(day_dir / "market-snapshot.raw.txt", text)
        payload = _normalize_snapshot_payload(_parse_json_block(text))
        snapshot = MarketSnapshot.model_validate({"date": date_str, **payload})
        snapshot = _normalize_indices(snapshot)
        _validate_capital_iq_only(snapshot)
        chart_path, chart_url = _snapshot_chart(snapshot, date_str)
        snapshot.chart_path = chart_path
        snapshot.chart_url = chart_url
        snapshot.markdown = _build_snapshot_markdown(snapshot)
    except Exception:
        logger.exception("Market snapshot generation failed for %s", date_str)
        snapshot = _fallback_snapshot(date_str, "Capital IQ-only market snapshot was unavailable for this run.")

    write_json(market_snapshot_path(date_str), snapshot.model_dump(mode="json"))
    return snapshot
