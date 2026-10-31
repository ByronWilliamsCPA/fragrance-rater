import { api } from '../api/client'
import type { Enrollment, Sample } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { EmptyState } from '../components/PageState'
import { FitChoiceField } from '../components/FitChoiceField'
import { ScaleField } from '../components/ScaleField'
import {
  blotterGroups,
  numericFieldNames,
  observationNotes,
  ownedOrWornChoices,
  recognitionChoices,
  seasonFitChoices,
  settingFitChoices,
  skinGroups,
  skinTimepoints,
  unansweredReasons,
  type ScaleGroup,
} from '../content/calibrationScales'
import type { useTask } from '../hooks/useTask'

/**
 * Renders one group of scales under a shared heading.
 *
 * The heading is what carries the descriptive/affective separation: without
 * it the twelve scales read as one undifferentiated run, and an evaluator has
 * no cue that "Discomfort" is a fact about them rather than about the scent.
 */
function ScaleGroupFields({
  group,
  isDisabled,
}: {
  group: ScaleGroup
  isDisabled?: (name: string) => boolean
}) {
  return (
    <div className="scale-group">
      <h3 className="scale-group__legend">{group.legend}</h3>
      <p className="scale-group__description">{group.description}</p>
      <div className="scale-stack">
        {group.scales.map((item) => (
          <ScaleField key={item.name} scale={item} disabled={isDisabled?.(item.name)} />
        ))}
      </div>
    </div>
  )
}

/**
 * Non-detection forces intensity to 0 and clears liking, so those two must not
 * accept input. The perceptual dimensions stay enabled, which is the behaviour
 * this form already had: whether they should also be closed off when nothing
 * was smelled is a data-model question, not a presentational one.
 */
function disabledOnNonDetection(name: string) {
  return name === 'intensity' || name === 'liking'
}

/**
 * Orders a sample's observations into a readable log.
 *
 * Blotter screens precede skin tests, and within a stage the timepoints run
 * earliest first. The API does not guarantee an order, and an out-of-sequence
 * row in an evaporation curve is actively misleading rather than merely untidy.
 */
function timeOrdered(observations: Enrollment['presentations'][number]['observations']) {
  const stageRank = (stage: string) => (stage === 'SKIN' ? 1 : 0)
  return [...observations].sort(
    (first, second) =>
      stageRank(first.stage) - stageRank(second.stage) ||
      first.elapsed_minutes - second.elapsed_minutes
  )
}

export type SampleObservationPanelProps = {
  enrollment: Enrollment
  sample: Sample
  stage: string
  /** Omitted when `stageFixed` is true: nothing to feed a selection back into. */
  setStage?: (stage: string) => void
  detected: string
  setDetected: (detected: string) => void
  task: ReturnType<typeof useTask>
  refresh: () => Promise<void>
  /**
   * True when the caller derives `stage` from something other than its own
   * switchable state (the guided wizard picks it from the current step, not
   * from a local selection). The selector then renders as read-only instead
   * of inviting a choice the caller can't act on.
   */
  stageFixed?: boolean
}

