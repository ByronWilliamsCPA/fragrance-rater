import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import {
  confirmableFields,
  identityFields,
  permissionOptions,
  type AdoptInput,
  type CatalogCandidate,
  type ConfirmableField,
  type GenderTarget,
  type HouseSubmission,
  type ProposedFacts,
  type ReviewContext,
  type UpdatableField,
} from '../api/houseIntake'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { LoadingState } from '../components/PageState'
import { useTask } from '../hooks/useTask'

const NEW = 'new'
/** ADR-014's sentinel for a fragrance whose tradition no Edwards family covers. */
const UNCLASSIFIED = 'Unclassified'
const edwardsFamilies = ['Fresh', 'Floral', 'Amber', 'Woody', UNCLASSIFIED]
const genderTargets: GenderTarget[] = ['Feminine', 'Masculine', 'Unisex']
const updatable = (field: ConfirmableField): field is UpdatableField =>
  field === 'launch_year' || field === 'gender_target'

function agreementHint(item: CatalogCandidate): string {
  const agreeing = [...identityFields].filter((field) => item.comparison[field] === 'same').length
  return agreeing === identityFields.size
    ? 'Name, brand, and concentration all agree.'
    : `${agreeing} of ${identityFields.size} identity facts (name, brand, concentration) agree.`
}

function display(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === '' ? 'Not given' : String(value)
}

/** The facts a manager would accept by default: everything that already agrees. */
function defaultAccepted(candidate: CatalogCandidate | undefined): Set<ConfirmableField> {
  if (!candidate) return new Set()
  return new Set(
    confirmableFields
      .map(({ field }) => field)
      .filter((field) => candidate.comparison[field] === 'same')
  )
}

type Props = {
  submission: HouseSubmission
  onReviewed: (submission: HouseSubmission, notice: string) => void
}

/**
 * Decide what a house's submission becomes.
 *
 * The manager answers two questions, in order: which catalog version the
 * house is describing (a close match, a search result, or a new version
 * built from the house's own values), and which of the house's facts to
 * accept. Every accepted fact is cited to the house in the evidence record;
 * nothing the house did not say is ever cited to it.
 */
