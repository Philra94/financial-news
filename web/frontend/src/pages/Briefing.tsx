import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { MarkdownRenderer } from '../components/MarkdownRenderer'
import { getBriefing } from '../lib/api'
import { formatReadableDate } from '../lib/date'
import type { BriefingResponse } from '../types'

export function BriefingPage() {
  const { date = '' } = useParams()
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null)
  const [language, setLanguage] = useState<'de' | 'en'>('de')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      return
    }
    getBriefing(date)
      .then((payload) => {
        setBriefing(payload)
        setLanguage(payload.default_language)
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load briefing.')
      })
  }, [date])

  if (error) {
    return <p className="empty-state">{error}</p>
  }

  if (!briefing) {
    return <p className="empty-state">Loading briefing...</p>
  }

  const selectedMarkdown = briefing.markdowns[language] ?? briefing.markdown

  return (
    <article>
      <header className="article-chrome">
        <div className="article-meta">
          <span>{formatReadableDate(briefing.date)}</span>
          {briefing.available_languages.length > 1 ? (
            <div className="language-switch" aria-label="Briefing language">
              {briefing.available_languages.map((option) => (
                <button
                  className={`language-switch__button ${language === option ? 'language-switch__button--active' : ''}`}
                  key={option}
                  onClick={() => setLanguage(option)}
                  type="button"
                >
                  {option.toUpperCase()}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </header>
      <MarkdownRenderer claims={briefing.claims} date={briefing.date} markdown={selectedMarkdown} />
    </article>
  )
}
