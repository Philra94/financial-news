import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { getClaimDetail, queueResearch } from '../lib/api'
import type { Claim } from '../types'

type ClaimInlineProps = {
  claim: Claim
  date: string
  label?: string
}

export function ClaimInline({ claim, date, label }: ClaimInlineProps) {
  const location = useLocation()
  const target = `/claim/${date}/${claim.id}`

  const [status, setStatus] = useState(claim.status)

  useEffect(() => {
    setStatus(claim.status)
  }, [claim.status])

  useEffect(() => {
    if (status !== 'queued' && status !== 'researching') {
      return
    }

    let cancelled = false
    const timer = window.setInterval(async () => {
      try {
        const payload = await getClaimDetail(date, claim.id)
        if (!cancelled) {
          setStatus(payload.job?.status ?? payload.claim.status)
        }
      } catch {
        // Keep the current state if polling fails.
      }
    }, 3000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [claim.id, date, status])

  async function handleVerifyClick() {
    if (status === 'queued' || status === 'researching' || status === 'completed') {
      return
    }

    setStatus('queued')

    try {
      const payload = await queueResearch(claim.id, date)
      setStatus(payload.job.status)
    } catch {
      setStatus('failed')
    }
  }

  const busy = status === 'queued' || status === 'researching'
  const chipLabel = busy ? <span aria-hidden="true" className="claim-inline__spinner" /> : 'V'
  const chipTitle =
    status === 'completed'
      ? 'Open verification'
      : status === 'failed'
        ? 'Retry verification'
        : busy
          ? 'Verification in progress'
          : 'Verify claim'

  return (
    <span className={`claim-inline claim-inline--${status}`}>
      <Link
        className="claim-inline__text"
        state={{ from: location.pathname }}
        to={target}
      >
        {label ?? claim.text}
      </Link>
      {status === 'completed' ? (
        <Link aria-label={chipTitle} className="claim-inline__chip" state={{ from: location.pathname }} title={chipTitle} to={target}>
          {chipLabel}
        </Link>
      ) : (
        <button
          aria-label={chipTitle}
          className="claim-inline__chip"
          disabled={busy}
          onClick={handleVerifyClick}
          title={chipTitle}
          type="button"
        >
          {chipLabel}
        </button>
      )}
    </span>
  )
}
