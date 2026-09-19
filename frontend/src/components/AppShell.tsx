import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react'
import type { Access, Capabilities } from '../api/types'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { navigationItems, type Route } from '../routing/routes'
import { ThemeToggle } from './ThemeToggle'

type AppShellProps = {
  access: Access
  capabilities: Capabilities
  route: Route
  navigate: (route: Route) => void
  children: ReactNode
}

export function AppShell({ access, capabilities, route, navigate, children }: AppShellProps) {
  const mainContent = useRef<HTMLElement>(null)
  const previousRoute = useRef(route)
  const aboutNavItem = navigationItems.find((item) => item.route === 'about')
  const role = capabilities.canManagePrograms
    ? 'Manager'
    : capabilities.canRecordCalibration
      ? 'Recorder'
      : 'Participant'

  useDocumentTitle(route)

  useEffect(() => {
    if (previousRoute.current !== route) mainContent.current?.focus()
    previousRoute.current = route
  }, [route])

  function follow(event: MouseEvent<HTMLAnchorElement>, destination: Route) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return
    event.preventDefault()
    navigate(destination)
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header__brand">
          <p className="eyebrow">Personal scent journal</p>
          <h1 className="app-header__title">Fragrance Rater</h1>
          <p className="app-header__tagline">Explore your preferences, one encounter at a time.</p>
        </div>
        <div className="app-header__aside">
          <ThemeToggle />
          {/*
            The value of each row is kept in its own element so the
            visually-hidden prefix names it for a screen reader without
            becoming part of the visible string.
          */}
          <div className="identity">
            <span className="identity__name">
              <span className="visually-hidden">Signed in as </span>
              <span>{access.username || 'Verified family account'}</span>
            </span>
            <strong>
              <span className="visually-hidden">Role: </span>
              <span>{role}</span>
            </strong>
          </div>
        </div>
      </header>
      <nav className="app-nav" aria-label="Main navigation">
        {navigationItems
          .filter(
            (item) => !item.hiddenFromNav && (!item.managerOnly || capabilities.canManagePrograms)
          )
          .map((item) => (
            <a
              key={item.route}
              href={item.path}
              aria-current={route === item.route ? 'page' : undefined}
              onClick={(event) => follow(event, item.route)}
            >
              {item.label}
            </a>
          ))}
      </nav>
      <main ref={mainContent} id="main-content" tabIndex={-1}>
        {children}
      </main>
      <footer className="app-footer">
        <p>Ordinary encounters and controlled observations share one preference history.</p>
        {aboutNavItem && (
          <p>
            <a href={aboutNavItem.path} onClick={(event) => follow(event, aboutNavItem.route)}>
              About this project
            </a>
          </p>
        )}
      </footer>
    </div>
  )
}
