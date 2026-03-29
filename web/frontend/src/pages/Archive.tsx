import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getBriefings } from '../lib/api'
import type { BriefingMetadata } from '../types'

export function Archive() {
  const [briefings, setBriefings] = useState<BriefingMetadata[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getBriefings().then(setBriefings).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load archive.')
    })
  }, [])

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  return (
    <section>
      <div className="section-label">Archive</div>
      <h1 className="briefing-title">Previous editions</h1>
      <div className="archive-list">
        {briefings.map((item) => (
          <article className="archive-item" key={item.date}>
            <div className="archive-item__date">{item.date}</div>
            <div className="archive-item__body">
              <Link className="archive-item__title" to={`/briefing/${item.date}`}>
                {item.title}
              </Link>
              <p className="archive-item__summary">{item.summary}</p>
            </div>
            <div className="archive-item__claims">{item.claim_count} claims</div>
          </article>
        ))}
        {briefings.length === 0 ? <p className="empty-state">No briefings compiled yet.</p> : null}
      </div>
    </section>
  )
}
