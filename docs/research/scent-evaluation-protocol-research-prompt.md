---
title: "Deep-research prompt: scent evaluation protocol"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Provide a self-contained prompt for a deep-research model to validate the family calibration protocol against sensory-science and perfumery practice."
tags:
  - research
  - evaluation
  - planning
---

**Why this exists.** The controlled calibration protocol (43 fragrances, 49 presentations, 13
sessions of 3 samples, hidden repeats, holdouts, compressed into 5 days) was designed from first
principles and has not been checked against sensory-evaluation standards, olfactory-fatigue
evidence, or perfumery practice. Decision Q8 in [ML Decisions 2026-09](../planning/ml-decisions-2026-09.md)
adopted within-session ranking provisionally and made the protocol's session structure, pacing,
and judgment format contingent on this research. Paste the prompt below, in full, into a
deep-research model. Record the response under `docs/research/` with the date, the model, and a
short reconciliation note stating which protocol elements changed as a result.

---

## Prompt

You are a sensory scientist and perfumery evaluation specialist. Produce a rigorous, cited
research report that validates or corrects a small-family fragrance evaluation protocol. Prefer
primary literature, standards bodies, and named industry practice over blogs. Give DOIs or
standard numbers for every substantive claim. Where evidence is thin, contradictory, or specific to
trained panels rather than untrained consumers, say so explicitly. Where you extrapolate, label
the extrapolation. Do not invent citations; if you cannot find support, say "no direct evidence
found" and give your best-reasoned recommendation separately from the evidence.

### The protocol under review

- **Population**: four family members, ages roughly teen to adult, untrained, no prior
  sensory-panel experience. Individual preference prediction is the goal, not a consensus panel.
- **Stimuli**: 33 baseline fine fragrances chosen to span diagnostic olfactory roles (citrus,
  aquatic, green, aldehydic floral, rose, white floral, iris, musk, animalic, Iso E Super,
  ambroxan, vetiver, sandalwood, chypre, amber, leather, oud, incense, vanilla, patchouli
  gourmand, bakery gourmand, honey, tobacco, tea, smoke) plus 10 validation holdouts chosen to
  test generalization from the baseline. Concentrations range from eau de cologne to extrait.
- **Presentation**: blind, three-digit codes, randomized per evaluator. Blotter (paper strip)
  first; a subset chosen for skin wear with observations at elapsed times (opening, drydown,
  longevity in minutes, projection).
- **Design**: 13 sessions of 3 samples each (39 blotter slots), 6 of the 33 baseline
  fragrances presented twice as hidden repeats to estimate test-retest reliability, initial and
  repeat placed on different days; 10 holdouts presented after a model has frozen predictions for
  them.
- **Pacing**: an accelerated 5-day schedule (day 1 sessions 1 to 3, day 2 sessions 4 to 6, day 3
  sessions 7 to 9, day 4 sessions 10 to 11, day 5 sessions 12 to 13), so up to 9 samples per day
  on days 1 to 3. Session context (time of day, food, ambient odor, illness, menstrual phase,
  caffeine, prior fragrance worn) is currently not recorded.
- **Judgments collected per sample**: detection (yes/no), intensity 0 to 5, overall liking 0 to
  10, opening liking and drydown liking 0 to 10 for skin, would-wear 0 to 10, would-buy 0 to 10,
  artistic appreciation 0 to 10, confidence 0 to 5, perceptual dimensions 0 to 5 (sweetness,
  freshness, density, dryness, clean/soapy, earthy/rooty, bodily/animalic, discomfort),
  familiarity 0 to 5, free-text perceived notes, likes, dislikes, reminds-me-of, comments.
  Unanswered is recorded as missing; zero is a real answer. Non-detection records intensity zero
  and no liking.
- **Proposed addition**: at the end of each 3-sample session, the evaluator ranks the three
  samples from most to least preferred, yielding three pairwise preferences per session.
- **Modeling constraint**: about 33 labeled fragrances per evaluator; the analysis will use a
  partially pooled (hierarchical) model with strong priors and will report holdout error against a
  test-retest noise ceiling estimated from the 6 repeats per evaluator.

### Questions to answer, with evidence

1. **Samples per session and per day.** What do ISO 8586, ISO 8589, ISO 11035, ISO 13299, ASTM
   E18 guidance, and the olfactory adaptation and fatigue literature say about the number of
   fragrance samples an untrained evaluator can assess per session and per day before adaptation,
   cross-adaptation, or hedonic drift degrades judgments? Is 3 per session appropriate; is 9 per
   day too many; what inter-stimulus interval and recovery practices are supported by evidence
   (clean air, own skin, water, time), and which common practices (coffee beans) lack support?
