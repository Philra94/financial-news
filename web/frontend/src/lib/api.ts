import type { AppSettings, BriefingMetadata, BriefingResponse, ResearchJob, ResearchResult } from '../types'

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
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
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

export function queueResearch(claimId: string, date: string): Promise<{ queued: boolean; job: ResearchJob }> {
  return request(`/research/${claimId}`, {
    method: 'POST',
    body: JSON.stringify({ date }),
  })
}

export function getResearch(claimId: string): Promise<{ job: ResearchJob; result: ResearchResult | null }> {
  return request(`/research/${claimId}`)
}
