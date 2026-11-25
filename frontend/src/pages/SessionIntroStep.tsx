import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import {
  contextNumbers,
  contextYesNo,
  hormonalChoices,
  hungerChoices,
  yesNoRefuse,
  type Choice,
} from '../content/calibrationScales'
import { contextPayload } from '../content/contextPayload'
import { toInstant } from '../content/transcription'
import { sessionsOf } from '../routing/wizardSteps'
import type { useTask } from '../hooks/useTask'

type ConsentText = { version: string; approved: boolean; text: string }
type ConsentState = { state: Record<string, string> }
type ContextRead = { recorded: boolean; withheld?: boolean }

function ChoiceSelect({
  name,
  label,
  choices,
}: {
  name: string
  label: string
  choices: Choice[]
}) {
  return (
    <label>
      {label}
      <select name={name} defaultValue="">
        <option value="">Not answered</option>
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/**
 * The first screen of a session: consent, optional conditions, then start.
 *
 * Nothing here is a prerequisite for evaluating: "Continue" is always
 * available, and every question can be skipped or refused. The consent wording
 * is shown exactly as the server holds it; while that wording is an unapproved
 * draft the screen says so and offers no way to agree, because the server
 * refuses a grant against a draft.
 *
 * In the facilitated format (`transcription`) a facilitator types a paper
 * sheet in on the evaluator's behalf. Consent is then asked ONCE per
 * evaluator, on their first session, with a note saying where it is written
 * (the paper sheet); later sessions never re-ask, and show conditions only if
 * consent was granted then. The session start time is the one written on the
 * sheet, not the moment the facilitator typed it.
 */
export function SessionIntroStep({
  enrollment,
  sessionId: requestedSessionId,
  task,
  onDone,
  transcription = false,
}: {
  enrollment: Enrollment
  /**
   * The session being opened. Start and conditions belong to THAT session;
   * defaulting to the first session is only for callers with one session.
   */
  sessionId?: string
  task: ReturnType<typeof useTask>
  onDone: () => void
  /** Facilitated format: consent once, with a note; start time from the paper sheet. */
  transcription?: boolean
}) {
  const sessionId = requestedSessionId ?? enrollment.presentations[0]?.session_id
  // Consent is per evaluator, so only their first session may ask for it.
  const firstSession = sessionsOf(enrollment)[0]?.id === sessionId
  const askConsent = !transcription || firstSession
  const [text, setText] = useState<ConsentText | null>(null)
  const [consent, setConsent] = useState<string>('none')
  const [context, setContext] = useState<ContextRead | null>(null)
  const [consentNote, setConsentNote] = useState('')
  const [startedAt, setStartedAt] = useState('')

  async function load() {
    const [wording, state, read] = await Promise.all([
      api.get<ConsentText>('/calibration/consent/text'),
      api.get<ConsentState>(`/calibration/reviewers/${enrollment.reviewer_id}/consent`),
      sessionId
        ? api.get<ContextRead>(`/calibration/sessions/${sessionId}/context`)
        : Promise.resolve({ data: { recorded: false } as ContextRead }),
    ])
    setText(wording.data)
    setConsent(state.data.state.session_context ?? 'none')
    setContext(read.data)
  }

  useEffect(() => {
    void task.run(load)
    // Loaded once per enrollment and session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollment.id, sessionId])

  async function record(eventType: 'granted' | 'withdrawn') {
    const note = consentNote.trim()
    if (transcription && eventType === 'granted' && !note) {
      task.setError(
        'Say where the evaluator wrote their consent (for example: signed on the paper sheet) before recording it.'
      )
      return
    }
    await api.post(`/calibration/reviewers/${enrollment.reviewer_id}/consent`, {
      scope: 'session_context',
      event_type: eventType,
      enrollment_id: enrollment.id,
      ...(transcription && note ? { note } : {}),
    })
    await load()
    task.setNotice(
      eventType === 'granted' ? 'Thank you. Your choice is recorded.' : 'Consent withdrawn.'
    )
  }

  async function continueToSamples() {
    // In the facilitated format the start is the time written on the sheet.
    const paperStart = transcription ? toInstant(startedAt) : null
    if (transcription && !paperStart) {
      task.setError('Enter the start time written on the sheet before continuing.')
      return
    }
    if (sessionId) {
      try {
        await api.post(`/calibration/sessions/${sessionId}/start`, {
          evaluator_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          started_at: paperStart ?? new Date().toISOString(),
        })
      } catch (reason) {
        // A session that already started is fine; anything else is real.
        const status = (reason as { response?: { status?: number } }).response?.status
        if (status !== 409) throw reason
      }
    }
    onDone()
  }

  return (
    <>
      <p className="notice">
        Before you begin: please read how your answers are used. Taking part never depends on saying
        yes, and you can still evaluate every sample whatever you choose.
      </p>
      {text && askConsent && (
        <section aria-label="Consent wording" className="consent-text">
          <pre className="consent-text__body">{text.text}</pre>
        </section>
      )}
      {text && askConsent && !text.approved && (
        <p className="notice" role="status">
          This wording is still being finalized, so questions about your conditions are switched off
          for now. You can go straight to the samples.
        </p>
      )}
      {text?.approved && askConsent && consent !== 'granted' && (
        <div className="fields fields-compact">
          {transcription && (
            <label>
              Where the evaluator wrote their consent
              <input
                value={consentNote}
                onChange={(event) => setConsentNote(event.target.value)}
                placeholder="For example: signed on the paper sheet"
              />
            </label>
          )}
          <button disabled={task.busy} onClick={() => void task.run(() => record('granted'))}>
            I agree to answer questions about my conditions
          </button>
        </div>
      )}
      {!askConsent && consent !== 'granted' && (
        <p className="notice" role="status">
          Consent to answer questions about conditions is asked once, before the first session. It
          was not given, so conditions are not recorded for this session.
        </p>
      )}
      {consent === 'granted' && context?.recorded === false && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const form = event.currentTarget
            void task.run(async () => {
              const values = Object.fromEntries(new FormData(form))
              await api.post(`/calibration/sessions/${sessionId}/context`, contextPayload(values))
              await load()
              task.setNotice('Conditions saved.')
            })
          }}
        >
          <fieldset disabled={task.busy}>
            <legend>Today&apos;s conditions (every question is optional)</legend>
            {contextYesNo.map((item) => (
              <ChoiceSelect
                key={item.name}
                name={item.name}
                label={item.label}
                choices={yesNoRefuse}
              />
            ))}
            <ChoiceSelect name="hunger" label="How hungry are you?" choices={hungerChoices} />
            <ChoiceSelect
              name="hormonal_context"
              label="Is a hormonal or cycle change affecting your sense of smell today?"
              choices={hormonalChoices}
            />
            <div className="fields fields-compact">
              {contextNumbers.map((item) => (
                <label key={item.name}>
                  {item.label}
                  <input name={item.name} type="number" step="any" min={item.min} max={item.max} />
                </label>
              ))}
            </div>
            <label>
              What can you smell in the room?
              <input name="ambient_odor_detail" />
            </label>
            <label>
              Anything else we should know
              <textarea name="note" rows={2} />
            </label>
            <button>Save conditions</button>
          </fieldset>
        </form>
      )}
      {consent === 'granted' && context?.recorded && (
        <p className="notice" role="status">
          Your conditions are saved.
        </p>
      )}
      {consent === 'granted' && (
        <button
          className="secondary"
          disabled={task.busy}
          onClick={() => void task.run(() => record('withdrawn'))}
        >
          Withdraw my consent
        </button>
      )}
      {transcription && (
        <label>
          Session start time written on the sheet
          <input
            type="datetime-local"
            value={startedAt}
            onChange={(event) => setStartedAt(event.target.value)}
          />
        </label>
      )}
      <button disabled={task.busy} onClick={() => void task.run(continueToSamples)}>
        Continue to the samples
      </button>
    </>
  )
}
