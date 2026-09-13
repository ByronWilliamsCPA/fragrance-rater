# ADR-010: Preference-Learning and Scenario Data Model

> **Status**: Partially implemented (approved by product owner for the ML-testing slice below);
> the scenario/pairwise/behavioral-event portions remain Proposed
>
> **Date**: 2026-09-12 | **Updated**: 2026-09-12

## Implementation status

The product owner asked to begin ML testing against recommendation/liking projections and
approved implementing, in one pass, the two changes this needed most:

- **Typed controlled-observation fields** (first bullet of the Decision below): implemented in
  migration `9ded7f54996c`. `calibration_observations.responses` is retired; `confidence`,
  `sweetness`, `freshness`, `density`, `familiarity`, `dryness`, `clean_soapy`, `earthy_rooty`,
  `bodily_animalic`, `discomfort`, `opening_liking`, `drydown_liking`, `would_wear`, `would_buy`,
  `artistic_appreciation`, `projection`, `longevity_minutes`, `perceived_notes`, `likes`,
  `dislikes`, `reminds_me_of`, and `comments`, 22 columns in total, are now typed. Of those 22,
  17 carry database-level CHECK-constraint bounds; the remaining 5 (`likes`, `dislikes`,
  `reminds_me_of`, and `comments` as free text, plus `perceived_notes` as JSON) are validated at
  the API layer only, not at the database level.
  `PreferenceHistoryService.training_manifest()` exposes them as a named `features` dict (plus a
  separate `notes_text` dict for free text) instead of one opaque blob.
- **`PredictionSnapshot`**: implemented as a new model, migration, service
  (`PredictionService`), and manager-gated API (`/api/v1/predictions`). A model's predicted
  rating is frozen before the real outcome exists and linked to exactly one later `Evaluation`
  or `Observation` outcome, without ever recomputing the frozen prediction.

**Note on naming**: the `PredictionSnapshot` entity above is a new, standalone model, service,
and API endpoint shipped in this PR for freezing a model's predicted rating against a later real
outcome. It is a different concept from the still-deferred, unimplemented
`ModelCheckpoint.predictions` decomposition mentioned in the Decision below and in the
[Data Model Gap Analysis](../data-model-gap-analysis.md) (§XXXVII, §6 Deferred): that item would
split the existing `ModelCheckpoint.predictions` JSON column into typed rows and remains
unimplemented. The two must not be conflated.

The regenerated `docs/api/openapi.json` accompanying this PR also picks up two pre-existing,
previously undocumented routes from prior work that are unrelated to the changes described here;
this is expected spec-regeneration behavior, not new functionality introduced by this PR.

Everything else in the Decision below (brand/accord lookup tables, familiarity as a controlled
code rather than a raw int, `perceived_notes` normalized against `Note`, sample-provenance
columns, the full scenario/context domain, `PairwiseComparison`, `BehavioralEvent`,
`ClassificationSystem`) remains Proposed and unimplemented; see the gap analysis for the
still-open sequence.

## Context

A full review against the requirements for controlled baseline evaluation, repeated encounters,
structured preference capture, scenario/context modeling, pairwise preference, behavioral
outcomes, and future ML/recommendation work found the existing encounter/experiment/measurement
architecture (ADR-005 through ADR-009) already satisfies most of the highest-value requirements:
atomic non-destructive encounters, prospective holdouts, relational perfumer/source provenance,
and immutable recommendation impressions. The full analysis is recorded in
[Data Model Gap Analysis](../data-model-gap-analysis.md).

The review found one concentrated, consequential gap, since closed by the implemented slice
described above: `calibration_observations.responses` **used to** store validated, bounded,
clearly analytical fields, including `would_wear`, `would_buy`, opening/drydown liking, sensory
dimensions, perceived notes, and confidence, inside a single untyped JSON column, and
`PreferenceHistoryService.training_manifest()` forwarded that blob unchanged into the frozen ML
training manifest. The review also found a smaller number of domains
(scenario/context, pairwise comparison, general behavioral events, multiple classification
systems, brand identity, accord vocabulary) that are entirely or partly missing and are named
directly in the roadmap's stated future ML outputs.

## Decision

Extend, rather than replace, the existing catalog/encounter/experiment/measurement schema:

- Promote the fixed, already-validated set of `calibration_observations.responses` fields to
  typed, constrained columns, and normalize `perceived_notes` against the existing `Note`
  vocabulary. Add an equivalent controlled `familiarity` code to both `evaluations` and
  `calibration_observations`, replacing the current ambiguous numeric scale.
