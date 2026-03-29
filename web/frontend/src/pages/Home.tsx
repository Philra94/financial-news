import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getLatestBriefing, getPipelineRun, getStatus, queuePipelineRun } from '../lib/api'
import type { BriefingResponse, PipelineJob, StatusResponse } from '../types'
import { MarkdownRenderer } from '../components/MarkdownRenderer'

function describeRunStatus(job: PipelineJob | null): string {
  if (!job) {
    return 'No manual run has been queued yet.'
  }
  if (job.status === 'queued') {
    return 'Queued and waiting for the worker.'
  }
  if (job.status === 'running') {
    return 'Running now.'
  }
  if (job.status === 'failed') {
    return job.error ? `Failed: ${job.error}` : 'The last run failed.'
  }
  return 'Completed successfully.'
}

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
    const timer = window.setInterval(async () => {
      try {
        const payload = await getStatus()
        setStatus(payload)
        setManualRun((current) => {
          if (!current) {
            return payload.manual_runs.latest
          }
          if (payload.manual_runs.latest?.id === current.id) {
            return payload.manual_runs.latest
          }
          return current
        })
      } catch {
        // Keep the current status when background refresh fails.
      }
    }, 15000)

    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (
      !manualRun ||
      (manualRun.status !== 'queued' && manualRun.status !== 'running') ||
      !status?.pipeline.worker_running
    ) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const [runPayload, statusPayload] = await Promise.all([getPipelineRun(manualRun.id), getStatus()])
        setManualRun(runPayload.job)
        setStatus(statusPayload)
      } catch {
        // Ignore transient polling failures.
      }
    }, 3000)

    return () => window.clearInterval(timer)
  }, [manualRun, status?.pipeline.worker_running])

  useEffect(() => {
    if (manualRun?.status !== 'completed') {
      return
    }
    getLatestBriefing().then(setBriefing).catch(() => {
      // Keep the previous briefing if refresh fails.
    })
  }, [manualRun?.status])

  async function handleManualRun() {
    if (manualRun?.status === 'queued' || manualRun?.status === 'running') {
      return
    }
    const targetDate = new Date().toISOString().slice(0, 10)
    setManualRunMessage(null)
    try {
      const payload = await queuePipelineRun(targetDate)
      setManualRun(payload.job)
      setManualRunMessage('Manual run queued. It will start as soon as the worker picks it up.')
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

  const manualRunBusy = manualRun?.status === 'queued' || manualRun?.status === 'running'
  const workerLabel = status?.pipeline.worker_running ? 'Connected' : 'Offline'
  const runLabel = manualRun ? manualRun.status : 'idle'

  return (
    <article>
      <header className="article-chrome">
        <div className="article-meta">
          <span>{briefing.date}</span>
          <span>{briefing.claims.length} researchable claims</span>
        </div>
        <details className="desk-menu">
          <summary className="desk-menu__summary">Desk</summary>
          <div className="desk-menu__panel">
            <div className="desk-menu__actions">
              <button
                className="editorial-button editorial-button--boxed"
                disabled={manualRunBusy}
                onClick={handleManualRun}
                type="button"
              >
                {manualRun?.status === 'running'
                  ? 'Briefing running'
                  : manualRun?.status === 'queued'
                    ? 'Briefing queued'
                    : 'Run briefing now'}
              </button>
              <Link className="editorial-link" to="/archive">
                Browse archive
              </Link>
            </div>
            <div className="desk-menu__status">
              <div className="status-strip__item">
                <span className="status-strip__label">Worker</span>
                <strong className="status-strip__value">{workerLabel}</strong>
              </div>
              <div className="status-strip__item">
                <span className="status-strip__label">Latest run</span>
                <strong className="status-strip__value">{runLabel}</strong>
              </div>
              <div className="status-strip__item">
                <span className="status-strip__label">Claims</span>
                <strong className="status-strip__value">{briefing.claims.length}</strong>
              </div>
            </div>
            <div className="manual-run-panel__meta">{describeRunStatus(manualRun)}</div>
            {!status?.pipeline.worker_running ? (
              <div className="form-note">The queue is ready, but the worker is currently offline.</div>
            ) : null}
            {manualRunMessage ? <div className="form-note">{manualRunMessage}</div> : null}
          </div>
        </details>
      </header>
      <MarkdownRenderer claims={briefing.claims} date={briefing.date} markdown={briefing.markdown} />
    </article>
  )
}
