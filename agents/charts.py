from __future__ import annotations

import json
import math
import re
from html import escape
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from agents.storage import write_text


CHART_SPEC_PATTERN = re.compile(r"```chart-spec\s*(.*?)```", re.DOTALL)
SVG_WIDTH = 720
SVG_HEIGHT = 360
INK = "#1d1a16"
ACCENT = "#c0392b"
POSITIVE = "#1f7a4d"
NEGATIVE = "#c0392b"
MUTED = "rgba(29, 26, 22, 0.14)"
CHAR_PX = 7.2  # rough advance width at 13px sans
TITLE_CHAR_PX = 11.5  # rough advance width at 22px


# ---------- Shared primitives ----------


class ChartPoint(BaseModel):
    label: str
    value: float
    annotation: str = ""


class ChartEvent(BaseModel):
    label: str
    at: str  # x-axis label this marker attaches to
    note: str = ""


class ChartRegime(BaseModel):
    label: str
    start: str
    end: str


class WaterfallStep(BaseModel):
    label: str
    value: float


class ScatterPoint(BaseModel):
    label: str
    x: float
    y: float


class _Base(BaseModel):
    title: str
    headline_insight: str = ""
    caption: str = ""
    highlight: str | None = None


# ---------- Spec types ----------


class BarComparisonSpec(_Base):
    type: Literal["bar"] = "bar"
    data: list[ChartPoint] = Field(default_factory=list)
    unit: str = ""
    label_suffix: str = ""


class TimeSeriesSpec(_Base):
    type: Literal["line"] = "line"
    data: list[ChartPoint] = Field(default_factory=list)
    unit: str = ""
    label_suffix: str = ""
    events: list[ChartEvent] = Field(default_factory=list)
    regimes: list[ChartRegime] = Field(default_factory=list)


class WaterfallSpec(_Base):
    type: Literal["waterfall"] = "waterfall"
    start_label: str = "Start"
    start_value: float = 0.0
    steps: list[WaterfallStep] = Field(default_factory=list)
    end_label: str = "End"
    label_suffix: str = ""


class ScatterSpec(_Base):
    type: Literal["scatter"] = "scatter"
    x_axis: str = ""
    y_axis: str = ""
    points: list[ScatterPoint] = Field(default_factory=list)
    quadrant_labels: list[str] = Field(default_factory=list)
    label_suffix: str = ""


class SmallMultiplesSpec(_Base):
    type: Literal["small_multiples"] = "small_multiples"
    metrics: list[str] = Field(default_factory=list)
    peers: list[str] = Field(default_factory=list)
    values: list[list[float]] = Field(default_factory=list)
    label_suffix: str = ""


ChartSpec = Annotated[
    Union[BarComparisonSpec, TimeSeriesSpec, WaterfallSpec, ScatterSpec, SmallMultiplesSpec],
    Field(discriminator="type"),
]
_SPEC_ADAPTER: TypeAdapter[ChartSpec] = TypeAdapter(ChartSpec)


# ---------- Helpers ----------


def _format_value(value: float, suffix: str) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _header_svg(spec: _Base, width: int) -> tuple[str, int]:
    title_lines = _wrap_text(spec.title, max_chars=int((width - 48) / TITLE_CHAR_PX))
    insight_lines = _wrap_text(spec.headline_insight, max_chars=int((width - 48) / CHAR_PX))
    parts: list[str] = []
    y = 30
    for line in title_lines:
        parts.append(
            f'<text x="24" y="{y}" fill="{INK}" font-size="22" font-weight="600">{escape(line)}</text>'
        )
        y += 26
    if insight_lines:
        y += 4
        for line in insight_lines:
            parts.append(
                f'<text x="24" y="{y}" fill="{INK}" fill-opacity="0.78" font-size="13">{escape(line)}</text>'
            )
            y += 18
    return "".join(parts), y + 8


def _footer_svg(spec: _Base, width: int, height: int) -> str:
    if not spec.caption:
        return ""
    caption_lines = _wrap_text(spec.caption, max_chars=int((width - 48) / CHAR_PX))
    parts: list[str] = []
    y = height - 8 - (len(caption_lines) - 1) * 16
    for line in caption_lines:
        parts.append(
            f'<text x="24" y="{y}" fill="{INK}" fill-opacity="0.55" font-size="12">{escape(line)}</text>'
        )
        y += 16
    return "".join(parts)


