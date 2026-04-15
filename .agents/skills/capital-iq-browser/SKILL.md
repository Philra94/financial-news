---
name: capital-iq-browser
description: Uses browser automation to access S&P Capital IQ pages with credentials from project settings or local overrides, then extract financial, news, sustainability, or research data. Use when the task requires navigating Capital IQ, especially for data lookup, company research, news discovery, or evidence gathering from the Capital IQ web client.
---

# Capital IQ Browser

Use this skill when information is best retrieved from the S&P Capital IQ web client rather than public search results.

Primary entry page:

- `https://www.capitaliq.spglobal.com/web/client?auth=inherit#sustainability/sustainabilityHome`

## Goals

- access Capital IQ with browser automation
- use saved credentials from settings where available
- navigate efficiently to the relevant page or module
- extract only the information needed for the research task
- leave better navigation notes for the next agent when possible

## Credential Rules

- Never hardcode credentials into code, prompts, or committed files.
- First check project settings and local overrides for stored Capital IQ credentials.
- Prefer local, untracked settings files for secrets.
- If credentials are not present, ask the user instead of guessing.

Suggested places to check:

- `config/settings.local.json`
- `config/settings.json`
- other repo-local untracked settings the user explicitly points to

Look for a dedicated `capital_iq` or similar settings section first. If no dedicated section exists, use only the settings path the user has provided for this run.

## Browser Workflow

Use the existing browser automation skill and default to `browser-use`.

1. Open the Capital IQ entry URL.
2. Inspect page state before interacting.
3. If login is required, fill only the required fields using credentials from settings.
4. Confirm successful login by checking the page title, URL, or visible navigation labels.
5. Navigate to the smallest section that answers the user request.
6. Extract the result with source context, dates, and labels.

Useful commands:

```bash
browser-use open "https://www.capitaliq.spglobal.com/web/client?auth=inherit#sustainability/sustainabilityHome"
browser-use state
browser-use input <index> "value"
browser-use click <index>
browser-use get text <index>
browser-use screenshot
```

## Extraction Priorities

When using Capital IQ for research, prefer:

- primary company data
- structured financial metrics
- news items visible in the platform
- sustainability or ESG data when relevant
- timestamps, reporting periods, and units

Always capture:

- what page or module the result came from
- the company, instrument, or topic searched
- the date or reporting period
- units and currency when shown
- whether the value is historical, current, consensus, or estimated

## Navigation Strategy

Start broad, then narrow quickly:

1. confirm whether the request is about a company, market theme, document, news item, or sustainability topic
2. use the closest Capital IQ section for that task
3. avoid wandering across unrelated tabs once the needed module is found
4. if a route is slow or confusing, note a better path for next time

Before improvising, read [navigation-notes.md](navigation-notes.md).

## Index Snapshot Workflow

When the task is a top-of-briefing market snapshot:

- stay inside Capital IQ for the entire run
- prefer the top-header global search before broader browsing
- try canonical index symbols or names first:
  - `S&P 500` -> `SPX`
  - `Nasdaq 100` -> `NDX`
  - `DAX` -> `DAX`
  - `Euro Stoxx 50` -> `SX5E`
  - `Nikkei 225` -> `NKY`
- prefer a clean quote or market-data style page for the index itself
- capture the latest visible daily move, level, currency, and session label from Capital IQ only
- if Capital IQ does not expose a clean result after reasonable effort, mark that index unavailable instead of supplementing with public sites or APIs
- do not mention Yahoo Finance, Investing.com, Google Finance, Reuters, Bloomberg, or similar sources in the final result

## Output Guidance

Return concise, source-aware notes.

- distinguish platform facts from your interpretation
- state where in Capital IQ the information was found
- include dates and labels exactly when they matter
- if a page is ambiguous or gated, say so
- if Capital IQ does not provide a clear answer, mark the item unavailable and say so plainly instead of supplementing with other sources

## Safety And Restraint

- Do not change account settings unless the user asked.
- Do not download large exports unless they are necessary.
- Avoid broad scraping; extract only what supports the current task.
- Close or leave the session in a clean state when done.

## Post-Run Improvement

After each run, briefly review whether this skill or the navigation notes can be improved for the next agent.

The agent may update the documented Capital IQ paths in this skill and in `navigation-notes.md` when it has actually verified a faster or more reliable route during the run.

If you discovered:

- a faster route
- a renamed menu
- a reliable landing page
- a better search pattern
- a login quirk

then update [navigation-notes.md](navigation-notes.md), and refine this `SKILL.md` if the improvement is general, verified, and clearly better for the next run.

If you are unsure what to improve, or do not have enough confidence, it is fine to skip this step.

## Additional Resources

- For route memory and discovered navigation patterns, see [navigation-notes.md](navigation-notes.md)