2. **Session compression.** Is a 5-day schedule for 13 sessions defensible, or does the
   literature support spreading sessions over weeks to reduce carry-over, context effects, and
   fatigue? What is known about day-to-day variability in olfactory sensitivity and hedonic
   response (time of day, circadian, hunger, illness, hormonal cycle, humidity, temperature)?
3. **Blotter versus skin.** How well do blotter judgments predict skin judgments for hedonic
   response and for wear intent? What elapsed-time observation points (for example 10 minutes, 1
   hour, 4 hours, 8 hours) are standard in perfumery evaluation, and which matter most for
   predicting liking and wear behavior?
4. **Hedonic scale choice.** Compare the 9-point hedonic scale, labeled affective magnitude
   (LAM) scale, 0 to 10 numeric, and visual analog scales for untrained consumers: reliability,
   end-avoidance, discriminability, and ease. Is a 0 to 10 integer scale a reasonable choice,
   and should it carry verbal anchors?
5. **Rating versus ranking versus paired comparison.** For four untrained evaluators and 33
   stimuli, what is the evidence on test-retest reliability and discrimination for absolute
   ratings versus within-session ranking versus paired comparison (ISO 8587 ranking, ISO 5495
   paired comparison, Thurstone and Bradley-Terry models)? Is ranking three samples at the end
   of a session a sound way to obtain pairwise preferences, and how should ranking data be
   combined with absolute liking in analysis?
6. **Order, position, and carry-over.** What counterbalancing designs (Williams Latin squares,
   balanced incomplete block designs) are appropriate for 3-sample sessions, and how large are
   first-position and contrast effects in fragrance hedonics? Should strong or animalic stimuli
   be placed last or isolated?
7. **Hidden repeats and reliability.** What test-retest reliability (correlation or intraclass
   correlation) is typical for untrained consumers rating fragrance liking days apart? Is 6
   repeats per person enough to estimate a noise ceiling, and what separation between initial
   and repeat presentations is recommended so recognition does not inflate agreement?
8. **Perceptual dimension questionnaire.** Do the eight perceptual dimensions above align with
   validated descriptive frameworks (for example the Michael Edwards wheel, Cinquieme Sens
   facets, Zarzo and Stanton dimensions, the Dravnieks descriptor set, ISO 11035 descriptive
   analysis)? Which dimensions are reliably rated by untrained evaluators, and which need
   training or anchors? Is 0 to 5 adequate?
9. **Familiarity and mere exposure.** How should prior familiarity and repeated exposure be
   measured and controlled, given that liking for fragrances changes with exposure? Is a
   categorical familiarity code (never smelled, smelled before, owned, formerly owned) better than
   a 0 to 5 integer?
10. **Detection and intensity.** How should non-detection and low-intensity presentations be
    handled in analysis (censoring versus exclusion), and how does perceived intensity interact
    with liking (inverted-U relationships)?
11. **Health and safety.** Any contraindications or exposure limits relevant to up to 9 fine
    fragrances per day on blotters and several on skin (IFRA guidance, dermal sensitization,
    headache and migraine triggers), and standard consent and stop rules.
12. **Minimum data for individual models.** What does the literature on individual-level
    fragrance or odor preference modeling say about how many stimuli per person are needed to
    predict liking of new stimuli with useful accuracy, and which stimulus representations (odor
    descriptors, molecular features, published notes) have shown out-of-sample predictive value?

### Required output

1. An executive summary of at most 300 words: keep, change, or stop for each of the six protocol
   elements (session size, daily load, compression, judgment set, ranking addition, repeat
   design).
2. A table with one row per question above: finding, strength of evidence (strong, moderate,
   weak, none), citations, and the specific recommendation for this protocol.
3. A recommended revised protocol: sessions per day, samples per session, inter-stimulus
   procedure, calendar spread, blotter and skin timepoints, the judgment set with scale
   anchors, the ranking procedure, repeat placement, and the session-context fields to record.
4. A list of the changes in your recommendation that would alter the data model (new fields,
   changed scales, new tables), because the schema must be finalized before the pilot.
5. Risks and unknowns you could not resolve, with the cheapest pilot check for each.
6. A bibliography with DOIs, standard numbers, or stable URLs.

Constraints: be concrete, prefer numbers with their source, distinguish trained-panel evidence
from consumer evidence, and do not recommend more than the four evaluators can realistically do.
