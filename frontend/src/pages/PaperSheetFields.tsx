import { useState } from 'react'
import type { Sample } from '../api/types'
import {
  SPRAY_TO_SMELL_CEILING_MINUTES,
  elapsedWholeMinutes,
  fromServerInstant,
  overCeiling,
  sprayToSmellMinutes,
} from '../content/transcription'

/**
 * The fields a facilitator copies from one column of an evaluator's paper
 * sheet: the blind code printed on it and the three times written on it.
 *
 * The code is typed, not picked, on purpose: reading it off the sheet is what
 * proves this column is open on the right sample for the right evaluator, and
 * the save is refused when it does not match. The first smell is asked for
 * only while it is still unrecorded; after that the recorded time is shown and
 * later columns of the same sample need only the spray and finish times.
 * Elapsed minutes are worked out here and by the server, never typed.
 *
 * The inputs are uncontrolled form fields (read by name when saving); the
 * state here only drives the live elapsed-minutes and ceiling notes, and the
 * parent remounts this component after each saved column to clear it.
 */
export function PaperSheetFields({
  sample,
  defaultSprayed,
  groupBlotter = false,
  restored,
}: {
  sample: Sample
  /** The spray time last typed for this sample, so later columns start from it. */
  defaultSprayed: string
  /**
   * True for a SHARED_GROUP program: one blotter per sample goes round the
   * evaluators, so the blind code is shared and each column's spray time is
   * that of the blotter this evaluator smelled, not of the first blotter.
   */
  groupBlotter?: boolean
  /** The times typed before a page reload, which start the three time fields. */
  restored?: Record<string, string>
}) {
  const [sprayed, setSprayed] = useState(restored?.sprayed_at ?? defaultSprayed)
  const [smelled, setSmelled] = useState(restored?.first_smelled_at ?? '')
  const [finished, setFinished] = useState(restored?.observed_at ?? '')
  const recorded = sample.presented_at ? fromServerInstant(sample.presented_at) : null
  const elapsed = elapsedWholeMinutes(sprayed, finished)
  const gap = recorded ? null : sprayToSmellMinutes(sprayed, smelled)

  return (
    <fieldset className="paper-sheet">
      <legend>Copy from the paper sheet</legend>
      <p className="notice">
        Type what is written on this column. The sheet keeps the exact times; the app keeps when the
        blotter was first smelled, when this column finished, and the whole minutes since the spray.
      </p>
      {groupBlotter && (
        <p className="notice" role="note">
          Group blotter session: every evaluator shares this blind code, so a matching code does not
          show whose sheet this is. Type the time sprayed of the blotter THIS evaluator smelled. If
          the {SPRAY_TO_SMELL_CEILING_MINUTES}-minute window from spray to this evaluator&apos;s
          first smell would have been exceeded, the facilitator sprays a new blotter of the same
          sample (same blind code) and writes its spray time on the sheet instead.
        </p>
      )}
      <label>
        Blind code printed on the sheet
        <input name="confirmed_blind_code" autoComplete="off" spellCheck={false} />
      </label>
      <div className="fields fields-compact">
        <label>
          Time sprayed
          <input
            name="sprayed_at"
            type="datetime-local"
            value={sprayed}
            onChange={(event) => setSprayed(event.target.value)}
          />
        </label>
        {recorded ? (
          <p>
            First smelled at{' '}
            <time dateTime={recorded.toISOString()}>{recorded.toLocaleString()}</time>, already
            recorded.
          </p>
        ) : (
          <label>
            Time first smelled
            <input
              name="first_smelled_at"
              type="datetime-local"
              value={smelled}
              onChange={(event) => setSmelled(event.target.value)}
            />
          </label>
        )}
        <label>
          Time this column finished
          <input
            name="observed_at"
            type="datetime-local"
            value={finished}
            onChange={(event) => setFinished(event.target.value)}
          />
        </label>
      </div>
      <p aria-live="polite">
        {elapsed === null
          ? 'Elapsed minutes will be worked out from the spray and finish times.'
          : `Elapsed since the spray: ${elapsed} whole minute${elapsed === 1 ? '' : 's'}.`}
      </p>
      {gap !== null && overCeiling(sprayed, smelled) && (
        <p className="notice" role="status">
          First smelled {Math.round(gap * 10) / 10} minutes after the spray, over the{' '}
          {SPRAY_TO_SMELL_CEILING_MINUTES}-minute ceiling. It is saved as written and flagged as a
          deviation; nothing is dropped.
        </p>
      )}
    </fieldset>
  )
}
