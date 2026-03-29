import { useEffect, useState } from 'react'

import { getResearch, queueResearch } from '../lib/api'
import type { Claim, ResearchResult } from '../types'
import { ResearchSidebar } from './ResearchSidebar'

type ClaimInlineProps = {
  claim: Claim
  date: string
}

export function ClaimInline({ claim, date }: ClaimInlineProps) {
  const [status, setStatus] = useState(claim.status)
  const [result, setResult] = useState<ResearchResult | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setStatus(claim.status)
  }, [claim.status])

  useEffect(() => {
    if (status !== 'researching' && status !== 'queued') {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const payload = await getResearch(claim.id)
        setStatus(payload.job.status)
        if (payload.result) {
          setResult(payload.result)
          setOpen(true)
        }
      } catch {
        // Ignore transient polling failures.
      }
    }, 3000)

    return () => window.clearInterval(timer)
  }, [claim.id, status])

  async function triggerResearch() {
    setError(null)
    try {
      const payload = await queueResearch(claim.id, date)
      setStatus(payload.job.status)
    } catch (triggerError) {
      setError(triggerError instanceof Error ? triggerError.message : 'Unable to queue research.')
    }
  }

  async function toggleOpen() {
    if (!result && status === 'completed') {
      const payload = await getResearch(claim.id)
      if (payload.result) {
        setResult(payload.result)
      }
    }
    setOpen((value) => !value)
  }

  const isActionable = status === 'pending' || status === 'failed'

  return (
    <div className="claim-block">
      <div className="claim-inline">
        <span className={`claim-inline__text claim-inline__text--${status}`}>{claim.text}</span>
        {isActionable ? (
          <button className="claim-inline__action" onClick={triggerResearch} type="button">
            {status === 'failed' ? 'retry' : 'verify'}
          </button>
        ) : status === 'researching' || status === 'queued' ? (
          <span className="claim-inline__meta">researching...</span>
        ) : (
          <button className="claim-inline__action" onClick={toggleOpen} type="button">
            {open ? 'hide analysis' : 'view analysis'}
          </button>
        )}
      </div>
      {error ? <div className="form-note form-note--error">{error}</div> : null}
      {open && result ? <ResearchSidebar result={result} /> : null}
    </div>
  )
}
