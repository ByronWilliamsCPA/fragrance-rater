import { useState } from 'react'
import { api } from '../api/client'
import { isSessionAlreadyEnded, toInstant } from '../content/transcription'
import type { useTask } from '../hooks/useTask'

/**
 * The pause between two sessions: nothing moves on until the facilitator
 * continues.
 *
 * In the facilitated format (`transcription`) the session's end is recorded
 * here, as the time written on the paper sheet. A session that already ended
 * (a reload that shows this screen again) is not an error.
 */
export function SessionBoundaryStep({
  sessionId,
  task,
  onContinue,
  transcription = false,
}: {
  sessionId: string
  task: ReturnType<typeof useTask>
  onContinue: () => void
  transcription?: boolean
}) {
  const [endedAt, setEndedAt] = useState('')

  async function endAndContinue() {
    const paperEnd = toInstant(endedAt)
    if (!paperEnd) {
      task.setError('Enter the end time written on the sheet before continuing.')
      return
    }
    try {
      await api.post(`/calibration/sessions/${sessionId}/end`, { ended_at: paperEnd })
    } catch (reason) {
      if (!isSessionAlreadyEnded(reason)) throw reason
    }
    onContinue()
  }

  return (
    <>
      <p className="notice" role="status">
        Session complete. Wait for the facilitator.
      </p>
      <p>
        Every sample in this session is saved. The next part starts only when the facilitator
        continues.
      </p>
      {transcription && (
        <label>
          Session end time written on the sheet
          <input
            type="datetime-local"
            value={endedAt}
            onChange={(event) => setEndedAt(event.target.value)}
          />
        </label>
      )}
      <button
        disabled={task.busy}
        onClick={() => (transcription ? void task.run(endAndContinue) : onContinue())}
      >
        Facilitator: continue
      </button>
    </>
  )
}
