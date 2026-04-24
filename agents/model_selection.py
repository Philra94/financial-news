from __future__ import annotations

from agents.models import AppSettings


def _clean_model(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def default_agent_model(settings: AppSettings) -> str | None:
    return _clean_model(settings.agent.model)


def analysis_agent_model(settings: AppSettings) -> str | None:
    return _clean_model(settings.agent.analysis_model) or default_agent_model(settings)


def research_agent_model(settings: AppSettings) -> str | None:
    return _clean_model(settings.agent.research_model) or default_agent_model(settings)


def capital_iq_agent_model(settings: AppSettings) -> str | None:
    return (
        _clean_model(settings.agent.research_model)
        or _clean_model(settings.agent.capital_iq_model)
        or default_agent_model(settings)
    )


def editorial_agent_model(settings: AppSettings) -> str | None:
    return _clean_model(settings.agent.editorial_model) or default_agent_model(settings)


def translation_agent_model(settings: AppSettings) -> str | None:
    return _clean_model(settings.agent.translation_model) or default_agent_model(settings)
