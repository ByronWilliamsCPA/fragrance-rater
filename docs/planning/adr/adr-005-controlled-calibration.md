# ADR-005: Controlled Calibration and Disclosure State

> **Status**: Accepted; amended 2026-09-19 (protocol research reconciliation), 2026-09-21
> (exposure cardinality and would_buy permanence), 2026-10-30 (role-neutral answers) and 2026-11-24
> (six-evaluator facilitated F1 format)
>
> **Date**: 2026-09-11 | **Amended**: 2026-09-19, 2026-09-21, 2026-10-30, 2026-11-24

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
`docs/research/Fragrance Evaluation Protocol Validation.md`. An initial six-citation sample from
each was independently verified against primary sources rather than trusted as written; no full
audit of either report was performed. The sampled citations from the first report all checked
out (correct DOIs, the correct ISO 8589:2007/Amendment 1:2014 edition, and a correct denial that
IFRA sets any numeric per-day sampling limit for consumer testing) -- a verified sample, not a
clean bill for every citation in that report. The sampled citations from the second report
included a fabricated DOI for a study also cited by the first report, a wrong ISO 8589 edition
year, and an IFRA/QRA2 claim its own cited paper does not support. A supplementary check against
every DOI in the second report's own "Protocol Parameter Analysis and Evidence Synthesis" table
(not just the six-citation sample) found the problem count in that report runs higher than the
sample alone showed: at least three
real DOIs are reattributed to unrelated findings under invented author framing (including a rat
olfactory-bulb-deafferentation study misattributed as human circadian/hunger/hormonal-cycle
evidence, and a pediatric ski-helmet-safety study misattributed as fragrance
freshness/substantivity evidence), and at least two further DOIs beyond the originally
identified fabricated one do not resolve at all. See the second report's own front matter for
its current tally; treat any citation count given for that report as a floor, not a ceiling.
Where the two reports disagree, this amendment follows the first, verified report. Where they
agree, the agreement is treated as corroborating regardless of which report's citation trail is
sound.

This closes ML Decisions Q8 as decided (previously provisional pending this research) and
settles the daily-load, calendar-spread, and judgment-set half of the protocol design that
`ml-decisions-2026-09.md` deferred.

> **Scope caveat**: the numeric parameters below (daily load, calendar spread, session-context
> fields, scale anchors, and similar) come from reports whose citations were sample-checked, not
> exhaustively audited, and one report's own supplementary check (above) found more citation
> problems than the original sample surfaced. These numbers will govern a human-subject pilot
> protocol (Milestone F1). Treat them as a literature-informed starting point, not a
> peer-reviewed clinical protocol; re-verify any specific citation before treating its numeric
> claim as load-bearing for a safety decision.

