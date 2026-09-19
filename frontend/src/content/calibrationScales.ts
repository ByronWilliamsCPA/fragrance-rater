/**
 * Display wording for the controlled-observation scales.
 *
 * The response columns (`src/fragrance_rater/schemas/calibration.py`,
 * ADR-010) are typed and range-bounded but carry no semantic definitions
 * anywhere in the repository, and the calibration guide does not define them
 * either. The interface previously rendered the raw column names through
 * `text-transform: capitalize`, so an evaluator saw "Clean Soapy" and
 * "Bodily Animalic" with a bare 0-5 dropdown and no statement of what either
 * end meant.
 *
 * #CRITICAL: data-integrity: every evaluator has to read these scales the
 * same way for the recorded numbers to be comparable across people and across
 * sessions; wording that drifts silently changes what the model is trained on.
 * The anchors below describe scale DIRECTION only ("not present" to "very
 * strong"), deliberately avoiding perfumery definitions that no accepted
 * document in this project establishes.
 * #VERIFY: this wording is DRAFT and needs the maintainer's sign-off before
 * the F1 family pilot records any real observation against it. Once approved,
 * it belongs in the calibration guide as the authoritative definition, with
 * this module referencing it rather than owning it.
 */

export type ScaleDefinition = {
  /** Response field name; must match the API column exactly. */
  name: string
  /** Visible label. */
  label: string
  /** Highest selectable value. The scale always starts at 0. */
  max: number
  /** What the lowest value means. */
  lowAnchor: string
  /** What the highest value means. */
  highAnchor: string
  /** Optional clarification, associated via aria-describedby. */
  hint?: string
}

function scale(
  name: string,
  label: string,
  max: number,
  lowAnchor: string,
  highAnchor: string,
  hint?: string
): ScaleDefinition {
  if (max <= 0) {
    throw new Error(`scale("${name}"): max must be positive, got ${max}`)
  }
  if (lowAnchor === highAnchor) {
    throw new Error(`scale("${name}"): lowAnchor and highAnchor must differ`)
  }
  return { name, label, max, lowAnchor, highAnchor, hint }
}

/**
 * Grouping.
 *
 * The Specialty Coffee Association's Coffee Value Assessment separates a
 * DESCRIPTIVE judgement ("how much smoke is there") from an AFFECTIVE one
 * ("do I like smoke") from an overall assessment. Collapsing them is the
 * classic failure of consumer sensory forms, and this form collapsed them:
 * twelve scales ran together with nothing saying which were about the
 * fragrance and which were about the evaluator.
 *
 * #CRITICAL: data-integrity: an evaluator who reads "Discomfort" as a
 * property of the scent rather than as their own reaction records a different
 * number than one who reads it correctly, and nothing downstream can tell the
 * two apart.
 * #VERIFY: the grouping below is presentational only. The schema still has no
 * per-dimension preference field (ADR-010), so "perceives a lot of sweetness
 * AND dislikes sweetness" remains unrecordable; that needs a decision before
 * it can be captured.
 */
export type ScaleGroup = {
  key: string
  legend: string
  description: string
  scales: ScaleDefinition[]
}

const intensityScale = scale('intensity', 'Intensity', 5, 'Nothing at all', 'Overpowering')

const likingScale = scale(
  'liking',
  'Liking',
  10,
  'Strongly dislike',
  'Love it',
  'A strong dislike is as useful as a strong like.'
)

/** Descriptive: properties of the fragrance itself. */
const perceived: ScaleDefinition[] = [
  intensityScale,
  scale('sweetness', 'Sweetness', 5, 'Not sweet', 'Very sweet'),
  scale('freshness', 'Freshness', 5, 'Not fresh', 'Very fresh'),
  scale(
    'density',
    'Density',
    5,
    'Thin and airy',
    'Thick and heavy',
    'How much the scent seems to fill the space around it, regardless of strength.'
  ),
  scale('dryness', 'Dryness', 5, 'Not dry', 'Very dry'),
  scale('clean_soapy', 'Clean or soapy', 5, 'Not at all', 'Strongly'),
  scale('earthy_rooty', 'Earthy or rooty', 5, 'Not at all', 'Strongly'),
  scale('bodily_animalic', 'Bodily or animalic', 5, 'Not at all', 'Strongly'),
]

/** Affective: the evaluator's own response. */
const responded: ScaleDefinition[] = [
  likingScale,
  scale(
    'discomfort',
    'Discomfort',
    5,
    'Comfortable',
    'Had to step away',
    'Physical discomfort such as headache, stinging or nausea. This is separate from disliking the smell.'
  ),
]

/** Meta: how much weight this record should carry. */
const certainty: ScaleDefinition[] = [
  scale(
    'confidence',
    'Confidence in this rating',
    5,
    'Just guessing',
    'Completely sure',
    'How sure you are of the answers above, not how much you liked it.'
  ),
  scale(
    'familiarity',
    'Familiarity',
    5,
    'Completely new to me',
    'I know this well',
    'Whether the smell reminds you of something you already know. It is fine to be certain here and unsure everywhere else.'
  ),
]

export const blotterGroups: ScaleGroup[] = [
  {
    key: 'perceived',
    legend: 'What you perceived',
    description: 'Properties of the fragrance itself, whether or not you liked them.',
    scales: perceived,
  },
  {
    key: 'responded',
    legend: 'How you responded',
    description: 'Your own reaction. A fragrance can be strongly perceived and still disliked.',
    scales: responded,
  },
  {
    key: 'certainty',
    legend: 'How sure you are',
    description: 'How much weight this record should carry.',
    scales: certainty,
  },
]

/** Recorded only for a planned skin test. */
export const skinGroups: ScaleGroup[] = [
  {
    key: 'skin-performance',
    legend: 'How it performed on skin',
    description: 'Measurable behaviour over the wear.',
    // Longevity is a free minute count, not a bounded scale, so it stays a
    // number input rendered alongside this group rather than inside it.
    scales: [scale('projection', 'Projection', 5, 'Only on skin', 'Fills the room')],
  },
  {
    key: 'skin-response',
    legend: 'How you responded on skin',
    description: 'Your reaction at each stage of the wear, and what you would do about it.',
    scales: [
      scale('opening_liking', 'Liking at the opening', 10, 'Strongly dislike', 'Love it'),
      scale('drydown_liking', 'Liking at the drydown', 10, 'Strongly dislike', 'Love it'),
      scale('would_wear', 'Would wear', 10, 'Never', 'Definitely'),
      scale('would_buy', 'Would buy', 10, 'Never', 'Definitely'),
      scale(
        'artistic_appreciation',
        'Artistic appreciation',
        10,
        'Nothing to admire',
        'Remarkable',
        'Whether you think it is well made, even if you would never wear it.'
      ),
    ],
  },
]

/**
 * Every numeric response field, flattened.
 *
 * Derived from the groups rather than repeated as literals, so a dimension
 * cannot be rendered but left out of the submitted payload.
 */
export const numericFieldNames: string[] = [
  ...blotterGroups.flatMap((group) => group.scales.map((item) => item.name)),
  ...skinGroups.flatMap((group) => group.scales.map((item) => item.name)),
  'longevity_minutes',
]

/** Free-text fields, in the order they are presented. */
export const observationNotes = [
  { name: 'likes', label: 'What you liked' },
  { name: 'dislikes', label: 'What you disliked' },
  { name: 'reminds_me_of', label: 'Reminds you of' },
  { name: 'comments', label: 'Anything else' },
] as const
