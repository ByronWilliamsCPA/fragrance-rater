# ADR-014: Training Eligibility and the Unclassified Family Sentinel

> **Status**: Proposed (not yet approved by product owner; recorded here per
> ADR-005/ADR-010's practice of stating approval status explicitly rather
> than assuming it)
> **Date**: 2026-09-19

## Context

### The gap: every fragrance is forced into the Michael Edwards Wheel

`Fragrance.primary_family` and `Fragrance.subfamily` are `NOT NULL` columns
in the ORM model, and `FragranceCreate`/`FragranceUpdate` mirror that with
`Field(..., min_length=1)` in the Pydantic schema. There is no way to create
or update a fragrance without supplying a non-empty value for both fields,
and no sentinel value exists for "not yet classified." Every fragrance in
the catalog, whatever its actual provenance, is forced to carry a family and
subfamily string drawn from (or at least shaped like) the Michael Edwards
Wheel taxonomy that ADR-013 crosswalks against external ontologies.

That constraint was harmless while the catalog only held fragrances the
Wheel already covers. It stops being harmless the moment a fragrance whose
real classification doesn't fit the Wheel needs to enter the catalog: the
API has no way to say "this fragrance doesn't have a real family yet,"
only ways to say "here is a family," true or not. A caller is left with two
bad options: invent a plausible-looking value, or refuse to create the row
at all. The first quietly corrupts the taxonomy; the second blocks the
catalog from growing.

The corruption is not contained to the fragrance record itself. Whatever
value goes into `primary_family`/`subfamily` flows automatically into
`RecommendationService.build_preference_profile`, which accumulates every
evaluated fragrance's notes, accords, and family into a reviewer's affinity
profile with no opt-out. A fabricated family value doesn't just sit
inertly in a row; it actively shapes recommendations the moment anyone
evaluates that fragrance.

This gap surfaced during scoping for a prior, separately-decided piece of
work: integrating fragrances whose classification does not originate from
the Michael Edwards Wheel. That scoping discussion rejected both extremes
considered (a fully separate "sidecar" catalog that never touches the main
schema, and a full rebuild of the existing baseline/holdout panel around a
new taxonomy) in favor of a narrower path: a new versioned Program plus a
small number of additive changes to the existing schema, of which the gate
described in this ADR is one piece. That scoping decision was made and
recorded outside this repository; nothing here should be read as
introducing or re-litigating it. This ADR addresses only the schema gap it
exposed: the training-eligibility gate.

### ADR-010 already proposed the two pieces that close this gap, but never built them

ADR-010's Decision section lists, among its still-unbuilt additive lookup
tables:

> Add small, additive lookup tables for `brands`, `accord_types`, sample
> source types/containers, and `training_eligibility`, following the
> stable-code/display-label/sort_order/active pattern already established by
> `core/vocabulary.py`.

and, separately, describes the deeper fix for the taxonomy problem itself:

> Add `ClassificationSystem`/`FragranceClassification` so
> `primary_family`/`subfamily` become the default system's materialized
> values in a versioned, pluggable model rather than the only possible
> taxonomy.

Neither piece was ever implemented; ADR-010's own status line still records
the scenario/classification portions as "remain Proposed," and the gap
analysis (`docs/planning/data-model-gap-analysis.md`, row VIII) confirms:
"No `ClassificationSystem` entity; only one taxonomy, unversioned." This ADR
builds the first of ADR-010's two pieces, the `training_eligibility` lookup
table, as a standalone, minimal slice. It does not build the second:
`ClassificationSystem`/`FragranceClassification` remains Proposed and
unimplemented, exactly as ADR-010 left it. In its place, this ADR adds a
single sentinel value, `UNCLASSIFIED_FAMILY`, as a stopgap so a fragrance
with no real classification has a truthful value to write into
`primary_family`/`subfamily` instead of a fabricated one, until
`ClassificationSystem` exists to replace it properly.

### A related but distinct concept: data-model-gap-analysis row XL

The gap analysis's row XL ("Training eligibility / data quality status")
independently identified a related need, but scoped to a different
attachment point:

> An ordinary encounter cannot be marked `WITHHELD`/`INVALIDATED`/
> `QUESTIONABLE` (e.g., a contaminated sample) | Add optional
> `training_eligibility` code to `evaluations`, default `ELIGIBLE`

Row XL's concept is per-*evaluation*: a data-quality flag on one reviewer's
one encounter with one fragrance (a contaminated sample, a mis-administered
trial). This ADR's concept is per-*fragrance*: whether the fragrance itself
has a real classification to contribute at all. The two are not the same
gate and this ADR does not build row XL's evaluation-level flag. Putting the
gate on `Fragrance` rather than `Evaluation` was deliberate: the
unclassified-taxonomy problem is a property of the fragrance record itself,
true for every reviewer who ever evaluates it, not a property of any one
encounter. A per-evaluation flag would require re-flagging the same
fragrance every time a new reviewer evaluates it, and would let a fresh
evaluation of a known-unclassified fragrance silently default back to
"eligible" the moment nobody remembers to set the flag again. Row XL's
per-evaluation data-quality gate remains a distinct, unimplemented gap; nothing
in this ADR closes it.

