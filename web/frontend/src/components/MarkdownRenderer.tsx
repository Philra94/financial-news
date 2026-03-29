import { Children } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { Claim } from '../types'
import { ClaimInline } from './ClaimInline'

type MarkdownRendererProps = {
  markdown: string
  claims: Claim[]
  date: string
}

const CLAIM_PATTERN = /\[\[claim:([^|\]]+)\|([^\]]+)\]\]/g

function normalizeClaims(markdown: string): string {
  return markdown.replace(CLAIM_PATTERN, (_match, claimId: string, text: string) => `[${text}](claim://${claimId})`)
}

export function MarkdownRenderer({ markdown, claims, date }: MarkdownRendererProps) {
  const claimMap = new Map(claims.map((claim) => [claim.id, claim]))

  return (
    <div className="editorial-markdown">
      <ReactMarkdown
        components={{
          a({ href, children }) {
            if (href?.startsWith('claim://')) {
              const claimId = href.replace('claim://', '')
              const claim = claimMap.get(claimId)
              const label = Children.toArray(children)
                .map((child) => (typeof child === 'string' ? child : ''))
                .join('')
              if (!claim) {
                return <span>{label}</span>
              }
              return <ClaimInline claim={claim} date={date} label={label} />
            }
            return (
              <a href={href}>
                {children}
              </a>
            )
          },
          img({ alt, src, title }) {
            return <img alt={alt ?? ''} className="editorial-markdown__image" loading="lazy" src={src} title={title} />
          },
        }}
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => url}
      >
        {normalizeClaims(markdown)}
      </ReactMarkdown>
    </div>
  )
}
