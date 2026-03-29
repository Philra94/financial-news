import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getBriefings, getClaimsIndex } from '../lib/api'
import type { BriefingMetadata, ClaimListItem } from '../types'

type ArchiveTab = 'articles' | 'claims'

export function Archive() {
  const [activeTab, setActiveTab] = useState<ArchiveTab>('articles')
  const [briefings, setBriefings] = useState<BriefingMetadata[]>([])
  const [claims, setClaims] = useState<ClaimListItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getBriefings(), getClaimsIndex()])
      .then(([briefingItems, claimItems]) => {
        setBriefings(briefingItems)
        setClaims(claimItems)
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load archive.')
      })
  }, [])

  const visibleClaims = useMemo(
    () => claims.filter((item) => item.status === 'completed' || item.status === 'queued' || item.status === 'researching'),
    [claims],
  )

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  return (
    <section>
      <div className="section-label">Archive</div>
      <h1 className="briefing-title">Archive</h1>
      <p className="page-lead">Browse past editions or jump straight into completed claim verification.</p>
      <div className="archive-tabs" role="tablist" aria-label="Archive views">
        <button
          aria-selected={activeTab === 'articles'}
          className={`archive-tab ${activeTab === 'articles' ? 'archive-tab--active' : ''}`}
          onClick={() => setActiveTab('articles')}
          role="tab"
          type="button"
        >
          Articles
        </button>
        <button
          aria-selected={activeTab === 'claims'}
          className={`archive-tab ${activeTab === 'claims' ? 'archive-tab--active' : ''}`}
          onClick={() => setActiveTab('claims')}
          role="tab"
          type="button"
        >
          Claims
        </button>
      </div>
      <div className="archive-list">
        {activeTab === 'articles'
          ? briefings.map((item) => (
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
            ))
          : visibleClaims.map((item) => (
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
                <div className="archive-item__claims">{item.status === 'completed' ? 'verified' : 'in progress'}</div>
              </article>
            ))}
        {activeTab === 'articles' && briefings.length === 0 ? <p className="empty-state">No articles available yet.</p> : null}
        {activeTab === 'claims' && visibleClaims.length === 0 ? (
          <p className="empty-state">No completed or in-progress claims available yet.</p>
        ) : null}
      </div>
    </section>
  )
}
