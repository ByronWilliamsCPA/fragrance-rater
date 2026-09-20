import type { Access, Capabilities } from '../api/types'
import { roleLabelFor } from '../api/types'
import type { Route } from '../routing/routes'

type WelcomePageProps = {
  access: Access
  capabilities: Capabilities
  navigate: (route: Route) => void
}

export function WelcomePage({ access, capabilities, navigate }: WelcomePageProps) {
  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Fragrance Rater</h2>
        </div>
      </div>
      <p className="hero-statement">
        Learn your fragrance taste by measuring what you actually respond to.
      </p>
      <p>
        Welcome, {access.username}, you're set up as {roleLabelFor(capabilities)}.
      </p>
      <div className="button-row">
        <button onClick={() => navigate('workspace')}>Continue</button>
        <button className="secondary" onClick={() => navigate('about')}>
          Read the full methodology
        </button>
      </div>
    </section>
  )
}
