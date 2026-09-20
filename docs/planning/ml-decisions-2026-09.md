---
title: "ML Decisions, September 2026"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Present the options and recommendation for each decision the ML structure review requires, and record the owner's answers."
tags:
  - planning
  - decisions
  - evaluation
---

> **Source**: [ML Structure Review 2026-09](ml-structure-review-2026-09.md), Section 8.
> **Status**: decided 2026-09-19 by the product owner. Q1 is recorded as the 2026-09-19 amendment to
> ADR-009. Q8 is decided: the
> [scent evaluation protocol research prompt](../research/scent-evaluation-protocol-research-prompt.md)
> was run and reconciled as the
> [2026-09-19 ADR-005 amendment](adr/adr-005-controlled-calibration.md#2026-09-19-amendment-protocol-research-reconciliation),
> which also changes the session's daily load, calendar spread, and judgment scales.

## Decision record

| # | Decision | Recommendation | Decision | Date |
| :--- | :--- | :--- | :--- | :--- |
| Q1 | Declared learning problem | A: accept Section 3; report would-wear beside liking | A | 2026-09-19 |
| Q2 | Vocabulary work before F1 | A: do it now for the 43 versions with P1.1 | A | 2026-09-19 |
| Q3 | Pairwise and behavioral tables before F1 | A: schema plus a session ranking prompt | A | 2026-09-19 |
| Q4 | Subfamily as a feature | A: exclude from new bases; v1 untouched | A (as recommended) | 2026-09-19 |
| Q5 | Kaggle positional accord intensities | A: keep, flag source, exclude by default | A | 2026-09-19 |
| Q6 | Freeze v1, fix as v2 | A: v1 pinned; register v2; compare | C, modified: fix now and make the corrected scorer (v2) the default because no family ratings exist; keep v1 registered as a reference model for the comparison harness | 2026-09-19 |
| Q7 | ML dependencies | A: optional dependency group in this repo | A | 2026-09-19 |
| Q8 | Pairwise judgments during F1 | B: rank the three samples per session | B, decided: rank all three, analyzed as one rank event (see the ADR-005 amendment) | 2026-09-19 |

## Q1. Declare the learning problem

Context: no target, loss, eligibility set, or decision rule is written down; ADR-009 forbids
collecting outcomes before they are.

- **A** (recommended): accept the review's Section 3. Primary target is the latest locked
  pre-reveal `liking` (0 to 10), skin preferred over blotter; `would_wear` and `would_buy` are
  secondary on the same observation; ordinary 1 to 5 ratings stay a separate, never-pooled
  outcome; metrics are paired MAE and Spearman per evaluator and pooled against the repeat-derived
  noise ceiling; affinity-v1 is the frozen baseline. Amendment: report would-wear beside liking in
  every scorecard.
- **B**: primary target `would_wear`. Closer to the vision's wear-or-buy measure, but a decision
  intent rather than a perception, more skewed, and the holdout design was built around liking.
- **C**: blotter-only liking. Cleaner stage control, but discards the skin observations the
  protocol collects and the ADR-007 rule already prefers.
- **D**: defer until after F1. The pilot then runs with no declared target.

Unblocks: the ADR-009 amendment and every evaluation report.

## Q2. Pull the vocabulary work ahead of F1

Context: note aliases, controlled accords, and the note-category fix are scheduled in D1, after
F1. Notes are case-sensitive strings; the category column mixes pyramid position and family;
accord names are free text.

- **A** (recommended): do it now, scoped to the 43 baseline and holdout versions, alongside the
  P1.1 manifest verification. About two pull requests: a migration adding an alias table and a
  normalized key, and one resolver used by both importers.
- **B**: keep the sequence and backfill after F1. Pilot checkpoints and manifests then carry
  fragmented features, and a backfill under frozen manifests contradicts their immutability.
- **C**: minimum fix only: normalize case in the importers and stop writing position into the
  category column; defer the alias table.

Unblocks: Tier 1 items 2 and 3; the reduced feature basis every viable model needs.

## Q3. Pairwise-comparison and behavioral-event tables before F1

Context: neither exists; neither can be reconstructed from independent ratings later.

- **A** (recommended): schema plus a minimal prompt in the calibration page (rank the three
  samples in this session). One extra interaction per session; see Q8.
- **B**: schema only. Leaves the shape ready but captures nothing during F1.
- **C**: defer to D4.

Unblocks: a rank-based training signal that roughly triples labels per session.

## Q4. Subfamily as a feature

Context: Parfumo writes it empty, Kaggle copies primary family into it, and the heuristic shares
one dictionary between family and subfamily.

- **A** (recommended): exclude it from every new feature basis until the versioned classification
  system exists; leave affinity-v1 untouched because it is frozen.
- **B**: keep it everywhere as-is (noise or a double count).
- **C**: keep it under a namespaced key in the v2 heuristic (do this as part of Q6).

Unblocks: a trustworthy "families" basis in the dataset builder.

## Q5. Kaggle positional accord intensities

Context: one importer fabricates intensity from list position; the other scrapes a percentage;
both feed the same column.

- **A** (recommended): keep the values, add an intensity-source flag, exclude positional values
  from measured features by default; the list order stays available as a rank feature.
- **B**: NULL the positional values. Honest, but throws away the ordering.
- **C**: leave as-is; a model treats a fabricated 0.85 as a measurement.

Unblocks: the accords basis, the natural 20 to 30 dimension reduced space.

## Q6. Freeze affinity-v1 with its defects; fix them as v2

Context: family and subfamily collide in one namespace, accord intensity enters the score twice,
and the veto and sigmoid operate on an unnormalized sum that grows with history.

- **A** (recommended): v1 stays pinned (done; digest-tested). Register a v2 with namespaced keys,
  intensity used once, evidence-count shrinkage, and the same veto rule on the shrunk affinity.
  Compare v1 against v2 on the same holdouts with the new harness.
- **B**: fix in place under the v1 label. Loses the record of what the family experienced.
- **C**: fix in place and bump to v2, dropping v1. Loses the baseline comparison.

Unblocks: Tier 4 item 18 and the first real use of the comparison harness.

## Q7. Where ML dependencies live

Context: the pipeline is pure Python; the first learned model wants numerical libraries.

- **A** (recommended): an optional dependency group in this repository (`numpy`, `scipy`,
  `scikit-learn`) installed only for notebooks and batch jobs; the API imports only the `Scorer`
  protocol, so the production image does not grow. Start with ridge regression over
  group-structured features before any Bayesian library.
- **B**: a separate package or repository. Isolation without benefit at this scale.
- **C**: stay pure Python. Fine for metrics; a partially pooled model without a solver is a
  research project.

Unblocks: Tier 4 item 18.

## Q8. Pairwise judgments during F1

Context: the participant-facing half of Q3.

- **A**: one question per adjacent pair. Two labels per three-sample session.
- **B** (recommended): rank all three samples at the end of the session. Three labels per
  session, one gesture, fits the existing session structure.
- **C**: none; the pilot yields only absolute scales.

Unblocks: a training signal that does not depend on the absolute scale holding steady across the
five-day protocol.

## Q8 follow-up: protocol research (resolved)

The 5-day, 13-session, 3-sample protocol was designed in concept and had not been verified
against sensory-evaluation practice. The
[deep-research prompt](../research/scent-evaluation-protocol-research-prompt.md) was run against
two independent deep-research models (`docs/research/deep-research-report (12).md` and
`docs/research/Fragrance Evaluation Protocol Validation.md`). Spot-verifying citations from both
found the first report accurate throughout and the second showing real citation fabrication
(a garbled DOI, two real DOIs reattributed to invented findings, a wrong ISO edition, an
unsupported IFRA/QRA2 claim); the reconciliation below follows the first report where they
disagree.

Reconciled and recorded as the
[2026-09-19 ADR-005 amendment](adr/adr-005-controlled-calibration.md#2026-09-19-amendment-protocol-research-reconciliation):
session size (3, unchanged), the 33-baseline/10-holdout/6-repeat structure (unchanged), daily load
(9 to 6), calendar spread (5 days to 7 test days over 10 to 14 calendar days), scale anchoring
(0 to 10 kept, verbal anchors added), familiarity (integer to categorical recognition), `would_buy`
placement (moved out of the blinded core, matching ADR-007), descriptive dimensions (`discomfort`
split out as its own field), the ranking procedure (confirmed, analyzed as one rank event, not
independent pairwise comparisons), order/position balancing (explicit constrained randomization),
session-context fields (added), and skin timepoints (10 min / 1 h / 4 h / 8 h with interval-censored
longevity). Schema implementation for these changes is R7's scope, not this amendment's.

## Sequence once decided

Scheduled as Milestone R in [PROJECT-PLAN.md section 11a](PROJECT-PLAN.md#11a-milestone-r-review-remediation-and-ml-foundation):
Q2 and Q5 are R6, Q3 and Q8 are R7 (R5's research reconciliation is done; R7's schema now also
carries the daily-load, calendar, scale, familiarity, `would_buy`, descriptor, and
session-context changes from the ADR-005 amendment), Q6 is done, Q7 is R15.

1. ADR-009 amendment recording Q1. Done.
2. Vocabulary migration and shared resolver for the 43 versions (Q2).
3. Protocol research reconciliation, recorded as the ADR-005 amendment (R5). Done.
4. Pairwise and behavioral tables with the session ranking prompt, plus the R5-derived schema
   changes (Q3, Q8, R7).
5. affinity-v2 as the default scorer, v1 retained for comparison (Q6, Q4). Implemented 2026-09-19;
   see the ADR-004 amendment.
6. Intensity-source flag (Q5) and the optional dependency group (Q7).