export function HouseReviewPanel({ submission, onReviewed }: Props) {
  const [context, setContext] = useState<ReviewContext | null>(null)
  const [query, setQuery] = useState('')
  const [targetId, setTargetId] = useState('')
  const [accepted, setAccepted] = useState<Set<ConfirmableField>>(new Set())
  const [versionKey, setVersionKey] = useState('original')
  const [primaryFamily, setPrimaryFamily] = useState('')
  const [subfamily, setSubfamily] = useState('')
  const [chosenGender, setChosenGender] = useState<GenderTarget | ''>('')
  const [recordPerfumers, setRecordPerfumers] = useState(submission.payload.perfumers.length > 0)
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const task = useTask()

  async function load(search = '') {
    const response = await api.get<ReviewContext>(
      `/house-intake/submissions/${submission.id}/review`,
      { params: search.trim() ? { q: search.trim() } : undefined }
    )
    setContext(response.data)
    if (search.trim())
      task.setNotice(
        `${response.data.candidates.length} catalog version(s) match "${search.trim()}".`
      )
  }

  useEffect(() => {
    void task.run(() => load())
    // Load once per submission; useTask is stable for this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submission.id])

  const candidate = context?.candidates.find((item) => item.id === targetId)
  const isNew = targetId === NEW

  function chooseTarget(id: string) {
    setTargetId(id)
    setAccepted(defaultAccepted(context?.candidates.find((item) => item.id === id)))
  }

  function toggle(field: ConfirmableField, on: boolean) {
    setAccepted((current) => {
      const next = new Set(current)
      if (on) next.add(field)
      else next.delete(field)
      return next
    })
  }

  const differingIdentity = useMemo(
    () =>
      candidate
        ? confirmableFields.filter(
            ({ field }) => identityFields.has(field) && candidate.comparison[field] === 'differs'
          )
        : [],
    [candidate]
  )

  if (!context)
    return task.error ? (
      <FeedbackBanner error={task.error} />
    ) : (
      <LoadingState label="Loading review…" />
    )

  const proposed = context.proposed
  const needsGender = isNew && proposed.gender_target === null
  const newReady =
    versionKey.trim() !== '' &&
    primaryFamily.trim() !== '' &&
    subfamily.trim() !== '' &&
    (!needsGender || chosenGender !== '')
  const canAdopt = Boolean(candidate) || (isNew && newReady)
  const permission = permissionOptions.find(
    (option) => option.value === submission.permission_state
  )

  function decision(): AdoptInput {
    const confirmed = isNew ? [] : [...accepted]
    return {
      target: isNew
        ? {
            kind: 'new',
            version_key: versionKey.trim(),
            primary_family: primaryFamily.trim(),
            subfamily: subfamily.trim(),
            gender_target: needsGender && chosenGender ? chosenGender : null,
          }
        : { kind: 'existing', fragrance_id: targetId },
      confirmed_fields: confirmed,
      apply_updates: isNew
        ? []
        : confirmed.filter(
            (field): field is UpdatableField =>
              updatable(field) && candidate?.comparison[field] === 'differs'
          ),
      record_perfumers: recordPerfumers,
      review_note: note.trim() || null,
    }
  }

  async function adopt() {
    const response = await api.post<HouseSubmission>(
      `/house-intake/submissions/${submission.id}/adopt`,
      decision()
    )
    onReviewed(response.data, 'Adopted. The house’s statement is now recorded as evidence.')
  }

  async function decline() {
    const response = await api.post<HouseSubmission>(
      `/house-intake/submissions/${submission.id}/decline`,
      { reason: reason.trim() }
    )
    onReviewed(response.data, 'Declined. The house can now see your reason.')
  }

  const acceptedCount = isNew
    ? confirmableFields.filter(({ field }) => proposed[field] !== null).length
    : accepted.size

  return (
    <section className="house-review-panel" aria-labelledby="house-review-panel-heading">
      <h3 id="house-review-panel-heading">Review</h3>
      <p>
        The house allowed: <strong>{permission?.label ?? 'Unknown'}</strong>. Adopting records this
        statement as manufacturer evidence under that permission; you cannot widen it.
      </p>

      <fieldset className="choice-group">
        <legend>1. Which catalog version is this?</legend>
        <form
          className="search-row"
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            void task.run(() => load(query))
          }}
        >
          <label>
            Search the catalog
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <button type="submit" className="secondary" disabled={task.busy}>
            Search
          </button>
        </form>
        {context.candidates.length === 0 && (
          <p className="field-hint">No catalog version looks like this one.</p>
        )}
        {context.candidates.map((item) => (
          <div key={item.id} className="choice">
            <input
              type="radio"
              id={`review-target-${item.id}`}
              name="review-target"
              checked={targetId === item.id}
              onChange={() => chooseTarget(item.id)}
            />
            <label htmlFor={`review-target-${item.id}`}>
              {item.brand} · {item.name} · {item.concentration} · version {item.version_key}
              {item.launch_year ? ` · ${item.launch_year}` : ''}
            </label>
            <p className="field-hint choice__hint">{agreementHint(item)}</p>
          </div>
        ))}
        <div className="choice">
          <input
            type="radio"
            id="review-target-new"
            name="review-target"
            checked={isNew}
            onChange={() => chooseTarget(NEW)}
          />
          <label htmlFor="review-target-new">Add it as a new catalog version</label>
          <p className="field-hint choice__hint">
            Built from the house’s own name, concentration, and launch year. You supply only what a
            house cannot.
          </p>
        </div>
      </fieldset>

      {isNew && (
        <div className="fields-compact">
          <label>
            Version key
            <input value={versionKey} onChange={(event) => setVersionKey(event.target.value)} />
          </label>
          <label>
            Edwards family
            <input
              list="review-edwards-families"
              value={primaryFamily}
              onChange={(event) => setPrimaryFamily(event.target.value)}
            />
          </label>
          <datalist id="review-edwards-families">
            {edwardsFamilies.map((family) => (
              <option key={family} value={family} />
            ))}
          </datalist>
          <label>
            Subfamily
            <input value={subfamily} onChange={(event) => setSubfamily(event.target.value)} />
          </label>
          {needsGender && (
            <label>
              Gender target (the house did not say)
              <select
                value={chosenGender}
                onChange={(event) => setChosenGender(event.target.value as GenderTarget | '')}
              >
                <option value="">Choose</option>
                {genderTargets.map((gender) => (
                  <option key={gender} value={gender}>
                    {gender}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setPrimaryFamily(UNCLASSIFIED)
              setSubfamily(UNCLASSIFIED)
            }}
          >
            No Edwards family fits
          </button>
        </div>
      )}

      {(candidate || isNew) && (
        <>
          <h4>2. Facts the house confirms</h4>
          {differingIdentity.length > 0 && (
            <p className="error" role="note">
              The {differingIdentity.map(({ label }) => label.toLowerCase()).join(' and ')}{' '}
              {differingIdentity.length === 1 ? 'differs' : 'differ'} from this catalog version,
              which usually means it is a different version. If it is only a typo in the catalog,
              correct the catalog first; otherwise choose another version or add a new one.
            </p>
          )}
          <FactsTable
            proposed={proposed}
            candidate={candidate}
            accepted={accepted}
            onToggle={toggle}
          />
          {submission.payload.perfumers.length > 0 && (
            <div className="choice">
              <input
                type="checkbox"
                id="review-perfumers"
                checked={recordPerfumers}
                onChange={(event) => setRecordPerfumers(event.target.checked)}
              />
              <label htmlFor="review-perfumers">
                Record the house’s perfumer credits: {submission.payload.perfumers.join(', ')}
              </label>
            </div>
          )}
          <p className="field-hint">
            The house’s notes, accords, family, and description are kept word for word with the
            evidence. They are mapped to the project vocabulary later (D1), not now.
          </p>
          <label>
            Note to the house (optional)
            <textarea
              value={note}
              maxLength={2000}
              rows={2}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <ConfirmAction
            actionLabel="Adopt as evidence"
            confirmLabel="Confirm adoption"
            description={`This records ${acceptedCount} fact(s) from ${submission.house} as evidence${
              isNew ? ' for a new catalog version' : ` for ${candidate?.name ?? 'this version'}`
            }${
              !isNew &&
              [...accepted].some(
                (field) => updatable(field) && candidate?.comparison[field] === 'differs'
              )
                ? ' and updates the catalog where you accepted a different value'
                : ''
            }. A review cannot be undone; the house can submit a correction later.`}
            disabled={task.busy || !canAdopt}
            onConfirm={() => void task.run(adopt)}
          />
        </>
      )}

      <FeedbackBanner error={task.error} notice={task.notice} />

      <details className="house-review-panel__decline">
        <summary>Decline instead</summary>
        <label>
          Reason (the house will see this)
          <textarea
            value={reason}
            maxLength={2000}
            rows={3}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <ConfirmAction
          actionLabel="Decline submission"
          confirmLabel="Confirm decline"
          description="The house will see this reason and can submit a correction."
          disabled={task.busy || !reason.trim()}
          onConfirm={() => void task.run(decline)}
        />
      </details>
    </section>
  )
}

function FactsTable({
  proposed,
  candidate,
  accepted,
  onToggle,
}: {
  proposed: ProposedFacts
  candidate: CatalogCandidate | undefined
  accepted: Set<ConfirmableField>
  onToggle: (field: ConfirmableField, on: boolean) => void
}) {
  return (
    <div className="review-facts-wrap">
      <table className="review-facts">
        <caption className="visually-hidden">
          Facts the house gave, compared with the catalog
        </caption>
        <thead>
          <tr>
            <th scope="col">Fact</th>
            {candidate && <th scope="col">Catalog now</th>}
            <th scope="col">House says</th>
            <th scope="col">Decision</th>
          </tr>
        </thead>
        <tbody>
          {confirmableFields.map(({ field, label }) => {
            const house = proposed[field]
            const outcome = candidate
              ? candidate.comparison[field]
              : house === null
                ? 'house_silent'
                : 'same'
            const id = `review-accept-${field}`
            return (
              <tr key={field} data-outcome={outcome}>
                <th scope="row">{label}</th>
                {candidate && <td>{display(candidate[field])}</td>}
                <td>{display(house)}</td>
                <td>
                  {outcome === 'house_silent' ? (
                    <span className="field-hint">The house did not say</span>
                  ) : !candidate ? (
                    <span>Recorded from the house</span>
                  ) : outcome === 'differs' && identityFields.has(field) ? (
                    <span className="field-error">Differs: likely another version</span>
                  ) : (
                    <span className="choice">
                      <input
                        type="checkbox"
                        id={id}
                        checked={accepted.has(field)}
                        onChange={(event) => onToggle(field, event.target.checked)}
                      />
                      <label htmlFor={id}>
                        {outcome === 'differs' ? 'Accept and update the catalog' : 'Accept'}
                      </label>
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