export function SampleObservationPanel({
  enrollment,
  sample,
  stage,
  setStage,
  detected,
  setDetected,
  task,
  refresh,
  stageFixed = false,
}: SampleObservationPanelProps) {
  async function save(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const data: Record<string, unknown> = {
      stage,
      elapsed_minutes: Number(values.elapsed_minutes || 0),
      detected: detected === '' ? null : detected === 'yes',
      // The client clock at submit, unless a recorder is transcribing a
      // paper sheet and names the real time of the observation.
      observed_at: values.observed_at
        ? new Date(String(values.observed_at)).toISOString()
        : new Date().toISOString(),
    }
    const reason = String(values.unanswered_reason || '')
    if (reason) data.response_status = reason
    else if (detected === 'no') data.response_status = 'not_detected'
    else if (detected === 'yes') data.response_status = 'completed'
    if (stage === 'BLOTTER') {
      data.recognition = values.recognition || null
      data.owned_or_worn = values.owned_or_worn || null
    } else {
      if (values.scrubbed_off) data.scrubbed_off = values.scrubbed_off === 'yes'
      if (values.scrubbed_off === 'yes' && values.time_to_scrub_minutes) {
        data.time_to_scrub_minutes = Number(values.time_to_scrub_minutes)
      }
      data.season_fit = new FormData(form).getAll('season_fit')
      data.setting_fit = new FormData(form).getAll('setting_fit')
    }
    for (const name of numericFieldNames) data[name] = !values[name] ? null : Number(values[name])
    if (detected === 'no') {
      data.intensity = 0
      data.liking = null
    }
    for (const note of observationNotes) data[note.name] = values[note.name] || null
    data.perceived_notes = values.perceived_notes
      ? String(values.perceived_notes)
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean)
      : null
    await api.post(
      `/calibration/presentations/${sample.id}/${sample.post_reveal_entry ? 'post-reveal' : 'observations'}`,
      data
    )
    form.reset()
    setDetected('')
    await refresh()
    task.setNotice('Observation saved. Original responses are retained.')
  }

  return (
    <>
      <p className="eyebrow">Sample {sample.position}</p>
      <h2 className="sample-heading">
        <span className="visually-hidden">Blind code </span>
        {sample.blind_code}
      </h2>
      {sample.identity && (
        <>
          <p className="notice">
            {sample.identity.brand} · {sample.identity.name} · {sample.identity.concentration}
          </p>
          {/*
            Rendered only inside this `identity` branch, which the backend
            populates only after reveal. Each name links to the source that
            attributes it: ADR-006 keeps a claim and its evidence together,
            and an attribution presented without a source reads as
            established fact when it is not.
          */}
          {sample.identity.perfumers && sample.identity.perfumers.length > 0 && (
            <p className="attribution">
              <span className="attribution__label">
                {sample.identity.perfumers.length === 1 ? 'Perfumer' : 'Perfumers'}
              </span>
              {sample.identity.perfumers.map((attribution, index) => (
                <span key={attribution.name}>
                  {index > 0 && ', '}
                  <a href={attribution.source_url} target="_blank" rel="noreferrer">
                    {attribution.name}
                    <span className="visually-hidden"> (opens the source)</span>
                  </a>
                </span>
              ))}
            </p>
          )}
        </>
      )}
      <label>
        Stage
        {stageFixed ? (
          <p>{stage === 'BLOTTER' ? 'Blotter screen' : 'Skin test'}</p>
        ) : (
          <select value={stage} onChange={(event) => setStage?.(event.target.value)}>
            <option value="BLOTTER">Blotter screen</option>
            {sample.skin_planned && <option value="SKIN">Skin test</option>}
          </select>
        )}
      </label>
      {!sample.skin_planned && !enrollment.skin_plan_locked && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const reason = String(new FormData(event.currentTarget).get('reason'))
            void task.run(async () => {
              await api.post(`/calibration/presentations/${sample.id}/skin-plan`, { reason })
              await refresh()
            })
          }}
        >
          <label>
            Reason to add a skin test
            <input name="reason" required placeholder="For example: low confidence" />
          </label>
          <button disabled={task.busy}>Plan skin test</button>
        </form>
      )}
      <form
        key={`${sample.id}-${stage}`}
        onSubmit={(event) => {
          event.preventDefault()
          const form = event.currentTarget
          void task.run(() => save(form))
        }}
      >
        <fieldset
          disabled={
            task.busy ||
            (!sample.post_reveal_entry &&
              (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked))
          }
        >
          <legend>
            {sample.post_reveal_entry ? 'Post-reveal observation' : 'Blind observation'}
          </legend>
          <div className="fields fields-compact">
            {stage === 'SKIN' ? (
              <label>
                Timepoint
                <select name="elapsed_minutes" defaultValue="10">
                  {skinTimepoints.map((point) => (
                    <option key={point.value} value={point.value}>
                      {point.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label>
                Elapsed minutes
                <input name="elapsed_minutes" type="number" min="0" defaultValue="0" />
              </label>
            )}
            <label>
              Detected
              <select value={detected} onChange={(event) => setDetected(event.target.value)}>
                <option value="">Unanswered</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
          </div>
          <label>
            Anything stopping you answering?
            <select name="unanswered_reason" defaultValue="">
              {unansweredReasons.map((reason) => (
                <option key={reason.value} value={reason.value}>
                  {reason.label}
                </option>
              ))}
            </select>
          </label>
          {detected === 'no' && (
            <p className="notice">Intensity will be saved as 0; liking will remain unanswered.</p>
          )}
          {stage === 'BLOTTER' && (
            <div className="fields fields-compact">
              <label>
                Do you recognize this?
                <select name="recognition" defaultValue="">
                  <option value="">Not answered</option>
                  {recognitionChoices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Have you owned or worn it?
                <select name="owned_or_worn" defaultValue="">
                  <option value="">Not answered</option>
                  {ownedOrWornChoices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          {blotterGroups.map((group) => (
            <ScaleGroupFields
              key={group.key}
              group={group}
              isDisabled={detected === 'no' ? disabledOnNonDetection : undefined}
            />
          ))}
          {stage === 'SKIN' && (
            <>
              {skinGroups.map((group) => (
                <ScaleGroupFields key={group.key} group={group} />
              ))}
              <label>
                Longevity (minutes)
                <input name="longevity_minutes" type="number" min="0" />
              </label>
              <div className="fields fields-compact">
                <label>
                  Did you wash it off?
                  <select name="scrubbed_off" defaultValue="">
                    <option value="">Not answered</option>
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </label>
                <label>
                  Minutes until you washed it off
                  <input name="time_to_scrub_minutes" type="number" min="0" />
                </label>
              </div>
              <FitChoiceField
                name="season_fit"
                legend="Which seasons suit it?"
                hint="Tick all that apply."
                choices={seasonFitChoices}
              />
              <FitChoiceField
                name="setting_fit"
                legend="Where would it suit you?"
                hint="Tick all that apply."
                choices={settingFitChoices}
              />
            </>
          )}
          <label>
            Perceived notes
            <input name="perceived_notes" placeholder="Your own words, separated by commas" />
          </label>
          {observationNotes.map((note) => (
            <label key={note.name}>
              {note.label}
              <textarea name={note.name} rows={2} />
            </label>
          ))}
          <label>
            Time of this observation (leave blank to use now)
            <input name="observed_at" type="datetime-local" />
          </label>
          <button>Save observation</button>
        </fieldset>
      </form>
      {!sample.post_reveal_entry && (
        <ConfirmAction
          actionLabel={`Lock ${stage.toLowerCase()} responses`}
          confirmLabel={`Confirm ${stage.toLowerCase()} lock`}
          description="Locking ends blind entry for this sample and stage. Review the saved observations before continuing."
          disabled={task.busy || (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked)}
          onConfirm={() =>
            void task.run(async () => {
              await api.post(`/calibration/presentations/${sample.id}/lock/${stage}`)
              await refresh()
            })
          }
        />
      )}
      <h3>Saved observations</h3>
      {sample.observations.length ? (
        /*
         * A blotter log: one row per timepoint, ordered by elapsed time, so
         * the evaporation curve is legible at a glance. Every professional
         * evaluation sheet this interface is modelled on is laid out this
         * way, and an unordered list of prose lines made a sequence of
         * observations read as unrelated entries.
         */
        /*
         * A region that can scroll sideways must be reachable by keyboard
         * (WCAG 2.1.1), so it is focusable and named.
         */
        <div
          className="log-scroll"
          // The rule assumes a non-interactive element needs no focus. A region that
          // scrolls sideways does: without it a keyboard user cannot reach the
          // hidden columns (WCAG 2.1.1; axe: scrollable-region-focusable).
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          role="region"
          aria-label="Saved observations, scrolls sideways on a narrow screen"
        >
          <table className="log">
            <caption className="visually-hidden">
              Saved observations for this sample, earliest first
            </caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Stage</th>
                <th scope="col">Phase</th>
                <th scope="col">Intensity</th>
                <th scope="col">Liking</th>
                <th scope="col">Comment</th>
              </tr>
            </thead>
            <tbody>
              {timeOrdered(sample.observations).map((observation) => (
                <tr key={observation.id}>
                  <th scope="row" data-numeric>
                    {observation.elapsed_minutes} min
                  </th>
                  <td>{observation.stage === 'SKIN' ? 'Skin' : 'Blotter'}</td>
                  <td>{observation.phase.replace(/_/g, ' ')}</td>
                  <td data-numeric>{observation.intensity ?? 'n/a'}</td>
                  <td data-numeric>{observation.liking ?? 'n/a'}</td>
                  <td>{observation.comments || 'n/a'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No observations yet">
          Save a timepoint to begin this sample history.
        </EmptyState>
      )}
    </>
  )
}
