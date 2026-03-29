from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime


TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
FENCED_BLOCK_PATTERN = re.compile(r"^```(?:markdown|md|mdx)?\s*\n(?P<body>.*)\n```\s*$", re.DOTALL)


def utc_now() -> datetime:
    return datetime.now(UTC)


def claim_id_from_text(text: str) -> str:
    digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:8]
    return f"claim-{digest}"


def extract_tickers(text: str) -> list[str]:
    ignore = {"THE", "WITH", "THIS", "THAT", "FROM", "WILL", "YOUR", "ABOUT", "INTO"}
    tickers = []
    for token in TICKER_PATTERN.findall(text.upper()):
        if token not in ignore and token not in tickers:
            tickers.append(token)
    return tickers[:8]


def sentence_chunks(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def unwrap_markdown_response(text: str) -> str:
    cleaned = text.strip()
    match = FENCED_BLOCK_PATTERN.match(cleaned)
    if match:
        return match.group("body").strip()
    return cleaned
