Compile a concise morning financial briefing from the structured inputs below.

Requirements:
- Neutral tone.
- Quote opinions directly and attribute them.
- Represent claims as the marker syntax `[[claim:CLAIM_ID|CLAIM_TEXT]]`.
- Prefer clean sections such as MARKET OVERVIEW, EQUITIES, MACRO, and WATCHLIST.
- When an item includes `sub_analyses`, weave the useful findings into the relevant section instead of dropping them.
- Give special weight to stock-focused `sub_analyses` in equities coverage. Surface concrete stock numbers such as price move, market cap, enterprise value, shares outstanding, and valuation multiples when they sharpen the analysis.
- If several equities items contain strong stock-focused `sub_analyses`, create a dedicated stock-focused subsection or clearly stock-led paragraphs inside `EQUITIES`.
- Preserve useful markdown from `sub_analyses` when it reads cleanly. If a sub-analysis contains a graph idea rather than a rendered graph, turn it into a short data-rich sentence instead of exposing internal planning language.
- Output markdown only.

Date: {{date}}
Site title: {{title}}
Structured input:
{{payload}}
