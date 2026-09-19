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
  return { name, label, max, lowAnchor, highAnchor, hint }
}

/** Ten perceptual dimensions recorded at every timepoint. */
export const perceptualScales: ScaleDefinition[] = [
  scale(
    'confidence',
    'Confidence in this rating',
    5,
    'Just guessing',
    'Completely sure',
    'How sure you are of the answers above, not how much you liked it.'
  ),
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
  scale(
    'familiarity',
    'Familiarity',
    5,
    'Completely new to me',
    'I know this well',
    'Whether the smell reminds you of something you already know. It is fine to be certain here and unsure everywhere else.'
  ),
  scale('dryness', 'Dryness', 5, 'Not dry', 'Very dry'),
  scale('clean_soapy', 'Clean or soapy', 5, 'Not at all', 'Strongly'),
  scale('earthy_rooty', 'Earthy or rooty', 5, 'Not at all', 'Strongly'),
  scale('bodily_animalic', 'Bodily or animalic', 5, 'Not at all', 'Strongly'),
  scale(
    'discomfort',
    'Discomfort',
    5,
    'Comfortable',
    'Had to step away',
    'Physical discomfort such as headache, stinging, or nausea. This is separate from disliking the smell.'
  ),
]

/** Recorded at every timepoint, alongside detection. */
export const intensityScale = scale('intensity', 'Intensity', 5, 'Nothing at all', 'Overpowering')

export const likingScale = scale(
  'liking',
  'Liking',
  10,
  'Strongly dislike',
  'Love it',
  'Your own reaction. There is no wrong answer, and a strong dislike is as useful as a strong like.'
)

/** Additional scales recorded only for a planned skin test. */
export const skinScales: ScaleDefinition[] = [
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
  scale('projection', 'Projection', 5, 'Only on skin', 'Fills the room'),
]

/** Free-text fields, in the order they are presented. */
export const observationNotes = [
  { name: 'likes', label: 'What you liked' },
  { name: 'dislikes', label: 'What you disliked' },
  { name: 'reminds_me_of', label: 'Reminds you of' },
  { name: 'comments', label: 'Anything else' },
] as const
