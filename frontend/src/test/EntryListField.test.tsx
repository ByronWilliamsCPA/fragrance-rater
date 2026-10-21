import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useState } from 'react'
import { EntryListField } from '../components/EntryListField'

function Harness({ initial = [], maxEntries = 5 }: { initial?: string[]; maxEntries?: number }) {
  const [entries, setEntries] = useState(initial)
  return (
    <EntryListField
      id="notes"
      label="Notes"
      itemNoun="note"
      entries={entries}
      maxEntries={maxEntries}
      maxLength={10}
      onChange={setEntries}
    />
  )
}

describe('EntryListField', () => {
  it('refuses an entry longer than the limit and says why', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Add note'), {
      target: { value: 'Bergamot, Labdanum absolute' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByText('Each note can be up to 10 characters.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Note 1')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Add note')).toHaveAttribute('aria-invalid', 'true')
  })

  it('stops offering to add once the list is full, keeping only what fits', () => {
    render(<Harness initial={['Iris']} maxEntries={2} />)
    fireEvent.change(screen.getByLabelText('Add note'), { target: { value: 'Rose, Oud' } })
    fireEvent.keyDown(screen.getByLabelText('Add note'), { key: 'Enter' })
    expect(screen.getByLabelText('Note 2')).toHaveValue('Rose')
    expect(screen.queryByLabelText('Add note')).not.toBeInTheDocument()
    expect(screen.getByText('The limit is 2 entries.')).toBeInTheDocument()
  })

  it('edits an entry in place and moves focus when one is removed', () => {
    const frame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      callback(0)
      return 0
    })
    render(<Harness initial={['Iris', 'Rose']} />)
    fireEvent.change(screen.getByLabelText('Note 1'), { target: { value: 'Orris' } })
    expect(screen.getByLabelText('Note 1')).toHaveValue('Orris')
    fireEvent.click(screen.getByRole('button', { name: 'Remove Orris' }))
    expect(screen.getByLabelText('Note 1')).toHaveValue('Rose')
    expect(screen.getByLabelText('Note 1')).toHaveFocus()
    frame.mockRestore()
  })

  it('ignores keys other than Enter and blank additions', () => {
    render(<Harness />)
    const add = screen.getByLabelText('Add note')
    fireEvent.change(add, { target: { value: ' , ' } })
    fireEvent.keyDown(add, { key: 'Enter' })
    fireEvent.keyDown(add, { key: 'a' })
    expect(screen.queryByLabelText('Note 1')).not.toBeInTheDocument()
  })
})
