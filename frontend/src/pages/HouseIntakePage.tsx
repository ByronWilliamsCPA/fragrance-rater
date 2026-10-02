import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import {
  concentrationOptions,
  emptyPayload,
  labelFor,
  permissionOptions,
  type HouseAccess,
  type HouseSubmission,
  type HouseSubmissionPayload,
} from '../api/houseIntake'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { EmptyState, LoadingState } from '../components/PageState'
import { useTask } from '../hooks/useTask'
import { HouseSubmissionForm } from './HouseSubmissionForm'
import { HouseSubmissionSummary } from './HouseSubmissionSummary'

type View =
  | { kind: 'list' }
  | { kind: 'edit'; submission: HouseSubmission | null; initial: HouseSubmissionPayload }
  | { kind: 'record'; submission: HouseSubmission }

function formatUtc(value: string): string {
  const utc = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(utc)
  )
}

function statusLine(submission: HouseSubmission): string {
  if (submission.superseded_by_id) return 'Replaced by a correction'
  if (submission.status === 'submitted' && submission.submitted_at)
    return `Submitted ${formatUtc(submission.submitted_at)}`
  return submission.supersedes_id ? 'Correction in progress' : 'Draft'
}

type Props = { access: HouseAccess }

/**
 * Where a fragrance house describes its fragrances, and where a manager
 * reads what houses have sent.
 *
 * A house sees only its own records (the server scopes every read to the
 * house on the account). A manager sees every house's records, read-only:
 * a manager writing on a house's behalf would no longer be the house's own
 * statement (ADR-012).
 */
export function HouseIntakePage({ access }: Props) {
  const [submissions, setSubmissions] = useState<HouseSubmission[] | null>(null)
  const [view, setView] = useState<View>({ kind: 'list' })
  const task = useTask()
  const house = access.house
  const canWrite = house !== null

  const load = useCallback(async () => {
    const response = await api.get<HouseSubmission[]>('/house-intake/submissions')
    setSubmissions(response.data)
  }, [])

  useEffect(() => {
    void task.run(load)
    // Load once on mount; useTask is stable for this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load])

  function backToList(notice = '') {
    setView({ kind: 'list' })
    void task.run(async () => {
      await load()
      if (notice) task.setNotice(notice)
    })
  }

  async function startCorrection(original: HouseSubmission) {
    const response = await api.post<HouseSubmission>(
      `/house-intake/submissions/${original.id}/revise`
    )
    setView({ kind: 'edit', submission: response.data, initial: response.data.payload })
  }

  async function openRecord(id: string) {
    const response = await api.get<HouseSubmission>(`/house-intake/submissions/${id}`)
    setView({ kind: 'record', submission: response.data })
  }

  if (view.kind === 'edit' && house)
    return (
      <section>
        <HouseSubmissionForm
          // A new key per record, so switching records resets the form state.
          key={view.submission?.id ?? 'new'}
          house={house}
          submission={view.submission}
          initial={view.initial}
          onSaved={() => undefined}
          onSubmitted={() =>
            backToList('Thank you. Your submission has been received and will be reviewed.')
          }
          onDiscarded={() => backToList('Draft discarded.')}
          onBack={() => backToList()}
        />
      </section>
    )

  if (view.kind === 'record') {
    const record = view.submission
    const permission = permissionOptions.find((option) => option.value === record.permission_state)
    const earlierId = record.supersedes_id
    const correctionId = record.superseded_by_id
    return (
      <section aria-labelledby="house-record-heading">
        <div className="page-heading">
          <div>
            <p className="eyebrow">{statusLine(record)}</p>
            <h3 id="house-record-heading">{record.payload.fragrance_name}</h3>
          </div>
          <button type="button" className="secondary" onClick={() => backToList()}>
            Back to submissions
          </button>
        </div>
        <dl className="standing">
          <dt>Submitted by</dt>
          <dd>{record.submitted_by ?? 'Not yet submitted'}</dd>
          <dt>Permission granted</dt>
          <dd>{permission?.label ?? 'Not yet granted'}</dd>
          {earlierId && (
            <>
              <dt>Corrects</dt>
              <dd>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => void task.run(() => openRecord(earlierId))}
                >
                  View the earlier record
                </button>
              </dd>
            </>
          )}
        </dl>
        <HouseSubmissionSummary house={record.house} payload={record.payload} />
        <FeedbackBanner error={task.error} />
        {correctionId ? (
          <button
            type="button"
            className="secondary"
            onClick={() => void task.run(() => openRecord(correctionId))}
          >
            View the correction
          </button>
        ) : (
          canWrite &&
          record.status === 'submitted' && (
            <div className="confirm-action">
              <p>
                Something changed or was wrong? A correction starts a new draft from these answers.
                This record stays on file until the correction is submitted.
              </p>
              <button
                type="button"
                disabled={task.busy}
                onClick={() => void task.run(() => startCorrection(record))}
              >
                Start a correction
              </button>
            </div>
          )
        )}
      </section>
    )
  }

  return (
    <section aria-labelledby="house-intake-heading">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{canWrite ? house : 'All houses'}</p>
          <h3 id="house-intake-heading">House submissions</h3>
          <p>
            {canWrite
              ? 'Describe each of your fragrances in your own words. Save a draft at any time and submit when it is complete.'
              : 'What fragrance houses have sent, read-only. Nothing here changes the catalog until it is reviewed.'}
          </p>
        </div>
        {canWrite && (
          <button
            type="button"
            onClick={() => setView({ kind: 'edit', submission: null, initial: emptyPayload() })}
          >
            Describe a new fragrance
          </button>
        )}
      </div>
      <FeedbackBanner error={task.error} notice={task.notice} />
      {submissions === null ? (
        task.error ? null : (
          <LoadingState label="Loading submissions…" />
        )
      ) : submissions.length === 0 ? (
        <EmptyState title="Nothing here yet">
          {canWrite
            ? 'Start with one fragrance. Most people finish in ten to fifteen minutes with the product page open beside them.'
            : 'No house has sent a submission yet.'}
        </EmptyState>
      ) : (
        <ul className="data-list house-submissions">
          {submissions.map((submission) => (
            <li key={submission.id}>
              <strong>{submission.payload.fragrance_name}</strong>
              <span>
                {!canWrite && `${submission.house} · `}
                {submission.payload.concentration === 'OTHER'
                  ? (submission.payload.concentration_other ?? 'Concentration not given')
                  : submission.payload.concentration
                    ? labelFor(concentrationOptions, submission.payload.concentration)
                    : 'Concentration not given'}
                {submission.payload.launch_year ? ` · ${submission.payload.launch_year}` : ''}
              </span>
              <small>{statusLine(submission)}</small>
              <div className="button-row">
                {submission.status === 'draft' && canWrite ? (
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Continue editing ${submission.payload.fragrance_name}`}
                    onClick={() =>
                      setView({ kind: 'edit', submission, initial: submission.payload })
                    }
                  >
                    Continue editing
                  </button>
                ) : (
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`View ${submission.payload.fragrance_name}`}
                    onClick={() => setView({ kind: 'record', submission })}
                  >
                    View
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
