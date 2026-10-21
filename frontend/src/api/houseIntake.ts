/**
 * Fragrance house intake: the payload contract and its client-side checks.
 *
 * Mirrors `src/fragrance_rater/schemas/house_intake.py`. The server is the
 * authority; these checks exist so a house sees what is missing before a
 * round trip, in the same words the server would use.
 */

export type Concentration = 'EDC' | 'EDT' | 'EDP' | 'PARFUM' | 'EXTRAIT' | 'OIL' | 'SOLID' | 'OTHER'
export type Availability = 'in_production' | 'limited_edition' | 'upcoming' | 'discontinued'
export type MarketedFor = 'Feminine' | 'Masculine' | 'Unisex' | 'not_specified'
export type NoteStructure = 'pyramid' | 'linear'
export type NotePosition = 'top' | 'heart' | 'base' | 'unspecified'
export type PermissionScope = 'retain_and_train' | 'retain_for_qc_only'

export type DeclaredNote = { text: string; position: NotePosition }

export type HouseSubmissionPayload = {
  fragrance_name: string
  line: string | null
  concentration: Concentration | null
  concentration_other: string | null
  version_label: string | null
  launch_year: number | null
  availability: Availability | null
  marketed_for: MarketedFor | null
  perfumers: string[]
  product_url: string | null
  gtins: string[]
  note_structure: NoteStructure
  notes: DeclaredNote[]
  accords: string[]
  family_as_described: string | null
  description: string | null
  permission_scope: PermissionScope | null
  contact_name: string | null
  contact_role: string | null
  attested: boolean
  note_to_reviewer: string | null
}

export type HouseSubmission = {
  id: string
  house: string
  status: 'draft' | 'submitted'
  created_by: string
  created_at: string
  updated_at: string
  submitted_at: string | null
  submitted_by: string | null
  permission_state: PermissionScope | null
  supersedes_id: string | null
  superseded_by_id: string | null
  payload: HouseSubmissionPayload
  review_status: ReviewStatus | null
  reviewed_at: string | null
  /** Shown to the house; required when a manager declines. */
  review_note: string | null
  /** Manager view only; always null in a response to a house. */
  reviewed_by: string | null
  fragrance_id: string | null
  source_snapshot_id: string | null
}

export type ReviewStatus = 'pending' | 'adopted' | 'declined' | 'superseded'

export type ConfirmableField =
  'name' | 'brand' | 'line' | 'concentration' | 'launch_year' | 'market_status' | 'gender_target'
export type UpdatableField = 'line' | 'launch_year' | 'market_status' | 'gender_target'
export type Comparison = 'same' | 'differs' | 'house_silent'
export type GenderTarget = 'Masculine' | 'Feminine' | 'Unisex'

export const confirmableFields: ReadonlyArray<{ field: ConfirmableField; label: string }> = [
  { field: 'name', label: 'Name' },
  { field: 'brand', label: 'Brand' },
  { field: 'line', label: 'Collection or line' },
  { field: 'concentration', label: 'Concentration' },
  { field: 'launch_year', label: 'Launch year' },
  { field: 'market_status', label: 'On sale' },
  { field: 'gender_target', label: 'Gender target' },
]

/** Facts the catalog may take from the house; the rest only confirm. */
export const updatableFields: ReadonlySet<ConfirmableField> = new Set([
  'line',
  'launch_year',
  'market_status',
  'gender_target',
])

/** Facts ADR-006 freezes once a calibration program uses the version. */
export const calibrationLockedFields: ReadonlySet<ConfirmableField> = new Set([
  'launch_year',
  'gender_target',
])

/** A different name, brand, or concentration means another version, not a fix. */
export const identityFields: ReadonlySet<ConfirmableField> = new Set([
  'name',
  'brand',
  'concentration',
])

export type ProposedFacts = {
  name: string
  brand: string
  line: string | null
  concentration: string | null
  launch_year: number | null
  market_status: Availability | null
  gender_target: GenderTarget | null
  /** Normalized to GTIN-14. */
  gtins: string[]
}

export type CatalogCandidate = {
  id: string
  name: string
  brand: string
  line: string | null
  concentration: string
  version_key: string
  launch_year: number | null
  market_status: Availability | null
  gender_target: string
  primary_family: string
  subfamily: string
  comparison: Record<ConfirmableField, Comparison>
  gtins: string[]
  /** House barcodes already linked to this version: the strongest match signal. */
  gtin_matches: string[]
  /** A calibration program uses it, so launch year and gender target are frozen. */
  in_calibration: boolean
}

