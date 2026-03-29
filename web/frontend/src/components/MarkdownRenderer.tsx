import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { Claim } from '../types'
import { ClaimInline } from './ClaimInline'

type MarkdownRendererProps = {
  markdown: string
  claims: Claim[]
  date: string
}

type Segment =
  | { kind: 'markdown'; value: string }
  | { kind: 'claim'; claimId: string; text: string }

const CLAIM_PATTERN = /\[\[claim:([^|\]]+)\|([^\]]+)\]\]/g

function splitMarkdown(markdown: string): Segment[] {
  const segments: Segment[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null = CLAIM_PATTERN.exec(markdown)

  while (match) {
    if (match.index > lastIndex) {
      segments.push({ kind: 'markdown', value: markdown.slice(lastIndex, match.index) })
    }
    segments.push({ kind: 'claim', claimId: match[1], text: match[2] })
    lastIndex = match.index + match[0].length
    match = CLAIM_PATTERN.exec(markdown)
  }

  if (lastIndex < markdown.length) {
    segments.push({ kind: 'markdown', value: markdown.slice(lastIndex) })
  }

  return segments
}

export function MarkdownRenderer({ markdown, claims, date }: MarkdownRendererProps) {
  const claimMap = new Map(claims.map((claim) => [claim.id, claim]))
  const segments = splitMarkdown(markdown)

  return (
    <div className="editorial-markdown">
      {segments.map((segment, index) => {
        if (segment.kind === 'claim') {
          const claim = claimMap.get(segment.claimId)
          if (!claim) {
            return (
              <p className="claim-inline" key={`${segment.claimId}-${index}`}>
                {segment.text}
              </p>
            )
          }
          return <ClaimInline claim={claim} date={date} key={`${segment.claimId}-${index}`} />
        }

        return (
          <ReactMarkdown key={`md-${index}`} remarkPlugins={[remarkGfm]}>
            {segment.value}
          </ReactMarkdown>
        )
      })}
    </div>
  )
}
