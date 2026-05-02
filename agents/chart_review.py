from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable, Protocol

from pydantic import BaseModel, Field

from agents.charts import (
    ChartSpec,
    parse_chart_spec,
    render_chart_svg,
    validate_overflow,
)
from agents.prompts_loader import render_prompt
from agents.runner import AgentRunner
from agents.storage import write_text


logger = logging.getLogger(__name__)


class CritiqueResult(BaseModel):
    verdict: str = "ok"
    issues: list[str] = Field(default_factory=list)
    replacement_spec: ChartSpec | None = None


class ChartCritic(Protocol):
    def critique(self, spec: ChartSpec, svg: str, precheck_issues: list[str]) -> CritiqueResult:
        ...


def _rasterize_svg(svg: str) -> bytes | None:
    try:
        import cairosvg  # type: ignore
    except Exception:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=720)
    except Exception:
        logger.exception("Failed to rasterize SVG for chart review")
        return None


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_critique(raw: str) -> CritiqueResult:
    if not raw.strip():
        return CritiqueResult()
    match = _FENCE_RE.search(raw)
    payload = match.group(1).strip() if match else raw.strip()
    try:
        data = json.loads(payload)
    except Exception:
        return CritiqueResult()
    return CritiqueResult.model_validate(data)


class RunnerChartCritic:
    """Vision critic that delegates to an AgentRunner (e.g. Kimi CLI)."""

    def __init__(
        self,
        runner_factory: Callable[[Path], AgentRunner],
        workspace_root: Path,
        slug_prefix: str = "chart-review",
    ) -> None:
        self._runner_factory = runner_factory
        self._workspace_root = workspace_root
        self._slug_prefix = slug_prefix
        self._counter = 0

    def critique(self, spec: ChartSpec, svg: str, precheck_issues: list[str]) -> CritiqueResult:
        png = _rasterize_svg(svg)
        if png is None:
            # No vision capability available — surface only the pre-check signal.
            return CritiqueResult(
                verdict="revise" if precheck_issues else "ok",
                issues=precheck_issues,
            )
        self._counter += 1
        workspace = self._workspace_root / f"{self._slug_prefix}-{self._counter:02d}"
        workspace.mkdir(parents=True, exist_ok=True)
        png_path = workspace / "chart.png"
        png_path.write_bytes(png)
        write_text(workspace / "chart.svg", svg)
        prompt = render_prompt(
            "review_chart.md",
            png_path=str(png_path),
            spec_json=spec.model_dump_json(indent=2),
            precheck_issues="\n".join(f"- {issue}" for issue in precheck_issues) or "- (none)",
        )
        runner = self._runner_factory(workspace)
        try:
            import asyncio

            raw = asyncio.run(runner.run(prompt, []))
        except Exception:
            logger.exception("Chart vision critic call failed; keeping spec as-is")
            return CritiqueResult(verdict="ok", issues=precheck_issues)
        return _parse_critique(raw)


def review_chart(
    spec: ChartSpec,
    critic: ChartCritic,
    *,
    max_rounds: int = 2,
) -> ChartSpec:
    """Render → check → critique → revise loop. Returns the best spec we can defend."""
    current = spec
    for _ in range(max_rounds + 1):
        try:
            svg = render_chart_svg(current)
        except Exception:
            logger.exception("Chart render failed during review")
            return current
        precheck_issues = validate_overflow(current)
        result = critic.critique(current, svg, precheck_issues)
        if result.verdict == "ok" and not precheck_issues:
            return current
        if result.replacement_spec is None:
            return current
        current = result.replacement_spec
    return current