export type ReviewContext = {
  submission: HouseSubmission
  proposed: ProposedFacts
  candidates: CatalogCandidate[]
}

export type AdoptInput = {
  target:
    | { kind: 'existing'; fragrance_id: string }
    | {
        kind: 'new'
        version_key: string
        primary_family: string
        subfamily: string
        gender_target: GenderTarget | null
      }
  confirmed_fields: ConfirmableField[]
  apply_updates: UpdatableField[]
  record_perfumers: boolean
  record_barcodes: boolean
  review_note: string | null
}

export type HouseAccess = {
  username: string
  house: string | null
  manager: boolean
  /** An external house account; with no `house`, one whose mapping was removed. */
  house_account?: boolean
}

export type SubmissionProblem = { field: string; message: string }

export const concentrationOptions: ReadonlyArray<{ value: Concentration; label: string }> = [
  { value: 'EDC', label: 'Eau de Cologne' },
  { value: 'EDT', label: 'Eau de Toilette' },
  { value: 'EDP', label: 'Eau de Parfum' },
  { value: 'PARFUM', label: 'Parfum' },
  { value: 'EXTRAIT', label: 'Extrait de Parfum' },
  { value: 'OIL', label: 'Perfume oil or attar' },
  { value: 'SOLID', label: 'Solid perfume' },
  { value: 'OTHER', label: 'Something else' },
]

export const availabilityOptions: ReadonlyArray<{ value: Availability; label: string }> = [
  { value: 'in_production', label: 'On sale now' },
  { value: 'limited_edition', label: 'Limited edition' },
  { value: 'upcoming', label: 'Announced, not yet released' },
  { value: 'discontinued', label: 'Discontinued' },
]

export const marketedForOptions: ReadonlyArray<{ value: MarketedFor; label: string }> = [
  { value: 'Feminine', label: 'Women' },
  { value: 'Masculine', label: 'Men' },
  { value: 'Unisex', label: 'Everyone (unisex)' },
  { value: 'not_specified', label: 'The house does not say' },
]

export const permissionOptions: ReadonlyArray<{
  value: PermissionScope
  label: string
  hint: string
}> = [
  {
    value: 'retain_and_train',
    label: 'Keep it and use it in recommendations',
    hint: 'We store these details and may use them to train the model that suggests fragrances to the family. We never resell or republish them.',
  },
  {
    value: 'retain_for_qc_only',
    label: 'Use it only to check our records',
    hint: 'We use these details to confirm the facts in our catalog, and nothing else. They are never used to train a model.',
  },
]

export const pyramidTiers: ReadonlyArray<{
  position: Exclude<NotePosition, 'unspecified'>
  label: string
}> = [
  { position: 'top', label: 'Top notes' },
  { position: 'heart', label: 'Heart notes' },
  { position: 'base', label: 'Base notes' },
]

export const labelFor = <T extends string>(
  options: ReadonlyArray<{ value: T; label: string }>,
  value: T | null
): string => options.find((option) => option.value === value)?.label ?? 'Not given'

export const EARLIEST_LAUNCH_YEAR = 1700
export const LAUNCH_YEAR_LEAD = 3
export const MAX_DESCRIPTION = 4000

export function emptyPayload(): HouseSubmissionPayload {
  return {
    fragrance_name: '',
    line: null,
    concentration: null,
    concentration_other: null,
    version_label: null,
    launch_year: null,
    availability: null,
    marketed_for: null,
    perfumers: [],
    product_url: null,
    gtins: [],
    note_structure: 'pyramid',
    notes: [],
    accords: [],
    family_as_described: null,
    description: null,
    permission_scope: null,
    contact_name: null,
    contact_role: null,
    attested: false,
    note_to_reviewer: null,
  }
}

/** GS1 mod-10 check, the same rule as `utils/gtin.py`. */
export function isValidGtin(value: string): boolean {
  if (!/^\d+$/.test(value) || ![8, 12, 13, 14].includes(value.length)) return false
  const digits = value.slice(0, -1)
  let total = 0
  for (let index = 0; index < digits.length; index += 1) {
    const digit = Number(digits[digits.length - 1 - index])
    total += index % 2 === 0 ? digit * 3 : digit
  }
  return (10 - (total % 10)) % 10 === Number(value[value.length - 1])
}

