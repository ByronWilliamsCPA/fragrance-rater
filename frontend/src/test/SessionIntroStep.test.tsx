import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SessionIntroStep } from '../pages/SessionIntroStep'
import { contextPayload } from '../content/contextPayload'
import type { Enrollment } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

const enrollment = {
  id: 'e1',
  reviewer_id: 'r1',
  presentations: [{ id: 's1', session_id: 'sess1' }],
} as unknown as Enrollment

function setup(options: { approved: boolean; consent?: string; recorded?: boolean }) {
  get.mockImplementation((url: string) => {
    if (url.includes('/consent/text'))
      return Promise.resolve({
        data: { version: 'v1', approved: options.approved, text: 'Consent wording here' },
      })
    if (url.includes('/consent'))
      return Promise.resolve({ data: { state: { session_context: options.consent ?? 'none' } } })
    return Promise.resolve({ data: { recorded: options.recorded ?? false } })
  })
  const onDone = vi.fn()
  const task = {
    busy: false,
    // Like the real useTask, a failed action is caught and reported, not thrown.
    run: async (work: () => Promise<void>) => {
      try {
        await work()
      } catch {
        /* surfaced through task.error in the app */
      }
    },
    setNotice: vi.fn(),
  } as never
  render(<SessionIntroStep enrollment={enrollment} task={task} onDone={onDone} />)
  return onDone
}

describe('SessionIntroStep', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    post.mockResolvedValue({ data: {} })
  })

  it('shows the wording and, while it is a draft, offers no way to agree', async () => {
    setup({ approved: false })

    expect(await screen.findByText('Consent wording here')).toBeInTheDocument()
    expect(screen.getByText(/still being finalized/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /i agree/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue to the samples' })).toBeInTheDocument()
  })

  it('records a grant against the enrollment once the wording is approved', async () => {
    setup({ approved: true })

    fireEvent.click(await screen.findByRole('button', { name: /i agree/i }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/reviewers/r1/consent', {
        scope: 'session_context',
        event_type: 'granted',
        enrollment_id: 'e1',
      })
    )
  })

  it('asks the conditions questions only after consent, with every answer optional', async () => {
    setup({ approved: true, consent: 'granted' })

    expect(await screen.findByText(/every question is optional/i)).toBeInTheDocument()
    const unwell = screen.getByLabelText(/feeling unwell/i) as HTMLSelectElement
    expect(Array.from(unwell.options).map((option) => option.value)).toEqual([
      '',
      'yes',
      'no',
      'prefer_not_to_answer',
    ])
    expect(screen.getByLabelText(/hours since you last ate/i)).not.toBeRequired()
  })

  it('does not show the questions without a current grant', async () => {
    setup({ approved: true, consent: 'withdrawn' })

    await screen.findByText('Consent wording here')
    expect(screen.queryByText(/every question is optional/i)).not.toBeInTheDocument()
  })

  it('sends only the answered fields', async () => {
    setup({ approved: true, consent: 'granted' })
    await screen.findByText(/every question is optional/i)
    fireEvent.change(screen.getByLabelText(/feeling unwell/i), { target: { value: 'no' } })
    fireEvent.change(screen.getByLabelText(/hours since you last ate/i), {
      target: { value: '3.5' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save conditions' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/sessions/sess1/context', {
        illness: 'no',
        hours_since_food: 3.5,
      })
    )
  })

  it('lets the evaluator withdraw consent', async () => {
    setup({ approved: true, consent: 'granted', recorded: true })

    fireEvent.click(await screen.findByRole('button', { name: 'Withdraw my consent' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/reviewers/r1/consent', {
        scope: 'session_context',
        event_type: 'withdrawn',
        enrollment_id: 'e1',
      })
    )
  })

  it('starts the session with the local time zone and moves on, whatever was answered', async () => {
    const onDone = setup({ approved: false })

    fireEvent.click(await screen.findByRole('button', { name: 'Continue to the samples' }))

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    const [url, body] = post.mock.calls[0] as [string, Record<string, unknown>]
    expect(url).toBe('/calibration/sessions/sess1/start')
    expect(typeof body.evaluator_timezone).toBe('string')
    expect(Date.parse(String(body.started_at))).not.toBeNaN()
  })

  it('moves on when the session was already started', async () => {
    const onDone = setup({ approved: false })
    post.mockRejectedValueOnce({ response: { status: 409 } })

    fireEvent.click(await screen.findByRole('button', { name: 'Continue to the samples' }))

    await waitFor(() => expect(onDone).toHaveBeenCalled())
  })

  it('stays put and reports when starting fails for any other reason', async () => {
    const onDone = setup({ approved: false })
    post.mockRejectedValueOnce({ response: { status: 500 } })

    fireEvent.click(await screen.findByRole('button', { name: 'Continue to the samples' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(onDone).not.toHaveBeenCalled()
  })
})

describe('contextPayload', () => {
  it('keeps a deliberate zero and drops blanks', () => {
    expect(
      contextPayload({ hours_since_caffeine: '0', hours_since_food: '', illness: '' })
    ).toEqual({ hours_since_caffeine: 0 })
  })
})
