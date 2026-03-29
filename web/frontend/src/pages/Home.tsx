import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getLatestBriefing, getPipelineRun, getStatus, queuePipelineRun } from '../lib/api'
import type { BriefingResponse, PipelineJob, StatusResponse } from '../types'
import { MarkdownRenderer } from '../components/MarkdownRenderer'

export function Home() {
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [manualRun, setManualRun] = useState<PipelineJob | null>(null)
  const [manualRunMessage, setManualRunMessage] = useState<string | null>(null)

  useEffect(() => {
    getLatestBriefing().then(setBriefing).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load briefing.')
    })
    getStatus().then((payload) => {
      setStatus(payload)
      setManualRun(payload.manual_runs.latest)
    })
  }, [])

  useEffect(() => {
    if (!manualRun || (manualRun.status !== 'queued' && manualRun.status !== 'running')) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const payload = await getPipelineRun(manualRun.id)
        setManualRun(payload.job)
      } catch {
        // Ignore transient polling failures.
      }
    }, 3000)

    return () => window.clearInterval(timer)
  }, [manualRun])

  useEffect(() => {
    if (manualRun?.status !== 'completed') {
      return
    }
    getLatestBriefing().then(setBriefing).catch(() => {
      // Keep the previous briefing if refresh fails.
    })
  }, [manualRun?.status])

  async function handleManualRun() {
    const targetDate = new Date().toISOString().slice(0, 10)
    setManualRunMessage(null)
    try {
      const payload = await queuePipelineRun(targetDate)
      setManualRun(payload.job)
      setManualRunMessage('Manual run queued. The host worker will pick it up.')
    } catch (runError) {
      setManualRunMessage(runError instanceof Error ? runError.message : 'Unable to queue manual run.')
    }
  }

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  if (!briefing) {
    return <p className="empty-state">Loading the latest briefing...</p>
  }

  return (
    <article>
      <header className="briefing-header">
        <div className="section-label">Morning Briefing</div>
        <h1 className="briefing-title">{briefing.metadata?.title ?? 'Morning Briefing'}</h1>
        <p className="briefing-subtitle">
          {briefing.date} · {briefing.claims.length} researchable claims
        </p>
        <p className="briefing-kicker">
          Objective summary first, with quoted opinions preserved and research available on demand.
        </p>
        <div className="manual-run-panel">
          <button className="editorial-button editorial-button--boxed" onClick={handleManualRun} type="button">
            Run briefing now
          </button>
          <div className="manual-run-panel__meta">
            Worker: {status?.pipeline.worker_running ? 'running' : 'offline'}
            {manualRun ? ` · latest manual run: ${manualRun.status}` : ''}
          </div>
          {manualRunMessage ? <div className="form-note">{manualRunMessage}</div> : null}
        </div>
        <p className="archive-link-wrap">
          <Link to="/archive">Browse archive</Link>
        </p>
      </header>
      <MarkdownRenderer claims={briefing.claims} date={briefing.date} markdown={briefing.markdown} />
    </article>
  )
}