- Add small, additive lookup tables for `brands`, `accord_types`, sample source
  types/containers, and `training_eligibility`, following the stable-code/display-label/
  sort_order/active pattern already established by `core/vocabulary.py`. Keep every existing
  free-text column (`Fragrance.brand`, `FragranceAccord.accord_type`) unchanged during a
  transition period rather than dropping it.
- Add a scenario/context domain (`seasons`, `climate_bands`, `occasions`, `desired_effects` as
  controlled multi-select vocabularies; `ScenarioSuitability` for hypothetical judgments and
  `ActualWearContext` for observed wear, kept as separate entities) once UI capacity exists to
  expose it.
- Add `PairwiseComparison` and `BehavioralEvent` as new first-class entities, generalizing what
  `RecommendationResponseRevision.would_wear`/`would_buy`/`sampling_state` currently answer only
  in the narrower context of one recommendation impression.
- Add `ClassificationSystem`/`FragranceClassification` so `primary_family`/`subfamily` become the
  default system's materialized values in a versioned, pluggable model rather than the only
  possible taxonomy.
- Defer a `FragranceVariant` split from `Fragrance` (governed by ADR-006, unchanged by this
  decision), a full `PhysicalSample` entity, backend-published `FeatureDefinition`/`FeatureValue`
  rows, the `ModelCheckpoint.predictions` decomposition (deferred; distinct from the
  already-implemented `PredictionSnapshot` entity described above), a recommendation
  `selection_objective` taxonomy, and embedding storage until the milestone or concrete
  consumer that needs each one actually exists.

Every change is additive at the row/history level: no existing encounter, evaluation, or
calibration observation is discarded, and uncertain or absent legacy values are left NULL rather
than fabricated. This does **not** mean every column survives unchanged forever: the implemented
slice below retires the `calibration_observations.responses` column once its data has been
backfilled into typed columns (a one-time, reviewed structural change), not a permanent
dual-write. New tables and columns are otherwise additive, backfilled from existing data where
reasonably inferable and left null where not, per the same migration discipline ADR-006 already
established for source/vocabulary changes. Because this changes the table's shape, `downgrade()`
on the implementing migration intentionally refuses (raises) rather than attempting a lossy
in-place reversal; rollback is by restoring a pre-upgrade backup, consistent with every other
migration in this repository that touches encounter or calibration history (e.g. `c731b42e9a01`).

## Consequences

- The single highest-priority fix (typed columns replacing the `responses` JSON blob) must land
  before controlled baseline data collection scales up under milestone P1.1/F1, or the resulting
  history requires a backfill migration instead of a clean read.
- Ordinary quick-rating workflows (`POST /evaluations`) are unaffected by the P0 changes; no
  existing required field changes.
- Scenario/context, pairwise, and general behavioral-event modeling remain unavailable to any ML
  work until their respective schema changes land, consistent with the roadmap already treating
  discovery/statistics/prospective-evaluation work (milestones D1-D5) as sequenced after the
  family pilot (F1).
- No existing ADR is superseded. This ADR is additive to ADR-005/006/007/009 and does not reopen
  the ADR-006 decision to keep `Fragrance` as the canonical version entity through milestone D5.

## Validation

**Implemented and tested** (the slice described in "Implementation status" above): repeated
encounters retained, typed-observation round-trip through `observe()`/`participant_view()`,
checkpoint immutability across later model/source changes, no-overwrite on correction,
raw-comment preservation, NULL-vs-zero missingness for the typed observation fields, prediction
snapshots frozen independently of their later outcome link, one-time outcome linking (reject a
second link, a mismatched reviewer/fragrance, or an outcome recorded before the prediction), and
migration backfill correctness against a real PostgreSQL 16 instance (fresh install, full
upgrade chain, and backfill of a seeded pre-migration row).

**Recommended, not yet implemented**, for the remaining Decision items above (multi-select
season/occasion storage, hypothetical-suitability-vs-actual-wear-context separation,
published-vs-perceived accord/note separation, stable vocabulary codes across label changes,
independent EDT/EDP evaluation as a regression fixture): see
[Data Model Gap Analysis §8](../data-model-gap-analysis.md#8-testing-requirements) for the
complete recommended list, to be implemented alongside each corresponding schema change.

Each migration step is reviewed against the Project Plan's existing "Definition of Done" (§19):
PostgreSQL-tested where constraints or concurrency are involved, generated OpenAPI and
documentation updated in the same pull request, and no destructive change to existing rows.

## Related

- [Data Model Gap Analysis](../data-model-gap-analysis.md)
- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-006](adr-006-version-identity-and-source-provenance.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
