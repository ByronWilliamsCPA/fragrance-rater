import { useId } from 'react'
import type { ScaleDefinition } from '../content/calibrationScales'

type ScaleFieldProps = {
  scale: ScaleDefinition
  disabled?: boolean
}

/**
 * A 0-to-max rating scale rendered as a radio group.
 *
 * Replaces the previous `<select>` per dimension. A native radio group gives
 * the whole scale one tab stop with arrow-key movement between values, shows
 * every option and both anchors without opening a menu, and gives each value
 * a target that satisfies WCAG 2.2 AA 2.5.8. The hint and the anchor pair are
 * associated with the group through aria-describedby, so a screen-reader user
 * hears what the ends mean before choosing.
 *
 * Serialisation is unchanged: the radios share the field's `name`, so
 * `new FormData(form)` still yields one value per dimension, and the explicit
 * "Not answered" option submits an empty string exactly as the select's
 * placeholder option did. That keeps the caller's
 * `!values[name] ? null : Number(values[name])` mapping correct, including
 * for a deliberate zero.
 */
export function ScaleField({ scale, disabled }: ScaleFieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const anchorsId = `${id}-anchors`
  const describedBy = scale.hint ? `${hintId} ${anchorsId}` : anchorsId

  return (
    <fieldset className="scale-field" disabled={disabled} aria-describedby={describedBy}>
      <legend className="scale-field__legend">{scale.label}</legend>
      {scale.hint && (
        <p className="scale-field__hint" id={hintId}>
          {scale.hint}
        </p>
      )}
      {/*
        The wrapper exists so the anchor line is exactly as wide as the option
        run it describes. Left to themselves the two rows size independently,
        and "10 — Love it" landed short of the 10 it labels.
      */}
      <div className="scale-field__scale">
        <div className="scale-field__options">
          <label className="scale-field__option">
            <input type="radio" name={scale.name} value="" defaultChecked />
            <span>Not answered</span>
          </label>
          {Array.from({ length: scale.max + 1 }, (_, value) => (
            <label className="scale-field__option" key={value}>
              <input type="radio" name={scale.name} value={value} />
              <span>{value}</span>
            </label>
          ))}
        </div>
        <p className="scale-field__anchors" id={anchorsId}>
          <span>0 — {scale.lowAnchor}</span>
          <span>
            {scale.max} — {scale.highAnchor}
          </span>
        </p>
      </div>
    </fieldset>
  )
}
