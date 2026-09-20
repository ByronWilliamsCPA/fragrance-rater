import { useEffect } from 'react'
import type { Assignment } from './api/types'
import { AppShell } from './components/AppShell'
import { ErrorState, LoadingState } from './components/PageState'
import { useAppData } from './hooks/useAppData'
import { AboutPage } from './pages/AboutPage'
import { CalibrationPage } from './pages/CalibrationPage'
import { CalibrationProtocolPage } from './pages/CalibrationProtocolPage'
import { ProgramSetupPage } from './pages/ProgramSetupPage'
import { RatingsPage } from './pages/RatingsPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { WelcomePage } from './pages/WelcomePage'
import { WorkspacePage } from './pages/WorkspacePage'
import { useRoute } from './routing/routes'

/**
 * Validates the `assignment` query param against the assignments this
 * identity actually has, guarding against a stale bookmarked link to a
 * revoked assignment (which falls back to CalibrationPage's existing empty
 * "Choose assignment" state instead of erroring).
 */
function assignmentIdFromQuery(assignments: Assignment[]): string | undefined {
  const requested = new URLSearchParams(window.location.search).get('assignment')
  return requested && assignments.some((assignment) => assignment.id === requested)
    ? requested
    : undefined
}

function App() {
  const appData = useAppData()
  const { route, navigate } = useRoute()

  useEffect(() => {
    if (
      !appData.loading &&
      !appData.error &&
      route === 'programs' &&
      !appData.capabilities.canManagePrograms
    )
      navigate('calibration', true)
  }, [appData.capabilities.canManagePrograms, appData.error, appData.loading, navigate, route])

  if (appData.loading) return <LoadingState />
  if (appData.error)
    return <ErrorState message={appData.error} retry={() => void appData.reload()} />

  return (
    <AppShell
      access={appData.access}
      capabilities={appData.capabilities}
      route={route}
      navigate={navigate}
    >
      {route === 'welcome' && (
        <WelcomePage
          access={appData.access}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
      {route === 'workspace' && (
        <WorkspacePage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
      {route === 'calibration' && (
        <CalibrationPage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          navigate={navigate}
          initialAssignmentId={assignmentIdFromQuery(appData.assignments)}
        />
      )}
      {route === 'protocol' && <CalibrationProtocolPage navigate={navigate} />}
      {route === 'recommendations' && <RecommendationsPage reviewers={appData.reviewers} />}
      {route === 'ratings' && <RatingsPage reviewers={appData.reviewers} />}
      {route === 'programs' && appData.capabilities.canManagePrograms && (
        <ProgramSetupPage
          programs={appData.programs}
          reviewers={appData.reviewers}
          reload={appData.reload}
        />
      )}
      {route === 'about' && <AboutPage navigate={navigate} />}
    </AppShell>
  )
}

export default App
