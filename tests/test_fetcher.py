from datetime import UTC, datetime
from pathlib import Path

from agents.fetcher import _parse_duration_seconds, _published_window, fetch_latest_videos
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

    class FakeVideosRequest:
        def execute(self) -> dict:
            return {
                "items": [
                    {
                        "id": "video-123",
                        "snippet": {
                            "title": "Market Update",
                            "channelTitle": "Example Channel",
                            "description": "Daily market recap",
                            "defaultAudioLanguage": "en-US",
                        },
                        "contentDetails": {"duration": "PT12M30S"},
                    }
                ]
            }

    class FakeVideos:
        def list(self, **_: object) -> FakeVideosRequest:
            return FakeVideosRequest()

    class FakeYouTube:
        def search(self) -> FakeSearch:
            return FakeSearch()

        def videos(self) -> FakeVideos:
            return FakeVideos()

    monkeypatch.setattr("agents.fetcher.build", lambda *args, **kwargs: FakeYouTube())
    monkeypatch.setattr("agents.fetcher.raw_day_dir", lambda date_str: tmp_path / date_str)

    def fake_transcribe(settings: AppSettings, date_str: str, video):
        assert date_str == "2026-03-27"
        video.transcript = f"Transcript for {video.video_id}"
        video.transcript_source = "faster_whisper"
        video.transcript_status = "completed"
        return video

    monkeypatch.setattr("agents.fetcher.transcribe_source_video", fake_transcribe)

    videos = fetch_latest_videos(settings, "2026-03-27")

    assert len(videos) == 1
    assert videos[0].transcript == "Transcript for video-123"
    assert videos[0].duration_seconds == 750
    assert videos[0].default_audio_language == "en-US"
    assert videos[0].transcript_source == "faster_whisper"

    payload = (tmp_path / "2026-03-27" / "videos.json").read_text(encoding="utf-8")
    assert "Transcript for video-123" in payload

def test_parse_duration_seconds_supports_standard_youtube_iso8601() -> None:
    assert _parse_duration_seconds("PT1H2M3S") == 3723
    assert _parse_duration_seconds("PT45M") == 2700
    assert _parse_duration_seconds("PT59S") == 59
    assert _parse_duration_seconds(None) is None
