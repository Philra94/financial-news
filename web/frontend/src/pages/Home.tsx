import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getLatestBriefing } from '../lib/api'
import type { BriefingResponse } from '../types'
import { MarkdownRenderer } from '../components/MarkdownRenderer'

export function Home() {
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLatestBriefing().then(setBriefing).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load briefing.')
    })
  }, [])

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
        <p className="archive-link-wrap">
          <Link to="/archive">Browse archive</Link>
        </p>
      </header>
      <MarkdownRenderer claims={briefing.claims} date={briefing.date} markdown={briefing.markdown} />
    </article>
  )
}