const hasText = (value: string | null): boolean => Boolean(value?.trim())

/**
 * Problems that would make the server refuse even a draft: wrong formats,
 * out-of-range values, duplicates. Checked on every save.
 */
export function formatProblems(
  payload: HouseSubmissionPayload,
  currentYear = new Date().getFullYear()
): SubmissionProblem[] {
  const problems: SubmissionProblem[] = []
  if (!hasText(payload.fragrance_name))
    problems.push({ field: 'fragrance_name', message: 'Enter the fragrance name' })
  const latest = currentYear + LAUNCH_YEAR_LEAD
  if (
    payload.launch_year !== null &&
    (!Number.isInteger(payload.launch_year) ||
      payload.launch_year < EARLIEST_LAUNCH_YEAR ||
      payload.launch_year > latest)
  )
    problems.push({
      field: 'launch_year',
      message: `Enter a launch year between ${EARLIEST_LAUNCH_YEAR} and ${latest}`,
    })
  if (
    payload.product_url !== null &&
    (!/^https:\/\/\S+$/.test(payload.product_url) || payload.product_url.length > 1000)
  )
    problems.push({
      field: 'product_url',
      message: 'Enter the product page as a full https:// address',
    })
  const invalidGtins = payload.gtins.filter((gtin) => !isValidGtin(gtin))
  if (invalidGtins.length)
    problems.push({
      field: 'gtins',
      message: `Check these barcodes, the digits or check digit look wrong: ${invalidGtins.join(', ')}`,
    })
  else if (new Set(payload.gtins).size !== payload.gtins.length)
    problems.push({ field: 'gtins', message: 'List each barcode once' })
  const seen = new Set<string>()
  for (const note of payload.notes) {
    const key = `${note.position}\u0000${note.text}`
    if (seen.has(key)) {
      problems.push({
        field: 'notes',
        message: `"${note.text}" is listed twice in the same tier`,
      })
      break
    }
    seen.add(key)
  }
  if ((payload.description?.length ?? 0) > MAX_DESCRIPTION)
    problems.push({
      field: 'description',
      message: `Shorten the description to ${MAX_DESCRIPTION} characters`,
    })
  return problems
}

/** What a draft still needs before it can be submitted; mirrors `submission_problems`. */
export function completenessProblems(payload: HouseSubmissionPayload): SubmissionProblem[] {
  const problems: SubmissionProblem[] = []
  if (payload.concentration === null)
    problems.push({ field: 'concentration', message: 'Choose the concentration' })
  else if (payload.concentration === 'OTHER' && !hasText(payload.concentration_other))
    problems.push({ field: 'concentration_other', message: 'Name the concentration' })
  if (payload.launch_year === null && payload.availability !== 'upcoming')
    problems.push({ field: 'launch_year', message: 'Enter the launch year' })
  if (payload.availability === null)
    problems.push({ field: 'availability', message: 'Choose whether the fragrance is on sale' })
  if (!payload.notes.length && !payload.accords.length && !hasText(payload.description))
    problems.push({
      field: 'notes',
      message: 'Describe the scent with at least one note, an accord, or the official description',
    })
  if (payload.permission_scope === null)
    problems.push({
      field: 'permission_scope',
      message: 'Choose how we may use this information',
    })
  if (!hasText(payload.contact_name))
    problems.push({ field: 'contact_name', message: 'Enter your name' })
  if (!hasText(payload.contact_role))
    problems.push({ field: 'contact_role', message: 'Enter your role at the house' })
  if (!payload.attested)
    problems.push({
      field: 'attested',
      message: "Confirm you may provide this on the house's behalf",
    })
  return problems
}

/** Reads the `problems` list from a SUBMISSION_INCOMPLETE 422, if that is what it is. */
export function serverProblems(error: unknown): SubmissionProblem[] | null {
  if (typeof error !== 'object' || error === null || !('response' in error)) return null
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail !== 'object' || detail === null || !('problems' in detail)) return null
  const problems = (detail as { problems: unknown }).problems
  return Array.isArray(problems) ? (problems as SubmissionProblem[]) : null
}
