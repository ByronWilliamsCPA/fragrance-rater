# ADR-016: Per-Dimension Preference Capture

> **Status**: Proposed — requires maintainer decision, not implemented
>
> **Date**: 2026-09-19

**Numbering note**: `main` already contains ADR-014 (frontend e2e and accessibility), merged in
PR #103 without being added to the index. PR #105 proposes a second, unrelated ADR-014 and needs to
renumber; ADR-015 is left free for it, since it was opened first. This record takes 016 to avoid a
third collision.

## TL;DR

Record whether an evaluator *likes* a perceived attribute, not only how much of it they perceived.
The schema currently captures perception and overall liking but nothing in between, so the affinity
model can rank a candidate without being able to say why. Recommended approach is a single sparse
follow-up per timepoint rather than a preference scale per dimension, sequenced after F1.

## Context

### Problem

`ResponseInput` (`src/fragrance_rater/schemas/calibration.py`, ADR-010) captures four kinds of
response:

| Kind | Fields |
| :--- | :--- |
| Descriptive | `intensity`, `sweetness`, `freshness`, `density`, `dryness`, `clean_soapy`, `earthy_rooty`, `bodily_animalic` |
| Affective (whole fragrance) | `liking`, `opening_liking`, `drydown_liking`, `would_wear`, `would_buy`, `artistic_appreciation` |
| Physical response | `discomfort` |
| Meta | `confidence`, `familiarity` |

Nothing records whether the evaluator likes a *perceived attribute*. An evaluator can record
`sweetness: 5` and `liking: 3`, and the record cannot distinguish "too sweet for me" from "sweet,
which was fine, but I disliked it for some other reason."

### Why this matters

ADR-004 and ADR-007 define a deterministic weighted affinity over notes, accords and families as an
*interpretable* ranking baseline. That interpretability is currently thinner than it looks. The
model can say a candidate shares accords with fragrances the evaluator rated highly. It cannot say
the evaluator dislikes an attribute, because no one ever recorded it. The direction has to be
inferred from correlations across whole-fragrance liking, which needs far more observations than one
person's panel provides and is confounded every time somebody likes a fragrance *despite* one of its
attributes.

This is the descriptive/affective separation that the Specialty Coffee Association's Coffee Value
Assessment makes explicit. It was identified as the strongest cross-domain lesson in the 2026-09-19
design reference survey, and it is the one recommendation from that survey that is a data-model
question rather than a styling one.

### Constraints

- The 43-fragrance V3.1 baseline and its 49 presentations are frozen, and ADR-009 checkpoints depend
  on observations being comparable. Adding fields mid-panel splits the record into pre-change and
  post-change observations.
- P6 is the pilot-readiness gate and F1 is the first pilot with real perfume. Neither should slip
  for this.
- Form length is already a real cost. The blotter stage presents twelve scales per timepoint, across
  49 presentations. Doubling the descriptive block is not acceptable.

## Options considered

### Option A: a preference scale per perceptual dimension

Add `{dimension}_preference` for each of the eight descriptive dimensions.

- Complete and unambiguous.
- Takes the descriptive block from 8 scales to 16, per timepoint, across 49 presentations.
- **Rejected on evaluator burden.** The most likely outcome is fatigue and lower-quality answers
  across the whole form, which costs more than the new field gains.

### Option B: one sparse directional follow-up per timepoint (recommended)

Keep the eight descriptive scales unchanged. Add one optional follow-up: *which of these pushed your
rating, and which way?* The evaluator marks at most two or three dimensions as pushing liking up or
down, and leaves the rest alone.

- Captures direction where direction exists, which is the part the model cannot infer cheaply.
- Adds roughly one control per timepoint instead of eight.
- Sparse by construction. An unmarked dimension means "not decisive for me here", which is itself
  informative and is the common case.
- Stored as a `response_preferences` child table (`response_id`, `dimension`, `direction`) rather
  than eight nullable columns, so adding or renaming a dimension later is a data change rather than
  a migration.

### Option C: infer preference from correlation

No schema change. Estimate per-dimension preference from the joint distribution of perceived
intensity and overall liking.

- No evaluator burden at all.
- Needs far more observations than a 49-presentation panel gives per person, and cannot separate
  "dislikes sweetness" from "disliked this particular sweet fragrance".
- **Rejected as the sole mechanism**, but retained as the fallback for evaluators who leave the new
  control blank, which Option B guarantees will happen often.

## Consequences

### Positive

- A recommendation explanation can cite a preference the evaluator actually stated, instead of
  inferring one from a ranking.
- Holdout predictions gain a per-person feature rather than a pooled one.
- The distinction is already visible in the interface (the calibration form groups scales into what
  you perceived, how you responded, and how sure you are), so the capture would land in a form
  evaluators already read that way.

### Trade-offs

- One more control per timepoint.
- Coverage will be partial by design, so every consumer has to handle absence rather than treating a
  blank as a neutral preference.

### Technical debt

Nothing in the current training manifest consumes this. ADR-004's weighting needs a follow-up
decision on how much a stated preference counts relative to observed liking, and that decision
should not be made implicitly in code.

## Sequencing

**This should not land before F1.** Adding it mid-panel splits the baseline into observations that
have the field and observations that do not, which is exactly the comparability problem ADR-009's
checkpoints exist to avoid.

Recommended: land after F1 closes and before D1, so the first pilot is internally consistent and the
second wave collects the richer signal.

## Open questions for the maintainer

1. Signed direction (pushed up / pushed down) or a graded preference score?
2. Blotter stage, skin stage, or both?
3. Does a stated preference outrank observed liking in the affinity weighting, and by how much?
   (ADR-004 follow-up.)
4. Does this apply to ordinary encounters too, or only to controlled observations?

## Related

- [ADR-004](./adr-004-recommendation-algorithm.md): the weighting this would feed
- [ADR-007](./adr-007-preference-evidence-and-score-semantics.md): score semantics and what the
  affinity figure may be called
- [ADR-009](./adr-009-prospective-evaluation-and-checkpoints.md): why this cannot land mid-panel
- [ADR-010](./adr-010-preference-learning-and-scenario-data-model.md): the typed response columns
  this amends
- [Design system](../../development/design-system.md): the interface grouping that already makes the
  descriptive/affective split visible
