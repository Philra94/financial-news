import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getClaimsIndex } from '../lib/api'
import type { ClaimListItem } from '../types'

export function Archive() {
  const [claims, setClaims] = useState<ClaimListItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getClaimsIndex().then(setClaims).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load claim archive.')
    })
  }, [])

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  return (
    <section>
      <div className="section-label">Archive</div>
      <h1 className="briefing-title">Claim archive</h1>
      <p className="page-lead">Browse extracted claims across editions and open the full verification page for each one.</p>
      <div className="archive-list">
        {claims.map((item) => (
          <article className="archive-item archive-item--claim" key={`${item.date}-${item.id}`}>
            <div className="archive-item__date">{item.date}</div>
            <div className="archive-item__body">
              <Link className="archive-item__title" state={{ from: '/archive' }} to={`/claim/${item.date}/${item.id}`}>
                {item.text}
              </Link>
              <p className="archive-item__summary">
                {item.speaker} · {item.source_title}
              </p>
            </div>
            <div className="archive-item__claims">{item.status}</div>
          </article>
        ))}
        {claims.length === 0 ? <p className="empty-state">No claims available yet.</p> : null}
      </div>
    </section>
  )
}
