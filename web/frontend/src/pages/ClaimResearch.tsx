import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { getClaimDetail, queueResearch } from '../lib/api'
import type { ClaimDetailResponse } from '../types'
import { ResearchSidebar } from '../components/ResearchSidebar'

export function ClaimResearchPage() {
  const { date = '', claimId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [detail, setDetail] = useState<ClaimDetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    if (!date || !claimId) {
      return
    }
    getClaimDetail(date, claimId).then(setDetail).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load claim research.')
    })
  }, [date, claimId])

  useEffect(() => {
    if (!detail?.job || (detail.job.status !== 'queued' && detail.job.status !== 'researching')) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const payload = await getClaimDetail(date, claimId)
        setDetail(payload)
      } catch {
        // Ignore transient polling failures.
      }
    }, 3000)

    return () => window.clearInterval(timer)
  }, [claimId, date, detail?.job])

  async function verifyClaim() {
    if (!date || !claimId) {
      return
    }
    setNote(null)
    setError(null)
    try {
      await queueResearch(claimId, date)
      setNote('Verification queued.')
      const payload = await getClaimDetail(date, claimId)
      setDetail(payload)
    } catch (triggerError) {
      setError(triggerError instanceof Error ? triggerError.message : 'Unable to queue research.')
    }
  }

  function goBack() {
    const from = location.state?.from
    if (typeof from === 'string' && from) {
      navigate(from)
      return
    }
    navigate(`/briefing/${date}`)
  }

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  if (!detail) {
    return <p className="empty-state">Loading claim research...</p>
  }

  const status = detail.job?.status ?? detail.claim.status

  return (
    <article>
      <header className="claim-page-header">
        <button className="editorial-button" onClick={goBack} type="button">
          Back to article
        </button>
        <div className="article-meta">
          <span>{detail.date}</span>
          <span>{status}</span>
        </div>
        <h1 className="claim-page-title">{detail.claim.text}</h1>
        <p className="briefing-kicker">
          {detail.claim.speaker} ·{' '}
          <a href={detail.claim.source_url} rel="noreferrer" target="_blank">
            {detail.claim.source_title}
          </a>
        </p>
        <div className="claim-page-actions">
          {!detail.result ? (
            <button className="editorial-button editorial-button--boxed" onClick={verifyClaim} type="button">
              {status === 'failed' ? 'Retry verification' : status === 'queued' || status === 'researching' ? 'Verification running' : 'Verify claim'}
            </button>
          ) : null}
          <Link className="editorial-link" to="/archive">
            View claim archive
          </Link>
        </div>
        {note ? <div className="form-note">{note}</div> : null}
      </header>

      {status === 'queued' || status === 'researching' ? (
        <p className="empty-state">Research is in progress. This page will refresh automatically.</p>
      ) : null}

      {detail.result ? <ResearchSidebar result={detail.result} /> : null}
    </article>
  )
}
