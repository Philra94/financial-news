from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from agents.analyzer import _agent_analysis, _run_sp_data_subtask
from agents.compiler import _generate_briefing, _translate_briefing_to_german
from agents.model_selection import (
    analysis_agent_model,
    capital_iq_agent_model,
    editorial_agent_model,
    research_agent_model,
    translation_agent_model,
)
from agents.models import AnalysisResearchTask, AppSettings, Claim, DailyClaimsManifest, ResearchJob, SourceVideo
from agents.researcher import process_job


def test_stage_model_selectors_fall_back_cleanly() -> None:
    settings = AppSettings()
    settings.agent.model = "opus"
    settings.agent.capital_iq_model = "legacy-haiku"

    assert analysis_agent_model(settings) == "opus"
    assert research_agent_model(settings) == "opus"
    assert capital_iq_agent_model(settings) == "legacy-haiku"
    assert editorial_agent_model(settings) == "opus"
    assert translation_agent_model(settings) == "opus"

    settings.agent.analysis_model = "sonnet"
    settings.agent.research_model = "haiku"
    settings.agent.editorial_model = "opus-strong"
    settings.agent.translation_model = "cheap-haiku"

    assert analysis_agent_model(settings) == "sonnet"
    assert research_agent_model(settings) == "haiku"
    assert capital_iq_agent_model(settings) == "haiku"
    assert editorial_agent_model(settings) == "opus-strong"
    assert translation_agent_model(settings) == "cheap-haiku"


def test_agent_analysis_uses_analysis_model(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    settings.agent.backend = "claude-code"
    settings.agent.model = "opus"
    settings.agent.analysis_model = "sonnet"

    video = SourceVideo(
        video_id="video-1",
        title="AI market wrap",
        channel_id="UC123",
        channel_name="Example Channel",
        published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        url="https://example.com/video-1",
        transcript="Nvidia and Microsoft were both discussed.",
    )

    captured: dict[str, str | None] = {}

    class FakeRunner:
        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return '{"summary": "ok"}'

    def fake_build_runner(backend, workspace, timeout, model=None):
        captured["backend"] = backend
        captured["model"] = model
        return FakeRunner()

    monkeypatch.setattr("agents.analyzer.build_runner", fake_build_runner)
    monkeypatch.setattr("agents.analyzer.raw_day_dir", lambda date_str: tmp_path / date_str)

    payload = asyncio.run(_agent_analysis(settings, video, "2026-04-20"))

    assert payload["summary"] == "ok"
    assert captured == {"backend": "claude-code", "model": "sonnet"}


def test_sp_research_subtask_prefers_research_model(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    settings.agent.backend = "claude-code"
    settings.agent.model = "opus"
    settings.agent.capital_iq_model = "legacy-haiku"
    settings.agent.research_model = "haiku"

    video = SourceVideo(
        video_id="video-1",
        title="Apple valuation",
        channel_id="UC123",
        channel_name="Example Channel",
        published_at=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        url="https://example.com/video-1",
        transcript="Apple valuation and multiples were discussed.",
    )
    task = AnalysisResearchTask(
        task_type="sp_data_research",
        topic="Apple valuation refresh",
        goal="Refresh valuation context from Capital IQ.",
        priority="high",
    )
    captured: dict[str, str | None] = {}

    class FakeRunner:
        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return "## Valuation\n\n- Forward PE: 28x"

    def fake_build_runner(backend, workspace, timeout, model=None):
        captured["backend"] = backend
        captured["model"] = model
        return FakeRunner()

    monkeypatch.setattr("agents.analyzer.build_runner", fake_build_runner)
    monkeypatch.setattr("agents.analyzer.video_subtasks_dir", lambda date_str, video_id: tmp_path / date_str / video_id)

    result = asyncio.run(
        _run_sp_data_subtask(
            settings,
            video,
            "2026-04-20",
            {"summary": "Apple stayed in focus.", "tickers": ["AAPL"], "topic_tags": ["equities"]},
            task,
            1,
        )
    )

    assert result.markdown.startswith("## Valuation")
    assert captured == {"backend": "claude-code", "model": "haiku"}


def test_generate_and_translate_briefing_use_distinct_models(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    settings.agent.backend = "claude-code"
    settings.agent.model = "opus"
    settings.agent.editorial_model = "opus-editor"
    settings.agent.translation_model = "haiku-translator"

    captured: list[str | None] = []

    class FakeRunner:
        def __init__(self, output: str) -> None:
            self.output = output

        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return self.output

    def fake_build_runner(backend, workspace, timeout, model=None):
        captured.append(model)
        if workspace.name == "agent-translate":
            return FakeRunner("# Morgenbriefing\n\nEin sauberer Entwurf.\n")
        return FakeRunner("# Morning Briefing\n\nA clean draft.\n")

    monkeypatch.setattr("agents.compiler.build_runner", fake_build_runner)
    monkeypatch.setattr("agents.compiler.report_day_dir", lambda date_str: tmp_path / date_str)

    english = _generate_briefing(settings, {"sections": {}}, "2026-04-20")
    german = _translate_briefing_to_german(settings, english, "2026-04-20")

    assert english.startswith("# Morning Briefing")
    assert german.startswith("# Morgenbriefing")
    assert captured == ["opus-editor", "haiku-translator"]


def test_claim_research_uses_research_model(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    settings.agent.model = "opus"
    settings.agent.research_model = "haiku"

    claim = Claim(
        id="claim-1",
        text="Nvidia demand is still accelerating.",
        speaker="Host",
        source_video_id="video-1",
        source_url="https://example.com/video-1",
        source_title="AI market wrap",
    )
    manifest = DailyClaimsManifest(date="2026-04-20", claims=[claim])
    job = ResearchJob(
        claim_id="claim-1",
        date="2026-04-20",
        claim_text=claim.text,
        source_video="video-1",
        speaker="Host",
        backend="claude-code",
        created_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
    )
    captured: dict[str, str | None] = {}

    class FakeRunner:
        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return "# Supporting\n\nCapital spending commentary remained firm."

    def fake_build_runner(backend, workspace, timeout, model=None):
        captured["backend"] = backend
        captured["model"] = model
        return FakeRunner()

    monkeypatch.setattr("agents.researcher.build_runner", fake_build_runner)
    monkeypatch.setattr("agents.researcher.load_claim_manifest", lambda date_str: manifest)
    monkeypatch.setattr("agents.researcher.google_search_is_configured", lambda settings: False)
    monkeypatch.setattr("agents.researcher.job_path", lambda claim_id: tmp_path / f"{claim_id}.job.json")
    monkeypatch.setattr(
        "agents.researcher.research_result_path", lambda date_str, claim_id: tmp_path / date_str / claim_id / "result.md"
    )
    monkeypatch.setattr(
        "agents.researcher.research_result_json_path",
        lambda date_str, claim_id: tmp_path / date_str / claim_id / "result.json",
    )
    monkeypatch.setattr(
        "agents.researcher.research_search_results_path",
        lambda date_str, claim_id: tmp_path / date_str / claim_id / "search.json",
    )

    result = asyncio.run(process_job(settings, job))

    assert result.summary == "Supporting"
    assert captured == {"backend": "claude-code", "model": "haiku"}
