# ADR-016: Per-Dimension Preference Capture and Perfumer as an Evaluable Dimension

> **Status**: Proposed, requires maintainer decision, not implemented; amended 2026-09-21
> (permanence for the initial four F1 evaluators)
>
> **Date**: 2026-09-19 | **Amended**: 2026-09-21

**Numbering note**: `main` already contains ADR-014 (frontend e2e and accessibility), merged in
PR #103 without being added to the index. PR #105 has since merged a second, unrelated ADR-014
without renumbering (see the duplicate-number callout in `docs/planning/adr/README.md`); ADR-015
remains free. This record takes 016 to avoid a third collision.

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

For the initial four F1 evaluators specifically, this deferral is permanent, not merely sequenced.
See the 2026-09-21 amendment below for the exposure cardinality and why the permanence conclusion
still holds.

## 2026-09-21 amendment: permanence for the initial four F1 evaluators

The paragraph above asserted that each (evaluator, fragrance) pair has one pre-reveal exposure.
That understated the count: a pair can have up to three pre-reveal exposures (blotter, a second
blotter presentation for the 6 hidden-repeat fragrances, and skin for the roughly 6 skin
candidates), all within F1's single blind pass; see ADR-005's 2026-09-21 amendment.

The permanence conclusion does not rest on the exposure count; it rests on the instrument. Neither
the blotter nor the skin instrument has a structured preference-driver field ("which attributes
pushed your rating up or down"), and this ADR is not implemented before F1, so no pre-reveal stage
collects it. Once identities are revealed, it cannot be collected retroactively for any initial
evaluator's pair. The fatigue and comparability reasoning above still justifies the deferral; it is
recorded here so the trade-off is visible rather than read as a neutral delay.

## Perfumer as an evaluable dimension

Added 2026-09-19 at the maintainer's request. Related to the above because both ask the same
question: what is the model allowed to reason over, and on what evidence.

### What already existed

`Perfumer` and `VersionPerfumer` have been in `models/calibration.py` since migration
`c731b42e9a01`, with `VersionPerfumer.source_url` carrying provenance per ADR-006. The Parfumo
scraper has been populating them. But `Fragrance` had no relationship reaching them, no schema
exposed them and no endpoint returned them, so the attribution was **write-only**: recorded and
readable by nothing.

That gap is now closed. No migration was required, and none was added.

### The disclosure consequence

Perfumer is identity-revealing. An evaluator who recognises the perfumer can often name a coded
sample outright, which is the exact failure ADR-005's blind protocol exists to prevent. The
attribution is therefore disclosed on precisely the same condition as brand, name and
concentration: inside the `identity` block that `participant_view` populates only once
`revealed_at` is set, and nowhere else in the participant payload.

Three tiers now hold that line: a unit test that drives an enrollment to reveal and asserts the
name is absent from the entire pre-reveal payload (verified to fail when the gate is removed), a
mocked e2e assertion, and a structural check in the real-backend smoke tier.

### The provenance problem, which is not solved

**The only writer of perfumer rows is the Parfumo scraper, and ADR-012 deprecates Parfumo as a
data source.** The Kaggle importer does not supply perfumer at all, and there is no API to enter
an attribution by hand. So in practice this dimension will be either empty or populated from a
source the project has already decided not to rely on.

Reading the field is now possible; having trustworthy data in it is a separate problem, and it
blocks any evaluation that depends on it. The realistic options are a manual manufacturer-sourced
entry path (consistent with ADR-012's preference for manufacturer provenance), or accepting
Parfumo attribution as evidence-of-claim with its `source_url` shown, which is what the interface
currently does.

### What was deliberately not done

Perfumer is **not** wired into affinity scoring. ADR-004 defines the weighted score over notes,
accords and families; adding a fourth dimension changes recommendation output, which ADR-009's
frozen checkpoints depend on being stable. That is a decision to take explicitly, not a change to
slip in because the data became readable.

## Open questions for the maintainer

1. Signed direction (pushed up / pushed down) or a graded preference score?
2. Blotter stage, skin stage, or both?
3. Does a stated preference outrank observed liking in the affinity weighting, and by how much?
   (ADR-004 follow-up.)
4. Does this apply to ordinary encounters too, or only to controlled observations?
5. Where does trustworthy perfumer data come from, given ADR-012? A manual entry path, or accept
   Parfumo attribution as evidence-of-claim?
6. Does perfumer become a scoring dimension in ADR-004, and if so, does it land before or after F1?
7. Should attribution be recorded per fragrance *version*, as it is now, or per fragrance? A
   reformulation can change the perfumer, and the current shape already allows for that.

## Related

- [ADR-004](./adr-004-recommendation-algorithm.md): the weighting this would feed
- [ADR-007](./adr-007-preference-evidence-and-score-semantics.md): score semantics and what the
  affinity figure may be called
- [ADR-009](./adr-009-prospective-evaluation-and-checkpoints.md): why this cannot land mid-panel
- [ADR-010](./adr-010-preference-learning-and-scenario-data-model.md): the typed response columns
  this amends
- [Design system](../../development/design-system.md): the interface grouping that already makes the
  descriptive/affective split visible