def _svg_open(width: int, height: int, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<rect width="100%" height="100%" fill="white" />'
    )


# ---------- Renderers ----------


def _render_bar(spec: BarComparisonSpec) -> str:
    points = spec.data[:7]
    width = SVG_WIDTH
    header, header_bottom = _header_svg(spec, width)
    row_height = 40
    chart_x = 220
    chart_width = 420
    half_width = chart_width / 2
    center_x = chart_x + half_width
    max_abs = max((abs(p.value) for p in points), default=1.0) or 1.0
    chart_top = header_bottom + 12
    height = chart_top + len(points) * row_height + 56
    rows: list[str] = []
    rows.append(
        f'<line x1="{center_x:.1f}" y1="{chart_top - 6}" x2="{center_x:.1f}" '
        f'y2="{chart_top + len(points) * row_height + 4}" stroke="{INK}" stroke-opacity="0.2" stroke-width="1" />'
    )
    for index, point in enumerate(points):
        y = chart_top + index * row_height
        bar_size = (abs(point.value) / max_abs) * (half_width - 24)
        is_highlight = bool(spec.highlight and point.label == spec.highlight)
        color = ACCENT if is_highlight else (POSITIVE if point.value >= 0 else NEGATIVE)
        x = center_x if point.value >= 0 else center_x - bar_size
        rows.append(
            f'<text x="24" y="{y + 17}" fill="{INK}" font-size="14" '
            f'font-weight="{600 if is_highlight else 500}">{escape(point.label)}</text>'
        )
        rows.append(
            f'<rect x="{x:.1f}" y="{y + 4:.1f}" width="{max(bar_size, 1):.1f}" height="20" rx="3" '
            f'fill="{color}" fill-opacity="0.92" />'
        )
        value_text = _format_value(point.value, spec.label_suffix or spec.unit)
        if point.value >= 0:
            label_x = center_x + bar_size + 8
            anchor = "start"
        else:
            label_x = center_x - bar_size - 8
            anchor = "end"
        rows.append(
            f'<text x="{label_x:.1f}" y="{y + 18}" fill="{INK}" font-size="13" '
            f'text-anchor="{anchor}">{escape(value_text)}</text>'
        )
        if point.annotation:
            rows.append(
                f'<text x="{width - 24}" y="{y + 18}" fill="{INK}" fill-opacity="0.6" '
                f'font-size="11" text-anchor="end">{escape(point.annotation)}</text>'
            )
    body = (
        _svg_open(width, height, spec.title)
        + header
        + "".join(rows)
        + _footer_svg(spec, width, height)
        + "</svg>"
    )
    return body


