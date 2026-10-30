import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, requestErrorMessage } from '../api/client'
import {
  availabilityOptions,
  completenessProblems,
  concentrationOptions,
  formatProblems,
  marketedForOptions,
  MAX_DESCRIPTION,
  permissionOptions,
  pyramidTiers,
  serverProblems,
  type Availability,
  type Concentration,
  type HouseSubmission,
  type HouseSubmissionPayload,
  type MarketedFor,
  type NotePosition,
  type NoteStructure,
  type PermissionScope,
  type SubmissionProblem,
} from '../api/houseIntake'
import { EntryListField } from '../components/EntryListField'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { ConfirmAction } from '../components/ConfirmAction'
import { HouseSubmissionSummary } from './HouseSubmissionSummary'

type Tier = Exclude<NotePosition, 'unspecified'>

/**
 * The form's own state: what is on screen, before trimming and typing.
 *
 * Pyramid and linear notes are held separately so switching between the two
 * layouts never discards what the house typed; only the layout chosen at
 * save time is sent.
 */
type FormState = {
  fragrance_name: string
  line: string
  concentration: Concentration | ''
  concentration_other: string
  version_label: string
  launch_year: string
  availability: Availability | ''
  marketed_for: MarketedFor | ''
  perfumers: string[]
  product_url: string
  gtins: string[]
  note_structure: NoteStructure
  pyramid: Record<Tier, string[]>
  linear: string[]
  accords: string[]
  family_as_described: string
  description: string
  permission_scope: PermissionScope | ''
  contact_name: string
  contact_role: string
  attested: boolean
  note_to_reviewer: string
}

function fromPayload(payload: HouseSubmissionPayload): FormState {
  const tier = (position: NotePosition) =>
    payload.notes.filter((note) => note.position === position).map((note) => note.text)
  return {
    fragrance_name: payload.fragrance_name,
    line: payload.line ?? '',
    concentration: payload.concentration ?? '',
    concentration_other: payload.concentration_other ?? '',
    version_label: payload.version_label ?? '',
    launch_year: payload.launch_year === null ? '' : String(payload.launch_year),
    availability: payload.availability ?? '',
    marketed_for: payload.marketed_for ?? '',
    perfumers: payload.perfumers,
    product_url: payload.product_url ?? '',
    gtins: payload.gtins,
    note_structure: payload.note_structure,
    pyramid: { top: tier('top'), heart: tier('heart'), base: tier('base') },
    linear: tier('unspecified'),
    accords: payload.accords,
    family_as_described: payload.family_as_described ?? '',
    description: payload.description ?? '',
    permission_scope: payload.permission_scope ?? '',
    contact_name: payload.contact_name ?? '',
    contact_role: payload.contact_role ?? '',
    attested: payload.attested,
    note_to_reviewer: payload.note_to_reviewer ?? '',
  }
}

const optional = (value: string): string | null => value.trim() || null
const entries = (values: string[]): string[] => values.map((value) => value.trim()).filter(Boolean)

function toPayload(state: FormState): HouseSubmissionPayload {
  const year = state.launch_year.trim()
  const notes =
    state.note_structure === 'pyramid'
      ? pyramidTiers.flatMap(({ position }) =>
          entries(state.pyramid[position]).map((text) => ({ text, position }))
        )
      : entries(state.linear).map((text) => ({ text, position: 'unspecified' as const }))
  return {
    fragrance_name: state.fragrance_name.trim(),
    line: optional(state.line),
    concentration: state.concentration || null,
    concentration_other:
      state.concentration === 'OTHER' ? optional(state.concentration_other) : null,
    version_label: optional(state.version_label),
    // A non-numeric year becomes NaN, which formatProblems reports, rather
    // than silently saving as "no year".
    launch_year: year ? Number(year) : null,
    availability: state.availability || null,
    marketed_for: state.marketed_for || null,
    perfumers: entries(state.perfumers),
    product_url: optional(state.product_url),
    gtins: entries(state.gtins).map((gtin) => gtin.replace(/[\s-]/g, '')),
    note_structure: state.note_structure,
    notes,
    accords: entries(state.accords),
    family_as_described: optional(state.family_as_described),
    description: optional(state.description),
    permission_scope: state.permission_scope || null,
    contact_name: optional(state.contact_name),
    contact_role: optional(state.contact_role),
    attested: state.attested,
    note_to_reviewer: optional(state.note_to_reviewer),
  }
}

