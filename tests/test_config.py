import json

from agents.config import load_settings


def test_load_settings_deep_merges_local_override(monkeypatch, tmp_path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_local_path = tmp_path / "settings.local.json"

    settings_path.write_text(
        json.dumps(
            {
                "capital_iq": {"username": "user@example.com", "password": "secret"},
                "agent": {"backend": "codex", "research_timeout_seconds": 600, "analysis_model": "sonnet"},
            }
        ),
        encoding="utf-8",
    )
    settings_local_path.write_text(
        json.dumps(
            {
                "agent": {"backend": "claude-code", "research_model": "haiku"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("agents.config.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("agents.config.SETTINGS_LOCAL_PATH", settings_local_path)
    monkeypatch.setattr("agents.config.ensure_directories", lambda: None)

    settings = load_settings()

    assert settings.agent.backend == "claude-code"
    assert settings.agent.research_timeout_seconds == 600
    assert settings.agent.analysis_model == "sonnet"
    assert settings.agent.research_model == "haiku"
    assert settings.capital_iq.username == "user@example.com"
    assert settings.capital_iq.password == "secret"