| Element | Prior design | Decision | Rationale |
| :--- | :--- | :--- | :--- |
| Samples per session | 3 | Unchanged: 3 | No untrained-consumer standard sets a lower ceiling; matches olfactory-adaptation literature for block size. |
| Daily load | Up to 9 (protocol days 1 to 3) | Maximum 6 (two sessions of 3) | 9/day was never shown safe or unsafe; 6/day is a conservative extrapolation from adaptation and questionnaire-fatigue evidence, not a standards requirement. |
| Calendar spread | 13 sessions compressed into 5 days | 13 sessions over 7 test days, distributed across 10 to 14 calendar days; same-day sessions separated by at least 3 hours | Circadian, hunger, and illness effects are documented and get conflated with trait preference under 5-day compression. This keeps the existing 43-fragrance/49-presentation baseline and 6-repeat design unchanged, unlike the alternative considered (1 session/day over 3 to 4 weeks with 15 repeats), which would have restructured both. |
| Inter-stimulus procedure | Coffee beans between samples; interval unspecified | Coffee beans removed; minimum 2 minutes of clean air, extended to about 5 minutes after a persistent or aversive sample | Direct exploratory evidence found coffee beans no better than plain air; no evidence supports a bean-based reset. |
| Liking / wear / buy / appreciation scale | 0 to 10 integer, unanchored | Unchanged: 0 to 10 integer; add verbal anchors at 0, 5, and 10 (0/5 for the 0 to 5 descriptors) | ISO 4121 supports quantitative scales generally without mandating a change of scale; anchoring fixes the real defect (an ambiguous midpoint) without a costly VAS/LAM migration to an already-merged schema. |
| Familiarity | 0 to 5 integer | Categorical recognition (new / vaguely familiar / recognize exact fragrance), stored separately from a prior-exposure/ownership field (has owned or regularly worn this fragrance: yes / no / unknown); optional 0 to 5 "feels familiar" strength kept as its own field | Familiarity, recognition, and exposure/ownership are different constructs; folding "owned or worn" into the recognition scale would repeat the same conflation a bare integer caused. |
| `would_buy` | Captured per sample in the core blinded questionnaire, same structure as liking | Moved out of the blinded per-sample core; collected after the wear phase as a secondary outcome, with price context when available | Aligns with ADR-007's existing rule that would-buy is "a separate event and outcome"; without price or identity it is a different construct from sensory liking. |
| Descriptive dimensions | 8 dimensions including `discomfort` alongside sweetness, freshness, etc. | 7 exploratory descriptors (sweetness, freshness, density/weight, dryness, clean/soapy, earthy/rooty, bodily/animalic); `discomfort` becomes its own aversiveness/adverse-response field, not a descriptor | Discomfort is a reaction to the fragrance, not an odor-character quality; conflating it with sweetness treats a safety signal as a perceptual dimension. |
| `artistic_appreciation` | Core 0 to 10 field alongside liking/wear/buy | Optional and secondary, collected only if wanted, never a default model target | Reduces respondent burden and avoids proliferating correlated targets in an already data-poor (33-fragrance) model. |
| Ranking | Not implemented (ML Decisions Q8 provisional: rank 3 samples per session) | Confirmed: rank detected samples only, after absolute ratings; a non-detected sample (intensity 0) is `eligible_for_rank = false` and never assigned a rank position; omit the rank event entirely when fewer than 2 samples in the session are detected; analyzed as one rank event (Plackett-Luce or an equivalent rank-ordered likelihood) over the eligible subset, never as independent pairwise comparisons | ISO 8587 covers ranking methodology; a rank over N eligible items is one dependent event, not N independent observations; forcing a non-detected sample into a rank position would manufacture a preference the evaluator never expressed. |
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
- Milestone R sprint R7a implements the resulting schema changes (session-context fields,
  familiarity encoding, the ranking/pairwise tables, skin-observation timepoints); R7b implements
  the resulting participant-instrument changes, including `would_buy` relocation, per each sprint's
  existing scope. This amendment is R7a/R7b's input, not a substitute for either.
- ADR-009's declared-learning-problem amendment quotes holdout error "against the hidden-repeat
  noise ceiling." Read that phrase alongside the repeat-design row above: 6 repeats per evaluator
  support a pooled, wide-uncertainty benchmark, not a precise individual ceiling. See the
  companion ADR-009 terminology amendment.
- Moving `would_buy` out of the blinded per-sample core is a permanent omission for the initial F1
  evaluators, not an ordinary deferral. See the 2026-09-21 amendment below for the exact exposure
  cardinality and why the permanence conclusion still holds.

## 2026-09-21 amendment: exposure cardinality and would_buy permanence

The bullet above asserted that each (evaluator, fragrance) pair gets one pre-reveal blotter or skin
exposure. That understated the count. Every pre-reveal exposure falls within F1's single blind pass,
because identities stay hidden until all blotter stages, repeats, and planned skin stages are locked
(`docs/calibration-v1.md`): one blotter presentation per fragrance, a second blind blotter
presentation for the 6 hidden-repeat fragrances
(`docs/planning/evidence/baseline-v3.1-universal-and-holdout.md`), and a skin-stage exposure for
the roughly 6 candidates each evaluator carries forward to skin. The skin plan does not currently
say whether a hidden-repeat fragrance may be selected for skin, so a pair can have up to three
pre-reveal exposures.

The permanence conclusion does not rest on the exposure count; it rests on the instrument. Today's
skin core asks `would_buy` (`calibrationScales.ts:184`). DEC-03 removes it in R7b, and R7b is a
hard gate on P6.3 (`gates/p6.md`), so F1 runs on an instrument that asks `would_buy` at no
pre-reveal stage. Once F1's blind pass is over and identities are revealed, a blind, price-free
`would_buy` judgment cannot be collected for any initial evaluator's pair. The decision to move
`would_buy` out of the blinded core stands (an offer-conditioned `would_buy` would itself leak
identity through price and size, so it is necessarily post-reveal), but the loss is acknowledged
here rather than left implicit. ADR-009's matching 2026-09-21 amendment redefines `would_buy` as a
separately linked post-reveal outcome.