def _render_line(spec: TimeSeriesSpec) -> str:
    points = spec.data[:14]
    width = SVG_WIDTH
    header, header_bottom = _header_svg(spec, width)
    left = 64
    chart_top = header_bottom + 16
    chart_width = width - left - 32
    chart_height = 200
    height = chart_top + chart_height + 80
    if not points:
        return _svg_open(width, height, spec.title) + header + "</svg>"
    values = [p.value for p in points]
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        min_value -= 1.0
        max_value += 1.0
    span = max_value - min_value
    step_x = chart_width / max(len(points) - 1, 1)

    def y_for(value: float) -> float:
        return chart_top + chart_height - ((value - min_value) / span) * chart_height

    label_index = {p.label: i for i, p in enumerate(points)}
    regime_svg: list[str] = []
    for regime in spec.regimes:
        si = label_index.get(regime.start)
        ei = label_index.get(regime.end)
        if si is None or ei is None or ei <= si:
            continue
        x_start = left + si * step_x
        x_end = left + ei * step_x
        regime_svg.append(
            f'<rect x="{x_start:.1f}" y="{chart_top}" width="{x_end - x_start:.1f}" '
            f'height="{chart_height}" fill="{ACCENT}" fill-opacity="0.07" />'
        )
        regime_svg.append(
            f'<text x="{(x_start + x_end) / 2:.1f}" y="{chart_top + 14}" fill="{ACCENT}" '
            f'fill-opacity="0.7" font-size="11" text-anchor="middle">{escape(regime.label)}</text>'
        )
    grid: list[str] = []
    for value in (max_value, (max_value + min_value) / 2, min_value):
        y = y_for(value)
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" '
            f'stroke="{INK}" stroke-opacity="0.12" />'
        )
        grid.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" fill="{INK}" fill-opacity="0.6" '
            f'font-size="11" text-anchor="end">{escape(_format_value(value, spec.label_suffix or spec.unit))}</text>'
        )
    polyline = " ".join(
        f"{left + i * step_x:.1f},{y_for(p.value):.1f}" for i, p in enumerate(points)
    )
    dots: list[str] = []
    x_labels: list[str] = []
    label_stride = max(1, len(points) // 8)
    for i, point in enumerate(points):
        x = left + i * step_x
        y = y_for(point.value)
        is_highlight = bool(spec.highlight and point.label == spec.highlight)
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4 if is_highlight else 3}" '
            f'fill="{ACCENT if is_highlight else INK}" />'
        )
        if i % label_stride == 0 or i == len(points) - 1:
            x_labels.append(
                f'<text x="{x:.1f}" y="{chart_top + chart_height + 18}" fill="{INK}" '
                f'fill-opacity="0.6" font-size="11" text-anchor="middle">{escape(point.label)}</text>'
            )
    events: list[str] = []
    for event in spec.events:
        idx = label_index.get(event.at)
        if idx is None:
            continue
        x = left + idx * step_x
        events.append(
            f'<line x1="{x:.1f}" y1="{chart_top}" x2="{x:.1f}" y2="{chart_top + chart_height}" '
            f'stroke="{ACCENT}" stroke-opacity="0.45" stroke-dasharray="3 3" />'
        )
        events.append(
            f'<text x="{x:.1f}" y="{chart_top - 4}" fill="{ACCENT}" font-size="11" '
            f'text-anchor="middle">{escape(event.label)}</text>'
        )
    return (
        _svg_open(width, height, spec.title)
        + header
        + "".join(regime_svg)
        + "".join(grid)
        + f'<polyline fill="none" stroke="{INK}" stroke-width="2" points="{polyline}" />'
        + "".join(dots)
        + "".join(events)
        + "".join(x_labels)
        + _footer_svg(spec, width, height)
        + "</svg>"
    )


def _render_waterfall(spec: WaterfallSpec) -> str:
    width = SVG_WIDTH
    header, header_bottom = _header_svg(spec, width)
    steps = spec.steps[:8]
    bars = len(steps) + 2  # start + steps + end
    left = 56
    chart_top = header_bottom + 24
    chart_width = width - left - 32
    chart_height = 220
    height = chart_top + chart_height + 80
    bar_slot = chart_width / bars
    bar_width = bar_slot * 0.6

    cumulative = [spec.start_value]
    for step in steps:
        cumulative.append(cumulative[-1] + step.value)
    end_value = cumulative[-1]
    all_values = [spec.start_value, end_value, *cumulative]
    min_v = min(all_values + [0.0])
    max_v = max(all_values + [0.0])
    if math.isclose(min_v, max_v):
        min_v -= 1.0
        max_v += 1.0
    span = max_v - min_v

    def y_for(value: float) -> float:
        return chart_top + chart_height - ((value - min_v) / span) * chart_height

    elements: list[str] = []
    zero_y = y_for(0.0)
    elements.append(
        f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left + chart_width}" y2="{zero_y:.1f}" '
        f'stroke="{INK}" stroke-opacity="0.25" />'
    )

    def draw_pillar(idx: int, label: str, top_value: float, bottom_value: float, color: str, value_label: str) -> None:
        x = left + idx * bar_slot + (bar_slot - bar_width) / 2
        y_top = y_for(max(top_value, bottom_value))
        y_bot = y_for(min(top_value, bottom_value))
        bar_h = max(y_bot - y_top, 2)
        elements.append(
            f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" '
            f'rx="2" fill="{color}" fill-opacity="0.92" />'
        )
        elements.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{chart_top + chart_height + 18}" fill="{INK}" '
            f'fill-opacity="0.7" font-size="11" text-anchor="middle">{escape(label)}</text>'
        )
        elements.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{y_top - 4:.1f}" fill="{INK}" font-size="12" '
            f'text-anchor="middle">{escape(value_label)}</text>'
        )

    draw_pillar(
        0,
        spec.start_label,
        spec.start_value,
        0.0,
        INK,
        _format_value(spec.start_value, spec.label_suffix),
    )
    prev_top = spec.start_value
    for i, step in enumerate(steps, start=1):
        new_top = prev_top + step.value
        color = POSITIVE if step.value >= 0 else NEGATIVE
        draw_pillar(i, step.label, new_top, prev_top, color, _format_value(step.value, spec.label_suffix))
        x_a = left + (i - 1) * bar_slot + (bar_slot + bar_width) / 2
        x_b = left + i * bar_slot + (bar_slot - bar_width) / 2
        elements.append(
            f'<line x1="{x_a:.1f}" y1="{y_for(prev_top):.1f}" x2="{x_b:.1f}" '
            f'y2="{y_for(prev_top):.1f}" stroke="{INK}" stroke-opacity="0.3" stroke-dasharray="2 3" />'
        )
        prev_top = new_top
    draw_pillar(
        len(steps) + 1,
        spec.end_label,
        end_value,
        0.0,
        ACCENT,
        _format_value(end_value, spec.label_suffix),
    )

    return (
        _svg_open(width, height, spec.title)
        + header
        + "".join(elements)
        + _footer_svg(spec, width, height)
        + "</svg>"
    )


