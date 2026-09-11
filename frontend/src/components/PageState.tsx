import type { ReactNode } from 'react'

export function LoadingState({ label = 'Loading your fragrance journal…' }: { label?: string }) {
  return (
    <section className="page-state" aria-live="polite" aria-busy="true">
      <div className="loading-mark" aria-hidden="true" />
      <p>{label}</p>
    </section>
  )
}

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <section className="page-state">
      <h2>We could not load this page</h2>
      <p role="alert">{message}</p>
      <button onClick={retry}>Try again</button>
    </section>
  )
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}
