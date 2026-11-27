import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Person } from '../api/types'
import { ProgramSetupPage } from '../pages/ProgramSetupPage'

const { get, post, put } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('../api/client', () => ({
  api: { get, post, put },
  requestErrorMessage: () => 'Request failed.',
}))

const NEW_PERSON: Person = { id: 'new-id', name: 'Test Evaluator' }

/** An error shaped like the one axios throws for a non-2xx response. */
function httpError(status: number, detail: unknown) {
  return Object.assign(new Error(`status ${status}`), {
    isAxiosError: true,
    response: { status, data: { detail } },
  })
}

/**
 * Stands in for the app shell: `reload` appends the newly created person to
 * the `reviewers` prop, the way the real reload refetches `/reviewers`.
 */
function Harness({ reload }: { reload: () => Promise<void> }) {
  const [reviewers, setReviewers] = useState<Person[]>([{ id: 'rev', name: 'Evaluator One' }])
  return (
    <ProgramSetupPage
      programs={[{ id: 'p', name: 'Pilot', version: '1', status: 'active' }]}
      reviewers={reviewers}
      reload={async () => {
        await reload()
        setReviewers((current) =>
          current.some((person) => person.id === NEW_PERSON.id) ? current : [...current, NEW_PERSON]
        )
      }}
      navigate={vi.fn()}
      initialProgramId="p"
    />
  )
}

async function renderPage(reload = vi.fn(() => Promise.resolve())) {
  render(<Harness reload={reload} />)
  await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
  return reload
}

/** The enrollment form's Evaluator dropdown (other forms on the page share the label). */
function enrollmentDropdown() {
  const form = screen.getByRole('button', { name: 'Enroll evaluator' }).closest('form')
  if (!form) throw new Error('Enrollment form missing')
  return within(form).getByLabelText('Evaluator')
}

function addEvaluator(name: string) {
  fireEvent.change(screen.getByLabelText('Evaluator name'), { target: { value: name } })
  fireEvent.click(screen.getByRole('button', { name: 'Add evaluator' }))
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockResolvedValue({ data: [] })
  put.mockResolvedValue({ data: {} })
  post.mockResolvedValue({
    data: { ...NEW_PERSON, created_at: '2026-11-26T00:00:00', evaluation_count: 0 },
  })
})

describe('program setup: add an evaluator', () => {
  it('posts the trimmed name, reloads, announces success and preselects the new person', async () => {
    const reload = await renderPage()

    addEvaluator('  Test Evaluator  ')

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Evaluator added. They can now be enrolled below.'
    )
    expect(post).toHaveBeenCalledWith('/reviewers', { name: 'Test Evaluator' })
    expect(reload).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Evaluator name')).toHaveValue('')
    // The refreshed list reaches the Evaluator dropdown and the new person is selected.
    const dropdown = enrollmentDropdown()
    expect(within(dropdown).getByRole('option', { name: 'Test Evaluator' })).toBeInTheDocument()
    expect(dropdown).toHaveValue('new-id')
  })

  it('shows a plain-language message for a duplicate name and keeps the input', async () => {
    post.mockRejectedValue(
      httpError(409, {
        error: 'REVIEWER_EXISTS',
        message: "Reviewer 'Test Evaluator' already exists",
      })
    )
    const reload = await renderPage()

    addEvaluator('Test Evaluator')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That name is already in use. Choose a different name.'
    )
    expect(screen.queryByText(/already exists/)).toBeNull()
    expect(reload).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.getByLabelText('Evaluator name')).toHaveValue('Test Evaluator')
    expect(
      within(enrollmentDropdown()).queryByRole('option', { name: 'Test Evaluator' })
    ).toBeNull()
  })

  it('uses the shared request error for other failures', async () => {
    post.mockRejectedValue(httpError(500, 'boom'))
    const reload = await renderPage()

    addEvaluator('Test Evaluator')

    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed.')
    expect(reload).not.toHaveBeenCalled()
  })

  it('rejects a whitespace-only name without calling the API', async () => {
    const reload = await renderPage()

    addEvaluator('   ')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Enter the evaluator's name, 1 to 100 characters."
    )
    expect(post).not.toHaveBeenCalled()
    expect(reload).not.toHaveBeenCalled()
  })

  it('rejects an empty submission without calling the API', async () => {
    await renderPage()

    fireEvent.submit(screen.getByRole('form', { name: 'Add an evaluator' }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('limits the name to 100 characters and labels the control', async () => {
    await renderPage()

    const input = screen.getByLabelText('Evaluator name')
    expect(input).toHaveAttribute('maxlength', '100')
    expect(input).toBeRequired()
    expect(screen.getByRole('heading', { name: 'Add an evaluator' })).toBeInTheDocument()
  })
})