def _render_scatter(spec: ScatterSpec) -> str:
    width = SVG_WIDTH
    header, header_bottom = _header_svg(spec, width)
    points = spec.points[:18]
    left = 70
    chart_top = header_bottom + 24
    chart_width = width - left - 40
    chart_height = 240
    height = chart_top + chart_height + 80
    if not points:
        return _svg_open(width, height, spec.title) + header + "</svg>"

    xs = [p.x for p in points]
    ys = [p.y for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if math.isclose(x_min, x_max):
        x_min -= 1.0
        x_max += 1.0
    if math.isclose(y_min, y_max):
        y_min -= 1.0
        y_max += 1.0
    x_pad = (x_max - x_min) * 0.08
    y_pad = (y_max - y_min) * 0.08
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def x_for(value: float) -> float:
        return left + ((value - x_min) / (x_max - x_min)) * chart_width

    def y_for(value: float) -> float:
        return chart_top + chart_height - ((value - y_min) / (y_max - y_min)) * chart_height

    elements: list[str] = []
    elements.append(
        f'<rect x="{left}" y="{chart_top}" width="{chart_width}" height="{chart_height}" '
        f'fill="none" stroke="{INK}" stroke-opacity="0.18" />'
    )
    mid_x = (x_min + x_max) / 2
    mid_y = (y_min + y_max) / 2
    elements.append(
        f'<line x1="{x_for(mid_x):.1f}" y1="{chart_top}" x2="{x_for(mid_x):.1f}" '
        f'y2="{chart_top + chart_height}" stroke="{INK}" stroke-opacity="0.12" stroke-dasharray="2 4" />'
    )
    elements.append(
        f'<line x1="{left}" y1="{y_for(mid_y):.1f}" x2="{left + chart_width}" '
        f'y2="{y_for(mid_y):.1f}" stroke="{INK}" stroke-opacity="0.12" stroke-dasharray="2 4" />'
    )
    if len(spec.quadrant_labels) >= 4:
        tr, tl, bl, br = spec.quadrant_labels[:4]
        elements.append(
            f'<text x="{left + chart_width - 8:.1f}" y="{chart_top + 16}" fill="{INK}" '
            f'fill-opacity="0.45" font-size="11" text-anchor="end">{escape(tr)}</text>'
        )
        elements.append(
            f'<text x="{left + 8:.1f}" y="{chart_top + 16}" fill="{INK}" '
            f'fill-opacity="0.45" font-size="11">{escape(tl)}</text>'
        )
        elements.append(
            f'<text x="{left + 8:.1f}" y="{chart_top + chart_height - 8:.1f}" fill="{INK}" '
            f'fill-opacity="0.45" font-size="11">{escape(bl)}</text>'
        )
        elements.append(
            f'<text x="{left + chart_width - 8:.1f}" y="{chart_top + chart_height - 8:.1f}" '
            f'fill="{INK}" fill-opacity="0.45" font-size="11" text-anchor="end">{escape(br)}</text>'
        )
    for point in points:
        cx = x_for(point.x)
        cy = y_for(point.y)
        is_highlight = bool(spec.highlight and point.label == spec.highlight)
        elements.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{6 if is_highlight else 4}" '
            f'fill="{ACCENT if is_highlight else INK}" fill-opacity="{0.95 if is_highlight else 0.7}" />'
        )
        elements.append(
            f'<text x="{cx + 8:.1f}" y="{cy + 4:.1f}" fill="{INK}" font-size="11" '
            f'font-weight="{600 if is_highlight else 400}">{escape(point.label)}</text>'
        )
    if spec.x_axis:
        elements.append(
            f'<text x="{left + chart_width / 2:.1f}" y="{chart_top + chart_height + 32}" '
            f'fill="{INK}" fill-opacity="0.7" font-size="12" text-anchor="middle">{escape(spec.x_axis)}</text>'
        )
    if spec.y_axis:
        cx = 18
        cy = chart_top + chart_height / 2
        elements.append(
            f'<text x="{cx}" y="{cy}" fill="{INK}" fill-opacity="0.7" font-size="12" '
            f'transform="rotate(-90 {cx} {cy})" text-anchor="middle">{escape(spec.y_axis)}</text>'
        )
    return (
        _svg_open(width, height, spec.title)
        + header
        + "".join(elements)
        + _footer_svg(spec, width, height)
        + "</svg>"
    )


