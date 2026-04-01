from datetime import UTC, datetime
from pathlib import Path

from agents.analyzer import _agent_analysis, analyze_videos
from agents.models import AppSettings, SourceVideo


def test_analyze_videos_uses_metadata_fallback_for_missing_transcripts(monkeypatch, tmp_path: Path) -> None:
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

    assert seen["analysis"] == 2
    assert seen["sp"] == 2
    assert len(analyses) == 2
    assert analyses[0].research_tasks[0].task_type == "sp_data_research"
    assert analyses[0].sub_analyses[0].topic == "Apple stock valuation"
    assert analyses[0].sp_enrichment == "- Last price: $123.45\n- Market cap: $2.1T"
    assert analyses[1].sp_enrichment == "- Last price: $123.45\n- Market cap: $2.1T"


def test_analyze_videos_uses_metadata_when_transcript_missing(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    videos = [
        SourceVideo(
            video_id="video-metadata",
            title="NVIDIA outlook improves",
            channel_id="UC123",
            channel_name="Example Channel",
            published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            url="https://example.com/full",
            transcript="",
            description="A quick market update on NVIDIA and AI infrastructure spending.",
            transcription_error="yt-dlp was blocked by YouTube.",
        ),
    ]

    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.analyzer.claims_manifest_path", lambda date_str: tmp_path / date_str / "claims.json")

    seen = {"analysis": 0}

    async def fake_agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, object]:
        seen["analysis"] += 1
        return {
            "summary": "The video discusses NVIDIA-related market momentum.",
            "topic_tags": ["equities", "ai"],
            "tickers": ["NVDA"],
            "research_tasks": [],
            "opinions": [],
            "claims": [],
        }

    monkeypatch.setattr("agents.analyzer._agent_analysis", fake_agent_analysis)

    analyses = analyze_videos(settings, videos, "2026-03-30")

    assert seen["analysis"] == 1
    assert len(analyses) == 1
    assert analyses[0].video.video_id == "video-metadata"
    assert analyses[0].summary == "The video discusses NVIDIA-related market momentum."


def test_analyze_videos_falls_back_to_local_metadata_summary_on_agent_failure(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    videos = [
        SourceVideo(
            video_id="video-fallback",
            title="NVIDIA outlook improves after Marvell stake",
            channel_id="UC123",
            channel_name="Example Channel",
            published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            url="https://example.com/full",
            transcript="",
            description="The host discusses NVIDIA, Marvell, and broader Wall Street sentiment.",
            transcription_error="yt-dlp was blocked by YouTube.",
        ),
    ]

    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.analyzer.claims_manifest_path", lambda date_str: tmp_path / date_str / "claims.json")

    async def fake_agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, object]:
        raise ValueError("No JSON object found in model response")

    monkeypatch.setattr("agents.analyzer._agent_analysis", fake_agent_analysis)

    analyses = analyze_videos(settings, videos, "2026-03-30")

    assert len(analyses) == 1
    assert "NVIDIA outlook improves after Marvell stake" in analyses[0].summary
    assert "equities" in analyses[0].topic_tags
    assert "NVDA" in analyses[0].tickers


def test_analyze_videos_falls_back_to_transcript_summary_on_agent_failure(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    videos = [
        SourceVideo(
            video_id="video-transcript-fallback",
            title="Daily market wrap",
            channel_id="UC123",
            channel_name="Example Channel",
            published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            url="https://example.com/full",
            transcript=(
                "Microsoft shares gained after management reiterated AI infrastructure demand. "
                "The host said enterprise spending remained resilient and cloud demand was still improving. "
                "The segment also highlighted Nvidia strength and broader software momentum."
            ),
            description="",
        ),
    ]

    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.analyzer.claims_manifest_path", lambda date_str: tmp_path / date_str / "claims.json")

    async def fake_agent_analysis(settings: AppSettings, video: SourceVideo, date_str: str) -> dict[str, object]:
        raise ValueError("No JSON object found in model response")

    monkeypatch.setattr("agents.analyzer._agent_analysis", fake_agent_analysis)

    analyses = analyze_videos(settings, videos, "2026-03-30")

    assert len(analyses) == 1
    assert "Microsoft shares gained" in analyses[0].summary
    assert "AI infrastructure demand" in analyses[0].summary
    assert "MSFT" in analyses[0].tickers
    assert "NVDA" in analyses[0].tickers


def test_agent_analysis_retries_once_for_invalid_json(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    video = SourceVideo(
        video_id="video-retry",
        title="Transcript available",
        channel_id="UC123",
        channel_name="Example Channel",
        published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
        url="https://example.com/full",
        transcript="Revenue grew 20 percent year over year.",
    )

    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)

    responses = iter(
        [
            "not json at all",
            '{"summary":"Neutral summary","topic_tags":["equities"],"tickers":["AAPL"],"research_tasks":[],"opinions":[],"claims":[]}',
        ]
    )
    prompts: list[str] = []

    class FakeRunner:
        async def run(self, prompt: str, skills: list[Path]) -> str:
            prompts.append(prompt)
            return next(responses)

    monkeypatch.setattr("agents.analyzer.build_runner", lambda backend, workspace, timeout: FakeRunner())

    payload = __import__("asyncio").run(_agent_analysis(settings, video, "2026-03-30"))

    assert payload["summary"] == "Neutral summary"
    assert len(prompts) == 2
    assert "Retry now and respond with JSON only" in prompts[1]
