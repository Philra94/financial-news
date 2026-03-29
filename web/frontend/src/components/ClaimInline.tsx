import { Link, useLocation } from 'react-router-dom'

import type { Claim } from '../types'

type ClaimInlineProps = {
  claim: Claim
  date: string
  label?: string
}

export function ClaimInline({ claim, date, label }: ClaimInlineProps) {
  const location = useLocation()
  const target = `/claim/${date}/${claim.id}`
  return (
    <span className="claim-inline">
      <Link
        className={`claim-inline__text claim-inline__text--${claim.status}`}
        state={{ from: location.pathname }}
        to={target}
      >
        {label ?? claim.text}
      </Link>
      <Link className="claim-inline__chip" state={{ from: location.pathname }} to={target}>
        verify
      </Link>
    </span>
  )
}
