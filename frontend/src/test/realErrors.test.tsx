import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import App from '../App'
import { api, requestErrorMessage } from '../api/client'
import { GuidedCalibrationFlow } from '../pages/GuidedCalibrationFlow'
import { apiUrl, bootstrapHandlers, getJson, server } from './msw/server'

/**
 * Real axios, real error objects (architecture review F-11). Every message
 * below is the one an evaluator would read, produced by the same code path the
 * browser runs rather than by a mock that pretends no error is ever an axios one.
 */
async function failureOf(path: string): Promise<unknown> {
  try {
    await api.get(path)
  } catch (error) {
    return error
  }
  throw new Error(`${path} did not fail`)
}

describe('requestErrorMessage with real axios errors', () => {
  it('reads a plain string detail from the server', async () => {
    server.use(
      http.get(apiUrl('/thing'), () =>
        HttpResponse.json({ detail: 'Skin test must be planned' }, { status: 409 })
      )
    )

    expect(requestErrorMessage(await failureOf('/thing'))).toBe('Skin test must be planned')
  })

  it('reads a structured detail message', async () => {
    server.use(
      http.get(apiUrl('/thing'), () =>
        HttpResponse.json({ detail: { message: 'Choose an active program.' } }, { status: 422 })
      )
    )

    expect(requestErrorMessage(await failureOf('/thing'))).toBe('Choose an active program.')
  })

  it('explains a refused session and a refused action in plain words', async () => {
    server.use(
      http.get(apiUrl('/unauthenticated'), () => new HttpResponse(null, { status: 401 })),
      http.get(apiUrl('/forbidden'), () => new HttpResponse(null, { status: 403 }))
    )

    expect(requestErrorMessage(await failureOf('/unauthenticated'))).toMatch(
      /session could not be verified/i
    )
    expect(requestErrorMessage(await failureOf('/forbidden'))).toMatch(/do not have access/i)
  })

  it('falls back for a server error with no usable detail', async () => {
    server.use(http.get(apiUrl('/thing'), () => new HttpResponse('boom', { status: 500 })))

    expect(requestErrorMessage(await failureOf('/thing'))).toMatch(/request failed/i)
  })

  it('tells the evaluator the service could not be reached when the connection drops', async () => {
    server.use(http.get(apiUrl('/thing'), () => HttpResponse.error()))

    expect(requestErrorMessage(await failureOf('/thing'))).toMatch(/could not be reached/i)
  })
})

describe('the app with real failures', () => {
  it('shows an understandable error, not a blank page, when the first load is refused', async () => {
    window.history.replaceState({}, '', '/home')
    // The first matching handler wins, so the refusal goes ahead of the defaults.
    server.use(
      http.get(apiUrl('/calibration/enrollments'), () =>
        HttpResponse.json({ detail: 'Not allowed here' }, { status: 403 })
      ),
      ...bootstrapHandlers()
    )

    render(<App />)

    expect(await screen.findByText('Not allowed here')).toBeInTheDocument()
  })
})

const enrollment = {
  id: 'enr1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: true,
  presentations: [
    {
      id: 'samp1',
      session_id: 'sess1',
      blind_code: 'ABC-123',
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      post_reveal_entry: false,
      observations: [],
    },
  ],
}

describe('saving an observation through interruption and retry', () => {
  function renderFlow() {
    return render(
      <GuidedCalibrationFlow
        enrollmentId="enr1"
        onExitToManualBrowse={() => undefined}
        onRevealed={async () => undefined}
      />
    )
  }

  it('keeps the form after a dropped connection and saves on retry', async () => {
    let attempts = 0
    server.use(
      getJson('/calibration/enrollments/enr1', enrollment),
      http.post(apiUrl('/calibration/presentations/samp1/observations'), () => {
        attempts += 1
        return attempts === 1
          ? HttpResponse.error()
          : HttpResponse.json({ id: 'o1' }, { status: 201 })
      })
    )
    renderFlow()

    fireEvent.change(await screen.findByLabelText('Detected'), { target: { value: 'yes' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    expect(await screen.findByText(/could not be reached/i)).toBeInTheDocument()
    // Nothing the evaluator chose was lost.
    expect(screen.getByLabelText('Detected')).toHaveValue('yes')

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    expect(await screen.findByText(/observation saved/i)).toBeInTheDocument()
    expect(attempts).toBe(2)
  })

  it('shows the server reason when a stage is already locked', async () => {
    server.use(
      getJson('/calibration/enrollments/enr1', enrollment),
      http.post(apiUrl('/calibration/presentations/samp1/observations'), () =>
        HttpResponse.json(
          { detail: 'Stage is locked; original responses are retained' },
          { status: 409 }
        )
      )
    )
    renderFlow()

    fireEvent.change(await screen.findByLabelText('Detected'), { target: { value: 'yes' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() =>
      expect(
        screen.getByText(/stage is locked; original responses are retained/i)
      ).toBeInTheDocument()
    )
  })

  it('names the access problem when a lock is refused', async () => {
    server.use(
      getJson('/calibration/enrollments/enr1', {
        ...enrollment,
        presentations: [{ ...enrollment.presentations[0] }],
      }),
      http.post(
        apiUrl('/calibration/presentations/samp1/lock/BLOTTER'),
        () => new HttpResponse(null, { status: 403 })
      )
    )
    renderFlow()

    fireEvent.click(await screen.findByRole('button', { name: /lock blotter responses/i }))
    fireEvent.click(await screen.findByRole('button', { name: /confirm blotter lock/i }))

    expect(await screen.findByText(/do not have access/i)).toBeInTheDocument()
  })
})
