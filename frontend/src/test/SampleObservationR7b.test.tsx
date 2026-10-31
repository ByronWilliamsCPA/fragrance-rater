import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SampleObservationPanel } from '../pages/SampleObservationPanel'
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
  skin_planned: true,
  blotter_locked: false,
  skin_locked: false,
  post_reveal_entry: false,
  observations: [],
}
const enrollment = { id: 'e1', skin_plan_locked: true } as unknown as Enrollment

function renderPanel(stage: 'BLOTTER' | 'SKIN', detected = 'yes') {
  const task = {
    busy: false,
    run: async (work: () => Promise<void>) => work(),
    setNotice: vi.fn(),
  } as never
  return render(
    <SampleObservationPanel
      enrollment={enrollment}
      sample={sample}
      stage={stage}
      stageFixed
      detected={detected}
      setDetected={vi.fn()}
      task={task}
      refresh={async () => undefined}
    />
  )
}

function pick(element: HTMLElement, value: string) {
  fireEvent.change(element, { target: { value } })
}

function typeInto(element: HTMLElement, value: string) {
  fireEvent.change(element, { target: { value } })
}

async function save() {
  fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
  await waitFor(() => expect(post).toHaveBeenCalled())
  return post.mock.calls[0][1] as Record<string, unknown>
}

describe('R7b observation form', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: { id: 'o1' } })
  })

  it('stamps observed_at from the client clock and marks a detected response completed', async () => {
    const before = Date.now()
    renderPanel('BLOTTER')

    const data = await save()

    expect(data.response_status).toBe('completed')
    expect(Date.parse(String(data.observed_at))).toBeGreaterThanOrEqual(before - 1000)
  })

  it('uses the time a recorder types when transcribing a paper sheet', async () => {
    renderPanel('BLOTTER')
    fireEvent.change(screen.getByLabelText(/time of this observation/i), {
      target: { value: '2026-10-30T09:15' },
    })

    const data = await save()

    expect(data.observed_at).toBe(new Date('2026-10-30T09:15').toISOString())
  })

  it('records recognition and prior ownership on the blotter only', async () => {
    renderPanel('BLOTTER')
    pick(screen.getByLabelText(/do you recognize this/i), 'vaguely_familiar')
    pick(screen.getByLabelText(/owned or worn/i), 'unknown')

    const data = await save()

    expect(data.recognition).toBe('vaguely_familiar')
    expect(data.owned_or_worn).toBe('unknown')
    expect(data).not.toHaveProperty('season_fit')
  })

  it('lets the evaluator say why a group has no answers', async () => {
    renderPanel('BLOTTER', '')
    pick(screen.getByLabelText(/anything stopping you answering/i), 'unable_to_assess')

    const data = await save()

    expect(data.response_status).toBe('unable_to_assess')
  })

  it('saves a non-detection as not_detected', async () => {
    renderPanel('BLOTTER', 'no')

    const data = await save()

    expect(data.response_status).toBe('not_detected')
    expect(data.intensity).toBe(0)
  })

  it('offers only the fixed skin timepoints and sends the chosen minutes', async () => {
    renderPanel('SKIN')
    const select = screen.getByLabelText('Timepoint')
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.value)).toEqual([
      '10',
      '60',
      '240',
      '480',
    ])
    pick(select, '240')

    const data = await save()

    expect(data.elapsed_minutes).toBe(240)
  })

  it('sends scrub-off facts and multi-select fit choices on skin', async () => {
    renderPanel('SKIN')
    pick(screen.getByLabelText(/did you wash it off/i), 'yes')
    typeInto(screen.getByLabelText(/minutes until you washed/i), '90')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Spring' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Fall' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'At home' }))

    const data = await save()

    expect(data.scrubbed_off).toBe(true)
    expect(data.time_to_scrub_minutes).toBe(90)
    expect(data.season_fit).toEqual(['spring', 'fall'])
    expect(data.setting_fit).toEqual(['home'])
  })

  it('drops the scrub time when the evaluator did not wash it off', async () => {
    renderPanel('SKIN')
    pick(screen.getByLabelText(/did you wash it off/i), 'no')
    typeInto(screen.getByLabelText(/minutes until you washed/i), '90')

    const data = await save()

    expect(data.scrubbed_off).toBe(false)
    expect(data).not.toHaveProperty('time_to_scrub_minutes')
  })

  it('treats "none of these" and "cannot judge" as standalone answers', async () => {
    renderPanel('SKIN')
    const spring = screen.getByRole('checkbox', { name: 'Spring' })
    const none = screen.getAllByRole('checkbox', { name: 'None of these' })[0]
    fireEvent.click(spring)
    fireEvent.click(none)
    expect(spring).not.toBeChecked()
    expect(none).toBeChecked()

    fireEvent.click(spring)

    expect(none).not.toBeChecked()
    expect(spring).toBeChecked()
  })
})
