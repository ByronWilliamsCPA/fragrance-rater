import { useEffect } from 'react'
import './App.css'
import { AppShell } from './components/AppShell'
import { ErrorState, LoadingState } from './components/PageState'
import { useAppData } from './hooks/useAppData'
import { CalibrationPage } from './pages/CalibrationPage'
import { HomePage } from './pages/HomePage'
import { ProgramSetupPage } from './pages/ProgramSetupPage'
import { RatingsPage } from './pages/RatingsPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { useRoute } from './routing/routes'

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
      {route === 'home' && (
        <HomePage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          navigate={navigate}
        />
      )}
      {route === 'calibration' && (
        <CalibrationPage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
        />
      )}
      {route === 'recommendations' && <RecommendationsPage reviewers={appData.reviewers} />}
      {route === 'ratings' && <RatingsPage reviewers={appData.reviewers} />}
      {route === 'programs' && appData.capabilities.canManagePrograms && (
        <ProgramSetupPage
          programs={appData.programs}
          reviewers={appData.reviewers}
          reload={appData.reload}
        />
      )}
    </AppShell>
  )
}

export default App
