---
title: "Idea Register from Reviewed Claude Branches"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Preserve the few still-open ideas from two superseded remote review documents without landing the documents themselves."
tags:
  - planning
  - ideas
  - review
---

> **Status**: Draft, non-authoritative idea register | **Captured**: 2026-10-30
>
> **Authority**: This register does not override [PROJECT-PLAN.md](PROJECT-PLAN.md) or any ADR, changes no
> milestone status, and schedules no work. An idea becomes work only when an ADR, the plan, or a tech-spec
> amendment adopts it.

## Provenance

Two remote branches carried planning documents that were never merged and were reviewed on 2026-10-30. Both are
mostly superseded by the ADRs, the plan, and [the 2026-09 architecture review](architecture-review-2026-09.md).
Only the items below were judged still unaddressed. Source tip SHAs are recorded in the PROJECT-PLAN current-state
ledger.

- `architecture-review.md` (branch `claude/fragrance-app-architecture-8i6v4i`, 2026-09-09): ideas 1 to 3.
- `dataset-constraint-concept.md` (branch `claude/fragrance-dataset-concept-w2qvwa`, 2026-09-15): ideas 4 to 6.

## Ideas

### 1. A separate `information_value` axis

The source proposed storing `information_value` (how much a sample would teach the model) as a column independent of
`predicted_liking`, alongside a `recommendation_type` (for example safe, discovery, diagnostic, reference).
Still open: D4 already keeps predicted liking, novelty, uncertainty, availability, and cost as separate fields, and
the [data model gap analysis](data-model-gap-analysis.md) assigns `recommendation_type` to D4, but no document
defines an information-value measure. ADR-009 defers active learning, so this stays out of scope until prospective
results justify it. Touches D4 and D5. Guardrail: never blend it into the affinity score (ADR-007 score semantics).

### 2. Coverage-gap reporting against the baseline panel

Report which taste dimensions the baseline panel does not cover (for example, no sampled leather or smoke
exemplars), so the family knows where a preference estimate is extrapolating. Still open: D4 requires coverage and
variety thresholds over recommended candidates, and ADR-013 and ADR-017 define vocabularies, but nothing reports
panel coverage over those facets. No milestone owns it today; the natural fit is a D2 descriptive output or a
later R-sprint report. Guardrail: a descriptive count per facet, not a score or a claim about taste.

### 3. Append-only versioning for role and fact rows

The source modeled corrections to role and fact rows as a new row with `is_current` and a `superseded_by_id`
self-reference instead of an in-place update, preserving "we used to believe this" as an auditable fact. Still open:
ADR-006 makes source evidence append-only and ADR-017 supersedes whole vocabulary sets, but no decision covers
correcting an individual role or fact row. R8's planned immutability triggers (PROJECT-PLAN section 11a, WS-9
items D-08 and Q14) forbid in-place edits to observations, checkpoints, activated membership, and assigned
identity; they define no way to record a legitimate correction. The two must be designed together, or the triggers
will leave corrections with no sanctioned path. Guardrail: do not add the pattern ahead of an ADR-010 amendment.

### 4. LLM nominates candidate names only (D4)

The source proposed an LLM that proposes only names ("given what you like, consider X"), with no notes and no score.
Each nomination is labeled model output, is never a catalog row, and is not scored until identity is verified and
notes are confirmed against an owned source; a hallucinated name fails verification and is discarded. Still open:
ADR-003 confines the LLM to explaining deterministic scores and does not cover nominating, and ADR-004's Fragella
amendment is the only current discovery source. Touches D4 and ADR-003. Guardrails: nominations cannot read holdout
outcomes (already a D4 criterion), and model output stays separate from published and perceived evidence (vision).

### 5. Confirmation must not degrade into click-through

Where a human confirmation is what turns a looked-up value into a stored first-party fact, the confirmation has to
be real. Still open: ADR-012 prefers manufacturer confirmation and ADR-004 forbids retaining vendor payloads, but
neither says how a UI prevents "OK" from counting as verification. Suggested enforcement idea: require the
confirmer to enter or select the verified value (for example retype the concentration or choose a note from the
source's list) rather than accept a prefilled one, and mark unconfirmed records ineligible for controlled
assignment. Touches ADR-012 and ADR-006 and any future write-through path.

### 6. D2 small-N caution

Lift, observed-minus-expected, and partner share computed over roughly 43 baseline and holdout versions are false
precision. D2 already requires minimum support, shrinkage, and denominators, but not an explicit statement that
catalog statistics at this scale are descriptive only. Capture: D2 outputs over a corpus this small should show raw
counts and denominators and make no beyond-chance claims. Touches D2 and tech-spec section on statistics.

## Open question for the owner (undecided)

> **Owner decision, not recommended here.** Most vendor data-licensing outreach was declined on 2026-09-23, with
> Fragella retained under a paid plan and not as training data. Do D2 and D4 survive as currently scoped?

Options, named without a recommendation: keep D2 and D4 as written; re-scope them to the data actually available
(descriptive baseline-scale statistics for D2, nominate-verify-score of user-selected candidates for D4); defer
them until a licensed corpus exists; or drop one or both. Ideas 4 and 6 only matter under the re-scoped option.

## Related

- [PROJECT-PLAN.md](PROJECT-PLAN.md) for D2, D4, D5, R8, and the ledger entry recording branch disposition.
- [ADR-003](adr/adr-003-llm-integration.md), [ADR-004](adr/adr-004-recommendation-algorithm.md),
  [ADR-007](adr/adr-007-preference-evidence-and-score-semantics.md),
  [ADR-009](adr/adr-009-prospective-evaluation-and-checkpoints.md),
  [ADR-012](adr/adr-012-data-source-compliance-and-manufacturer-provenance.md).
