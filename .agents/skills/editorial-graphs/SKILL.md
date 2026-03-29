---
name: editorial-graphs
description: Designs minimalist, markdown-embeddable charts for this financial news app. Use when creating graphs, chart images, visual data callouts, or report graphics for briefings and claim research that should match the app's editorial style.
---

# Editorial Graphs

Create charts only when the visual makes the point faster than a sentence or a compact table.

If the message is obvious in one line of prose, do not use a graph.

## Style Goal

Match the tone of the current app:

- restrained
- editorial
- information-dense but calm
- similar to The Economist rather than a dashboard

The chart should feel like part of the article, not a separate analytics product.

## Decision Rule

Use a graph only when at least one of these is true:

- the reader needs to compare change over time
- the reader needs to compare a small number of categories
- the magnitude or inflection point is the story
- a single highlighted datapoint carries the conclusion

Do not use a graph when:

- there are too many series
- the data quality is weak or mixed-frequency
- the takeaway depends on long explanation
- a two-row table or one sentence is clearer

## Preferred Chart Types

Default to these, in order:

1. Single-series line chart for time trends
2. Simple column chart for small category comparisons
3. Horizontal bar chart for ranked comparisons
4. Tiny annotated sparkline for a short inline visual

Avoid by default:

- pie charts
- stacked area charts
- dual-axis charts
- heatmaps
- radar charts
- 3D effects

## Visual Rules

Keep charts sparse and legible.

- Use one neutral ink color for the main data series.
- Use one accent color only for the most important point, bar, period, or comparison.
- Do not use more than one accent unless the comparison truly requires it.
- Prefer direct labels over legends when possible.
- Use thin rules and subtle gridlines.
- Remove any non-essential border, shadow, gradient, or decoration.
- Leave enough whitespace so the chart breathes inside the article.

## Palette

Base the chart on the app's current editorial colors:

- ink: `#1d1a16`
- accent: `#c0392b`
- muted rule: `rgba(29, 26, 22, 0.14)`
- light background: white or transparent

Color usage:

- neutral series, labels, and axes should stay close to `#1d1a16`
- highlights and key annotations may use `#c0392b`
- secondary reference lines should use a muted gray-brown, not a second bright color

## Typography And Labeling

- Keep titles short and declarative.
- The title should state the finding, not just the subject.
- Use sentence case for captions and notes.
- Axis labels should be minimal.
- Prefer a few meaningful ticks over dense scales.
- Always include units when relevant.
- Add source and date in a small caption or note.

Good title examples:

- `Euro area inflation has eased, but services remain sticky`
- `Nvidia still dominates revenue growth among mega-cap AI names`

Weak title examples:

- `Inflation chart`
- `Revenue by company`

## Embedding In Markdown

The current app renders standard markdown well, including markdown images. It does not rely on raw HTML chart embeds.

Preferred embedding pattern:

```md
![Euro area inflation has eased, but services remain sticky](/assets/charts/euro-area-inflation-mar-2026.svg)

*Source: Eurostat. Monthly CPI, year-over-year. Highlight shows latest reading.*
```

If a chart must be added to a report:

1. Create a static image asset, preferably SVG.
2. Reference it with normal markdown image syntax.
3. Use a served URL path, not a local filesystem path.
4. If no served asset path exists yet, add one before relying on the chart.

Prefer SVG for crisp editorial charts. Use PNG only when the rendering pipeline makes SVG impractical.

## Data Reduction

Before charting, simplify the story:

- limit to one key comparison
- trim the time window to the period that matters
- cap category count to roughly 3 to 7 items
- remove redundant precision
- annotate the one datapoint the reader should remember

If multiple insights compete, split them into separate small charts or choose prose instead.

## Annotation Rules

Annotations should do the explanatory work:

- highlight the latest point, peak, trough, or break in trend
- annotate only the datapoints needed to support the article's claim
- keep annotation text short
- place labels close to the data instead of using a distant legend

## Output Checklist

Before finalizing a chart, verify:

- the title communicates the takeaway
- the graphic works in monochrome plus one accent
- the reader can understand it in under five seconds
- the source and units are present
- the article still reads well if the chart is removed

## Examples

See [examples.md](examples.md) for recommended chart shapes and markdown patterns.
