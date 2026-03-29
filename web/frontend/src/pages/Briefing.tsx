import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { MarkdownRenderer } from '../components/MarkdownRenderer'
import { getBriefing } from '../lib/api'
import type { BriefingResponse } from '../types'

export function BriefingPage() {
  const { date = '' } = useParams()
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      return
    }
    getBriefing(date).then(setBriefing).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load briefing.')
    })
  }, [date])

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  if (!briefing) {
    return <p className="empty-state">Loading briefing...</p>
  }

  return (
    <article>
      <header className="briefing-header">
        <div className="section-label">Edition</div>
        <h1 className="briefing-title">{briefing.metadata?.title ?? 'Morning Briefing'}</h1>
        <p className="briefing-subtitle">{briefing.date}</p>
      </header>
      <MarkdownRenderer claims={briefing.claims} date={briefing.date} markdown={briefing.markdown} />
    </article>
  )
}
