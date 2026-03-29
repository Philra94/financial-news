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
        <div className="masthead-inner">
          <div className="masthead-copy">
            <div className="masthead-kicker">Local financial edition</div>
            <div className="masthead-title">Agentic Financial News</div>
            <p className="masthead-summary">
              A local editorial feed built from your selected market channels, with research available on demand.
            </p>
          </div>
          <nav className="top-nav" aria-label="Primary">
            <NavLink className={navClassName} to="/">
              Latest
            </NavLink>
            <NavLink className={navClassName} to="/archive">
              Archive
            </NavLink>
            <NavLink className={navClassName} to="/settings">
              Settings
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="page-container">{children}</main>
    </div>
  )
}
