import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { splitEntries } from './splitEntries'

type EntryListFieldProps = {
  /** Id of the "add" input, so an error summary link lands somewhere typeable. */
  id: string
  label: string
  hint?: string
  /** Singular noun for one entry, used in control names: "top note", "barcode". */
  itemNoun: string
  entries: string[]
  onChange: (entries: string[]) => void
  maxEntries: number
  maxLength?: number
  error?: string
  inputMode?: 'text' | 'numeric'
  disabled?: boolean
}

/**
 * An ordered list of short text entries the person can add, edit in place,
 * reorder, and remove.
 *
 * Order is meaningful (a house lists its most prominent note first), so
 * every entry can move, and every control names the entry it acts on for a
 * screen reader rather than repeating "Remove" down the list.
 */
export function EntryListField({
  id,
  label,
  hint,
  itemNoun,
  entries,
  onChange,
  maxEntries,
  maxLength = 200,
  error,
  inputMode = 'text',
  disabled,
}: EntryListFieldProps) {
  const [pending, setPending] = useState('')
  const [announcement, setAnnouncement] = useState('')
  const [addError, setAddError] = useState('')
  const legendId = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const addInput = useRef<HTMLInputElement>(null)
  const rowInputs = useRef<(HTMLInputElement | null)[]>([])
  const full = entries.length >= maxEntries
  const shownError = addError || error
  const describedBy = [hint && hintId, shownError && errorId].filter(Boolean).join(' ') || undefined

  function add() {
    const additions = splitEntries(pending).slice(0, maxEntries - entries.length)
    if (!additions.length) return
    if (additions.some((entry) => entry.length > maxLength)) {
      setAddError(`Each ${itemNoun} can be up to ${maxLength} characters.`)
      return
    }
    setAddError('')
    onChange([...entries, ...additions])
    setPending('')
    setAnnouncement(
      additions.length === 1 ? `Added ${additions[0]}.` : `Added ${additions.length} ${itemNoun}s.`
    )
    addInput.current?.focus()
  }

  function onAddKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    // Enter adds the entry instead of submitting the whole form.
    if (event.key !== 'Enter') return
    event.preventDefault()
    add()
  }

  function edit(index: number, value: string) {
    onChange(entries.map((entry, position) => (position === index ? value : entry)))
  }

  function remove(index: number) {
    const removed = entries[index]
    const next = entries.filter((_, position) => position !== index)
    onChange(next)
    setAnnouncement(`Removed ${removed || `${itemNoun} ${index + 1}`}.`)
    // Keep focus in the list: the entry that moved into this slot, else the
    // one above, else the add box.
    window.requestAnimationFrame(() => {
      const target = rowInputs.current[Math.min(index, next.length - 1)]
      ;(target ?? addInput.current)?.focus()
    })
  }

  function move(index: number, offset: -1 | 1) {
    const target = index + offset
    if (target < 0 || target >= entries.length) return
    const next = [...entries]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
    setAnnouncement(`Moved ${entries[index]} to position ${target + 1} of ${entries.length}.`)
  }

  return (
    <fieldset className="entry-list" aria-describedby={describedBy} aria-labelledby={legendId}>
      <legend id={legendId}>{label}</legend>
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {shownError && (
        <p id={errorId} className="field-error">
          {shownError}
        </p>
      )}
      {entries.length > 0 && (
        <ol className="entry-list__entries">
          {entries.map((entry, index) => {
            const name = entry.trim() || `${itemNoun} ${index + 1}`
            return (
              // Index keys are deliberate: entries are plain strings that may
              // repeat across edits, and every row is a controlled input, so
              // React reusing a row for the value now at that index is correct.
              <li key={index} className="entry-list__entry">
                <span className="entry-list__position" aria-hidden="true" data-numeric>
                  {index + 1}
                </span>
                <input
                  ref={(element) => {
                    rowInputs.current[index] = element
                  }}
                  aria-label={`${itemNoun[0].toUpperCase()}${itemNoun.slice(1)} ${index + 1}`}
                  value={entry}
                  maxLength={maxLength}
                  inputMode={inputMode}
                  disabled={disabled}
                  onChange={(event) => edit(index, event.target.value)}
                />
                <div className="entry-list__actions">
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Move ${name} up`}
                    disabled={disabled || index === 0}
                    onClick={() => move(index, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Move ${name} down`}
                    disabled={disabled || index === entries.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    aria-label={`Remove ${name}`}
                    disabled={disabled}
                    onClick={() => remove(index)}
                  >
                    Remove
                  </button>
                </div>
              </li>
            )
          })}
        </ol>
      )}
      {full ? (
        <p className="field-hint">The limit is {maxEntries} entries.</p>
      ) : (
        <div className="entry-list__add">
          <label htmlFor={id}>Add {itemNoun}</label>
          <div className="entry-list__add-row">
            <input
              ref={addInput}
              id={id}
              value={pending}
              inputMode={inputMode}
              disabled={disabled}
              aria-invalid={shownError ? true : undefined}
              aria-describedby={describedBy}
              onChange={(event) => setPending(event.target.value)}
              onKeyDown={onAddKeyDown}
            />
            <button
              type="button"
              className="secondary"
              disabled={disabled || !pending.trim()}
              onClick={add}
            >
              Add
            </button>
          </div>
        </div>
      )}
      <p className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>
    </fieldset>
  )
}
