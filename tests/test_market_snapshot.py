from pathlib import Path

from agents.market_snapshot import (
    _normalize_snapshot_payload,
    _snapshot_chart,
    _validate_capital_iq_only,
    build_market_snapshot,
)
from agents.models import AppSettings, MarketSnapshot, MarketSnapshotIndex


def test_validate_capital_iq_only_rejects_external_source_mentions() -> None:
    snapshot = MarketSnapshot(
        date="2026-04-11",
        summary="Mixed close across major indices.",
        indices=[
            MarketSnapshotIndex(
                label="Nasdaq 100",
                symbol="NDX",
                daily_change_percent=0.14,
                closing_level=25116.34,
                currency="USD",
                as_of="2026-04-10",
                session_label="close",
                note="Sourced from Yahoo Finance.",
            )
        ],
    )

    try:
        _validate_capital_iq_only(snapshot)
    except ValueError as exc:
        assert "External market source leaked" in str(exc)
    else:
        raise AssertionError("Expected snapshot validation to reject external sources")


def test_snapshot_chart_is_generated_with_single_available_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("agents.market_snapshot.report_charts_dir", lambda date_str: tmp_path / date_str / "charts")
    monkeypatch.setattr(
        "agents.market_snapshot.report_asset_url",
        lambda date_str, *parts: f"/report-assets/{date_str}/" + "/".join(parts),
    )
    snapshot = MarketSnapshot(
        date="2026-04-11",
        indices=[
            MarketSnapshotIndex(
                label="S&P 500",
                symbol="SPX",
                daily_change_percent=-0.11,
                closing_level=6816.89,
                currency="USD",
                as_of="2026-04-10",
                session_label="close",
            )
        ],
    )

    chart_path, chart_url = _snapshot_chart(snapshot, "2026-04-11")

    assert chart_path is not None
    assert chart_url == "/report-assets/2026-04-11/assets/charts/market-snapshot.svg"
    assert (tmp_path / "2026-04-11" / "charts" / "market-snapshot.svg").exists()


def test_normalize_snapshot_payload_coerces_null_strings_and_backfills_session_label() -> None:
    payload = {
        "summary": None,
        "indices": [
            {
                "label": "S&P 500",
                "symbol": "SPX",
                "daily_change_percent": -0.11,
                "closing_level": 6816.89,
                "currency": "USD",
                "as_of": None,
                "session_label": None,
                "note": None,
            }
        ],
    }

    normalized = _normalize_snapshot_payload(payload)

    assert normalized["summary"] == ""
    assert normalized["indices"][0]["as_of"] == ""
    assert normalized["indices"][0]["note"] == ""
    assert normalized["indices"][0]["session_label"] == "latest visible session"


def test_build_market_snapshot_falls_back_when_snapshot_uses_external_sources(tmp_path: Path, monkeypatch) -> None:
    settings = AppSettings()
    settings.capital_iq.username = "user@example.com"
    settings.capital_iq.password = "secret"

    class FakeRunner:
        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return """
            {
              "summary": "Wall Street was mixed.",
              "indices": [
                {
                  "label": "S&P 500",
                  "symbol": "SPX",
                  "daily_change_percent": -0.11,
                  "closing_level": 6816.89,
                  "currency": "USD",
                  "as_of": "2026-04-10",
                  "session_label": "close",
                  "note": "Checked against Investing.com."
                }
              ]
            }
            """

    monkeypatch.setattr("agents.market_snapshot.report_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.market_snapshot.market_snapshot_path", lambda date_str: tmp_path / date_str / "market-snapshot.json")
    monkeypatch.setattr(
        "agents.market_snapshot.build_runner",
        lambda backend, workspace, timeout, model=None: FakeRunner(),
    )
    monkeypatch.setattr("agents.market_snapshot.effective_settings_path", lambda: str(tmp_path / "config" / "settings.local.json"))

    snapshot = build_market_snapshot(settings, "2026-04-11")

    assert "Capital IQ-only market snapshot was unavailable" in snapshot.markdown
    assert snapshot.chart_url is None


def test_build_market_snapshot_persists_raw_agent_output(tmp_path: Path, monkeypatch) -> None:
    settings = AppSettings()
    settings.agent.model = "opus"
    settings.agent.capital_iq_model = "legacy-haiku"
    settings.agent.research_model = "haiku"
    settings.capital_iq.username = "user@example.com"
    settings.capital_iq.password = "secret"
    captured: dict[str, str | None] = {}

    raw_response = """
    {
      "summary": "US and European indices were mixed.",
      "indices": [
        {
          "label": "S&P 500",
          "symbol": "SPX",
          "daily_change_percent": -0.11,
          "closing_level": 6816.89,
          "currency": "USD",
          "as_of": "2026-04-10",
          "session_label": "close",
          "note": ""
        }
      ]
    }
    """

    class FakeRunner:
        async def run(self, task_prompt: str, skills: list[Path]) -> str:
            return raw_response

    monkeypatch.setattr("agents.market_snapshot.report_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr("agents.market_snapshot.market_snapshot_path", lambda date_str: tmp_path / date_str / "market-snapshot.json")
    monkeypatch.setattr(
        "agents.market_snapshot.build_runner",
        lambda backend, workspace, timeout, model=None: captured.update({"backend": backend, "model": model}) or FakeRunner(),
    )
    monkeypatch.setattr("agents.market_snapshot.effective_settings_path", lambda: str(tmp_path / "config" / "settings.local.json"))

    build_market_snapshot(settings, "2026-04-11")

    assert (tmp_path / "2026-04-11" / "market-snapshot.raw.txt").read_text(encoding="utf-8") == raw_response
    assert captured == {"backend": "codex", "model": "haiku"}
