from pathlib import Path

import pytest

from agents.charts import (
    BarComparisonSpec,
    ChartPoint,
    ScatterPoint,
    ScatterSpec,
    SmallMultiplesSpec,
    TimeSeriesSpec,
    WaterfallSpec,
    WaterfallStep,
    materialize_chart_markdown,
    parse_chart_spec,
    render_chart_svg,
    validate_overflow,
)
from agents.chart_review import CritiqueResult, review_chart


def _bar(points: list[tuple[str, float]], **kwargs) -> BarComparisonSpec:
    return BarComparisonSpec(
        title=kwargs.pop("title", "Title"),
        data=[ChartPoint(label=label, value=value) for label, value in points],
        **kwargs,
    )


def test_parse_dispatches_on_type_field() -> None:
    block = """
    {"type": "scatter", "title": "x", "points": [
        {"label": "A", "x": 1, "y": 2},
        {"label": "B", "x": 3, "y": 4},
        {"label": "C", "x": 5, "y": 6}
    ]}
    """
    spec = parse_chart_spec(block)
    assert isinstance(spec, ScatterSpec)
    assert len(spec.points) == 3


@pytest.mark.parametrize(
    "spec",
    [
        _bar([("AAPL", 1.2), ("MSFT", -0.4)]),
        TimeSeriesSpec(title="Yields", data=[ChartPoint(label="d1", value=4.0), ChartPoint(label="d2", value=4.4)]),
        WaterfallSpec(title="Bridge", start_value=10, steps=[WaterfallStep(label="A", value=2), WaterfallStep(label="B", value=-1)]),
        ScatterSpec(
            title="Growth vs Valuation",
            points=[
                ScatterPoint(label="A", x=1, y=2),
                ScatterPoint(label="B", x=3, y=4),
                ScatterPoint(label="C", x=5, y=6),
            ],
            quadrant_labels=["TR", "TL", "BL", "BR"],
        ),
        SmallMultiplesSpec(
            title="Peers",
            metrics=["EV/Sales", "FCF margin"],
            peers=["A", "B", "C"],
            values=[[1, 2, 3], [4, 5, 6]],
        ),
    ],
)
def test_render_does_not_raise(spec) -> None:
    svg = render_chart_svg(spec)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_validate_overflow_flags_too_many_points() -> None:
    spec = _bar([(f"L{i}", float(i)) for i in range(12)])
    issues = validate_overflow(spec)
    assert any("more than 7" in issue for issue in issues)


def test_validate_overflow_flags_long_label() -> None:
    spec = _bar([("WAY-TOO-LONG-LABEL-FOR-A-BAR", 1.0), ("OK", 2.0)])
    issues = validate_overflow(spec)
    assert any("18 chars" in issue for issue in issues)


def test_validate_overflow_flags_flat_values() -> None:
    spec = _bar([("A", 1.0), ("B", 1.0), ("C", 1.0)])
    issues = validate_overflow(spec)
    assert any("flat" in issue for issue in issues)


def test_validate_overflow_flags_duplicate_labels() -> None:
    spec = _bar([("A", 1.0), ("A", 2.0)])
    issues = validate_overflow(spec)
    assert any("duplicate" in issue for issue in issues)


class _OkCritic:
    def critique(self, spec, svg, issues):
        return CritiqueResult(verdict="ok")


class _ReplaceOnceCritic:
    def __init__(self, replacement):
        self.replacement = replacement
        self.calls = 0

    def critique(self, spec, svg, issues):
        self.calls += 1
        if self.calls == 1:
            return CritiqueResult(verdict="revise", replacement_spec=self.replacement)
        return CritiqueResult(verdict="ok")


def test_review_chart_short_circuits_on_ok() -> None:
    spec = _bar([("AAPL", 1.0), ("MSFT", -2.0)])
    result = review_chart(spec, _OkCritic(), max_rounds=2)
    assert result is spec


def test_review_chart_applies_replacement() -> None:
    bad = _bar([(f"L{i}", float(i)) for i in range(12)])
    good = _bar([("AAPL", 1.0), ("MSFT", 2.0)])
    critic = _ReplaceOnceCritic(replacement=good)
    result = review_chart(bad, critic, max_rounds=2)
    assert result is good


def test_materialize_chart_markdown_runs_review_and_writes_svg(tmp_path: Path) -> None:
    markdown = """## Heading

```chart-spec
{"type": "bar", "title": "Peers", "data": [{"label": "A", "value": 1.0}, {"label": "B", "value": -0.5}]}
```

trailing
"""

    seen: list = []

    def review(spec):
        seen.append(spec)
        return spec

    out = materialize_chart_markdown(
        markdown,
        tmp_path,
        "/report-assets/2026-05-02/assets/charts",
        "vid-01-slug",
        review=review,
    )
    assert seen, "review callback should be invoked"
    assert "![Peers](/report-assets/2026-05-02/assets/charts/vid-01-slug-01.svg)" in out
    written = list(tmp_path.glob("*.svg"))
    assert len(written) == 1


def test_materialize_chart_markdown_keeps_block_on_invalid_spec(tmp_path: Path) -> None:
    markdown = "```chart-spec\n{not json\n```"
    out = materialize_chart_markdown(markdown, tmp_path, "/x", "slug")
    assert "```chart-spec" in out