> **Superseded in part, pending owner confirmation (2026-11-24):** the R7b removal of blind `would_buy`
> described above was not carried out. See the [2026-11-24 `would_buy` amendment](#2026-11-24-amendment-would_buy-stays-on-the-blind-skin-form-pending-owner-confirmation).

## 2026-10-30 amendment: role-neutral answers and server-owned disclosure state (R4)

The blind policy covers every answer a participant surface can give, not only its payloads.
Architecture review B-01, B-02, and F-15 found three ways a holdout could still show through. R4
closes them:

- **Error bodies.** Feedback on a since-assigned holdout is refused with a role-neutral 409
  ("feedback cannot be recorded for this recommendation"), and the reason goes only to the server
  log. The reveal blocker no longer says "baseline and repeat", which announced hidden repeats.
- **Not-found answers.** Explanations are served only for a persisted impression. The catalog-ID
  route answered 404 for exactly the caller's holdouts among listable catalog fragrances, so it was
  removed. An impression whose fragrance became a holdout, or was deleted, explains exactly like a
  missing impression.
- **Client inference.** The server sends `post_reveal_entry` per sample, and the client chooses the
  blind or post-reveal form from that flag instead of from whether an identity is present. The
  recommendation follow-up lists linkable outcomes from a narrow endpoint that applies the server's
  linking rules, instead of pulling the reviewer's full history with its ratings, notes, and revealed
  identities.

Every participant-reachable error path is listed with the reason it is safe in the
[P4 participant disclosure matrix](../evidence/p4-participant-disclosure.md#participant-reachable-error-paths-r4).

## 2026-11-24 amendment: six-evaluator facilitated F1 format

The Decision and the amendments above were written for four independent evaluators, each with an
independently shuffled schedule and a per-enrollment reveal. The product owner decided on 2026-11-24
that F1 runs instead as a six-evaluator, facilitated, paper-first format. Three of the six are new to
fragrance evaluation. This amendment records the protocol consequences; the approval is the decision
date above, and no separate retained artifact exists in the repository. Nothing here changes
the 33-baseline, 10-holdout and 6-hidden-repeat structure, the 13 baseline sessions of 3, the scales,
the daily load or the inter-stimulus rule. It also does not mark any gate as passed: F1 stays blocked
on P6 (see [the F1 gate](../gates/f1.md)).

### Format

One facilitator, who is also the declared mapping holder and one of the six evaluators, runs
parallel silent sessions. Each evaluator has their own tray of three coded blotters, writes on a
paper sheet (one sheet per evaluator per session, three sample columns), and has no login and no
phone. The facilitator labels and sprays the vials, times the session, transcribes the sheets into
the application through one recorder login, verifies the transcription, and controls the reveal.
Because the facilitator is an evaluator and also sees the mapping, the facilitator's rows are
non-blind by construction (the 2026-09-21 mapping-holder consequence above, carried into ADR-009's
matching amendment); the facilitator's own observations are a single-blind design with observer
cues, not a blind one.

### Changes to the protocol table

| Element | Prior design | Decision for the facilitated format | Rationale |
| :--- | :--- | :--- | :--- |
| Evaluators | Four (three blind, one non-blind mapping holder) | Six (five blind, one non-blind mapping holder) | Product owner decision of 2026-11-24. |
| Session composition | Each evaluator's sessions independently shuffled | Shared triples: all six evaluators smell the same three fragrances in the same session, taken from the manifest's own 13 baseline sessions of 3, with holdouts in a separate final block | Parallel silent sessions need one tray composition per session; the facilitator can spray and time one set of triples. |
| Order within a session | Independent per-evaluator shuffle | Per-session Latin-square rotation: each evaluator's order within a session is a row of a balanced (Williams) Latin square of the triple, advanced by one row per session, so that across six evaluators every fragrance sits in every position exactly twice per session and adjacent-pair carryover is balanced; each evaluator's actual order is persisted (`intended_position`) | Shared triples would otherwise fix one order for everyone and confound fragrance with position. A single fixed permutation per evaluator was rejected because it would tie each evaluator to one position pattern across all 13 sessions. |
| Position balance per evaluator | 13 first, 13 second, 13 third across 39 baseline slots | Unchanged, and automatic: each of the 13 full sessions of 3 puts exactly one presentation in each position | No extra constraint is needed beyond using full triples. |
| Blind codes | `standard` scheme default (`E{n}-S{k}-{pos}`) | `random` scheme only (`secrets.token_hex(4).upper()`, evaluator-specific codes) | With shared triples the S number would identify the session for every evaluator, and holdout sessions are last, so the standard code would disclose holdout status. See the [calibration V1 label note](../../calibration-v1.md#configuration-and-workflow). |
| Skin | About 6 candidates per evaluator, at most 1 new application per evaluator per day | Skin-absent by design for the five blind evaluators; only the non-blind mapping holder carries a skin plan. The five finalize an intentionally empty skin plan. Skin is a separate optional path on its own day, never inside a facilitated blotter session | Facilitated sessions have no skin tests, and a single facilitator cannot supervise six skin timelines. The 1-per-evaluator-per-day limit and the candidate-selection rule apply unchanged to the holder. |
| Hidden repeats | 6 per evaluator; 24 pooled family-wide pairs (18 excluding the holder) | 6 per evaluator; 36 pooled pairs across six evaluators (30 excluding the holder). The repeat set is program-level and identical for every evaluator | Arithmetic: 6 evaluators x 6 hidden repeats = 36; 5 blind evaluators x 6 = 30. The earlier figures were 4 x 6 = 24 and 3 x 6 = 18. |
| Repeat consistency | Pooled, wide-uncertainty benchmark; no individual reliability figure | Same, and reported descriptively only. No exclusion threshold is declared, including for the three novices; everyone is included | Six pairs per evaluator give 5 degrees of freedom and are not an individual reliability figure, so a pass/fail cut on them would be statistically unsupported. This supersedes the earlier idea of a declared threshold. |
| Reveal | Per enrollment, after that evaluator's baseline, repeat and planned skin stages | One household (program-level) reveal, available only after every enrollment has locked its baseline, repeat and planned skin stages, the skin plans are finalized, a checkpoint exists for each enrollment and all holdouts are locked. All enrollments are then revealed together. Per-enrollment reveal stays the default for existing programs | A per-enrollment reveal would let one evaluator learn identities that the shared triples still show the others. |
| Phase order | Baseline, then skin, then reveal, then holdouts | All six complete baseline including hidden repeats; skin plans finalized (empty for five); a checkpoint per enrollment; holdouts; one household reveal. All six must be captured before the next session starts | Holdouts are smelled before the household reveal, so the checkpoint must be frozen first; checkpoint creation closes after any holdout response (ADR-009). |
| Timing | No elapsed-time rule beyond the clean-air interval | No fixed interval. Record the actual sprayed, first-smelled and column-finished times. A provisional 5-minute ceiling from spray to first smell applies, to be confirmed in P6.3; a breach is recorded as a deviation, never silently dropped. **Changed to 2 minutes on 2026-11-25, see the amendment below** | Blotters age; the ceiling bounds the exposure variation the facilitator cannot otherwise control. The 5 minutes is a provisional working value, not a researched one. |
| Session conditions | Recorded per session on the score page | Recorded on a separate slip, not the score page | The approved consent text promises that session-context answers are kept apart from the ratings. |
| Consent | Recorded per participant | Recorded once in the application before session 1, with the evaluator present; the server stamps `occurred_at` and the record persists per scope until withdrawn | Not recorded per sitting. |

### Primary target and completeness for the skin-absent evaluators

The 2026-09-19 table prefers a locked skin stage over a locked blotter stage when choosing an
evaluator's primary target. For the five skin-absent evaluators no skin stage exists, so their
primary target is the locked blotter liking. Fields that the instrument collects at the skin stage only
(`season_fit`, `setting_fit`, `would_wear`, `would_buy` and the skin timepoints) are absent for these five by
design. F1 completeness denominators therefore count skin-stage fields only for evaluators who have
a skin plan, and a missing skin value for one of the five is not a missing-data finding. Blotter
completeness is counted across all six. A reader of any F1 export must be able to see which
evaluators were skin-absent by design.

### Consequences (facilitated format)

- The only skin evidence in F1 comes from the non-blind holder, whose rows are excluded from
  blind-baseline training. F1 therefore yields no blind skin-stage training rows. Anything that
  needs blind skin data waits for a later program; this is the price of the one-facilitator format
  and is accepted by the 2026-11-24 decision.
- Position-effect and shared-room effects are not separable from the evaluators' own differences with
  six people in one room. Session context is recorded on the separate slip so these can at least be
  examined descriptively.
- The shared-triple template, the random-label requirement, the rotated order, the household reveal
  and the holdout gate are requirements that follow from this amendment. They are implemented by the
  facilitated-format work items in
  [PROJECT-PLAN.md section 11a](../PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24);
  until each item merges, the repository still behaves as the earlier amendments describe. The
  "at most one persistent or animalic stimulus per session" rule from the 2026-09-19 table is not
  enforced by any code today. The shared-triple enrollment work item is designed to enforce it in the
  template validator, from manager-supplied membership marks because no catalog field holds the property
  (design as reported by that work item; not verified here, since it has not merged).
- Calendar: with a maximum of 6 blotters (two sessions) a day, 17 sessions (13 baseline and 4 holdout)
  need at least 9 test days, not the 7 the 2026-09-19 row computed for the 13 baseline sessions alone.
- The three novices may be less consistent than experienced evaluators. This is reported, not
  filtered: the pooled repeat benchmark is expected to widen, which makes ADR-009's decision rule
  (clear the upper bound of the pooled interval) more conservative, not less. This expectation is
  inferred, not measured.

## 2026-11-25 amendment: group blotter mode, shared codes and order, 2 minute ceiling

The product owner decided on 2026-11-25 how F1 group sessions handle the physical blotters. This amendment records
the protocol consequences. It amends the 2026-11-24 amendment above; the text above is left as written and is
superseded where it conflicts. It marks no gate as passed, and the ceiling is still provisional.

> **Superseded for F1 later the same day.** The owner tried the group procedure physically and abandoned it; F1 uses
> one blotter per evaluator again. See the
> [individual-blotters addendum](#2026-11-25-addendum-group-blotter-mode-abandoned-for-f1-individual-blotters-return)
> below. The text of this amendment is kept as the record of what was decided first.

- **Group blotter mode.** The facilitator passes **one physical blotter per sample** around the six evaluators,
  one blotter at a time, in a fixed seat order. Eighteen blotters at once (six trays of three) is too strong a smell.
  This replaces "each evaluator has their own tray of three coded blotters" for F1 group sessions. Individual
  trays remain available as individual mode.
- **Shared code and order.** All evaluators therefore share the same blind code for a sample and see the same
  sample order within a session. This supersedes, for group sessions, the 2026-11-24 rows "Order within a session"
  (per-session Latin-square rotation across evaluators) and "Blind codes" (evaluator-specific codes). The `random`
  scheme is still required (a standard `S` number would still disclose session and holdout status). Position balance
  per evaluator across sessions is unchanged (each full session of 3 still puts one sample in each position), but the
  balance of a fragrance's position across the six evaluators is lost: order and seat position are confounded with
  the score. The owner accepts this limitation.
- **Flag only.** Scores from group sessions are marked by the informational session flag `group_shared_blotter`. They
  **remain eligible for training**, and the pooled repeat benchmark and per-evaluator metrics are reported both
  ways (with and without them). The flag exists so the decision to keep them can be reversed later. The new risk,
  recorded here rather than hidden: keeping them in training can let the order and seat-position confound reach a
  learned model.
- **Ceiling.** The spray-to-first-smell ceiling becomes **2 minutes**, measured from a blotter's spray to each
  evaluator's first smell of that blotter (it was 5 minutes in the 2026-11-24 amendment). It is still provisional:
  P6.3 tests whether six people can rotate within 2 minutes. If the window would be exceeded, the facilitator
  sprays a **new blotter of the same sample** (same blind code) and the remaining evaluators smell that one; each
  sheet's "Time sprayed" is the spray time of the blotter that evaluator smelled.
- **Not the clean-air interval.** The inter-stimulus interval (at least 2 minutes of clean air between the last
  sniff of one sample and the first sniff of the next, about 5 minutes after a persistent sample) is a different
  number and is unchanged. The two must not be conflated.
- **Implementation state.** The sheet (`facilitated-session-sheet v2.0` at that time; `v2.1` after the addendum below; `v2.2` from 2026-11-27), the run sheet and the spray-sheet generator
  describe the procedure. The application support (program `blotter_mode`, shared codes and order at enrollment, the
  flag, the 2 minute check) merged in #220, and the server-side safeguards below merged in #221; see
  [PROJECT-PLAN.md section 11a](../PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24). Merged code is
  not gate evidence: none of it has been rehearsed in P6.3.

### 2026-11-25 addendum: server-side safeguards for `SHARED_GROUP` programs (#221)

Recorded after #221 merged (`2bcd3cc`). It states what the code does and leaves the protocol decisions above
unchanged.

- **`SHARED_GROUP` implies a household reveal.** One blind code per sample goes to every evaluator, so one evaluator's
  own reveal would unblind the others. Setting the blotter mode to `SHARED_GROUP` sets `reveal_policy` to `HOUSEHOLD`
  (`CalibrationService.set_blotter_mode`); `PUT .../reveal-policy` refuses `ENROLLMENT` for a group program; and the
  reveal path reads `DisclosureGate.effective_reveal_policy`, which treats a stored `ENROLLMENT` on a group program as
  `HOUSEHOLD`, so no backfill is needed.
- **Program-wide holdout gate.** In a `SHARED_GROUP` program holdout samples open only when **every** enrollment has a
  checkpoint (`DisclosureGate.holdouts_open`, `missing_checkpoints`), because the one physical holdout blotter reaches
  all evaluators. `INDIVIDUAL` programs keep the per-enrollment rule. Enrolling a new evaluator is refused once every
  group enrollment has a checkpoint (`require_enrollment_open`), since the late enrollment would close the holdouts
  again for evaluators who may already have answered. The manager readiness view reports `blotter_mode`,
  `holdouts_open_program_wide`, `enrollments_missing_checkpoint` and a per-row `missing_checkpoint` and `holdouts_open`.
- **Evidence cannot pre-date the checkpoint.** For a holdout, an explicit evidence time (presented, sprayed, first
  smell, observed or column finished, ranking) earlier than the checkpoint that opened it is refused with HTTP 422
  (`EVIDENCE_BEFORE_CHECKPOINT`). When no time is supplied the server stamps receipt time, which cannot pre-date the
  checkpoint. The server cannot know when a blotter was physically smelled, so smelling a holdout before the
  checkpoint exists is prevented only by the facilitator's procedure (run sheet), not by software.
- **Ceiling flag.** The flag's `rule_version` is now `spray-to-smell-ceiling-v2` (a free-text column; earlier rows stay
  readable). `spray_to_smell_ceiling_exceeded` is not informational: it demotes training eligibility until the flag is
  closed, unlike `group_shared_blotter`.
- **Known gaps, not decided here.** No merged path withdraws an enrollment, and a withdrawn evaluator's unfinished
  enrollment blocks the household reveal for everyone (`household_blocker`). Because every group enrollment shares the
  blind code, the blind-code guard cannot detect a sheet entered under the wrong evaluator; a seat or initials check
  would change a recorded field and therefore the sheet version. Both are open owner decisions in the
  [F1 gate](../gates/f1.md).

### 2026-11-25 addendum: group blotter mode abandoned for F1, individual blotters return

On 2026-11-25 the owner tried the group blotter procedure physically (one blotter per sample passed round six
evaluators) and could get through only **two evaluators in two minutes**. Group mode is abandoned for F1 and F1 returns
to individual blotters. The owner's words, in intent: everyone does it on their own, the facilitator helps the children
keep theirs organized and does their own evaluations separately. This addendum records the protocol consequences; it
marks no gate as passed.

- **Code retained, unused.** Group blotter mode (`blotter_mode` `SHARED_GROUP`, `group_blotter.py`, the
  `shared-triples-group-blotter-v1` algorithm, the `group_shared_blotter` flag and the #221 safeguards) stays merged and
  is not used by F1. `INDIVIDUAL` is the default and F1 uses it.
- **One blotter per evaluator per sample.** Each evaluator has their own coded blotters, **sprays their own** (spray
  distance and count are an instruction to each evaluator; the proposed values, one spray from about 15 cm pointed
  away from faces and other blotters, are not yet confirmed by the owner), and writes their own spray time. Up to six
  sprayed blotters are in the room at once, which the run sheet handles with ventilation and prompt removal of used
  blotters.
- **Ceiling kept at 2 minutes, now per own blotter.** It is counted from an evaluator's own spray to that evaluator's
  own first smell. The two mirrored constants are unchanged. An evaluator whose own window passes unsmelled sprays a
  fresh blotter of the same sample and writes the new spray time. It is still provisional and is not the clean-air
  interval.
- **Roles.** The mapping holder facilitates (helps the other five keep blotters, trays and sheets organized, enforces
  silence and clean air) and does not evaluate during those sessions. The holder's own evaluations run in separate
  sessions, single-blind with observer cues, flagged non-blind. The holder still transcribes all six sheets through one
  recorder login, and skin tests stay holder-only.
- **What the code does with individual blotters (verified).** Enrollment with `shared-triples-latin-rotation-v1` gives
  every evaluator the same sessions with a Williams Latin-square order per evaluator and random evaluator-specific codes,
  so the 2026-11-24 rows on rotated order and evaluator-specific codes apply again and the shared-code confound
  accepted above does not arise. No session carries `group_shared_blotter`, so the pooled benchmark has only the holder
  split. The blind-code guard compares the code typed from the paper with the sample on screen, and because codes are
  now per evaluator it refuses a sheet entered under the wrong evaluator (409); the earlier statement that it cannot
  applied only to shared codes. `reveal_policy` `HOUSEHOLD` is allowed with `INDIVIDUAL` (the owner's plan: all six
  finish baseline, checkpoints and holdouts, then one program-level reveal). The holdout gate is per enrollment, the
  checkpoint of the evaluator concerned opens that evaluator's holdouts, and a holdout evidence time before that
  checkpoint is refused (422); the facilitator still runs no holdout sitting until all six checkpoints exist, which is
  procedure. The readiness view reports `holdouts_open` per row, and `holdouts_open_program_wide` is always false.
- **Sheet.** `facilitated-session-sheet v2.1` is a wording-only change that records no new field; the Part A Blotter
  mode row stays and records Individual. `v2.2` (2026-11-27) adds a pre-printed Atomizer row under the blind code row
  (a physical-location key for the standardized atomizers B01-B39 and H01-H10, not an identity); it records no new
  field. See the [F1 gate](../gates/f1.md) sign-off 16.

## 2026-11-24 amendment: `would_buy` stays on the blind skin form (pending owner confirmation)

> **Status of this amendment: pending owner confirmation of the leakage and analysis implications
> below.** It records what the repository currently says and does, not a re-decision.

The 2026-09-21 amendment above, the Consequences bullet that calls the move "a permanent omission for the
initial F1 evaluators", and the `would_buy` row of the 2026-09-19 table all assume that DEC-03 removes
`would_buy` from the blind skin core in R7b, so that F1 asks it at no pre-reveal stage. Verified in the
repository on 2026-11-24:

- `PROJECT-PLAN.md` section 11a, the R7b row, records an **owner decision of 2026-10-30: `would_buy` stays
  on the form; the removal is not carried out.**
- `tests/unit/test_schemas/test_response_input_r7b.py` (`test_would_buy_is_still_accepted`) encodes that
  decision: a skin-stage `would_buy` is still accepted.
- `frontend/src/content/calibrationScales.ts` still lists `would_buy` in `skinGroups`, and not in
  `blotterGroups`.

The 2026-10-30 decision is cited by the plan row and the test, but its own source document was not
found in the repository; this amendment relies on those two secondary records. Where the earlier text says
that F1 asks `would_buy` at no pre-reveal stage, that no F1 pre-reveal observation contains it, or that its
loss is permanent, the 2026-10-30 decision supersedes it: F1's instrument captures a blind, price-free
`would_buy` on the skin form. The reasoning that an offer-conditioned `would_buy` is necessarily post-reveal
is unaffected, and the post-reveal decision-block outcome ADR-009 describes remains the offer-conditioned
measurement; whether that block is still built is not established by the repository.

Implications the owner is asked to confirm:

- **Who produces blind `would_buy`.** It is a skin-stage field. Under the 2026-11-24 facilitated-format
  amendment above, only the non-blind mapping holder has a skin stage, so F1 yields no blind-evaluator
  `would_buy` at all, and the holder's value is non-blind and excluded from blind-baseline training.
  Under the earlier four-evaluator design the three blind evaluators would have produced it.
- **Leakage.** A price-free 0 to 10 purchase question can still be answered from brand or price
  recognition when the evaluator guesses the fragrance; the earlier concern (DC-06) that a context-free
  `would_buy` cannot separate dislike from price and size is not resolved by keeping it.
- **Analysis.** ADR-009 must again treat `would_buy` as a possible same-observation secondary target for
  evaluators who have a skin stage, reported with its own n, never pooled with liking.

## Related

- [ADR-006](adr-006-version-identity-and-source-provenance.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [ADR-008](adr-008-authentication-and-production-boundary.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
- [Controlled Calibration V1](../../calibration-v1.md)
