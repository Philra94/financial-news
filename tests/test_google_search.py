from agents.google_search import effective_google_api_key, format_search_context, google_search_is_configured
from agents.models import AppSettings, GoogleSearchResult


def test_effective_google_api_key_falls_back_to_youtube_key() -> None:
    settings = AppSettings()
    settings.youtube.api_key = "youtube-key"

    assert effective_google_api_key(settings) == "youtube-key"


def test_google_search_is_configured_requires_engine_id() -> None:
    settings = AppSettings()
    settings.youtube.api_key = "youtube-key"

    assert google_search_is_configured(settings) is False

    settings.google_search.engine_id = "engine-id"
    assert google_search_is_configured(settings) is True


def test_format_search_context_renders_results() -> None:
    context = format_search_context(
        [
            GoogleSearchResult(
                title="Reuters headline",
                link="https://www.reuters.com/example",
                snippet="Example snippet",
            )
        ]
    )

    assert "Reuters headline" in context
    assert "https://www.reuters.com/example" in context
    assert "Example snippet" in context