def _render_small_multiples(spec: SmallMultiplesSpec) -> str:
    width = SVG_WIDTH
    header, header_bottom = _header_svg(spec, width)
    metrics = spec.metrics[:6]
    peers = spec.peers[:6]
    cols = min(3, max(1, len(metrics)))
    rows = max(1, math.ceil(len(metrics) / cols))
    cell_w = (width - 48) / cols
    cell_h = 130
    chart_top = header_bottom + 16
    height = chart_top + rows * cell_h + 70
    elements: list[str] = []
    for m_idx, metric in enumerate(metrics):
        row = m_idx // cols
        col = m_idx % cols
        x0 = 24 + col * cell_w
        y0 = chart_top + row * cell_h
        elements.append(
            f'<text x="{x0 + 4:.1f}" y="{y0 + 16}" fill="{INK}" font-size="13" '
            f'font-weight="600">{escape(metric)}</text>'
        )
        try:
            metric_values = spec.values[m_idx][: len(peers)]
        except IndexError:
            metric_values = []
        if not metric_values:
            continue
        max_abs = max((abs(v) for v in metric_values), default=1.0) or 1.0
        bar_top = y0 + 28
        bar_area = cell_h - 50
        row_h = bar_area / max(len(peers), 1)
        for p_idx, peer in enumerate(peers[: len(metric_values)]):
            value = metric_values[p_idx]
            y = bar_top + p_idx * row_h
            bar_len = (abs(value) / max_abs) * (cell_w - 80)
            is_highlight = bool(spec.highlight and peer == spec.highlight)
            color = ACCENT if is_highlight else (POSITIVE if value >= 0 else NEGATIVE)
            elements.append(
                f'<text x="{x0 + 4:.1f}" y="{y + 11}" fill="{INK}" fill-opacity="0.78" '
                f'font-size="11" font-weight="{600 if is_highlight else 400}">{escape(peer)}</text>'
            )
            elements.append(
                f'<rect x="{x0 + 56:.1f}" y="{y + 2:.1f}" width="{max(bar_len, 1):.1f}" '
                f'height="{max(row_h - 6, 4):.1f}" rx="2" fill="{color}" fill-opacity="0.9" />'
            )
            elements.append(
                f'<text x="{x0 + 60 + bar_len:.1f}" y="{y + 11}" fill="{INK}" font-size="10" '
                f'fill-opacity="0.7">{escape(_format_value(value, spec.label_suffix))}</text>'
            )
    return (
        _svg_open(width, height, spec.title)
        + header
        + "".join(elements)
        + _footer_svg(spec, width, height)
        + "</svg>"
    )


_RENDERERS: dict[str, callable] = {
    "bar": _render_bar,
    "line": _render_line,
    "waterfall": _render_waterfall,
    "scatter": _render_scatter,
    "small_multiples": _render_small_multiples,
}


# ---------- Validation ----------


