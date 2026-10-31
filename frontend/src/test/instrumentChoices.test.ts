import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  ownedOrWornChoices,
  recognitionChoices,
  seasonFitChoices,
  settingFitChoices,
  skinTimepoints,
  unansweredReasons,
} from '../content/calibrationScales'

/** The literal values the API accepts for a named `Literal[...]` in the schema. */
function apiLiteral(name: string): string[] {
  const source = readFileSync(
    resolve(__dirname, '../../../src/fragrance_rater/schemas/calibration.py'),
    'utf8'
  )
  const match = new RegExp(`^${name} = Literal\\[([^\\]]+)\\]`, 'm').exec(source)
  if (!match) throw new Error(`${name} not found in the API schema`)
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1])
}

const values = (choices: { value: string }[]) => choices.map((choice) => choice.value)

describe('instrument choice lists', () => {
  it('match the API literals exactly, so a form never submits a rejected value', () => {
    expect(values(recognitionChoices)).toEqual(apiLiteral('Recognition'))
    expect(values(ownedOrWornChoices)).toEqual(apiLiteral('OwnedOrWorn'))
    expect(values(seasonFitChoices)).toEqual(apiLiteral('SeasonFit'))
    expect(values(settingFitChoices)).toEqual(apiLiteral('SettingFit'))
  })

  it('only offers response statuses the API knows', () => {
    const known = apiLiteral('ResponseStatus')
    for (const value of values(unansweredReasons).filter(Boolean)) {
      expect(known).toContain(value)
    }
  })

  it('offers the fixed skin timepoints', () => {
    expect(values(skinTimepoints)).toEqual(['10', '60', '240', '480'])
  })
})
