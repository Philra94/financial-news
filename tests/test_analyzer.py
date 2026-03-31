from datetime import UTC, datetime
from pathlib import Path

from agents.analyzer import analyze_videos
from agents.models import AppSettings, SourceVideo


def test_analyze_videos_skips_empty_transcripts(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    settings.capital_iq.username = "user@example.com"
    settings.capital_iq.password = "secret"
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

    seen = {"analysis": 0, "sp": 0}

    async def fake_agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, object]:
        seen["analysis"] += 1
        return {
            "summary": "Neutral summary",
            "topic_tags": ["equities"],
            "tickers": ["AAPL"],
            "research_tasks": [
                {
                    "task_type": "sp_data_research",
                    "topic": "Apple stock valuation",
                    "goal": "Add current stock and valuation context from S&P Capital IQ.",
                    "priority": "high",
                }
            ],
            "opinions": [],
            "claims": [],
        }

    async def fake_run_research_subtask(
        settings: AppSettings,
        video: SourceVideo,
        date_str: str,
        payload: dict[str, object],
        task,
        task_index: int,
    ):
        from agents.models import SubAnalysis

        seen["sp"] += 1
        assert payload["tickers"] == ["AAPL"]
        assert task.topic == "Apple stock valuation"
        assert task_index == 1
        return SubAnalysis(
            task_type="sp_data_research",
            topic=task.topic,
            goal=task.goal,
            priority=task.priority,
            markdown="- Last price: $123.45\n- Market cap: $2.1T",
            result_path=str(tmp_path / "2026-03-30" / "sub-analyses" / "video-full" / "01-apple-stock-valuation" / "analysis.md"),
        )

    monkeypatch.setattr("agents.analyzer._agent_analysis", fake_agent_analysis)
    monkeypatch.setattr("agents.analyzer._run_research_subtask", fake_run_research_subtask)

    analyses = analyze_videos(settings, videos, "2026-03-30")

    assert seen["analysis"] == 1
    assert seen["sp"] == 1
    assert len(analyses) == 1
    assert analyses[0].video.video_id == "video-full"
    assert analyses[0].research_tasks[0].task_type == "sp_data_research"
    assert analyses[0].sub_analyses[0].topic == "Apple stock valuation"
    assert analyses[0].sp_enrichment == "- Last price: $123.45\n- Market cap: $2.1T"