def validate_overflow(spec: ChartSpec) -> list[str]:
    issues: list[str] = []
    width = SVG_WIDTH
    title_chars = int((width - 48) / TITLE_CHAR_PX)
    if any(len(line) > title_chars for line in [spec.title]):
        issues.append("title is too long for the chart width and will wrap or clip")
    if isinstance(spec, BarComparisonSpec):
        if not spec.data:
            issues.append("bar chart has no datapoints")
        if len(spec.data) > 7:
            issues.append("bar chart has more than 7 points; trim to the most relevant")
        labels = [p.label for p in spec.data]
        if len(set(labels)) != len(labels):
            issues.append("duplicate labels in bar chart")
        if any(len(p.label) > 18 for p in spec.data):
            issues.append("a bar label exceeds 18 chars and will overflow the label gutter")
        values = [p.value for p in spec.data]
        if values and math.isclose(min(values), max(values)):
            issues.append("bar chart values collapse to a flat line; pick a sharper comparison")
    elif isinstance(spec, TimeSeriesSpec):
        if not spec.data:
            issues.append("time series has no datapoints")
        if len(spec.data) > 14:
            issues.append("time series exceeds 14 points; thin out the series")
        values = [p.value for p in spec.data]
        if values and math.isclose(min(values), max(values)):
            issues.append("time series is flat; either drop the chart or pick a richer window")
    elif isinstance(spec, WaterfallSpec):
        if not spec.steps:
            issues.append("waterfall has no steps")
        if len(spec.steps) > 8:
            issues.append("waterfall has more than 8 steps; consolidate")
        if any(len(s.label) > 14 for s in spec.steps):
            issues.append("a waterfall step label exceeds 14 chars and will collide")
    elif isinstance(spec, ScatterSpec):
        if len(spec.points) < 3:
            issues.append("scatter needs at least 3 points to be useful")
        if len(spec.points) > 18:
            issues.append("scatter exceeds 18 points; trim to the relevant universe")
        labels = [p.label for p in spec.points]
        if len(set(labels)) != len(labels):
            issues.append("duplicate labels in scatter")
    elif isinstance(spec, SmallMultiplesSpec):
        if not spec.metrics or not spec.peers:
            issues.append("small_multiples needs both metrics and peers")
        if len(spec.metrics) > 6:
            issues.append("small_multiples has more than 6 metrics; pick the most decisive")
        if len(spec.peers) > 6:
            issues.append("small_multiples has more than 6 peers")
        if len(spec.values) != len(spec.metrics):
            issues.append("values matrix length does not match metrics list")
        for row in spec.values:
            if len(row) != len(spec.peers):
                issues.append("values row length does not match peers list")
                break
    return issues


# ---------- Public API ----------


def render_chart_svg(spec: ChartSpec) -> str:
    renderer = _RENDERERS.get(spec.type)
    if renderer is None:
        raise ValueError(f"Unsupported chart type: {spec.type}")
    return renderer(spec)


def parse_chart_spec(block: str) -> ChartSpec:
    payload = json.loads(block)
    return _SPEC_ADAPTER.validate_python(payload)


def materialize_chart_markdown(
    markdown: str,
    asset_dir: Path,
    asset_url_prefix: str,
    slug_prefix: str,
    *,
    review: callable | None = None,
) -> str:
    if "```chart-spec" not in markdown:
        return markdown

    parts: list[str] = []
    cursor = 0
    chart_index = 0
    for match in CHART_SPEC_PATTERN.finditer(markdown):
        parts.append(markdown[cursor : match.start()])
        cursor = match.end()
        chart_index += 1
        try:
            spec = parse_chart_spec(match.group(1).strip())
        except Exception:
            parts.append(match.group(0))
            continue
        if review is not None:
            try:
                spec = review(spec)
            except Exception:
                pass
        try:
            svg = render_chart_svg(spec)
        except Exception:
            parts.append(match.group(0))
            continue
        filename = f"{slug_prefix}-{chart_index:02d}.svg"
        write_text(asset_dir / filename, svg)
        asset_url = f"{asset_url_prefix.rstrip('/')}/{filename}"
        replacement = f"![{spec.title}]({asset_url})"
        if spec.caption.strip():
            replacement += f"\n\n*{spec.caption.strip()}*"
        parts.append(replacement)
    parts.append(markdown[cursor:])
    return "".join(parts).strip()
