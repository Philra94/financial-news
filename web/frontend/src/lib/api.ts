import type {
  AppSettings,
  BriefingMetadata,
  BriefingResponse,
  ClaimDetailResponse,
  ClaimListItem,
  GoogleSearchResult,
  PipelineJob,
  ResolvedChannel,
  ResearchJob,
  ResearchResult,
  StatusResponse,
} from '../types'

const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const raw = await response.text()
    try {
      const parsed = JSON.parse(raw) as { detail?: string }
      throw new Error(parsed.detail || `Request failed: ${response.status}`)
    } catch {
      throw new Error(raw || `Request failed: ${response.status}`)
    }
  }

  return (await response.json()) as T
}

export function getBriefings(): Promise<BriefingMetadata[]> {
  return request<BriefingMetadata[]>('/briefings')
}

export function getLatestBriefing(): Promise<BriefingResponse> {
  return request<BriefingResponse>('/briefings/latest')
}

export function getBriefing(date: string): Promise<BriefingResponse> {
  return request<BriefingResponse>(`/briefings/${date}`)
}

export function getSettings(): Promise<AppSettings> {
  return request<AppSettings>('/settings')
}

export function putSettings(payload: AppSettings): Promise<AppSettings> {
  return request<AppSettings>('/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function resolveChannel(apiKey: string, channelInput: string): Promise<ResolvedChannel> {
  return request<ResolvedChannel>('/settings/resolve-channel', {
    method: 'POST',
    body: JSON.stringify({
      api_key: apiKey,
      channel_input: channelInput,
    }),
  })
}

export function testGoogleSearch(
  apiKey: string,
  fallbackApiKey: string,
  engineId: string,
): Promise<{ ok: boolean; results: GoogleSearchResult[] }> {
  return request('/settings/test-google-search', {
    method: 'POST',
    body: JSON.stringify({
      api_key: apiKey,
      fallback_api_key: fallbackApiKey,
      engine_id: engineId,
    }),
  })
}

export function getClaimsIndex(): Promise<ClaimListItem[]> {
  return request<ClaimListItem[]>('/claims')
}

export function getClaimDetail(date: string, claimId: string): Promise<ClaimDetailResponse> {
  return request<ClaimDetailResponse>(`/claims/${date}/${claimId}`)
}

export function queueResearch(claimId: string, date: string): Promise<{ queued: boolean; job: ResearchJob }> {
  return request(`/research/${claimId}`, {
    method: 'POST',
    body: JSON.stringify({ date }),
  })
}

export function getResearch(claimId: string): Promise<{ job: ResearchJob; result: ResearchResult | null }> {
  return request(`/research/${claimId}`)
}

export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>('/status')
}

export function queuePipelineRun(date: string): Promise<{ queued: boolean; job: PipelineJob }> {
  return request('/run', {
    method: 'POST',
    body: JSON.stringify({ date }),
  })
}

export function getPipelineRun(jobId: string): Promise<{ job: PipelineJob }> {
  return request(`/run/${jobId}`)
}
