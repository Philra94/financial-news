from datetime import UTC, datetime
from pathlib import Path

from agents.analyzer import analyze_videos
from agents.models import AppSettings, SourceVideo


def test_analyze_videos_skips_empty_transcripts(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    videos = [
        SourceVideo(
            video_id="video-empty",
            title="No transcript",
            channel_id="UC123",
            channel_name="Example Channel",
            published_at=datetime(2026, 3, 30, 8, 0, tzinfo=UTC),
            url="https://example.com/empty",
            transcript="",
        ),
        SourceVideo(
            video_id="video-full",
            title="Transcript available",
            channel_id="UC123",
            channel_name="Example Channel",
            published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            url="https://example.com/full",
            transcript="Revenue grew 20 percent year over year.",
        ),
    ]

    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.analyzer.claims_manifest_path", lambda date_str: tmp_path / date_str / "claims.json")

    seen = {"count": 0}

    def fake_asyncio_run(_coroutine: object) -> dict[str, object]:
        close = getattr(_coroutine, "close", None)
        if callable(close):
            close()
        seen["count"] += 1
        return {
            "summary": "Neutral summary",
            "topic_tags": ["equities"],
            "tickers": ["AAPL"],
            "opinions": [],
            "claims": [],
        }

    monkeypatch.setattr("agents.analyzer.asyncio.run", fake_asyncio_run)

    analyses = analyze_videos(settings, videos, "2026-03-30")

    assert seen["count"] == 1
    assert len(analyses) == 1
    assert analyses[0].video.video_id == "video-full"
