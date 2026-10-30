import { useEffect, useMemo } from 'react'
import { AppShell } from './components/AppShell'
import { ErrorState, LoadingState } from './components/PageState'
import { useAppData } from './hooks/useAppData'
import { AboutPage } from './pages/AboutPage'
import { CalibrationPage } from './pages/CalibrationPage'
import { CalibrationProtocolPage } from './pages/CalibrationProtocolPage'
import { EvidencePage } from './pages/EvidencePage'
import { HouseIntakePage } from './pages/HouseIntakePage'
import { ProgramSetupPage } from './pages/ProgramSetupPage'
import { RatingsPage } from './pages/RatingsPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { WelcomePage } from './pages/WelcomePage'
import { WorkspacePage, type AssignmentSummary } from './pages/WorkspacePage'
import { assignmentLinkFor, programLinkFor, useRoute } from './routing/routes'

function App() {
  const appData = useAppData()
  const { route, query, navigate } = useRoute()
  const { assignments, programs, reviewers } = appData

  /**
   * The assignment/program/reviewer join, written once here instead of
   * re-derived inside a render loop from three unjoined arrays.
   *
   * Memoized because WorkspacePage fetches enrollment progress in an effect
   * keyed on this array.
   */
  const assignmentSummaries: AssignmentSummary[] = useMemo(
    () =>
      assignments.map((assignment) => ({
        assignment,
        program: programs.find((program) => program.id === assignment.program_id),
        reviewer: reviewers.find((reviewer) => reviewer.id === assignment.reviewer_id),
      })),
    [assignments, programs, reviewers]
  )

  const assignmentLink = useMemo(
    () =>
      assignmentLinkFor(
        query,
        assignments.map((assignment) => assignment.id)
      ),
    [assignments, query]
  )

  const programId = useMemo(
    () => programLinkFor(query, programs.map((program) => program.id)),
    [programs, query]
  )

  const { canManagePrograms, isHouseContributor } = appData.capabilities

  useEffect(() => {
    if (appData.loading || appData.error) return
    // A house account has exactly one page; any other URL lands there.
    if (isHouseContributor && route !== 'house') navigate('house', true)
    else if (
      !isHouseContributor &&
      (route === 'programs' || route === 'house') &&
      !canManagePrograms
    )
      navigate('calibration', true)
  }, [canManagePrograms, isHouseContributor, appData.error, appData.loading, navigate, route])

  if (appData.loading) return <LoadingState />
  if (appData.error)
    return <ErrorState message={appData.error} retry={() => void appData.reload()} />

  if (isHouseContributor)
    return (
      <AppShell
        access={appData.access}
        capabilities={appData.capabilities}
        route="house"
        navigate={navigate}
      >
        <HouseIntakePage
          access={{
            username: appData.access.username,
            house: appData.access.house ?? null,
            manager: false,
          }}
        />
      </AppShell>
    )

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
          assignments={assignmentSummaries}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
      {route === 'calibration' && (
        <CalibrationPage
          assignments={assignments}
          programs={programs}
          reviewers={reviewers}
          access={appData.access}
          navigate={navigate}
          reload={appData.reload}
          initialAssignmentId={assignmentLink.initialAssignmentId}
          unresolvedAssignmentId={assignmentLink.unresolvedAssignmentId}
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
          initialProgramId={programId}
        />
      )}
      {route === 'house' && canManagePrograms && (
        <HouseIntakePage
          access={{ username: appData.access.username, house: null, manager: true }}
        />
      )}
      {route === 'about' && <AboutPage navigate={navigate} />}
      {route === 'evidence' && <EvidencePage navigate={navigate} />}
    </AppShell>
  )
}

export default App
