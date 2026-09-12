# ADR-010: Preference-Learning and Scenario Data Model

> **Status**: Proposed
>
> **Date**: 2026-09-12

## Context

A full review against the requirements for controlled baseline evaluation, repeated encounters,
structured preference capture, scenario/context modeling, pairwise preference, behavioral
outcomes, and future ML/recommendation work found the existing encounter/experiment/measurement
architecture (ADR-005 through ADR-009) already satisfies most of the highest-value requirements:
atomic non-destructive encounters, prospective holdouts, relational perfumer/source provenance,
and immutable recommendation impressions. The full analysis is recorded in
[Data Model Gap Analysis](../data-model-gap-analysis.md).

The review found one concentrated, consequential gap: `calibration_observations.responses`
stores validated, bounded, clearly analytical fields — `would_wear`, `would_buy`,
opening/drydown liking, sensory dimensions, perceived notes, confidence — inside a single
untyped JSON column, and `PreferenceHistoryService.training_manifest()` forwards that blob
unchanged into the frozen ML training manifest. It found a smaller number of domains
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
  rows, `PredictionSnapshot` decomposition of `ModelCheckpoint.predictions`, a recommendation
  `selection_objective` taxonomy, and embedding storage until the milestone or concrete
  consumer that needs each one actually exists.

Every change is additive: new nullable columns and new tables, backfilled from existing data
where reasonably inferable and left null where not, per the same migration discipline ADR-006
already established for source/vocabulary changes.

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

- Tests cover: repeated encounters retained, hidden-repeat/holdout exclusion from training,
  independent EDT/EDP evaluation, published-vs-perceived accord/note separation, multi-select
  season/occasion storage, hypothetical-suitability-vs-actual-wear-context separation,
  checkpoint immutability across later model updates, no-overwrite on correction, raw-comment
  preservation, NULL-vs-zero missingness, and stable vocabulary codes across label changes. See
  [Data Model Gap Analysis §8](../data-model-gap-analysis.md#8-testing-requirements) for the
  complete list.
- Each migration step is reviewed against the Project Plan's existing "Definition of Done"
  (§19): PostgreSQL-tested where constraints or concurrency are involved, generated OpenAPI and
  documentation updated in the same pull request, and no destructive change to existing rows.

## Related

- [Data Model Gap Analysis](../data-model-gap-analysis.md)
- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-006](adr-006-version-identity-and-source-provenance.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
