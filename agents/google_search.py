from __future__ import annotations

from googleapiclient.discovery import build

from agents.models import AppSettings, GoogleSearchResult


def effective_google_api_key(settings: AppSettings) -> str:
    return settings.google_search.api_key or settings.youtube.api_key


def google_search_is_configured(settings: AppSettings) -> bool:
    return bool(effective_google_api_key(settings) and settings.google_search.engine_id)


def search_google(query: str, settings: AppSettings, *, num_results: int = 5) -> list[GoogleSearchResult]:
    api_key = effective_google_api_key(settings)
    engine_id = settings.google_search.engine_id
    if not api_key or not engine_id:
        return []

    service = build("customsearch", "v1", developerKey=api_key)
    response = (
        service.cse()
        .list(
            q=query,
            cx=engine_id,
            num=min(max(num_results, 1), 10),
        )
        .execute()
    )
    return [
        GoogleSearchResult(
            title=item.get("title", ""),
            link=item.get("link", ""),
            snippet=item.get("snippet", ""),
        )
        for item in response.get("items", [])
        if item.get("link")
    ]


def format_search_context(results: list[GoogleSearchResult]) -> str:
    if not results:
        return "No Google search results were available."

    lines = []
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"   URL: {item.link}")
        if item.snippet:
            lines.append(f"   Snippet: {item.snippet}")
    return "\n".join(lines)
