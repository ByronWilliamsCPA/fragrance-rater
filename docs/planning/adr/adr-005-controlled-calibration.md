# ADR-005: Controlled Calibration and Disclosure State

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

Ordinary ratings alone cannot distinguish stable preference from context, recognition, order,
or measurement noise. Controlled programs need repeated blind observations and final holdouts
without losing the simpler family journal workflow.

The system must also prevent identity leakage through APIs and derived surfaces while preserving
all original observations.

## Decision

Use one canonical reviewer and fragrance-version catalog for ordinary and controlled workflows.
Controlled programs add immutable activated membership, randomized coded presentations,
append-only observations, stage locks, explicit skin-plan finalization, delayed reveal, and
separate post-reveal observations.

For each evaluator:

- non-holdout identities remain hidden until required blotter/repeat stages and planned skin
  stages are locked and the skin plan is finalized;
- holdout identities remain hidden until their own required stage is locked;
- participant responses never expose membership role, repeat link, selection evidence, or
  fragrance mapping before disclosure policy permits it;
- already known versions are marked previously revealed;
- blind corrections require a future append-only revision workflow.

Disclosure policy is a shared server-side service applied to history, profiles, recommendations,
explanations, caches, errors, exports, and future analytical views.

## Consequences

- Raw controlled evidence remains auditable and usable for prospective evaluation.
- Managers can retrieve physical-sample mappings; a manager who is also an evaluator cannot be
  made blind by software.
- Workflow state and authorization require more integration and end-to-end tests.
- Sample/session counts are data, not hard-coded application constants.

## Validation

- State-transition tests cover activation, enrollment, locking, reveal, and post-reveal append.
- Disclosure-matrix tests cover every direct and derived surface.
- Concurrent lock and observation attempts are exercised on PostgreSQL.
- Exact version evidence is required before program assignment.

## 2026-09-19 amendment: protocol research reconciliation

The Decision above treats sample and session counts as configuration data, not architecture,
but left the actual values undecided until checked against sensory-evaluation practice.
Milestone R sprint R5 ran the
[protocol research prompt](../../research/scent-evaluation-protocol-research-prompt.md) against
two independent deep-research models; the results are recorded at
`docs/research/deep-research-report (12).md` and
`docs/research/Fragrance Evaluation Protocol Validation.md`. Six citations from each were
independently verified against primary sources rather than trusted as written. The first
report's citations all checked out (correct DOIs, the correct ISO 8589:2007/Amendment 1:2014
edition, and a correct denial that IFRA sets any numeric per-day sampling limit for consumer
testing). The second contained a fabricated DOI for a study also cited by the first report, two
further real DOIs reattributed to unrelated findings under invented author names, a wrong ISO
8589 edition year, and an IFRA/QRA2 claim its own cited paper does not support. Where the two
reports disagree, this amendment follows the first, verified report. Where they agree, the
agreement is treated as corroborating regardless of which report's citation trail is sound.

This closes ML Decisions Q8 as decided (previously provisional pending this research) and
settles the daily-load, calendar-spread, and judgment-set half of the protocol design that
`ml-decisions-2026-09.md` deferred.

