import { useState } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CalibrationPage } from '../pages/CalibrationPage'
import type { Enrollment, EnrollmentSummary } from '../api/types'
import { assignmentLinkFor, assignmentQuery } from '../routing/routes'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

/*
 * Found by the real-stack tier: after a guided reveal the app reloads its
 * assignments, the entry routing finds nothing left to resume, and the page used
 * to swap the revealed identities for "Nothing new is assigned right now". They
 * must stay on screen until the person chooses to browse.
 */
const summary = (revealed: boolean): EnrollmentSummary => ({
  id: 'e1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed,
  has_started: true,
  total_presentations: 1,
  blotter_complete: 1,
  skin_planned: 0,
  skin_complete: 0,
  program_name: 'Baseline',
  program_version: '1',
})

const presentation = {
  id: 's1',
  session_id: 'sess1',
  blind_code: 'AAA1',
  position: 1,
  skin_planned: false,
  blotter_locked: true,
  skin_locked: false,
  post_reveal_entry: false,
  observations: [],
}

const beforeReveal: Enrollment = {
  id: 'e1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: false,
  reveal_eligible: true,
  reveal_blocker: null,
  skin_plan_locked: true,
  presentations: [presentation],
}

const afterReveal: Enrollment = {
  ...beforeReveal,
  revealed: true,
  presentations: [
    {
      ...presentation,
      post_reveal_entry: true,
      identity: { fragrance_id: 'f1', name: 'Signature', brand: 'House', concentration: 'EDP' },
    },
  ],
}

function Harness() {
  const [assignments, setAssignments] = useState<EnrollmentSummary[]>([summary(false)])
  return (
    <CalibrationPage
      assignments={assignments}
      programs={[]}
      reviewers={[]}
      access={{ username: 'recorder', manager: false }}
      navigate={vi.fn()}
      reload={async () => setAssignments([summary(true)])}
    />
  )
}

describe('guided reveal', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    post.mockResolvedValue({ data: {} })
  })

  it('keeps the revealed identities on screen after the assignments reload', async () => {
    let revealedOnServer = false
    post.mockImplementation((url: string) => {
      if (url.endsWith('/reveal')) revealedOnServer = true
      return Promise.resolve({ data: {} })
    })
    get.mockImplementation((url: string) => {
      if (url.includes('/rankings')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: revealedOnServer ? afterReveal : beforeReveal })
    })
    render(<Harness />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue without ranking' }))
    // The end of the last session waits for the facilitator before the reveal.
    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reveal completed baseline' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm reveal' }))

    expect(await screen.findByText(/Reveal complete\./)).toBeInTheDocument()
    expect(screen.getByText(/House.*Signature.*EDP/)).toBeInTheDocument()
    // Let the reload that follows the reveal settle, then look again.
    await waitFor(() => expect(post).toHaveBeenCalledWith(expect.stringContaining('/reveal')))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getByText(/Reveal complete\./)).toBeInTheDocument()
    expect(screen.getByText(/House.*Signature.*EDP/)).toBeInTheDocument()
    expect(screen.queryByText('Nothing new is assigned right now.')).not.toBeInTheDocument()
  })

  it('in manual browse, lists a closed sample without offering it and leaves a household reveal to the manager', async () => {
    const household: Enrollment = {
      ...beforeReveal,
      reveal_policy: 'HOUSEHOLD',
      presentations: [
        presentation,
        {
          ...presentation,
          id: 's2',
          session_id: 'sess2',
          blind_code: 'BBB2',
          blotter_locked: false,
          available: false,
        },
      ],
    }
    get.mockResolvedValue({ data: household })
    render(
      <CalibrationPage
        assignments={[summary(false)]}
        programs={[]}
        reviewers={[]}
        access={{ username: 'recorder', manager: false }}
        navigate={vi.fn()}
        reload={vi.fn()}
        initialAssignmentId={assignmentLinkFor(assignmentQuery('e1'), ['e1']).initialAssignmentId}
      />
    )

    const closed = await screen.findByRole('button', { name: /BBB2/ })
    expect(closed).toBeDisabled()
    expect(closed).toHaveTextContent('Not open yet')
    expect(screen.getByRole('button', { name: /AAA1/ })).toHaveTextContent('Locked')
    expect(screen.getByText(/reveals every evaluator together/)).toBeInTheDocument()
    expect(screen.getByText(/reveals the whole household together/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reveal completed baseline' })).toBeDisabled()
  })

  it('still lets the person leave the revealed view and browse', async () => {
    let revealedOnServer = false
    post.mockImplementation((url: string) => {
      if (url.endsWith('/reveal')) revealedOnServer = true
      return Promise.resolve({ data: {} })
    })
    get.mockImplementation((url: string) => {
      if (url.includes('/rankings')) return Promise.resolve({ data: [] })
      if (url.includes('/calibration/enrollments/e1'))
        return Promise.resolve({ data: revealedOnServer ? afterReveal : beforeReveal })
      return Promise.resolve({ data: [] })
    })
    render(<Harness />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue without ranking' }))
    // The end of the last session waits for the facilitator before the reveal.
    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reveal completed baseline' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm reveal' }))
    await screen.findByText(/Reveal complete\./)

    fireEvent.click(screen.getByRole('button', { name: 'Browse assignments manually instead' }))

    await waitFor(() => expect(screen.queryByText(/Reveal complete\./)).not.toBeInTheDocument())
  })
})
