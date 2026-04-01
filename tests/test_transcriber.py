from datetime import UTC, datetime
from pathlib import Path

from agents.models import AppSettings, SourceVideo, TranscriptSegment
from agents.transcriber import TranscriptionResult, _download_audio, transcribe_source_video


def _configure_artifact_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agents.transcriber.transcript_path",
        lambda date_str, video_id: tmp_path / date_str / "transcripts" / f"{video_id}.txt",
    )
    monkeypatch.setattr(
        "agents.transcriber.transcript_segments_path",
        lambda date_str, video_id: tmp_path / date_str / "transcripts" / "segments" / f"{video_id}.json",
    )
    monkeypatch.setattr(
        "agents.transcriber.transcript_metadata_path",
        lambda date_str, video_id: tmp_path / date_str / "transcripts" / "metadata" / f"{video_id}.json",
    )
    monkeypatch.setattr(
        "agents.transcriber.transcript_vtt_path",
        lambda date_str, video_id: tmp_path / date_str / "transcripts" / "vtt" / f"{video_id}.vtt",
    )
    monkeypatch.setattr(
        "agents.transcriber.downloaded_audio_dir",
        lambda date_str: tmp_path / date_str / "audio" / "downloaded",
    )
    monkeypatch.setattr(
        "agents.transcriber.normalized_audio_path",
        lambda date_str, video_id: tmp_path / date_str / "audio" / "normalized" / f"{video_id}.wav",
    )


def _example_video() -> SourceVideo:
    return SourceVideo(
        video_id="video-123",
        title="Transcript available",
        channel_id="UC123",
        channel_name="Example Channel",
        published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
        url="https://www.youtube.com/watch?v=video-123",
        duration_seconds=300,
        default_audio_language="en-US",
    )


def test_transcribe_source_video_uses_cached_artifacts(monkeypatch, tmp_path: Path) -> None:
    _configure_artifact_paths(monkeypatch, tmp_path)
    transcript_file = tmp_path / "2026-03-30" / "transcripts" / "video-123.txt"
    transcript_file.parent.mkdir(parents=True, exist_ok=True)
    transcript_file.write_text("Cached transcript\n", encoding="utf-8")
    metadata_file = tmp_path / "2026-03-30" / "transcripts" / "metadata" / "video-123.json"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text(
        '{"status":"completed","source":"captions","language":"en","model":null,"runtime_seconds":0.1}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("agents.transcriber._fetch_captions", lambda *args, **kwargs: 1 / 0)
    monkeypatch.setattr("agents.transcriber._run_local_transcription", lambda *args, **kwargs: 1 / 0)

    video = transcribe_source_video(AppSettings(), "2026-03-30", _example_video())

    assert video.transcript == "Cached transcript"
    assert video.transcript_source == "captions"
    assert video.transcript_status == "completed"


def test_transcribe_source_video_persists_caption_artifacts(monkeypatch, tmp_path: Path) -> None:
    _configure_artifact_paths(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "agents.transcriber._fetch_captions",
        lambda *args, **kwargs: TranscriptionResult(
            text="Manual captions",
            segments=[TranscriptSegment(start_seconds=0.0, end_seconds=1.0, text="Manual captions")],
            source="captions",
            status="completed",
            language="en",
        ),
    )
    monkeypatch.setattr("agents.transcriber._run_local_transcription", lambda *args, **kwargs: 1 / 0)

    video = transcribe_source_video(AppSettings(), "2026-03-30", _example_video())

    assert video.transcript == "Manual captions"
    assert video.transcript_source == "captions"
    assert video.transcript_status == "completed"
    assert (tmp_path / "2026-03-30" / "transcripts" / "video-123.txt").read_text(encoding="utf-8") == (
        "Manual captions\n"
    )
    assert (tmp_path / "2026-03-30" / "transcripts" / "segments" / "video-123.json").exists()
    assert (tmp_path / "2026-03-30" / "transcripts" / "vtt" / "video-123.vtt").exists()
    assert (tmp_path / "2026-03-30" / "transcripts" / "metadata" / "video-123.json").exists()


def test_transcribe_source_video_falls_back_to_local_whisper(monkeypatch, tmp_path: Path) -> None:
    _configure_artifact_paths(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "agents.transcriber._fetch_captions",
        lambda *args, **kwargs: TranscriptionResult(status="failed", error="No captions"),
    )
    monkeypatch.setattr(
        "agents.transcriber._run_local_transcription",
        lambda *args, **kwargs: TranscriptionResult(
            text="Whisper transcript",
            segments=[TranscriptSegment(start_seconds=0.0, end_seconds=2.0, text="Whisper transcript")],
            source="faster_whisper",
            status="completed",
            language="en",
            model="large-v3",
        ),
    )

    video = transcribe_source_video(AppSettings(), "2026-03-30", _example_video())

    assert video.transcript == "Whisper transcript"
    assert video.transcript_source == "faster_whisper"
    assert video.transcript_status == "completed"


def test_transcribe_source_video_skips_local_for_long_videos(monkeypatch, tmp_path: Path) -> None:
    _configure_artifact_paths(monkeypatch, tmp_path)
    settings = AppSettings()
    settings.transcription.max_duration_minutes = 1

    monkeypatch.setattr(
        "agents.transcriber._fetch_captions",
        lambda *args, **kwargs: TranscriptionResult(status="failed", error="No captions"),
    )

    called = {"local": 0}

    def fake_local(*args, **kwargs):
        called["local"] += 1
        return TranscriptionResult(text="should not run", status="completed", source="faster_whisper")

    monkeypatch.setattr("agents.transcriber._run_local_transcription", fake_local)

    long_video = _example_video()
    long_video.duration_seconds = 3600
    video = transcribe_source_video(settings, "2026-03-30", long_video)

    assert called["local"] == 0
    assert video.transcript == ""
    assert video.transcript_status == "skipped"


def test_download_audio_falls_back_to_browser_assisted_ytdlp(monkeypatch, tmp_path: Path) -> None:
    _configure_artifact_paths(monkeypatch, tmp_path)

    output_file = tmp_path / "2026-03-30" / "audio" / "downloaded" / "video-123.webm"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("cookie", encoding="utf-8")

    monkeypatch.setattr("agents.transcriber._existing_downloaded_audio", lambda *args, **kwargs: None)

    calls: list[tuple[str | None, str | None]] = []

    def fake_download(url: str, output_template: Path, *, cookiefile=None, user_agent=None):
        calls.append((str(cookiefile) if cookiefile else None, user_agent))
        if cookiefile is None:
            raise RuntimeError("direct failed")
        return output_file

    monkeypatch.setattr("agents.transcriber._download_audio_with_ytdlp", fake_download)
    monkeypatch.setattr("agents.transcriber._browser_cookie_file", lambda url: (cookie_file, "TestBrowser/1.0"))

    path = _download_audio("2026-03-30", _example_video(), force=False)

    assert path == output_file
    assert calls == [(None, None), (str(cookie_file), "TestBrowser/1.0")]
