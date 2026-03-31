from __future__ import annotations

import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi

from agents.models import AppSettings, SourceVideo, TranscriptSegment, TranscriptSource, TranscriptStatus
from agents.paths import (
    downloaded_audio_dir,
    normalized_audio_path,
    transcript_metadata_path,
    transcript_path,
    transcript_segments_path,
    transcript_vtt_path,
)
from agents.storage import read_json, read_text, write_json, write_text


class TranscriptionResult(BaseModel):
    text: str = ""
    segments: list[TranscriptSegment] = Field(default_factory=list)
    source: TranscriptSource = "none"
    status: TranscriptStatus = "failed"
    language: str | None = None
    error: str | None = None
    model: str | None = None
    runtime_seconds: float | None = None
    downloaded_audio_path: str | None = None
    normalized_audio_path: str | None = None


def transcribe_source_video(
    settings: AppSettings, date_str: str, video: SourceVideo, *, force: bool = False
) -> SourceVideo:
    cached = _load_cached_transcript(date_str, video.video_id, force=force)
    if cached is not None:
        return _apply_transcription_result(video, cached)

    result: TranscriptionResult
    backend = settings.transcription.backend

    if backend != "local_only":
        result = _fetch_captions(video.video_id, settings.transcription.caption_languages)
        if result.status == "completed":
            _persist_transcription_result(settings, date_str, video, result)
            return _apply_transcription_result(video, result)
        if backend == "captions_only":
            result.status = "failed"
            result.error = result.error or "Captions were required but unavailable."
            _persist_transcription_result(settings, date_str, video, result)
            return _apply_transcription_result(video, result)

    if _should_skip_local_transcription(settings, video):
        result = TranscriptionResult(
            status="skipped",
            error=(
                f"Skipped local transcription because duration exceeds "
                f"{settings.transcription.max_duration_minutes} minutes."
            ),
        )
        _persist_transcription_result(settings, date_str, video, result)
        return _apply_transcription_result(video, result)

    result = _run_local_transcription(settings, date_str, video, force=force)
    _persist_transcription_result(settings, date_str, video, result)
    return _apply_transcription_result(video, result)


def transcribe_videos(
    settings: AppSettings, date_str: str, videos: list[SourceVideo], *, force: bool = False
) -> list[SourceVideo]:
    return [transcribe_source_video(settings, date_str, video, force=force) for video in videos]


def _load_cached_transcript(date_str: str, video_id: str, *, force: bool) -> TranscriptionResult | None:
    if force:
        return None

    text = read_text(transcript_path(date_str, video_id)).strip()
    if not text:
        return None

    metadata = read_json(transcript_metadata_path(date_str, video_id), default={}) or {}
    segments_payload = read_json(transcript_segments_path(date_str, video_id), default=[]) or []
    segments = [TranscriptSegment.model_validate(item) for item in segments_payload]
    return TranscriptionResult(
        text=text,
        segments=segments,
        source=metadata.get("source", "captions"),
        status=metadata.get("status", "completed"),
        language=metadata.get("language"),
        error=metadata.get("error"),
        model=metadata.get("model"),
        runtime_seconds=metadata.get("runtime_seconds"),
        downloaded_audio_path=metadata.get("downloaded_audio_path"),
        normalized_audio_path=metadata.get("normalized_audio_path"),
    )


def _apply_transcription_result(video: SourceVideo, result: TranscriptionResult) -> SourceVideo:
    video.transcript = result.text
    video.transcript_source = result.source
    video.transcript_language = result.language
    video.transcript_status = result.status
    video.transcription_error = result.error
    return video


