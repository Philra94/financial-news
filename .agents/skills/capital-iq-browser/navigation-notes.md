# Capital IQ Navigation Notes

Use this file to record reliable routes through the Capital IQ web client.

Update it only when you have actually verified a route during a run.

## Entry Point

- Sustainability home:
  `https://www.capitaliq.spglobal.com/web/client?auth=inherit#sustainability/sustainabilityHome`

## Known Notes

- Start with `browser-use state` before clicking anything.
- Confirm whether the user needs sustainability data, company financials, news, or general research before navigating deeper.
- Record menu names exactly as shown in the UI when they help future navigation.

## Route Log

Add short notes in this format:

```md
### YYYY-MM-DD
- Goal: find latest company sustainability metrics
- Working route: Home -> Sustainability -> [module name] -> [subsection]
- Search method: [search box, ticker lookup, menu path]
- Notes: [quirks, delays, labels, blockers]
```

### 2026-03-31
- Goal: open a public company corporate profile and capture current valuation data
- Working route: Sustainability Home -> top navigation `Search` -> type company name or ticker -> select `Microsoft Corporation (NASDAQGS:MSFT) > Corporate Profile`
- Search method: global search box in the top header
- Notes: login is a two-step flow (`Email address` -> `Next` -> `Password` -> `Sign In`). The corporate profile page exposes usable valuation fields directly in `Market Data` and `Multiples`, including `Market Cap. ($M)`, `Total Enterprise Value ($M)`, and trading multiples. Intraday exchange data is delayed.