| Element | Prior design | Decision | Rationale |
| :--- | :--- | :--- | :--- |
| Samples per session | 3 | Unchanged: 3 | No untrained-consumer standard sets a lower ceiling; matches olfactory-adaptation literature for block size. |
| Daily load | Up to 9 (protocol days 1 to 3) | Maximum 6 (two sessions of 3) | 9/day was never shown safe or unsafe; 6/day is a conservative extrapolation from adaptation and questionnaire-fatigue evidence, not a standards requirement. |
| Calendar spread | 13 sessions compressed into 5 days | 13 sessions over 7 test days, distributed across 10 to 14 calendar days; same-day sessions separated by at least 3 hours | Circadian, hunger, and illness effects are documented and get conflated with trait preference under 5-day compression. This keeps the existing 43-fragrance/49-presentation baseline and 6-repeat design unchanged, unlike the alternative considered (1 session/day over 3 to 4 weeks with 15 repeats), which would have restructured both. |
| Inter-stimulus procedure | Coffee beans between samples; interval unspecified | Coffee beans removed; minimum 2 minutes of clean air, extended to about 5 minutes after a persistent or aversive sample | Direct exploratory evidence found coffee beans no better than plain air; no evidence supports a bean-based reset. |
| Liking / wear / buy / appreciation scale | 0 to 10 integer, unanchored | Unchanged: 0 to 10 integer; add verbal anchors at 0, 5, and 10 (0/5 for the 0 to 5 descriptors) | ISO 4121 supports quantitative scales generally without mandating a change of scale; anchoring fixes the real defect (an ambiguous midpoint) without a costly VAS/LAM migration to an already-merged schema. |
| Familiarity | 0 to 5 integer | Categorical recognition (new / vaguely familiar / recognize exact fragrance / owned or worn), with an optional 0 to 5 "feels familiar" strength kept as a separate field | Familiarity, recognition, and ownership are different constructs; a bare integer conflates them. |
| `would_buy` | Captured per sample in the core blinded questionnaire, same structure as liking | Moved out of the blinded per-sample core; collected after the wear phase as a secondary outcome, with price context when available | Aligns with ADR-007's existing rule that would-buy is "a separate event and outcome"; without price or identity it is a different construct from sensory liking. |
| Descriptive dimensions | 8 dimensions including `discomfort` alongside sweetness, freshness, etc. | 7 exploratory descriptors (sweetness, freshness, density/weight, dryness, clean/soapy, earthy/rooty, bodily/animalic); `discomfort` becomes its own aversiveness/adverse-response field, not a descriptor | Discomfort is a reaction to the fragrance, not an odor-character quality; conflating it with sweetness treats a safety signal as a perceptual dimension. |
| `artistic_appreciation` | Core 0 to 10 field alongside liking/wear/buy | Optional and secondary, collected only if wanted, never a default model target | Reduces respondent burden and avoids proliferating correlated targets in an already data-poor (33-fragrance) model. |
| Ranking | Not implemented (ML Decisions Q8 provisional: rank 3 samples per session) | Confirmed: rank all 3 samples per session after absolute ratings; analyzed as one rank event (Plackett-Luce or an equivalent rank-ordered likelihood), never as three independent pairwise comparisons | ISO 8587 covers ranking methodology; a 3-item rank is one dependent event, not three independent observations. |
| Repeat design | 6 hidden repeats per evaluator, treated informally | Unchanged: 6 hidden repeats; pool all 24 family-wide repeat differences hierarchically and report wide uncertainty; do not present six pairs as a precise individual reliability figure | Six repeats give only 5 degrees of freedom per evaluator; increasing the count would consume the fixed 33-fragrance training budget. See the related ADR-009 terminology note. |
| Order/position | Ad hoc; strong or animalic samples conventionally placed last | Explicit constrained randomization: each evaluator receives exactly 13 first-, 13 second-, and 13 third-position presentations across the 39 baseline slots; at most one exceptionally persistent/animalic stimulus per session; strong stimuli are not defaulted to last position | Placing strong stimuli last confounds fragrance character with position; balancing separates the two. |
| Session-context fields | Not recorded | Record per session: illness, nasal congestion, allergy symptoms, hunger, hours since food/caffeine, personal fragrance worn, ambient odor, room temperature/humidity, time of day; menstrual/hormonal context optional and refusable | Circadian and metabolic-state effects are documented; recording them supports sensitivity analysis without discarding otherwise-valid observations. |
| Non-detection handling | Intensity 0, liking NULL | Unchanged; already correct | Independently confirmed by both research reports as the right design. |
| Skin timepoints | Opening/drydown/longevity in minutes; exact schedule unspecified | 10 minutes, 1 hour, 4 hours, 8 hours; longevity stored as `last_detected_elapsed_min` / `first_not_detected_elapsed_min` (interval-censored), not a single exact-minute value | No standardized industry timepoints exist; this schedule samples the opening/heart/drydown/persistence trajectory without an hourly burden. Exact-minute longevity implies false precision. |
| Skin-phase selection | Ad hoc ("favorites"); daily skin-sample limit unspecified | About 6 skin candidates per evaluator (2 high-blotter-liking, 2 mid/borderline, 2 model-uncertain), excluding anything that produced discomfort; maximum 1 new skin application per evaluator per day | Testing only top scorers range-restricts the blotter/skin comparison. The 1/day limit is a protocol-level caution, not a claimed IFRA/QRA2 numeric limit; no such consumer-testing limit was found to exist. |

## Consequences (amendment)

- ML Decisions Q8 moves from provisional to decided; `ml-decisions-2026-09.md` is updated to
  record this amendment as its resolution.
- The 33-baseline/10-holdout/6-repeat structure and the existing catalog/identity mechanics in
  [Controlled Calibration V1](../../calibration-v1.md) and the baseline evidence
  (`docs/planning/evidence/baseline-v3.1-universal-and-holdout.md`) are unchanged; no version
  needs to be re-selected or renumbered.
- Milestone R sprint R7 implements the resulting schema changes (session-context fields,
  familiarity encoding, `would_buy` relocation, the ranking/pairwise tables, skin-observation
  timepoints) per its existing scope; this amendment is R7's input, not a substitute for it.
- ADR-009's declared-learning-problem amendment quotes holdout error "against the hidden-repeat
  noise ceiling." Read that phrase alongside the repeat-design row above: 6 repeats per evaluator
  support a pooled, wide-uncertainty benchmark, not a precise individual ceiling. See the
  companion ADR-009 terminology amendment.

## Related

- [ADR-006](adr-006-version-identity-and-source-provenance.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [ADR-008](adr-008-authentication-and-production-boundary.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
- [Controlled Calibration V1](../../calibration-v1.md)