def _fetch_captions(video_id: str, languages: list[str]) -> TranscriptionResult:
    try:
        api = YouTubeTranscriptApi()
        transcript_payload: object
        language_code: str | None = None

        if hasattr(api, "list"):
            transcript_list = api.list(video_id)
            transcript = transcript_list.find_transcript(languages)
            language_code = getattr(transcript, "language_code", None)
            transcript_payload = transcript.fetch()
        elif hasattr(api, "fetch"):
            transcript_payload = api.fetch(video_id, languages=languages)
        else:
            transcript_payload = YouTubeTranscriptApi.get_transcript(video_id, languages=tuple(languages))

        segments = _segments_from_payload(transcript_payload)
        text = " ".join(segment.text for segment in segments if segment.text)
        if not text.strip():
            return TranscriptionResult(status="failed", error="Caption payload was empty.")

        return TranscriptionResult(
            text=text.strip(),
            segments=segments,
            source="captions",
            status="completed",
            language=language_code or (languages[0] if languages else None),
        )
    except Exception as exc:
        return TranscriptionResult(status="failed", error=str(exc))


def _segments_from_payload(payload: object) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for chunk in payload:
        text = chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", "")
        if not text:
            continue
        start = chunk.get("start", 0.0) if isinstance(chunk, dict) else getattr(chunk, "start", 0.0)
        duration = (
            chunk.get("duration", 0.0) if isinstance(chunk, dict) else getattr(chunk, "duration", 0.0)
        )
        segments.append(
            TranscriptSegment(
                start_seconds=float(start or 0.0),
                end_seconds=float(start or 0.0) + float(duration or 0.0),
                text=text.strip(),
            )
        )
    return segments


def _should_skip_local_transcription(settings: AppSettings, video: SourceVideo) -> bool:
    if video.duration_seconds is None:
        return False
    return video.duration_seconds > settings.transcription.max_duration_minutes * 60


def _run_local_transcription(
    settings: AppSettings, date_str: str, video: SourceVideo, *, force: bool
) -> TranscriptionResult:
    download_path: Path | None = None
    normalized_path: Path | None = None
    started_at = time.perf_counter()

    try:
        download_path = _download_audio(date_str, video, force=force)
        normalized_path = _normalize_audio(date_str, video.video_id, download_path, force=force)
        language_hint = _language_hint(settings, video)
        segments, detected_language = _transcribe_audio(normalized_path, settings, language=language_hint)
        text = " ".join(segment.text for segment in segments if segment.text).strip()
        if not text:
            raise RuntimeError("Whisper produced no transcript text.")
        return TranscriptionResult(
            text=text,
            segments=segments,
            source="faster_whisper",
            status="completed",
            language=detected_language,
            model=settings.transcription.model,
            runtime_seconds=round(time.perf_counter() - started_at, 3),
            downloaded_audio_path=str(download_path),
            normalized_audio_path=str(normalized_path),
        )
    except Exception as exc:
        return TranscriptionResult(
            status="failed",
            error=str(exc),
            model=settings.transcription.model,
            runtime_seconds=round(time.perf_counter() - started_at, 3),
            downloaded_audio_path=str(download_path) if download_path else None,
            normalized_audio_path=str(normalized_path) if normalized_path else None,
        )
    finally:
        if not settings.transcription.keep_audio:
            _cleanup_audio(download_path)
            _cleanup_audio(normalized_path)


