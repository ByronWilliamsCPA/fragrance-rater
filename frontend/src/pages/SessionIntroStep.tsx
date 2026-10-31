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
 */
export function SessionIntroStep({
  enrollment,
  task,
  onDone,
}: {
  enrollment: Enrollment
  task: ReturnType<typeof useTask>
  onDone: () => void
}) {
  const sessionId = enrollment.presentations[0]?.session_id
  const [text, setText] = useState<ConsentText | null>(null)
  const [consent, setConsent] = useState<string>('none')
  const [context, setContext] = useState<ContextRead | null>(null)

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
    // Loaded once per enrollment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollment.id])

  async function record(eventType: 'granted' | 'withdrawn') {
    await api.post(`/calibration/reviewers/${enrollment.reviewer_id}/consent`, {
      scope: 'session_context',
      event_type: eventType,
      enrollment_id: enrollment.id,
    })
    await load()
    task.setNotice(
      eventType === 'granted' ? 'Thank you. Your choice is recorded.' : 'Consent withdrawn.'
    )
  }

  async function continueToSamples() {
    if (sessionId) {
      try {
        await api.post(`/calibration/sessions/${sessionId}/start`, {
          evaluator_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          started_at: new Date().toISOString(),
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
      {text && (
        <section aria-label="Consent wording" className="consent-text">
          <pre className="consent-text__body">{text.text}</pre>
        </section>
      )}
      {text && !text.approved && (
        <p className="notice" role="status">
          This wording is still being finalized, so questions about your conditions are switched off
          for now. You can go straight to the samples.
        </p>
      )}
      {text?.approved && consent !== 'granted' && (
        <div className="fields fields-compact">
          <button disabled={task.busy} onClick={() => void task.run(() => record('granted'))}>
            I agree to answer questions about my conditions
          </button>
        </div>
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
      <button disabled={task.busy} onClick={() => void task.run(continueToSamples)}>
        Continue to the samples
      </button>
    </>
  )
}
