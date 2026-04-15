export type ClaimStatus = 'pending' | 'queued' | 'researching' | 'completed' | 'failed'

export type Claim = {
  id: string
  text: string
  speaker: string
  source_video_id: string
  source_url: string
  source_title: string
  timestamp_label?: string | null
  topic_tags: string[]
  tickers: string[]
  status: ClaimStatus
  research_result_path?: string | null
  verdict: 'supporting' | 'mixed' | 'counter' | 'unknown'
}

export type BriefingMetadata = {
  date: string
  title: string
  summary: string
  claim_count: number
  updated_at: string
}

export type BriefingResponse = {
  date: string
  markdown: string
  markdowns: Record<string, string>
  default_language: 'de' | 'en'
  available_languages: Array<'de' | 'en'>
  metadata: BriefingMetadata | null
  claims: Claim[]
}

export type ResearchJob = {
  claim_id: string
  date: string
  claim_text: string
  source_video: string
  speaker: string
  status: 'queued' | 'researching' | 'completed' | 'failed'
  backend: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
  result_path?: string | null
}

export type ResearchResult = {
  claim_id: string
  date: string
  verdict: 'supporting' | 'mixed' | 'counter' | 'unknown'
  summary: string
  supporting_evidence: string[]
  counter_evidence: string[]
  sources: string[]
  markdown: string
}

export type GoogleSearchResult = {
  title: string
  link: string
  snippet: string
}

export type PipelineJob = {
  id: string
  date: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export type StatusResponse = {
  pipeline: {
    last_run_at?: string | null
    last_run_date?: string | null
    last_error?: string | null
    worker_running: boolean
    active_pipeline_job_id?: string | null
  }
  manual_runs: {
    queued: number
    running: number
    completed: number
    failed: number
    latest: PipelineJob | null
  }
  jobs: {
    queued: number
    researching: number
    completed: number
    failed: number
  }
}

export type AppSettings = {
  youtube: {
    api_key: string
    channels: Array<{ id: string; name: string; focus: string[]; source_input?: string | null }>
    max_videos_per_channel: number
    lookback_hours: number
  }
  agent: {
    backend: string
    model: string
    capital_iq_model: string
    max_concurrent_research: number
    research_timeout_seconds: number
  }
  google_search: {
    api_key: string
    engine_id: string
  }
  capital_iq: {
    username: string
    password: string
  }
  watchlist: {
    stocks: Array<{ ticker: string; name: string; notes: string }>
    valuation_refresh_days: number
  }
  transcription: {
    backend: 'captions_only' | 'captions_then_local' | 'local_only'
    model: string
    device: string
    compute_type: string
    language: string
    caption_languages: string[]
    vad_filter: boolean
    beam_size: number
    temperature: number
    condition_on_previous_text: boolean
    keep_audio: boolean
    max_duration_minutes: number
    output_formats: Array<'txt' | 'json' | 'vtt'>
  }
  schedule: {
    fetch_cron: string
    timezone: string
  }
  site: {
    title: string
    subtitle: string
    accent_color: string
  }
}

export type ResolvedChannel = {
  id: string
  name: string
  source_input: string
  url: string
}

export type ClaimListItem = Claim & {
  date: string
}

export type ClaimDetailResponse = {
  date: string
  claim: Claim
  job: ResearchJob | null
  result: ResearchResult | null
}
