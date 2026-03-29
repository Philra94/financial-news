import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { ResearchResult } from '../types'

type ResearchSidebarProps = {
  result: ResearchResult
}

export function ResearchSidebar({ result }: ResearchSidebarProps) {
  return (
    <section className="research-sidebar">
      <div className="research-sidebar__label">Analysis</div>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.markdown}</ReactMarkdown>
    </section>
  )
}
