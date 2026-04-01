from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = DATA_DIR / "reports"
RESEARCH_DIR = DATA_DIR / "research"
JOBS_DIR = DATA_DIR / "jobs"
PROMPTS_DIR = ROOT_DIR / "agents" / "prompts"
SKILLS_DIR = ROOT_DIR / ".agents" / "skills"
FRONTEND_DIST_DIR = ROOT_DIR / "web" / "frontend" / "dist"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
SETTINGS_LOCAL_PATH = CONFIG_DIR / "settings.local.json"
PIPELINE_STATUS_PATH = DATA_DIR / "pipeline_status.json"


def ensure_directories() -> None:
    for path in (CONFIG_DIR, DATA_DIR, RAW_DIR, REPORTS_DIR, RESEARCH_DIR, JOBS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def raw_day_dir(date_str: str) -> Path:
    return RAW_DIR / date_str


def transcript_dir(date_str: str) -> Path:
    return raw_day_dir(date_str) / "transcripts"


def transcript_path(date_str: str, video_id: str) -> Path:
    return transcript_dir(date_str) / f"{video_id}.txt"


def transcript_segments_dir(date_str: str) -> Path:
    return transcript_dir(date_str) / "segments"


def transcript_segments_path(date_str: str, video_id: str) -> Path:
    return transcript_segments_dir(date_str) / f"{video_id}.json"


def transcript_metadata_dir(date_str: str) -> Path:
    return transcript_dir(date_str) / "metadata"


def transcript_metadata_path(date_str: str, video_id: str) -> Path:
    return transcript_metadata_dir(date_str) / f"{video_id}.json"


def transcript_vtt_dir(date_str: str) -> Path:
    return transcript_dir(date_str) / "vtt"


def transcript_vtt_path(date_str: str, video_id: str) -> Path:
    return transcript_vtt_dir(date_str) / f"{video_id}.vtt"


def analysis_subtasks_dir(date_str: str) -> Path:
    return raw_day_dir(date_str) / "sub-analyses"


def video_subtasks_dir(date_str: str, video_id: str) -> Path:
    return analysis_subtasks_dir(date_str) / video_id


def downloaded_audio_dir(date_str: str) -> Path:
    return raw_day_dir(date_str) / "audio" / "downloaded"


def normalized_audio_dir(date_str: str) -> Path:
    return raw_day_dir(date_str) / "audio" / "normalized"


def normalized_audio_path(date_str: str, video_id: str) -> Path:
    return normalized_audio_dir(date_str) / f"{video_id}.wav"


def report_day_dir(date_str: str) -> Path:
    return REPORTS_DIR / date_str


def research_day_dir(date_str: str) -> Path:
    return RESEARCH_DIR / date_str


def claims_manifest_path(date_str: str) -> Path:
    return raw_day_dir(date_str) / "claims.json"


def briefing_path(date_str: str) -> Path:
    return report_day_dir(date_str) / "briefing.md"


def briefing_english_path(date_str: str) -> Path:
    return report_day_dir(date_str) / "briefing.en.md"


def briefing_german_path(date_str: str) -> Path:
    return report_day_dir(date_str) / "briefing.de.md"


def briefing_metadata_path(date_str: str) -> Path:
    return report_day_dir(date_str) / "briefing.json"


def job_path(claim_id: str) -> Path:
    return JOBS_DIR / f"{claim_id}.json"


def pipeline_job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def research_result_path(date_str: str, claim_id: str) -> Path:
    return research_day_dir(date_str) / claim_id / "result.md"


def research_result_json_path(date_str: str, claim_id: str) -> Path:
    return research_day_dir(date_str) / claim_id / "result.json"


def research_search_results_path(date_str: str, claim_id: str) -> Path:
    return research_day_dir(date_str) / claim_id / "google-search.json"
