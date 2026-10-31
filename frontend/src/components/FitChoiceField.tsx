import { useId, useState } from 'react'
import { standaloneFitCodes, type Choice } from '../content/calibrationScales'

type FitChoiceFieldProps = {
  /** Field name; submitted once per ticked option. */
  name: string
  legend: string
  hint?: string
  choices: Choice[]
}

const isStandalone = (value: string) => (standaloneFitCodes as readonly string[]).includes(value)

/**
 * A multi-select question rendered as checkboxes.
 *
 * "None of these" and "Cannot judge" answer the whole question, so ticking one
 * clears every other option and ticking any other option clears them; the API
 * refuses the combination, and refusing it here too means the evaluator never
 * meets that error. Serialised through the form: `new FormData(form).getAll(name)`
 * yields one entry per ticked option.
 */
export function FitChoiceField({ name, legend, hint, choices }: FitChoiceFieldProps) {
  const hintId = useId()
  const [selected, setSelected] = useState<string[]>([])

  function toggle(value: string, checked: boolean) {
    if (!checked) return setSelected(selected.filter((item) => item !== value))
    setSelected(
      isStandalone(value) ? [value] : [...selected.filter((i) => !isStandalone(i)), value]
    )
  }

  return (
    <fieldset className="scale-field" aria-describedby={hint ? hintId : undefined}>
      <legend className="scale-field__legend">{legend}</legend>
      {hint && (
        <p className="scale-field__hint" id={hintId}>
          {hint}
        </p>
      )}
      <div className="scale-field__options">
        {choices.map((choice) => (
          <label className="scale-field__option" key={choice.value}>
            <input
              type="checkbox"
              name={name}
              value={choice.value}
              checked={selected.includes(choice.value)}
              onChange={(event) => toggle(choice.value, event.target.checked)}
            />
            <span>{choice.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
