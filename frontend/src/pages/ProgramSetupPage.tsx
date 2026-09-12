import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type {
  FragellaUsage,
  FragranceSummary,
  ManagerEnrollment,
  MappingRow,
  Metrics,
  OperationalEvent,
  OperationalStatus,
  Person,
  Program,
  ProgramMember,
} from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { EmptyState } from '../components/PageState'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'

type Props = { programs: Program[]; reviewers: Person[]; reload: () => Promise<void> }

const roles = [
  'UNIVERSAL_BASELINE',
  'HIDDEN_REPEAT',
  'HOLDOUT',
  'ACTIVE_LEARNING',
  'RETEST',
  'OWNED_VALIDATION',
  'OTHER',
]

const blockerText = {
  BLOTTER: 'Blotter responses remain',
  SKIN_PLAN: 'Skin plan is not finalized',
  SKIN: 'Planned skin responses remain',
}

function percentage(value: number | null): string {
  return value === null ? 'No denominator yet' : `${Math.round(value * 100)}%`
}

function asUtc(value: string): string {
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
}

function formatUtcDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { timeZone: 'UTC' }).format(new Date(asUtc(value)))
}

function formatUtcDateTime(value: string): string {
  return `${new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(asUtc(value)))} UTC`
}

export function ProgramSetupPage({ programs, reviewers, reload }: Props) {
  const [programId, setProgramId] = useState('')
  const [members, setMembers] = useState<ProgramMember[]>([])
  const [catalog, setCatalog] = useState<FragranceSummary[]>([])
  const [enrollments, setEnrollments] = useState<ManagerEnrollment[]>([])
  const [mapping, setMapping] = useState<MappingRow[]>([])
  const [selectedEnrollment, setSelectedEnrollment] = useState('')
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [events, setEvents] = useState<OperationalEvent[]>([])
  const [status, setStatus] = useState<OperationalStatus | null>(null)
  const [fragellaUsage, setFragellaUsage] = useState<FragellaUsage | null>(null)
  const task = useTask()
  const selectedProgram = programs.find((program) => program.id === programId)
  const reviewerNames = useMemo(
    () => new Map(reviewers.map((reviewer) => [reviewer.id, reviewer.name])),
    [reviewers]
  )

  useEffect(() => {
    setMembers([])
    if (!programId) return
    let current = true
    void task.run(async () => {
      const response = await api.get<ProgramMember[]>(`/calibration/programs/${programId}/members`)
      if (current) setMembers(response.data)
    })
    return () => {
      current = false
    }
    // Program selection is the only trigger; useTask is stable for this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programId])

  async function createProgram(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const response = await api.post<{ id: string }>('/calibration/programs', values)
    setProgramId(response.data.id)
    await reload()
    form.reset()
    task.setNotice('Draft created.')
  }

  async function searchCatalog(form: HTMLFormElement) {
    const query = String(new FormData(form).get('catalog_search') ?? '').trim()
    const response = await api.get<FragranceSummary[]>('/fragrances', {
      params: { q: query, limit: 20 },
    })
    setCatalog(response.data)
    task.setNotice(`${response.data.length} exact catalog version(s) found.`)
  }

  async function addMember(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.post(`/calibration/programs/${programId}/members`, {
      fragrance_id: values.fragrance_id,
      role: values.role,
      repeat_of_id: values.repeat_of_id || null,
      group_name: values.group_name,
      identity_evidence: values.identity_evidence,
      gtin: values.gtin || null,
    })
    const response = await api.get<ProgramMember[]>(`/calibration/programs/${programId}/members`)
    setMembers(response.data)
    form.reset()
    task.setNotice('Catalog version added to the draft.')
  }

  async function runFragellaLookup(membershipId: string) {
    // Reference lookup only: this never changes fragrance_name/brand/
    // concentration or membership evidence, and spends one of the
    // account's 20 monthly Fragella requests, so it only ever runs when
    // a manager clicks it here - never automatically.
    await api.post(`/calibration/programs/${programId}/members/${membershipId}/fragella-lookup`)
    const response = await api.get<ProgramMember[]>(`/calibration/programs/${programId}/members`)
    setMembers(response.data)
    task.setNotice('Fragella reference lookup recorded below.')
  }

  async function checkFragellaUsage() {
    const response = await api.get<FragellaUsage>('/calibration/fragella/usage')
    setFragellaUsage(response.data)
  }

  async function activate() {
    await api.post(`/calibration/programs/${programId}/activate`)
    await reload()
    task.setNotice('Definition locked. Future enrollments use this frozen version.')
  }

  async function enroll(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.post(`/calibration/programs/${programId}/enroll`, {
      reviewer_id: values.reviewer_id,
      recorder_usernames: String(values.recorders)
        .split(',')
        .map((username) => username.trim())
        .filter(Boolean),
      session_size: Number(values.session_size),
    })
    form.reset()
    task.setNotice('Evaluator enrolled; sessions and blind codes are ready.')
  }

  async function loadOperations() {
    const [enrollmentResponse, eventResponse, statusResponse] = await Promise.all([
      api.get<ManagerEnrollment[]>('/calibration/manager/enrollments'),
      api.get<OperationalEvent[]>('/recommendation-measurement/operational-events'),
      api.get<OperationalStatus>('/recommendation-measurement/operational-status'),
    ])
    setEnrollments(enrollmentResponse.data)
    setEvents(eventResponse.data)
    setStatus(statusResponse.data)
    task.setNotice('Pilot operations refreshed.')
  }

  async function loadMapping(enrollmentId: string) {
    setSelectedEnrollment(enrollmentId)
    setMapping([])
    if (!enrollmentId) return
    const response = await api.get<MappingRow[]>(`/calibration/enrollments/${enrollmentId}/mapping`)
    setMapping(response.data)
  }

  async function revealEnrollment(enrollmentId: string) {
    await api.post(`/calibration/enrollments/${enrollmentId}/reveal`)
    await loadOperations()
    task.setNotice('Identities revealed after all prerequisites passed.')
  }

  async function loadMetrics(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const params: Record<string, string> = {}
    if (values.window_start) params.window_start = `${String(values.window_start)}T00:00:00Z`
    if (values.window_end) params.window_end = `${String(values.window_end)}T23:59:59Z`
    const response = await api.get<Metrics>(
      `/recommendation-measurement/reviewers/${String(values.reviewer_id)}/metrics`,
      { params }
    )
    setMetrics(response.data)
    task.setNotice('Metrics calculated from the selected population and window.')
  }

  function downloadMetrics() {
    if (!metrics) return
    const href = URL.createObjectURL(
      new Blob([JSON.stringify(metrics, null, 2)], { type: 'application/json' })
    )
    const link = document.createElement('a')
    link.href = href
    link.download = `pilot-metrics-${metrics.window_end.slice(0, 10)}.json`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(href), 1000)
  }

  async function recordEvent(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.post('/recommendation-measurement/operational-events', {
      reviewer_id: values.reviewer_id,
      event_type: values.event_type,
      details: values.details || null,
    })
    await loadOperations()
    form.reset()
    task.setNotice('Operational event recorded.')
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MANAGER</div>
          <h2>Program setup</h2>
        </div>
        <span className="status-chip">Restricted</span>
      </div>
      <p>Build frozen programs, prepare blind labels, and monitor the family pilot.</p>
      <FeedbackBanner error={task.error} notice={task.notice} />

      <div className="manager-grid">
        <div>
          <h3>1. Program definition</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void task.run(() => createProgram(event.currentTarget))
            }}
          >
            <div className="fields fields-compact">
              <label>
                Name
                <input name="name" required />
              </label>
              <label>
                Version
                <input name="version" required />
              </label>
            </div>
            <label>
              Description
              <textarea name="description" />
            </label>
            <button disabled={task.busy}>Create draft</button>
          </form>
          {programs.length ? (
            <label>
              Program
              <select value={programId} onChange={(event) => setProgramId(event.target.value)}>
                <option value="">Choose program</option>
                {programs.map((program) => (
                  <option key={program.id} value={program.id}>
                    {program.name} · {program.version} · {program.status}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <EmptyState title="No programs yet">Create a draft to begin program setup.</EmptyState>
          )}

          {programId && (
            <>
              <form
                className="search-row"
                onSubmit={(event) => {
                  event.preventDefault()
                  void task.run(() => searchCatalog(event.currentTarget))
                }}
              >
                <label>
                  Find catalog version
                  <input name="catalog_search" placeholder="Name or brand" />
                </label>
                <button disabled={task.busy}>Search catalog</button>
              </form>
              {selectedProgram?.status === 'draft' && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    void task.run(() => addMember(event.currentTarget))
                  }}
                >
                  <label>
                    Exact catalog version
                    <select name="fragrance_id" required>
                      <option value="">Choose search result</option>
                      {catalog.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.brand} · {item.name} · {item.concentration} · version{' '}
                          {item.version_key}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="fields">
                    <label>
                      Role
                      <select name="role">
                        {roles.map((role) => (
                          <option key={role}>{role}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Group
                      <input name="group_name" defaultValue="Baseline" required />
                    </label>
                    <label>
                      Original baseline
                      <select name="repeat_of_id">
                        <option value="">Only for hidden repeats</option>
                        {members
                          .filter((item) => item.role === 'UNIVERSAL_BASELINE')
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.fragrance_brand} · {item.fragrance_name}
                            </option>
                          ))}
                      </select>
                    </label>
                  </div>
                  <label>
                    Version verification evidence
                    <textarea name="identity_evidence" required />
                  </label>
                  <label>
                    GTIN barcode (optional)
                    <input
                      name="gtin"
                      placeholder="Scanned barcode, 8-14 digits"
                      minLength={8}
                      maxLength={14}
                    />
                  </label>
                  <button disabled={task.busy || catalog.length === 0}>Add version</button>
                </form>
              )}
              <div className="flex-row-between">
                <h3>Frozen definition preview</h3>
                <button
                  className="secondary"
                  disabled={task.busy}
                  onClick={() => void task.run(checkFragellaUsage)}
                >
                  Check Fragella quota
                </button>
              </div>
              {fragellaUsage && (
                <p className="fragella-usage">
                  Fragella plan: {fragellaUsage.plan ?? 'unknown'} · remaining this period:{' '}
                  {fragellaUsage.usage?.requests_remaining ?? 'unknown'}
                </p>
              )}
              {members.length ? (
                <ul className="data-list">
                  {members.map((item) => (
                    <li key={item.id}>
                      <strong>
                        {item.fragrance_brand} · {item.fragrance_name} · {item.concentration} ·
                        version {item.version_key}
                      </strong>
                      <span>
                        {item.role.replace(/_/g, ' ')} · {item.group_name}
                      </span>
                      <small>
                        {item.identity_evidence ?? 'Evidence unavailable for legacy membership'}
                      </small>
                      <div className="fragella-status">
                        {item.fragella ? (
                          <>
                            <small>
                              Fragella checked {formatUtcDateTime(item.fragella.checked_at)} (
                              {item.fragella.status}) - reference only, not used to fill in catalog
                              fields.
                            </small>
                            {item.fragella.status === 'error' && (
                              <p className="error">{item.fragella.error_message}</p>
                            )}
                            {item.fragella.status === 'success' &&
                              (item.fragella.results.length ? (
                                <ul className="data-list">
                                  {item.fragella.results.map((candidate) => (
                                    <li key={candidate.id}>
                                      {candidate.name} · {candidate.brand} ·{' '}
                                      {candidate.year ?? 'year unknown'} ·{' '}
                                      {candidate.oil_type ?? 'concentration unknown'} · confidence{' '}
                                      {candidate.confidence ?? 'unknown'}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p>No Fragella matches found.</p>
                              ))}
                            <ConfirmAction
                              actionLabel="Re-check Fragella"
                              confirmLabel="Spend another monthly request"
                              description="This uses one of the account's 20 monthly Fragella requests again - only re-check if the result above looks wrong or out of date."
                              disabled={task.busy}
                              onConfirm={() => void task.run(() => runFragellaLookup(item.id))}
                            />
                          </>
                        ) : (
                          <ConfirmAction
                            actionLabel="Run Fragella check"
                            confirmLabel="Spend a monthly request"
                            description="This uses one of the account's 20 monthly Fragella requests - only run this if Parfumo left a genuine gap (a same-name ambiguity, or a concentration/year Parfumo didn't publish)."
                            disabled={task.busy}
                            onConfirm={() => void task.run(() => runFragellaLookup(item.id))}
                          />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No catalog versions have been added.</p>
              )}
              {selectedProgram?.status === 'draft' && (
                <ConfirmAction
                  actionLabel="Activate and lock definition"
                  confirmLabel="Confirm activation"
                  description="Activation freezes every exact version, role, repeat, group, and evidence statement. Review the definition before continuing."
                  disabled={task.busy || members.length === 0}
                  onConfirm={() => void task.run(activate)}
                />
              )}
            </>
          )}
        </div>

        <div>
          <h3>2. Enrollment</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void task.run(() => enroll(event.currentTarget))
            }}
          >
            <label>
              Evaluator
              <select name="reviewer_id" required>
                <option value="">Choose evaluator</option>
                {reviewers.map((reviewer) => (
                  <option key={reviewer.id} value={reviewer.id}>
                    {reviewer.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Authorized recorder usernames
              <input name="recorders" required placeholder="Comma-separated usernames" />
            </label>
            <label>
              Samples per session
              <input name="session_size" type="number" min="1" max="20" defaultValue="3" />
            </label>
            <button disabled={task.busy || selectedProgram?.status !== 'active'}>
              Enroll evaluator
            </button>
          </form>
        </div>
      </div>

      <hr />
      <div className="page-heading">
        <div>
          <h3>3. Pilot operations</h3>
          <p>Progress, concealed mappings, printable labels, and service incidents.</p>
        </div>
        <button disabled={task.busy} onClick={() => void task.run(loadOperations)}>
          Refresh operations
        </button>
      </div>
      {status && (
        <div className={`service-status ${status.status}`} role="status">
          <strong>{status.status === 'available' ? 'Service available' : 'Action needed'}</strong>
          <span>{status.guidance}</span>
          {status.unresolved_reviewer_ids.length > 0 && (
            <small>
              Affected:{' '}
              {status.unresolved_reviewer_ids
                .map((id) => reviewerNames.get(id) ?? 'Unknown evaluator')
                .join(', ')}
            </small>
          )}
        </div>
      )}
      {enrollments.length > 0 && (
        <>
          <div className="progress-grid">
            {enrollments.map((item) => (
              <article key={item.id} className="progress-card">
                <strong>{item.reviewer_name}</strong>
                <span>
                  {item.program_name} · {item.program_version}
                </span>
                <progress value={item.blotter_complete} max={item.total_presentations} />
                <small>
                  {item.blotter_complete} of {item.total_presentations} blotter samples complete
                </small>
                <span>
                  {item.revealed
                    ? 'Identities revealed'
                    : item.reveal_eligible
                      ? 'Ready to reveal'
                      : blockerText[item.reveal_blocker!]}
                </span>
                {!item.revealed && (
                  <ConfirmAction
                    actionLabel="Reveal identities"
                    confirmLabel="Confirm reveal"
                    description={
                      item.reveal_eligible
                        ? 'Revealing ends blind collection for this enrollment.'
                        : `Reveal unavailable: ${blockerText[item.reveal_blocker!]}.`
                    }
                    disabled={task.busy || !item.reveal_eligible}
                    onConfirm={() => void task.run(() => revealEnrollment(item.id))}
                  />
                )}
              </article>
            ))}
          </div>
          <label>
            Label set
            <select
              value={selectedEnrollment}
              onChange={(event) => void task.run(() => loadMapping(event.target.value))}
            >
              <option value="">Choose evaluator and program</option>
              {enrollments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.reviewer_name} · {item.program_name} {item.program_version}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      {mapping.length > 0 && (
        <div className="print-area">
          <div className="page-heading no-print">
            <h3>Manager mapping and labels</h3>
            <button onClick={() => window.print()}>Print labels</button>
          </div>
          <div className="label-grid">
            {mapping.map((item) => (
              <article className="sample-label" key={item.blind_code}>
                <strong>{item.blind_code}</strong>
                <span>
                  {item.fragrance_brand} · {item.fragrance_name}
                </span>
                <small>
                  {item.concentration} · {item.role.replace(/_/g, ' ')} · position {item.position} ·
                  version {item.version_key}
                </small>
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="manager-grid">
        <div>
          <h3>4. Recommendation metrics</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void task.run(() => loadMetrics(event.currentTarget))
            }}
          >
            <label>
              Evaluator
              <select name="reviewer_id" required>
                <option value="">Choose evaluator</option>
                {reviewers.map((reviewer) => (
                  <option key={reviewer.id} value={reviewer.id}>
                    {reviewer.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="fields fields-compact">
              <label>
                Window start
                <input name="window_start" type="date" />
              </label>
              <label>
                Window end
                <input name="window_end" type="date" />
              </label>
            </div>
            <button disabled={task.busy}>Calculate metrics</button>
          </form>
          {metrics && (
            <div className="metric-contract">
              <div>
                <strong>{metrics.eligible_impressions}</strong>
                <span>Eligible impressions</span>
              </div>
              <div>
                <strong>{percentage(metrics.response_coverage)}</strong>
                <span>Response coverage</span>
              </div>
              <div>
                <strong>{percentage(metrics.interest_rate)}</strong>
                <span>Interest rate</span>
              </div>
              <div>
                <strong>{percentage(metrics.sampling_conversion)}</strong>
                <span>Sampling conversion</span>
              </div>
              <p>
                <strong>Population:</strong>{' '}
                {reviewerNames.get(metrics.reviewer_id) ?? 'Selected evaluator'} ·{' '}
                <strong>Excluded:</strong> {metrics.excluded_impressions} · <strong>Policy:</strong>{' '}
                {metrics.exclusion_policy.join(', ')}
              </p>
              <p>
                <strong>Algorithm:</strong> {metrics.algorithm_versions.join(', ') || 'No runs'} ·{' '}
                <strong>Strategy:</strong> {metrics.candidate_strategies.join(', ') || 'No runs'}
              </p>
              <p>
                <strong>Run filters:</strong> {JSON.stringify(metrics.run_filters)} ·{' '}
                <strong>Source snapshots:</strong> {metrics.source_snapshots.length}
              </p>
              <p>
                <strong>Window:</strong> {formatUtcDate(metrics.window_start)}–
                {formatUtcDate(metrics.window_end)} UTC
              </p>
              <button onClick={downloadMetrics}>Download evidence JSON</button>
            </div>
          )}
        </div>
        <div>
          <h3>5. Operational events</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void task.run(() => recordEvent(event.currentTarget))
            }}
          >
            <label>
              Evaluator
              <select name="reviewer_id" required>
                <option value="">Choose evaluator</option>
                {reviewers.map((reviewer) => (
                  <option key={reviewer.id} value={reviewer.id}>
                    {reviewer.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Event
              <select name="event_type">
                <option value="CONNECTIVITY_FAILURE">Connectivity failure</option>
                <option value="MANUAL_RECOVERY">Manual recovery</option>
              </select>
            </label>
            <label>
              Details
              <textarea
                name="details"
                placeholder="What happened and what the recorder should do"
              />
            </label>
            <button disabled={task.busy}>Record event</button>
          </form>
          {events.length > 0 && (
            <ul className="data-list">
              {events.map((item) => (
                <li key={item.id}>
                  <strong>
                    {reviewerNames.get(item.reviewer_id) ?? 'Unknown evaluator'} ·{' '}
                    {item.event_type.replace(/_/g, ' ')}
                  </strong>
                  <span>
                    {formatUtcDateTime(item.occurred_at)} · recorded by {item.recorded_by}
                  </span>
                  {item.details && <small>{item.details}</small>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
