from datetime import UTC, datetime
from pathlib import Path

from agents.compiler import _build_compiler_payload, _clean_public_markdown, compile_briefing
from agents.models import AppSettings, MarketSnapshot, MarketSnapshotIndex, SourceVideo, VideoAnalysis, WatchlistStock
from agents.storage import read_json


def _make_analysis(
    *,
    video_id: str,
    title: str,
    channel_name: str,
    summary: str,
    topic_tags: list[str],
    tickers: list[str],
    watchlist_matches: list[str] | None = None,
    transcript: str = "",
) -> VideoAnalysis:
    return VideoAnalysis(
        video=SourceVideo(
            video_id=video_id,
            title=title,
            channel_id="UC123",
            channel_name=channel_name,
            published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            url=f"https://example.com/{video_id}",
            transcript=transcript,
        ),
        summary=summary,
        topic_tags=topic_tags,
        tickers=tickers,
        watchlist_matches=watchlist_matches or [],
        opinions=[],
        claims=[],
    )


def test_build_compiler_payload_omits_transcripts_and_adds_related_analyses() -> None:
    settings = AppSettings()
    analyses = [
        _make_analysis(
            video_id="vid-1",
            title="Nvidia outlook",
            channel_name="Channel One",
            summary="Nvidia remained the center of AI spending debate.",
            topic_tags=["equities", "ai"],
            tickers=["NVDA"],
            transcript="Full transcript that should never reach the compiler payload.",
        ),
        _make_analysis(
            video_id="vid-2",
            title="Semis under pressure",
            channel_name="Channel Two",
            summary="Another channel covered the same Nvidia-led weakness.",
            topic_tags=["equities", "ai"],
            tickers=["NVDA", "AMD"],
            transcript="Another transcript that should be excluded from the payload.",
        ),
    ]

    payload, market_overview = _build_compiler_payload(settings, analyses, "2026-03-30")

    equities_items = payload["sections"]["EQUITIES"]
    assert market_overview.startswith("Nvidia remained the center")
    assert "transcript" not in equities_items[0]["video"]
    assert equities_items[0]["related_analyses"][0]["video_id"] == "vid-2"
    assert equities_items[0]["related_analyses"][0]["shared_tickers"] == ["NVDA"]
    assert equities_items[0]["related_analyses"][0]["shared_topic_tags"] == ["ai", "equities"]


