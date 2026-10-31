import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SampleObservationPanel } from '../pages/SampleObservationPanel'
import { submissionFor } from '../content/submissionKey'
import type { Enrollment, Sample } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

const sample: Sample = {
  id: 's1',
  session_id: 'sess1',
  blind_code: 'AAA1',
  position: 1,
  skin_planned: false,
  blotter_locked: false,
  skin_locked: false,
  post_reveal_entry: false,
  observations: [],
}
const enrollment = { id: 'e1', skin_plan_locked: true } as unknown as Enrollment

function renderPanel() {
  // A failed save leaves the form as it was, as useTask does.
  const task = {
    busy: false,
    run: async (work: () => Promise<void>) => {
      try {
        await work()
      } catch {
        // swallowed: the recorder sees an error and presses Save again
      }
    },
    setNotice: vi.fn(),
  } as never
  return render(
    <SampleObservationPanel
      enrollment={enrollment}
      sample={sample}
      stage="BLOTTER"
      stageFixed
      detected="yes"
      setDetected={vi.fn()}
      task={task}
      refresh={async () => undefined}
    />
  )
}

async function pressSave(times: number) {
  fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
  await waitFor(() => expect(post).toHaveBeenCalledTimes(times))
  return post.mock.calls[times - 1][1] as Record<string, unknown>
}

describe('submissionFor', () => {
  it('reuses the pending submission for the same answers', () => {
    const first = submissionFor(
      null,
      'answers',
      () => 't1',
      () => 'key-one-1'
    )
    const retry = submissionFor(
      first,
      'answers',
      () => 't2',
      () => 'key-two-2'
    )
    expect(retry).toBe(first)
    expect(retry).toEqual({ fingerprint: 'answers', key: 'key-one-1', observedAt: 't1' })
  })

  it('starts fresh when the answers changed', () => {
    const first = submissionFor(
      null,
      'answers',
      () => 't1',
      () => 'key-one-1'
    )
    const changed = submissionFor(
      first,
      'other answers',
      () => 't2',
      () => 'key-two-2'
    )
    expect(changed).toEqual({ fingerprint: 'other answers', key: 'key-two-2', observedAt: 't2' })
  })

  it('makes keys the server accepts by default', () => {
    const { key } = submissionFor(null, 'answers')
    expect(key).toMatch(/^[A-Za-z0-9_-]{8,64}$/)
    expect(submissionFor(null, 'answers').key).not.toBe(key)
  })

  it('still makes acceptable keys where randomUUID is missing (older browsers)', () => {
    let counter = 0
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.forEach((_, index) => {
          bytes[index] = (counter + index) % 256
        })
        counter += 16
        return bytes
      },
    })
    try {
      const { key } = submissionFor(null, 'answers')
      expect(key).toMatch(/^[A-Za-z0-9_-]{8,64}$/)
      expect(key).toHaveLength(32)
      expect(submissionFor(null, 'answers').key).not.toBe(key)
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('observation form idempotency key (D-22)', () => {
  beforeEach(() => {
    post.mockReset()
  })

  it('retries a failed save under the same key and observation time', async () => {
    post.mockRejectedValueOnce(new Error('network dropped'))
    post.mockResolvedValueOnce({ data: { id: 'o1', replayed: false } })
    renderPanel()

    const failed = await pressSave(1)
    const retried = await pressSave(2)

    expect(failed.idempotency_key).toEqual(expect.any(String))
    expect(retried.idempotency_key).toBe(failed.idempotency_key)
    expect(retried.observed_at).toBe(failed.observed_at)
    expect(retried).toEqual(failed)
  })

  it('sends a fresh key for the next submission after a success', async () => {
    post.mockResolvedValue({ data: { id: 'o1', replayed: false } })
    renderPanel()

    const first = await pressSave(1)
    const second = await pressSave(2)

    expect(second.idempotency_key).not.toBe(first.idempotency_key)
  })

  it('sends a fresh key when the recorder changes an answer before retrying', async () => {
    post.mockRejectedValueOnce(new Error('network dropped'))
    post.mockResolvedValueOnce({ data: { id: 'o1', replayed: false } })
    renderPanel()

    const failed = await pressSave(1)
    fireEvent.change(screen.getByLabelText(/time of this observation/i), {
      target: { value: '2026-10-30T09:15' },
    })
    const changed = await pressSave(2)

    expect(changed.idempotency_key).not.toBe(failed.idempotency_key)
    expect(changed.observed_at).toBe(new Date('2026-10-30T09:15').toISOString())
  })
})
