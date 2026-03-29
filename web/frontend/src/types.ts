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

export type AppSettings = {
  youtube: {
    api_key: string
    channels: Array<{ id: string; name: string; focus: string[] }>
    max_videos_per_channel: number
    lookback_hours: number
  }
  agent: {
    backend: string
    max_concurrent_research: number
    research_timeout_seconds: number
  }
  llm: {
    provider: 'openai' | 'anthropic'
    api_key: string
    model: string
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