## Decision

1. **`training_eligibilities` lookup table.** A small reference table
   using the stable-code/display-label/sort_order/active shape ADR-010
   proposed for it (Context above). No existing table or migration already
   implements that exact shape: `core/vocabulary.py` holds Python-level
   constants (a `Literal` and frozensets), not a lookup table with
   `display_label`/`sort_order`/`active` columns, and the `fragella_lookups`
   migration (`2c341c369192`) creates a reference-lookup attempt log
   (id/fragrance_id/status/results), not a seeded code/label lookup. This
   migration is the first concrete instance of the pattern ADR-010
   described, not a repeat of an established one. Seeded by migration with
   exactly three rows: `eligible` (sort 0), and two ways to be excluded,
   `excluded_pending_classification` (sort 10, no real classification
   exists yet) and `excluded_manual` (sort 20, a reviewer or maintainer has
   flagged the fragrance for some other reason).

2. **Nullable `Fragrance.training_eligibility_code` FK, defaulting to
   NULL meaning eligible.** `NULL` is not a third state to reason about
   separately; it is defined to mean the same thing as the `eligible` row.
   This keeps every existing fragrance's behavior unchanged (see
   Consequences) without a backfill migration, and lets a future write path
   set the code explicitly only when a fragrance actually needs to be
   excluded. The FK uses `ondelete="RESTRICT"` so a lookup row in active use
   cannot be deleted out from under a fragrance that references it.

3. **`RecommendationService.build_preference_profile` skips
   training-ineligible fragrances.** Before a fragrance's notes, accords,
   and family are folded into a reviewer's affinity accumulators, the
   service now checks whether that fragrance's `training_eligibility_code`
   is one of the codes in `TRAINING_INELIGIBLE_CODES`
   (`excluded_pending_classification`, `excluded_manual`) and skips the
   contribution entirely if so. The evaluation itself is untouched (it is
   not deleted, hidden, or invalidated); only its contribution to affinity
   scoring is withheld. `evaluation_count` on the returned profile reflects
   only the fragrances that actually contributed, not the reviewer's raw
   evaluation count, so it cannot overstate how much evidence the profile is
   actually built from.

4. **`UNCLASSIFIED_FAMILY` sentinel in `core/vocabulary.py`.** A single
   constant, `"Unclassified"`, that a caller can write into
   `primary_family`/`subfamily` instead of a fabricated Wheel-shaped value.
   It satisfies the existing `NOT NULL`/`min_length=1` constraints
   truthfully rather than working around them. It is a stopgap, not a
   taxonomy: it does not classify anything, it only names the absence of a
   classification, pending ADR-010's still-unbuilt
   `ClassificationSystem`/`FragranceClassification`.

`TRAINING_INELIGIBLE_CODES` is defined once, in `core/vocabulary.py`, and
used both as the migration's seed-data source of truth (the two excluded
codes) and as the service-layer check, the same anti-drift discipline
`core/vocabulary.py` already documents for `gender_target`: one constant, not
two lists that can silently diverge.

### Alternatives considered

- **Attach the gate to `Evaluation` instead of `Fragrance`** (row XL's
  original framing). Rejected for this ADR: it solves a different problem
  (per-encounter data quality) and would require re-flagging on every new
  evaluation of the same unclassified fragrance, discussed above.