/** Where an error summary link should land for each problem field. */
function controlId(field: string, state: FormState): string {
  if (field === 'notes')
    return state.note_structure === 'pyramid' ? 'house-notes-top' : 'house-notes-linear'
  if (field === 'availability') return `house-availability-${availabilityOptions[0].value}`
  if (field === 'permission_scope') return `house-permission-${permissionOptions[0].value}`
  return `house-${field}`
}

type Props = {
  house: string
  submission: HouseSubmission | null
  initial: HouseSubmissionPayload
  onSaved: (submission: HouseSubmission) => void
  onSubmitted: (submission: HouseSubmission) => void
  onDiscarded: () => void
  onBack: () => void
}

export function HouseSubmissionForm({
  house,
  submission,
  initial,
  onSaved,
  onSubmitted,
  onDiscarded,
  onBack,
}: Props) {
  const [state, setState] = useState<FormState>(() => fromPayload(initial))
  const [savedSnapshot, setSavedSnapshot] = useState(() =>
    JSON.stringify(toPayload(fromPayload(initial)))
  )
  const [draftId, setDraftId] = useState(submission?.id ?? null)
  const [problems, setProblems] = useState<SubmissionProblem[]>([])
  const [reviewing, setReviewing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const summary = useRef<HTMLDivElement>(null)
  const reviewHeading = useRef<HTMLHeadingElement>(null)
  const payload = useMemo(() => toPayload(state), [state])
  const dirty = JSON.stringify(payload) !== savedSnapshot

  useEffect(() => {
    if (problems.length) summary.current?.focus()
  }, [problems])

  useEffect(() => {
    if (reviewing) reviewHeading.current?.focus()
  }, [reviewing])

  function update(patch: Partial<FormState>) {
    setState((current) => ({ ...current, ...patch }))
    setNotice('')
  }

  function updateTier(tier: Tier, next: string[]) {
    setState((current) => ({ ...current, pyramid: { ...current.pyramid, [tier]: next } }))
    setNotice('')
  }

  const problemFor = (field: string) => problems.find((problem) => problem.field === field)
  const errorFor = (field: string) => problemFor(field)?.message

  /** Props for a single control with a visible label, hint, and error. */
  function describe(field: string, hasHint = false) {
    const describedBy = [
      hasHint && `house-${field}-hint`,
      errorFor(field) && `house-${field}-error`,
    ]
      .filter(Boolean)
      .join(' ')
    return {
      id: `house-${field}`,
      'aria-invalid': errorFor(field) ? true : undefined,
      'aria-describedby': describedBy || undefined,
    }
  }

  async function persist(): Promise<HouseSubmission> {
    const response = draftId
      ? await api.put<HouseSubmission>(`/house-intake/submissions/${draftId}`, payload)
      : await api.post<HouseSubmission>('/house-intake/submissions', payload)
    setDraftId(response.data.id)
    setSavedSnapshot(JSON.stringify(payload))
    onSaved(response.data)
    return response.data
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (reason) {
      const listed = serverProblems(reason)
      if (listed) {
        setReviewing(false)
        setProblems(listed)
      } else setError(requestErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  function saveDraft() {
    const found = formatProblems(payload)
    setProblems(found)
    if (found.length) return
    void run(async () => {
      await persist()
      setNotice('Draft saved. You can come back to it at any time.')
    })
  }

  function review() {
    const found = [...formatProblems(payload), ...completenessProblems(payload)]
    setProblems(found)
    if (!found.length) setReviewing(true)
  }

  function submit() {
    void run(async () => {
      const saved = await persist()
      const response = await api.post<HouseSubmission>(
        `/house-intake/submissions/${saved.id}/submit`
      )
      onSubmitted(response.data)
    })
  }

  function discard() {
    void run(async () => {
      if (draftId) await api.delete(`/house-intake/submissions/${draftId}`)
      onDiscarded()
    })
  }

  if (reviewing)
    return (
      <section className="house-review" aria-labelledby="house-review-heading">
        <h3 id="house-review-heading" ref={reviewHeading} tabIndex={-1}>
          Check your answers
        </h3>
        <p>
          Once you submit, this record is fixed. If something changes later, you can start a
          correction, which keeps the original and replaces it with the new version.
        </p>
        <HouseSubmissionSummary house={house} payload={payload} />
        <FeedbackBanner error={error} />
        <div className="button-row">
          <button type="button" disabled={busy} onClick={submit}>
            Submit to Fragrance Rater
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => setReviewing(false)}
          >
            Go back and edit
          </button>
        </div>
      </section>
    )

  return (
    <form
      className="house-form"
      noValidate
      aria-labelledby="house-form-heading"
      onSubmit={(event) => {
        event.preventDefault()
        review()
      }}
    >
      <div className="page-heading">
        <div>
          <p className="eyebrow">{submission?.supersedes_id ? 'Correction' : 'Submission'}</p>
          <h3 id="house-form-heading">
            {state.fragrance_name.trim() || 'Tell us about a fragrance'}
          </h3>
        </div>
        {dirty ? (
          <ConfirmAction
            actionLabel="Back to submissions"
            confirmLabel="Leave without saving"
            description="You have changes that are not saved. Save a draft first if you want to keep them."
            disabled={busy}
            onConfirm={onBack}
          />
        ) : (
          <button type="button" className="secondary" onClick={onBack} disabled={busy}>
            Back to submissions
          </button>
        )}
      </div>
      {submission?.supersedes_id && (
        <p className="notice" role="note">
          You are correcting a submitted record. Your earlier confirmation does not carry over:
          please confirm the details again at the end.
        </p>
      )}

      {problems.length > 0 && (
        <div
          className="error-summary"
          role="alert"
          aria-labelledby="house-error-summary-heading"
          tabIndex={-1}
          ref={summary}
        >
          <h4 id="house-error-summary-heading">
            {problems.length === 1
              ? 'One answer needs attention'
              : `${problems.length} answers need attention`}
          </h4>
          <ul>
            {problems.map((problem) => (
              <li key={`${problem.field}-${problem.message}`}>
                <a
                  href={`#${controlId(problem.field, state)}`}
                  onClick={(event) => {
                    event.preventDefault()
                    document.getElementById(controlId(problem.field, state))?.focus()
                  }}
                >
                  {problem.message}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Section number={1} title="The fragrance">
        <Field field="fragrance_name" label="Fragrance name" error={errorFor('fragrance_name')}>
          <input
            {...describe('fragrance_name')}
            value={state.fragrance_name}
            maxLength={255}
            autoComplete="off"
            onChange={(event) => update({ fragrance_name: event.target.value })}
          />
        </Field>
        <dl className="standing house-form__fixed">
          <dt>House</dt>
          <dd>{house}</dd>
        </dl>
        <Field
          field="line"
          label="Collection or line (optional)"
          hint="For example, a private collection or a named series the fragrance belongs to."
        >
          <input
            {...describe('line', true)}
            value={state.line}
            maxLength={255}
            onChange={(event) => update({ line: event.target.value })}
          />
        </Field>
        <div className="fields-compact">
          <Field field="concentration" label="Concentration" error={errorFor('concentration')}>
            <select
              {...describe('concentration')}
              value={state.concentration}
              onChange={(event) =>
                update({ concentration: event.target.value as Concentration | '' })
              }
            >
              <option value="">Choose a concentration</option>
              {concentrationOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          {state.concentration === 'OTHER' && (
            <Field
              field="concentration_other"
              label="What the house calls it"
              error={errorFor('concentration_other')}
            >
              <input
                {...describe('concentration_other')}
                value={state.concentration_other}
                maxLength={100}
                onChange={(event) => update({ concentration_other: event.target.value })}
              />
            </Field>
          )}
        </div>
        <Field
          field="version_label"
          label="Formulation or edition (optional)"
          hint="Only if this differs from an earlier fragrance of the same name: a reformulation, an anniversary edition, a new concentration of the same scent. Leave blank for the original."
        >
          <input
            {...describe('version_label', true)}
            value={state.version_label}
            maxLength={200}
            onChange={(event) => update({ version_label: event.target.value })}
          />
        </Field>
        <Field
          field="launch_year"
          label="Launch year"
          hint="The year this version first went on sale. Leave blank only if it has not been released yet."
          error={errorFor('launch_year')}
        >
          <input
            {...describe('launch_year', true)}
            className="house-form__year"
            value={state.launch_year}
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={4}
            data-numeric
            onChange={(event) => update({ launch_year: event.target.value })}
          />
        </Field>
        <RadioGroup
          field="availability"
          legend="Is it on sale?"
          options={availabilityOptions}
          value={state.availability}
          error={errorFor('availability')}
          onChange={(value) => update({ availability: value })}
        />
        <RadioGroup
          field="marketed_for"
          legend="Who is it marketed for? (optional)"
          options={marketedForOptions}
          value={state.marketed_for}
          onChange={(value) => update({ marketed_for: value })}
        />
        <EntryListField
          id="house-perfumers"
          label="Perfumers (optional)"
          hint="The perfumer or perfumers the house credits, most senior first."
          itemNoun="perfumer"
          entries={state.perfumers}
          maxEntries={10}
          onChange={(perfumers) => update({ perfumers })}
        />
        <Field
          field="product_url"
          label="Official product page (optional)"
          hint="The page on the house's own website, starting with https://"
          error={errorFor('product_url')}
        >
          <input
            {...describe('product_url', true)}
            type="url"
            value={state.product_url}
            maxLength={1000}
            inputMode="url"
            onChange={(event) => update({ product_url: event.target.value })}
          />
        </Field>
        <EntryListField
          id="house-gtins"
          label="Barcodes (optional)"
          hint="The EAN or UPC printed under the barcode on the box, one per bottle size. Digits only; spaces are removed."
          itemNoun="barcode"
          entries={state.gtins}
          maxEntries={20}
          maxLength={20}
          inputMode="numeric"
          error={errorFor('gtins')}
          onChange={(gtins) => update({ gtins })}
        />
      </Section>

      <Section number={2} title="The scent, in your words">
        <p className="field-hint house-form__intro">
          Please use the house&rsquo;s own words, exactly as you publish them. We record them as
          given and never translate them into anyone else&rsquo;s vocabulary. We ask only for the
          notes you already publish; this is not a request for your formula.
        </p>
        <RadioGroup
          field="note_structure"
          legend="How does the house present the notes?"
          options={[
            { value: 'pyramid', label: 'As top, heart, and base notes' },
            { value: 'linear', label: 'As a single list, without a pyramid' },
          ]}
          value={state.note_structure}
          onChange={(value) => update({ note_structure: value })}
        />
        {errorFor('notes') && (
          <p id="house-notes-error" className="field-error">
            {errorFor('notes')}
          </p>
        )}
        {state.note_structure === 'pyramid' ? (
          pyramidTiers.map((tier) => (
            <EntryListField
              key={tier.position}
              id={`house-notes-${tier.position}`}
              label={tier.label}
              hint={
                tier.position === 'top'
                  ? 'List the most prominent note first. You can paste a list separated by commas.'
                  : undefined
              }
              itemNoun={`${tier.position} note`}
              entries={state.pyramid[tier.position]}
              maxEntries={40}
              onChange={(next) => updateTier(tier.position, next)}
            />
          ))
        ) : (
          <EntryListField
            id="house-notes-linear"
            label="Notes"
            hint="List the most prominent note first. You can paste a list separated by commas."
            itemNoun="note"
            entries={state.linear}
            maxEntries={100}
            onChange={(linear) => update({ linear })}
          />
        )}
        <EntryListField
          id="house-accords"
          label="Accords (optional)"
          hint="Any accords the house names, such as 'leather accord' or 'smoky'."
          itemNoun="accord"
          entries={state.accords}
          maxEntries={30}
          onChange={(accords) => update({ accords })}
        />
        <Field
          field="family_as_described"
          label="Fragrance family (optional)"
          hint="However the house describes it, for example 'woody aromatic' or 'floral chypre'."
        >
          <input
            {...describe('family_as_described', true)}
            value={state.family_as_described}
            maxLength={255}
            onChange={(event) => update({ family_as_described: event.target.value })}
          />
        </Field>
        <Field
          field="description"
          label="Official description (optional)"
          hint={`The description the house publishes, up to ${MAX_DESCRIPTION} characters. ${state.description.length} used.`}
          error={errorFor('description')}
        >
          <textarea
            {...describe('description', true)}
            value={state.description}
            rows={6}
            onChange={(event) => update({ description: event.target.value })}
          />
        </Field>
      </Section>

      <Section number={3} title="Permission">
        <RadioGroup
          field="permission_scope"
          idPrefix="house-permission"
          legend="How may Fragrance Rater use this information?"
          options={permissionOptions}
          value={state.permission_scope}
          error={errorFor('permission_scope')}
          onChange={(value) => update({ permission_scope: value })}
        />
        <div className="fields-compact">
          <Field field="contact_name" label="Your name" error={errorFor('contact_name')}>
            <input
              {...describe('contact_name')}
              value={state.contact_name}
              maxLength={200}
              autoComplete="name"
              onChange={(event) => update({ contact_name: event.target.value })}
            />
          </Field>
          <Field
            field="contact_role"
            label="Your role at the house"
            error={errorFor('contact_role')}
          >
            <input
              {...describe('contact_role')}
              value={state.contact_role}
              maxLength={200}
              autoComplete="organization-title"
              onChange={(event) => update({ contact_role: event.target.value })}
            />
          </Field>
        </div>
        <div className={`choice ${errorFor('attested') ? 'choice--invalid' : ''}`}>
          {errorFor('attested') && (
            <p id="house-attested-error" className="field-error">
              {errorFor('attested')}
            </p>
          )}
          <input
            type="checkbox"
            id="house-attested"
            checked={state.attested}
            aria-invalid={errorFor('attested') ? true : undefined}
            aria-describedby={errorFor('attested') ? 'house-attested-error' : undefined}
            onChange={(event) => update({ attested: event.target.checked })}
          />
          <label htmlFor="house-attested">
            I am authorised to provide this information on behalf of {house}, and it matches what
            the house publishes.
          </label>
        </div>
        <Field
          field="note_to_reviewer"
          label="Anything else we should know? (optional)"
          hint="For example, a correction to a detail we hold, or a reformulation we should be aware of."
        >
          <textarea
            {...describe('note_to_reviewer', true)}
            value={state.note_to_reviewer}
            maxLength={2000}
            rows={3}
            onChange={(event) => update({ note_to_reviewer: event.target.value })}
          />
        </Field>
      </Section>

      <FeedbackBanner error={error} notice={notice} />
      <div className="button-row house-form__actions">
        <button type="submit" disabled={busy}>
          Review and submit
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={saveDraft}>
          Save draft
        </button>
        <span className="field-hint" aria-live="polite">
          {dirty ? 'Unsaved changes' : draftId ? 'All changes saved' : ''}
        </span>
      </div>
      {draftId && (
        <ConfirmAction
          actionLabel="Discard this draft"
          confirmLabel="Discard draft"
          description="This deletes the draft and everything typed into it. Submitted records are never deleted."
          disabled={busy}
          onConfirm={discard}
        />
      )}
    </form>
  )
}

function Section({
  number,
  title,
  children,
}: {
  number: number
  title: string
  children: ReactNode
}) {
  const headingId = `house-section-${number}`
  return (
    <section className="house-form__section" aria-labelledby={headingId}>
      <h4 id={headingId}>
        <span className="house-form__number" data-numeric>
          {number}.
        </span>{' '}
        {title}
      </h4>
      {children}
    </section>
  )
}

/**
 * A labelled control with its hint and error. The control itself is passed
 * in already carrying the matching `id` and `aria-describedby` from
 * `describe()`, so label, hint, and error are tied to it by id rather than
 * by nesting.
 */
function Field({
  field,
  label,
  hint,
  error,
  children,
}: {
  field: string
  label: string
  hint?: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className={`field ${error ? 'field--invalid' : ''}`}>
      <label htmlFor={`house-${field}`}>{label}</label>
      {hint && (
        <p id={`house-${field}-hint`} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`house-${field}-error`} className="field-error">
          {error}
        </p>
      )}
      {children}
    </div>
  )
}

function RadioGroup<T extends string>({
  field,
  idPrefix = `house-${field}`,
  legend,
  options,
  value,
  error,
  onChange,
}: {
  field: string
  idPrefix?: string
  legend: string
  options: ReadonlyArray<{ value: T; label: string; hint?: string }>
  value: T | ''
  error?: string
  onChange: (value: T) => void
}) {
  const errorId = `house-${field}-error`
  return (
    <fieldset
      className={`choice-group ${error ? 'choice-group--invalid' : ''}`}
      aria-describedby={error ? errorId : undefined}
    >
      <legend>{legend}</legend>
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
      {options.map((option) => {
        const id = `${idPrefix}-${option.value}`
        return (
          <div key={option.value} className="choice">
            <input
              type="radio"
              id={id}
              name={`house-${field}`}
              value={option.value}
              checked={value === option.value}
              aria-describedby={option.hint ? `${id}-hint` : undefined}
              onChange={() => onChange(option.value)}
            />
            <label htmlFor={id}>{option.label}</label>
            {option.hint && (
              <p id={`${id}-hint`} className="field-hint choice__hint">
                {option.hint}
              </p>
            )}
          </div>
        )
      })}
    </fieldset>
  )
}
