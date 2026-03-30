from __future__ import annotations

import asyncio
import json
from typing import Any

from agents.models import AppSettings, Claim, DailyClaimsManifest, Opinion, SourceVideo, VideoAnalysis
from agents.paths import claims_manifest_path, raw_day_dir
from agents.prompts_loader import render_prompt
from agents.runner import build_runner
from agents.storage import read_json, write_json
from agents.utils import claim_id_from_text, extract_tickers


def _parse_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


async def _agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, Any]:
    prompt = render_prompt(
        "analyze_transcript.md",
        title=video.title,
        channel=video.channel_name,
        transcript=video.transcript[:16000],
    )
    workspace = raw_day_dir(date_str) / "agent-analysis" / video.video_id
    runner = build_runner(settings.agent.backend, workspace, settings.agent.research_timeout_seconds)
    text = await runner.run(prompt, [])
    return _parse_json_block(text)


def analyze_videos(settings: AppSettings, videos: list[SourceVideo], date_str: str) -> list[VideoAnalysis]:
    day_dir = raw_day_dir(date_str)
    day_dir.mkdir(parents=True, exist_ok=True)

    analyses: list[VideoAnalysis] = []
    all_claims: list[Claim] = []

    for video in videos:
        if not video.transcript.strip():
            continue
        payload = asyncio.run(_agent_analysis(settings, video, date_str))
        if not payload:
            raise RuntimeError(f"Agent analysis returned no payload for video {video.video_id}")
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