- **Build `ClassificationSystem`/`FragranceClassification` now instead of a
  sentinel.** Rejected for this pass: it is a materially larger, versioned,
  pluggable data model that ADR-010 already scoped as its own decision.
  Building it as a side effect of closing this narrower gap would blur
  which ADR owns which piece of ADR-010's still-open sequence. `
  UNCLASSIFIED_FAMILY` is deliberately a minimal, low-risk placeholder that
  does not foreclose that future work.
- **Reject the fragrance at the API layer instead of admitting it with a
  sentinel.** Rejected: this is exactly the "refuse to create the row"
  option the prior sidecar-vs-rebuild scoping discussion moved away from;
  it blocks catalog growth rather than gating affinity scoring, which is
  where the actual risk (corrupting recommendations) lives.

## Consequences

### Positive

- A fragrance without a real Wheel classification can now be created
  honestly (`UNCLASSIFIED_FAMILY`) and excluded from affinity scoring
  (`training_eligibility_code`) instead of forcing a fabricated family value
  that would silently pollute every reviewer who evaluates it.
- The two lookup-table and gating pieces close exactly the slice of
  ADR-010's already-proposed `training_eligibility` lookup table that was
  never built, without waiting on the larger `ClassificationSystem` work.
- The change is additive and non-breaking: no existing behavior for any of
  the current 149 fragrances changes.

### Trade-offs

- **`UNCLASSIFIED_FAMILY` fragrances still bucket into `family_affinities`
  as their own bucket.** Marking a fragrance training-ineligible removes its
  contribution entirely (notes, accords, and family), but an eligible
  fragrance whose family happens to be `UNCLASSIFIED_FAMILY` is not itself
  ineligible, so if one is ever marked eligible while still carrying the
  sentinel value, `"Unclassified"` would accumulate in `family_affinities`
  like any other family string. This is a deliberate deferred limitation,
  not a bug: resolving it properly means giving `UNCLASSIFIED_FAMILY`
  first-class handling in the scoring algorithm (or, better, replacing it
  entirely once `ClassificationSystem` exists), which is out of scope here.
- **`UNCLASSIFIED_FAMILY` has zero production call sites today, and the
  places that would eventually need to handle it are broader than
  `family_affinities` alone.** This ADR deliberately leaves the sentinel
  inert pending `ClassificationSystem` (see Alternatives above), but every
  place that currently reads `primary_family`/`subfamily` as if they were
  always real Wheel values would need review once a caller actually starts
  writing `UNCLASSIFIED_FAMILY`, not only the scoring algorithm named above.
  Known examples in the current codebase:
  - `RecommendationService.build_preference_profile`'s `family_affinities`
    accumulation (already named above).
  - `PreferenceHistoryService.training_manifest()`, which copies
    `primary_family`/`subfamily` verbatim into each row's
    `source_features` for the frozen ML training manifest; a downstream
    model trained on that manifest would see `"Unclassified"` as an
    ordinary family value with no signal that it means "no real
    classification."
  - `api/recommendations.py`'s `FragranceDetails` construction, which
    already falls back to the literal string `"Unknown"` when
    `primary_family`/`subfamily` is falsy
    (`fragrance.primary_family or "Unknown"`). That fallback and
    `UNCLASSIFIED_FAMILY` are two different unclassified-ish strings
    (`"Unknown"` vs. `"Unclassified"`) that a future caller could easily
    conflate; reconciling them is follow-up work this ADR does not do.
  - Any future export, reporting, or classification-management UI that
    groups or displays fragrances by family would need the same review
    before `UNCLASSIFIED_FAMILY` is wired into an actual write path.
  This list is provided for scope disclosure only; no code in this ADR
  changes any of the sites above, and none of them raises, misbehaves, or
  needs to change today, because no write path yet produces
  `UNCLASSIFIED_FAMILY` for them to encounter.
- **No management API for `training_eligibilities` in this pass.** The
  table is seeded once by migration and has no CRUD endpoints; changing a
  fragrance's `training_eligibility_code` today requires a direct write
  (a future `FragranceUpdate` PATCH, which does already expose the field, or
  a manual data fix), not an admin workflow. Building that workflow is
  follow-up work, not part of this decision.
- **The existing 149 fragrances are unaffected.** No backfill migration
  runs; every existing row keeps `training_eligibility_code = NULL`, which
  this ADR defines as "eligible," so today's affinity scoring behavior is
  unchanged for the entire current catalog.

## Validation

- Migration upgrade/downgrade round-trip: the three seed rows exist with
  the specified `sort_order` and `active=True`, `training_eligibility_code`
  is nullable with no backfill on existing rows, the FK rejects an
  unknown code, and `downgrade()` cleanly reverses column, FK, index, and
  table.
- `RecommendationService.build_preference_profile`: a reviewer with one
  `eligible` (NULL) and one `excluded_pending_classification` evaluation
  produces affinities reflecting only the eligible fragrance; the excluded
  fragrance's notes, accords, and family never appear in the resulting
  profile, and `evaluation_count` reflects only the contributing
  evaluation.
- `core/vocabulary.py` constants: `UNCLASSIFIED_FAMILY` and
  `TRAINING_INELIGIBLE_CODES` exist with the specified values.
- Schema round-trip: `FragranceCreate`/`FragranceUpdate`/`FragranceResponse`
  all accept and return `training_eligibility_code`, including the
  omitted/`None` case, matching the existing `intensity` field's pattern.

All of the above are implemented and passing as of this ADR; see
`alembic/versions/7daf681ed339_training_eligibility_lookup.py`,
`tests/integration/test_training_eligibility_migration.py`,
`tests/unit/test_services/test_recommendation_service.py`,
`tests/unit/test_core/test_vocabulary.py`, and
`tests/unit/test_schemas/test_fragrance.py`.

## Related

- [ADR-004](./adr-004-recommendation-algorithm.md): the affinity-scoring
  algorithm this ADR adds a skip-gate to.
- [ADR-010](./adr-010-preference-learning-and-scenario-data-model.md): the
  source of both the `training_eligibility` lookup table and the
  `ClassificationSystem`/`FragranceClassification` proposals; this ADR
  implements the first and defers the second.
- [ADR-013](./adr-013-external-ontology-and-standards-crosswalk.md): the
  external-ontology crosswalk that a future `ClassificationSystem` would
  need to reconcile against once it replaces `UNCLASSIFIED_FAMILY`.
- [Data model gap analysis](../data-model-gap-analysis.md): row VIII
  (missing `ClassificationSystem`) and row XL (the related but distinct
  evaluation-level training-eligibility concept this ADR does not build).
- [Baseline evidence: Universal Baseline and Validation Holdout
  V3.1](../evidence/baseline-v3.1-universal-and-holdout.md): the existing
  43-fragrance calibration baseline and holdout panel, unaffected by this
  change since none of its fragrances carry a non-NULL
  `training_eligibility_code`.