def _download_audio(date_str: str, video: SourceVideo, *, force: bool) -> Path:
    existing = _existing_downloaded_audio(date_str, video.video_id)
    if existing is not None and not force:
        return existing
    if existing is not None and force:
        existing.unlink(missing_ok=True)

    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Add it to the local environment first.") from exc

    output_template = downloaded_audio_dir(date_str) / f"{video.video_id}.%(ext)s"
    options = {
        "format": "bestaudio[acodec^=opus]/bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "sleep_interval_requests": 1,
        "outtmpl": {"default": str(output_template)},
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(video.url, download=True)
        requested = info.get("requested_downloads") or []
        for item in requested:
            filepath = item.get("filepath")
            if filepath:
                return Path(filepath)
        filepath = ydl.prepare_filename(info)
        return Path(filepath)


def _normalize_audio(date_str: str, video_id: str, source_path: Path, *, force: bool) -> Path:
    target_path = normalized_audio_path(date_str, video_id)
    if target_path.exists() and not force:
        return target_path

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for audio normalization but was not found on PATH.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(target_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg normalization failed."
        raise RuntimeError(stderr)
    return target_path


def _transcribe_audio(
    audio_path: Path, settings: AppSettings, *, language: str | None
) -> tuple[list[TranscriptSegment], str | None]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Add it to the local environment first.") from exc

    device = _resolve_model_device(settings.transcription.device)
    compute_type = _resolve_compute_type(settings.transcription.compute_type, device)
    model = WhisperModel(settings.transcription.model, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=settings.transcription.vad_filter,
        beam_size=settings.transcription.beam_size,
        temperature=settings.transcription.temperature,
        condition_on_previous_text=settings.transcription.condition_on_previous_text,
    )

    segments: list[TranscriptSegment] = []
    for segment in segments_iter:
        text = segment.text.strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_seconds=float(segment.start),
                end_seconds=float(segment.end),
                text=text,
            )
        )
    return segments, getattr(info, "language", language)


def _resolve_model_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _resolve_compute_type(compute_type: str, device: str) -> str:
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


def _language_hint(settings: AppSettings, video: SourceVideo) -> str | None:
    if settings.transcription.language.strip():
        return settings.transcription.language.strip()
    if video.default_audio_language:
        return video.default_audio_language.split("-", 1)[0].strip() or None
    return None


def _persist_transcription_result(
    settings: AppSettings, date_str: str, video: SourceVideo, result: TranscriptionResult
) -> None:
    txt_path = transcript_path(date_str, video.video_id)
    segments_path = transcript_segments_path(date_str, video.video_id)
    vtt_path = transcript_vtt_path(date_str, video.video_id)
    metadata_path = transcript_metadata_path(date_str, video.video_id)

    if result.status == "completed" and result.text.strip():
        write_text(txt_path, result.text.rstrip() + "\n")
    else:
        txt_path.unlink(missing_ok=True)

    if result.segments and "json" in settings.transcription.output_formats:
        write_json(segments_path, [segment.model_dump(mode="json") for segment in result.segments])
    else:
        segments_path.unlink(missing_ok=True)

    if result.segments and "vtt" in settings.transcription.output_formats:
        write_text(vtt_path, _render_vtt(result.segments))
    else:
        vtt_path.unlink(missing_ok=True)

    write_json(
        metadata_path,
        {
            "video_id": video.video_id,
            "status": result.status,
            "source": result.source,
            "language": result.language,
            "error": result.error,
            "model": result.model,
            "runtime_seconds": result.runtime_seconds,
            "segment_count": len(result.segments),
            "downloaded_audio_path": result.downloaded_audio_path,
            "normalized_audio_path": result.normalized_audio_path,
            "transcript_path": str(txt_path) if txt_path.exists() else None,
            "segments_path": str(segments_path) if segments_path.exists() else None,
            "vtt_path": str(vtt_path) if vtt_path.exists() else None,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )


def _render_vtt(segments: list[TranscriptSegment]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(
            f"{_format_vtt_timestamp(segment.start_seconds)} --> {_format_vtt_timestamp(segment.end_seconds)}"
        )
        lines.append(segment.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_vtt_timestamp(value: float) -> str:
    total_milliseconds = max(int(round(value * 1000)), 0)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def _existing_downloaded_audio(date_str: str, video_id: str) -> Path | None:
    directory = downloaded_audio_dir(date_str)
    if not directory.exists():
        return None
    candidates = sorted(path for path in directory.glob(f"{video_id}.*") if path.is_file())
    return candidates[0] if candidates else None


def _cleanup_audio(path: Path | None) -> None:
    if path is None:
        return
    path.unlink(missing_ok=True)
