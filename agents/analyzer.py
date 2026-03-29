from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from agents.models import AppSettings, Claim, DailyClaimsManifest, Opinion, SourceVideo, VideoAnalysis
from agents.paths import claims_manifest_path, raw_day_dir
from agents.prompts_loader import render_prompt
from agents.storage import read_json, write_json
from agents.utils import claim_id_from_text, extract_tickers, sentence_chunks


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


def _llm_analysis(settings: AppSettings, video: SourceVideo) -> dict[str, Any] | None:
    if not settings.llm.api_key:
        return None

    prompt = render_prompt(
        "analyze_transcript.md",
        title=video.title,
        channel=video.channel_name,
        transcript=video.transcript[:16000],
    )
    try:
        if settings.llm.provider == "anthropic":
            client = Anthropic(api_key=settings.llm.api_key)
            message = client.messages.create(
                model=settings.llm.model,
                max_tokens=1600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", None) == "text"
            )
        else:
            client = OpenAI(api_key=settings.llm.api_key)
            response = client.responses.create(model=settings.llm.model, input=prompt)
            text = response.output_text
        return _parse_json_block(text)
    except Exception:
        return None


def _heuristic_analysis(video: SourceVideo) -> dict[str, Any]:
    sentences = sentence_chunks(video.transcript or video.description)
    summary = " ".join(sentences[:2])[:400] or f"{video.channel_name} discussed {video.title}."
    topic_tags: list[str] = []
    lowered = f"{video.title} {video.description} {video.transcript[:2000]}".lower()
    for tag in ("macro", "inflation", "rates", "equities", "earnings", "commodities", "ai"):
        if tag in lowered and tag not in topic_tags:
            topic_tags.append(tag)
    opinions: list[dict[str, str]] = []
    claims: list[dict[str, Any]] = []
    for sentence in sentences[:24]:
        if any(keyword in sentence.lower() for keyword in ("i think", "i believe", "in my view")):
            opinions.append({"quote": sentence[:280], "speaker": video.channel_name})
        if any(
            keyword in sentence.lower()
            for keyword in ("will", "expects", "forecast", "guidance", "because", "due to", "should")
        ):
            claims.append(
                {
                    "text": sentence[:280],
                    "speaker": video.channel_name,
                    "topic_tags": topic_tags[:3],
                    "tickers": extract_tickers(sentence),
                }
            )
    return {
        "summary": summary,
        "topic_tags": topic_tags,
        "tickers": extract_tickers(video.title + " " + video.description + " " + video.transcript),
        "opinions": opinions[:3],
        "claims": claims[:5],
    }


def analyze_videos(settings: AppSettings, videos: list[SourceVideo], date_str: str) -> list[VideoAnalysis]:
    day_dir = raw_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    analyses: list[VideoAnalysis] = []
    all_claims: list[Claim] = []

    for video in videos:
        payload = _llm_analysis(settings, video) or _heuristic_analysis(video)
        opinions = [
            Opinion(
                quote=item["quote"],
                speaker=item.get("speaker") or video.channel_name,
                source_video_id=video.video_id,
                source_url=video.url,
            )
            for item in payload.get("opinions", [])
            if item.get("quote")
        ]
        claims = []
        for item in payload.get("claims", []):
            text = item.get("text", "").strip()
            if not text:
                continue
            claim = Claim(
                id=claim_id_from_text(f"{video.video_id}:{text}"),
                text=text,
                speaker=item.get("speaker") or video.channel_name,
                source_video_id=video.video_id,
                source_url=video.url,
                source_title=video.title,
                topic_tags=item.get("topic_tags") or payload.get("topic_tags", []),
                tickers=item.get("tickers") or extract_tickers(text),
            )
            claims.append(claim)
            all_claims.append(claim)
        analysis = VideoAnalysis(
            video=video,
            summary=payload.get("summary", ""),
            topic_tags=payload.get("topic_tags", []),
            tickers=payload.get("tickers", []),
            opinions=opinions,
            claims=claims,
        )
        analyses.append(analysis)

    write_json(day_dir / "analysis.json", [item.model_dump(mode="json") for item in analyses])
    manifest = DailyClaimsManifest(date=date_str, claims=all_claims)
    write_json(claims_manifest_path(date_str), manifest.model_dump(mode="json"))
    return analyses


def load_analyses(date_str: str) -> list[VideoAnalysis]:
    payload = read_json(raw_day_dir(date_str) / "analysis.json", default=[])
    return [VideoAnalysis.model_validate(item) for item in payload]
