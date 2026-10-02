import { describe, expect, it } from 'vitest'
import {
  completenessProblems,
  emptyPayload,
  formatProblems,
  isValidGtin,
  serverProblems,
  type HouseSubmissionPayload,
} from '../api/houseIntake'
import { splitEntries } from '../components/splitEntries'

const draft = (overrides: Partial<HouseSubmissionPayload> = {}): HouseSubmissionPayload => ({
  ...emptyPayload(),
  fragrance_name: 'Cèdre Nocturne',
  ...overrides,
})

const fields = (problems: { field: string }[]) => problems.map((problem) => problem.field)

describe('house intake rules (mirroring schemas/house_intake.py)', () => {
  it('checks GS1 check digits for every barcode length', () => {
    expect(isValidGtin('3508440005953')).toBe(true)
    expect(isValidGtin('3508440005954')).toBe(false)
    expect(isValidGtin('96385074')).toBe(true)
    expect(isValidGtin('12345')).toBe(false)
    expect(isValidGtin('35084400059a3')).toBe(false)
  })

  it('accepts 1700 to three years ahead and rejects anything else', () => {
    expect(formatProblems(draft({ launch_year: 1709 }), 2026)).toEqual([])
    expect(fields(formatProblems(draft({ launch_year: 1699 }), 2026))).toEqual(['launch_year'])
    expect(fields(formatProblems(draft({ launch_year: 2030 }), 2026))).toEqual(['launch_year'])
    expect(fields(formatProblems(draft({ launch_year: Number.NaN }), 2026))).toEqual([
      'launch_year',
    ])
  })

  it('reports format problems a draft save would hit', () => {
    const problems = formatProblems(
      draft({
        fragrance_name: '  ',
        product_url: 'https://maison.example/a b',
        gtins: ['3508440005953', '3508440005953'],
        notes: [
          { text: 'Musk', position: 'base' },
          { text: 'Musk', position: 'base' },
        ],
        description: 'x'.repeat(4001),
      })
    )
    expect(fields(problems)).toEqual([
      'fragrance_name',
      'product_url',
      'gtins',
      'notes',
      'description',
    ])
    expect(problems[2].message).toBe('List each barcode once')
  })

  it('names the concentration when the house chose something else', () => {
    expect(fields(completenessProblems(draft({ concentration: 'OTHER' })))).toContain(
      'concentration_other'
    )
    expect(
      fields(
        completenessProblems(draft({ concentration: 'OTHER', concentration_other: 'Fraîche' }))
      )
    ).not.toContain('concentration_other')
  })

  it('lets an announced fragrance omit its launch year', () => {
    expect(fields(completenessProblems(draft({ availability: 'upcoming' })))).not.toContain(
      'launch_year'
    )
  })

  it('reads problem lists only from an incomplete-submission response', () => {
    const problems = [{ field: 'attested', message: 'Confirm' }]
    expect(serverProblems({ response: { data: { detail: { problems } } } })).toEqual(problems)
    expect(serverProblems({ response: { data: { detail: 'Nope' } } })).toBeNull()
    expect(serverProblems({ response: { data: { detail: { problems: 'x' } } } })).toBeNull()
    expect(serverProblems(new Error('network'))).toBeNull()
    expect(serverProblems(null)).toBeNull()
  })

  it('splits pasted lists on commas, semicolons, and lines', () => {
    expect(splitEntries('Bergamot, Pink pepper;\nCardamom ,, ')).toEqual([
      'Bergamot',
      'Pink pepper',
      'Cardamom',
    ])
  })
})
