from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AgentBackend = Literal["claude-code", "codex", "cursor", "copilot"]
ClaimStatus = Literal["pending", "queued", "researching", "completed", "failed"]
PipelineJobStatus = Literal["queued", "running", "completed", "failed"]
TranscriptionBackend = Literal["captions_only", "captions_then_local", "local_only"]
TranscriptSource = Literal["captions", "faster_whisper", "none"]
TranscriptStatus = Literal["pending", "completed", "failed", "skipped"]
TranscriptOutputFormat = Literal["txt", "json", "vtt"]
ResearchTaskType = Literal["sp_data_research"]
ResearchTaskPriority = Literal["low", "normal", "high"]


class YouTubeChannel(BaseModel):
    id: str
    name: str
    focus: list[str] = Field(default_factory=list)
    source_input: str | None = None


class YouTubeSettings(BaseModel):
    api_key: str = ""
    channels: list[YouTubeChannel] = Field(default_factory=list)
    max_videos_per_channel: int = 5
    lookback_hours: int = 24


class AgentSettings(BaseModel):
    backend: AgentBackend = "codex"
    max_concurrent_research: int = 2
    research_timeout_seconds: int = 600


class GoogleSearchSettings(BaseModel):
    api_key: str = ""
    engine_id: str = ""


class CapitalIQSettings(BaseModel):
    username: str = ""
    password: str = ""


class TranscriptionSettings(BaseModel):
    backend: TranscriptionBackend = "captions_then_local"
    model: str = "large-v3"
    device: str = "auto"
    compute_type: str = "auto"
    language: str = ""
    caption_languages: list[str] = Field(default_factory=lambda: ["en", "de"])
    vad_filter: bool = True
    beam_size: int = 5
    temperature: float = 0.0
    condition_on_previous_text: bool = True
    keep_audio: bool = False
    max_duration_minutes: int = 90
    output_formats: list[TranscriptOutputFormat] = Field(default_factory=lambda: ["txt", "json", "vtt"])


class ScheduleSettings(BaseModel):
    fetch_cron: str = "0 5 * * *"
    timezone: str = "Europe/Berlin"


class SiteSettings(BaseModel):
    title: str = "Morning Briefing"
    subtitle: str = "Local agentic financial news"
    accent_color: str = "#C0392B"


class AppSettings(BaseModel):
    youtube: YouTubeSettings = Field(default_factory=YouTubeSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    google_search: GoogleSearchSettings = Field(default_factory=GoogleSearchSettings)
    capital_iq: CapitalIQSettings = Field(default_factory=CapitalIQSettings)
    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    site: SiteSettings = Field(default_factory=SiteSettings)


class TranscriptSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str


class SourceVideo(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_name: str
    published_at: datetime
    url: str
    transcript: str = ""
    transcript_source: TranscriptSource = "none"
    transcript_language: str | None = None
    transcript_status: TranscriptStatus = "pending"
    transcription_error: str | None = None
    thumbnail_url: str | None = None
    description: str = ""
    duration_seconds: int | None = None
    default_audio_language: str | None = None


class Opinion(BaseModel):
    quote: str
    speaker: str
    source_video_id: str
    source_url: str
    timestamp_label: str | None = None


class Claim(BaseModel):
    id: str
    text: str
    speaker: str
    source_video_id: str
    source_url: str
    source_title: str
    timestamp_label: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    status: ClaimStatus = "pending"
    research_result_path: str | None = None
    verdict: Literal["supporting", "mixed", "counter", "unknown"] = "unknown"


class AnalysisResearchTask(BaseModel):
    task_type: ResearchTaskType
    topic: str
    goal: str
    priority: ResearchTaskPriority = "normal"


class SubAnalysis(BaseModel):
    task_type: ResearchTaskType
    topic: str
    goal: str
    priority: ResearchTaskPriority = "normal"
    markdown: str
    result_path: str | None = None


class VideoAnalysis(BaseModel):
    video: SourceVideo
    summary: str
    topic_tags: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    research_tasks: list[AnalysisResearchTask] = Field(default_factory=list)
    sub_analyses: list[SubAnalysis] = Field(default_factory=list)
    sp_enrichment: str = ""
    opinions: list[Opinion] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class DailyClaimsManifest(BaseModel):
    date: str
    claims: list[Claim] = Field(default_factory=list)


class ResearchJob(BaseModel):
    claim_id: str
    date: str
    claim_text: str
    source_video: str
    speaker: str
    status: Literal["queued", "researching", "completed", "failed"] = "queued"
    backend: AgentBackend
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result_path: str | None = None


class ResearchResult(BaseModel):
    claim_id: str
    date: str
    verdict: Literal["supporting", "mixed", "counter", "unknown"] = "unknown"
    summary: str
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    markdown: str


class GoogleSearchResult(BaseModel):
    title: str
    link: str
    snippet: str = ""


class PipelineJob(BaseModel):
    id: str
    date: str
    status: PipelineJobStatus = "queued"
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class BriefingIndexItem(BaseModel):
    date: str
    title: str
    summary: str
    claim_count: int = 0
    updated_at: datetime


class PipelineStatus(BaseModel):
    last_run_at: datetime | None = None
    last_run_date: str | None = None
    last_error: str | None = None
    worker_running: bool = False
    active_pipeline_job_id: str | None = None
