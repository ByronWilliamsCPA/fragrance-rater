import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Access, EnrollmentSummary, Program, ProgramMember } from '../api/types'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'
import type { Navigate } from '../routing/routes'

/**
 * The single group_name shared by a program's memberships, or "Mixed" when
 * split. Mirrors CalibrationService.group_name_summary on the backend
 * (calibration_service.py), but runs client-side against ProgramMember rows
 * fetched from the manager-only members endpoint: see the plan's "Spec
 * clarifications" section for why this isn't a second backend enrichment.
 */
function dominantGroupName(members: ProgramMember[]): string {
  if (members.length === 0) return 'Mixed'
  const names = new Set(members.map((member) => member.group_name))
  return names.size === 1 ? [...names][0] : 'Mixed'
}

type Candidate = { program: Program; groupName: string }

export function CalibrationChoiceScreen({
  assignments,
  programs,
  access,
  navigate,
  onBrowse,
}: {
  assignments: EnrollmentSummary[]
  programs: Program[]
  access: Access
  navigate: Navigate
  onBrowse: () => void
}) {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const task = useTask()

  useEffect(() => {
    if (!access.manager) return
    const enrolledProgramIds = new Set(assignments.map((entry) => entry.program_id))
    const openPrograms = programs.filter(
      (program) => program.status === 'active' && !enrolledProgramIds.has(program.id)
    )
    let current = true
    void task.run(async () => {
      const settled = await Promise.allSettled(
        openPrograms.map(async (program) => {
          const response = await api.get<ProgramMember[]>(
            `/calibration/programs/${program.id}/members`
          )
          return { program, groupName: dominantGroupName(response.data) }
        })
      )
      const fulfilled: Candidate[] = []
      let firstRejection: unknown
      for (const result of settled) {
        if (result.status === 'fulfilled') fulfilled.push(result.value)
        else firstRejection ??= result.reason
      }
      if (current) setCandidates(fulfilled)
      // A single failing candidate lookup (403/404/network blip) must not
      // discard every other candidate the manager could still act on; rethrow
      // only after the fulfilled ones are kept, so task.run's catch reports
      // the failure without wiping state set above.
      if (firstRejection !== undefined) throw firstRejection
    })
    return () => {
      current = false
    }
    // assignments/programs are the effect's only real inputs; access.manager
    // gates whether it runs at all. navigate/onBrowse are used outside the
    // effect body, so react-hooks/exhaustive-deps does not flag them here.
    // task is a fresh object every render (useTask isn't memoized), so it is
    // intentionally left out, matching the same pattern in
    // GuidedCalibrationFlow.tsx and CalibrationPage.tsx.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [access.manager, assignments, programs])

  function openEnrollFor(programId: string) {
    navigate('programs', false, { program: programId })
  }

  if (!access.manager) {
    return (
      <section>
        <div className="page-heading">
          <h2>Your calibration</h2>
        </div>
        <p>Nothing new is assigned right now.</p>
        <button className="secondary" onClick={onBrowse}>
          Browse assignments manually instead
        </button>
      </section>
    )
  }

  const baseline = candidates.find((candidate) => candidate.groupName === 'Baseline')
  const components = candidates.filter((candidate) => candidate.groupName !== 'Baseline')

  return (
    <section>
      <div className="page-heading">
        <h2>Your calibration</h2>
      </div>
      <p>Everything currently assigned is revealed. Start something new, or browse it again.</p>
      <FeedbackBanner error={task.error} notice={task.notice} />
      {baseline && (
        <button onClick={() => openEnrollFor(baseline.program.id)}>
          Start a new full baseline
        </button>
      )}
      {components.map((candidate) => (
        <button key={candidate.program.id} onClick={() => openEnrollFor(candidate.program.id)}>
          Redo &quot;{candidate.groupName}&quot;
        </button>
      ))}
      {!baseline && components.length === 0 && <p>Nothing new is assigned right now.</p>}
      <button className="secondary" onClick={onBrowse}>
        Browse assignments manually instead
      </button>
    </section>
  )
}
