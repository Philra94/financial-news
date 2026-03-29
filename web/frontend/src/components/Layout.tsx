import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

type LayoutProps = {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const navClassName = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : '')

  return (
    <div className="site-shell">
      <header className="masthead">
        <div className="masthead-kicker">Agentic Financial News</div>
        <div className="masthead-title">Morning Briefing</div>
        <nav className="top-nav" aria-label="Primary">
          <NavLink className={navClassName} to="/">
            Briefing
          </NavLink>
          <NavLink className={navClassName} to="/archive">
            Archive
          </NavLink>
          <NavLink className={navClassName} to="/settings">
            Settings
          </NavLink>
        </nav>
      </header>
      <main className="page-container">{children}</main>
    </div>
  )
}