def test_compile_briefing_marks_quality_fallback_when_translation_fails(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    analyses = [
        _make_analysis(
            video_id="vid-1",
            title="Macro wrap",
            channel_name="Channel One",
            summary="Rates stayed high while equities remained choppy.",
            topic_tags=["macro"],
            tickers=["TLT"],
        )
    ]

    report_dir = tmp_path / "2026-03-30"
    monkeypatch.setattr("agents.compiler.report_day_dir", lambda date_str: report_dir)
    monkeypatch.setattr("agents.compiler.briefing_path", lambda date_str: report_dir / "briefing.md")
    monkeypatch.setattr("agents.compiler.briefing_english_path", lambda date_str: report_dir / "briefing.en.md")
    monkeypatch.setattr("agents.compiler.briefing_german_path", lambda date_str: report_dir / "briefing.de.md")
    monkeypatch.setattr("agents.compiler.briefing_metadata_path", lambda date_str: report_dir / "briefing.json")
    monkeypatch.setattr(
        "agents.compiler._generate_briefing",
        lambda settings, payload, date_str: "# Morning Briefing\n\nA clean English draft.\n",
    )
    monkeypatch.setattr(
        "agents.compiler._review_briefing",
        lambda settings, payload, markdown, date_str: {"approved": True, "summary": "Ready", "revision_instructions": []},
    )
    monkeypatch.setattr(
        "agents.compiler._translate_briefing_to_german",
        lambda settings, markdown, date_str: (_ for _ in ()).throw(RuntimeError("translator down")),
    )

    compile_briefing(settings, analyses, "2026-03-30")

    metadata = read_json(report_dir / "briefing.json")
    assert metadata["quality"] == "fallback"
    assert metadata["source_count"] == 1
    assert (report_dir / "briefing.md").read_text(encoding="utf-8") == "# Morning Briefing\n\nA clean English draft.\n"


def test_build_compiler_payload_prioritizes_watchlist_matches() -> None:
    settings = AppSettings()
    settings.watchlist.stocks = [WatchlistStock(ticker="NVDA", name="NVIDIA", notes="Core AI capex holding")]
    analyses = [
        _make_analysis(
            video_id="vid-watch",
            title="NVIDIA valuation check",
            channel_name="Channel One",
            summary="NVIDIA stayed central to the AI spending debate.",
            topic_tags=["equities", "ai"],
            tickers=["NVDA"],
            watchlist_matches=["NVDA"],
        ),
        _make_analysis(
            video_id="vid-macro",
            title="Rates wrap",
            channel_name="Channel Two",
            summary="Treasury yields held near recent highs.",
            topic_tags=["macro"],
            tickers=["TLT"],
        ),
    ]

    payload, market_overview = _build_compiler_payload(settings, analyses, "2026-03-30")

    assert market_overview.startswith("NVIDIA stayed central")
    assert payload["market_overview_inputs"][0]["watchlist_matches"] == ["NVDA"]
    assert payload["sections"]["WATCHLIST"][0]["watchlist_matches"] == ["NVDA"]
    assert payload["watchlist"][0]["ticker"] == "NVDA"
    assert any("watchlist" in hint.lower() for hint in payload["synthesis_hints"])


def test_compile_briefing_injects_market_snapshot_and_preserves_image_markdown(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    analyses = [
        _make_analysis(
            video_id="vid-1",
            title="Macro wrap",
            channel_name="Channel One",
            summary="Rates stayed high while equities remained choppy.",
            topic_tags=["macro"],
            tickers=["TLT"],
        )
    ]
    snapshot = MarketSnapshot(
        date="2026-03-30",
        summary="Global equities were mixed into the close.",
        indices=[
            MarketSnapshotIndex(label="S&P 500", daily_change_percent=-0.8),
            MarketSnapshotIndex(label="Nasdaq 100", daily_change_percent=-1.2),
            MarketSnapshotIndex(label="DAX", daily_change_percent=0.4),
            MarketSnapshotIndex(label="Euro Stoxx 50", daily_change_percent=0.2),
            MarketSnapshotIndex(label="Nikkei 225", daily_change_percent=-0.5),
        ],
        markdown=(
            "## MARKET SNAPSHOT\n\n"
            "- `S&P 500`: -0.80%.\n"
            "- `Nasdaq 100`: -1.20%.\n"
            "\n"
            "![Global equity indices split on the latest session](/report-assets/2026-03-30/assets/charts/market-snapshot.svg)\n"
            "\n"
            "*Source: S&P Capital IQ.*\n"
            "\n"
            "- Global equities were mixed into the close."
        ),
    )

    report_dir = tmp_path / "2026-03-30"
    monkeypatch.setattr("agents.compiler.report_day_dir", lambda date_str: report_dir)
    monkeypatch.setattr("agents.compiler.briefing_path", lambda date_str: report_dir / "briefing.md")
    monkeypatch.setattr("agents.compiler.briefing_english_path", lambda date_str: report_dir / "briefing.en.md")
    monkeypatch.setattr("agents.compiler.briefing_german_path", lambda date_str: report_dir / "briefing.de.md")
    monkeypatch.setattr("agents.compiler.briefing_metadata_path", lambda date_str: report_dir / "briefing.json")
    monkeypatch.setattr(
        "agents.compiler._generate_briefing",
        lambda settings, payload, date_str: (
            "# Morning Briefing\n\n"
            "**2026-03-30 | Local agentic financial news**\n\n"
            "---\n\n"
            "## MARKET OVERVIEW\n\n"
            "A clean English draft.\n"
        ),
    )
    monkeypatch.setattr(
        "agents.compiler._review_briefing",
        lambda settings, payload, markdown, date_str: {"approved": True, "summary": "Ready", "revision_instructions": []},
    )

    def fake_translate(settings: AppSettings, markdown: str, date_str: str) -> str:
        assert "## MARKET SNAPSHOT" in markdown
        assert "![Global equity indices split on the latest session]" in markdown
        return markdown.replace("Morning Briefing", "Morgenbriefing")

    monkeypatch.setattr("agents.compiler._translate_briefing_to_german", fake_translate)

    compile_briefing(settings, analyses, "2026-03-30", market_snapshot=snapshot)

    english = (report_dir / "briefing.en.md").read_text(encoding="utf-8")
    german = (report_dir / "briefing.de.md").read_text(encoding="utf-8")

    assert english.index("## MARKET SNAPSHOT") < english.index("## MARKET OVERVIEW")
    assert "![Global equity indices split on the latest session]" in english
    assert "![Global equity indices split on the latest session]" in german


def test_compile_briefing_summary_skips_snapshot_image_line(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings()
    analyses = [
        _make_analysis(
            video_id="vid-1",
            title="Macro wrap",
            channel_name="Channel One",
            summary="Rates stayed high while equities remained choppy.",
            topic_tags=["macro"],
            tickers=["TLT"],
        )
    ]
    snapshot = MarketSnapshot(
        date="2026-03-30",
        summary="Global equities were mixed into the close.",
        markdown=(
            "## MARKET SNAPSHOT\n\n"
            "- `S&P 500`: -0.80%.\n\n"
            "![Global equity indices split on the latest session](/report-assets/2026-03-30/assets/charts/market-snapshot.svg)\n\n"
            "*Source: S&P Capital IQ.*\n\n"
            "- Global equities were mixed into the close."
        ),
    )

    report_dir = tmp_path / "2026-03-30"
    monkeypatch.setattr("agents.compiler.report_day_dir", lambda date_str: report_dir)
    monkeypatch.setattr("agents.compiler.briefing_path", lambda date_str: report_dir / "briefing.md")
    monkeypatch.setattr("agents.compiler.briefing_english_path", lambda date_str: report_dir / "briefing.en.md")
    monkeypatch.setattr("agents.compiler.briefing_german_path", lambda date_str: report_dir / "briefing.de.md")
    monkeypatch.setattr("agents.compiler.briefing_metadata_path", lambda date_str: report_dir / "briefing.json")
    monkeypatch.setattr(
        "agents.compiler._generate_briefing",
        lambda settings, payload, date_str: (
            "# Morning Briefing\n\n"
            "**2026-03-30 | Local agentic financial news**\n\n"
            "---\n\n"
            "## MARKET OVERVIEW\n\n"
            "Global equities were mixed into the close.\n"
        ),
    )
    monkeypatch.setattr(
        "agents.compiler._review_briefing",
        lambda settings, payload, markdown, date_str: {"approved": True, "summary": "Ready", "revision_instructions": []},
    )
    monkeypatch.setattr("agents.compiler._translate_briefing_to_german", lambda settings, markdown, date_str: markdown)

    compile_briefing(settings, analyses, "2026-03-30", market_snapshot=snapshot)

    metadata = read_json(report_dir / "briefing.json")
    assert metadata["summary"] == "Global equities were mixed into the close."


def test_clean_public_markdown_strips_agent_process_chatter(tmp_path: Path, monkeypatch) -> None:
    report_dir = tmp_path / "2026-03-30"
    monkeypatch.setattr("agents.compiler.report_day_dir", lambda date_str: report_dir)

    cleaned = _clean_public_markdown(
        (
            "I now have all the data I need from Capital IQ. Let me compile the analysis.\n\n"
            "# Morning Briefing\n\n"
            "## MARKET OVERVIEW\n\n"
            "Equities were mixed across major indices.\n"
        ),
        artifact_name="briefing.en.raw.md",
        date_str="2026-03-30",
    )

    assert cleaned == "# Morning Briefing\n\n## MARKET OVERVIEW\n\nEquities were mixed across major indices.\n"
    assert (report_dir / "briefing.en.raw.md").read_text(encoding="utf-8").startswith(
        "I now have all the data I need"
    )
