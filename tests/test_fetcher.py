from datetime import UTC, datetime
from pathlib import Path

from agents.fetcher import _fetch_transcript, _published_window, fetch_latest_videos
from agents.models import AppSettings


def test_published_window_uses_exact_day_for_historical_runs() -> None:
    settings = AppSettings()
    settings.schedule.timezone = "Europe/Berlin"
    settings.youtube.lookback_hours = 24

    start, end = _published_window(
        settings,
        "2026-03-27",
        now=datetime(2026, 3, 29, 12, 0, tzinfo=UTC),
    )

    assert start.isoformat() == "2026-03-26T23:00:00+00:00"
    assert end.isoformat() == "2026-03-27T23:00:00+00:00"


def test_published_window_clamps_current_day_to_lookback_hours() -> None:
    settings = AppSettings()
    settings.schedule.timezone = "Europe/Berlin"
    settings.youtube.lookback_hours = 6

    start, end = _published_window(
        settings,
        "2026-03-29",
        now=datetime(2026, 3, 29, 12, 0, tzinfo=UTC),
    )

    assert start.isoformat() == "2026-03-29T06:00:00+00:00"
    assert end.isoformat() == "2026-03-29T12:00:00+00:00"


def test_fetch_latest_videos_persists_transcripts(monkeypatch, tmp_path: Path) -> None:
    settings = AppSettings.model_validate(
        {
            "youtube": {
                "api_key": "test-key",
                "channels": [{"id": "UC123", "name": "Example Channel", "focus": []}],
                "max_videos_per_channel": 5,
                "lookback_hours": 24,
            },
            "schedule": {"fetch_cron": "0 5 * * *", "timezone": "UTC"},
            "agent": {"backend": "codex", "max_concurrent_research": 2, "research_timeout_seconds": 600},
            "site": {"title": "Morning Briefing", "subtitle": "Local agentic financial news", "accent_color": "#C0392B"},
        }
    )

    class FakeSearchRequest:
        def execute(self) -> dict:
            return {
                "items": [
                    {
                        "id": {"videoId": "video-123"},
                        "snippet": {
                            "title": "Market Update",
                            "channelTitle": "Example Channel",
                            "publishedAt": "2026-03-27T10:00:00Z",
                            "description": "Daily market recap",
                            "thumbnails": {"high": {"url": "https://example.com/thumb.jpg"}},
                        },
                    }
                ]
            }

    class FakeSearch:
        def list(self, **_: object) -> FakeSearchRequest:
            return FakeSearchRequest()

    class FakeYouTube:
        def search(self) -> FakeSearch:
            return FakeSearch()

    monkeypatch.setattr("agents.fetcher.build", lambda *args, **kwargs: FakeYouTube())
    monkeypatch.setattr("agents.fetcher._fetch_transcript", lambda video_id: f"Transcript for {video_id}")
    monkeypatch.setattr("agents.fetcher.raw_day_dir", lambda date_str: tmp_path / date_str)
    monkeypatch.setattr(
        "agents.fetcher.transcript_path",
        lambda date_str, video_id: tmp_path / date_str / "transcripts" / f"{video_id}.txt",
    )

    videos = fetch_latest_videos(settings, "2026-03-27")

    assert len(videos) == 1
    assert videos[0].transcript == "Transcript for video-123"
    assert (tmp_path / "2026-03-27" / "transcripts" / "video-123.txt").read_text(encoding="utf-8") == (
        "Transcript for video-123\n"
    )


def test_fetch_transcript_supports_new_api_shape(monkeypatch) -> None:
    class TranscriptChunk:
        def __init__(self, text: str) -> None:
            self.text = text

    class NewApi:
        def fetch(self, video_id: str, languages: tuple[str, ...]) -> list[TranscriptChunk]:
            assert video_id == "video-123"
            assert languages == ("en", "de")
            return [TranscriptChunk("Hello"), TranscriptChunk("world")]

    monkeypatch.setattr("agents.fetcher.YouTubeTranscriptApi", lambda: NewApi())

    assert _fetch_transcript("video-123") == "Hello world"


def test_fetch_transcript_supports_legacy_api_shape(monkeypatch) -> None:
    class LegacyApi:
        @staticmethod
        def get_transcript(video_id: str, languages: tuple[str, ...]) -> list[dict[str, str]]:
            assert video_id == "video-456"
            assert languages == ("en", "de")
            return [{"text": "Legacy"}, {"text": "captions"}]

    monkeypatch.setattr("agents.fetcher.YouTubeTranscriptApi", LegacyApi)

    assert _fetch_transcript("video-456") == "Legacy captions"
