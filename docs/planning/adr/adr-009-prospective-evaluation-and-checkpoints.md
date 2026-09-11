# ADR-009: Prospective Evaluation and Frozen Checkpoints

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

With four evaluators, recommendation strategies can easily overfit. Tuning aliases, thresholds,
filters, or model weights after seeing final outcomes and then reporting those same outcomes as
validation would not demonstrate predictive value.

Catalog and source data also change over time, so reconstructing inputs after the fact is
insufficient.

## Decision

Evaluate new recommendation and candidate strategies prospectively.

- Declare development, validation, and final holdout roles before eligible outcomes.
- Persist recommendation impressions before collecting feedback.
- Freeze algorithm/version, exact input manifest, source-feature snapshot, candidate strategy,
  exclusions, scores/predictions, and timestamp.
- Close prospective checkpoint creation for an enrollment after any holdout response.
- Never tune on final holdout outcomes and report performance against those outcomes.
- Compare strategies using the same candidate eligibility and outcome definitions.
- Report interest, response coverage, sampling conversion, liking, wear/buy outcomes, catalog
  coverage, variety, and availability separately.
- Treat repeated observations as reliability evidence rather than independent people.

## Consequences

- Experiments require more setup and provenance storage.
- Small samples will often support directional decisions rather than strong general claims.
- Frozen checkpoints preserve evidence even when catalog metadata or code changes.
- Automated active learning and calibrated predictions remain deferred until prospective results
  justify them.

## Validation

- Checkpoint creation fails after any eligible holdout response.
- Retrieved checkpoints retain their original manifest and source features after later mutations.
- Reports declare counts, denominators, exclusions, strategy, and uncertainty.
- Each D5 evaluation ends with an adopt, revise, or stop decision.

## Related

- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [Authoritative Project Plan](../PROJECT-PLAN.md)
