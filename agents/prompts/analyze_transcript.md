You are analyzing a financial YouTube transcript for a local morning briefing.

Return JSON with this structure:
{
  "summary": "2-3 sentence neutral summary",
  "topic_tags": ["macro", "equities"],
  "tickers": ["NVDA", "TSLA"],
  "opinions": [
    {
      "quote": "Exact quote from transcript",
      "speaker": "Channel host"
    }
  ],
  "claims": [
    {
      "text": "A factual claim that could be researched later",
      "speaker": "Channel host",
      "topic_tags": ["semiconductors"],
      "tickers": ["NVDA"]
    }
  ]
}

Rules:
- Keep the summary neutral and concise.
- Opinions must be direct quotes when available.
- Claims should be factual assertions, not vibes.
- Prefer up to 5 strong claims and 3 strong opinions.

Video title: {{title}}
Channel: {{channel}}
Transcript:
{{transcript}}
