# ADR-009: Prospective Evaluation and Frozen Checkpoints

> **Status**: Accepted; amended 2026-09-19 (declared learning problem; repeat-benchmark
> terminology) and 2026-09-21 (mapping-holder evaluator excluded from training, retained in
> evaluation)
>
> **Date**: 2026-09-11 | **Amended**: 2026-09-19, 2026-09-21

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

## 2026-09-19 amendment: the declared learning problem

The Decision above requires a target, eligibility, and decision rule to be declared before
outcomes are collected. None had been written down. The product owner accepted the following
declarations (ML Decisions 2026-09, Q1) as the `affinity-v1` and first learned-model contract.

| Element | Declaration |
| :--- | :--- |
| Unit of prediction | One (evaluator, fragrance version) pair in a declared stage |
| Primary target | The latest eligible pre-reveal controlled `liking` (0 to 10) for the pair, preferring a locked skin stage over a locked blotter stage, on its original scale |
| Secondary targets | `would_wear` and `would_buy` (0 to 10) from the same observation, reported beside liking in every scorecard; never pooled with the boolean recommendation-feedback fields of the same names |
| Ordinary ratings | A separate 1 to 5 outcome for the ordinary workflow, never mapped onto liking for evaluation; the `(liking - 5) / 2.5` map in ADR-007 is a scoring convenience, not an equivalence |
| Feature basis | A versioned, low-dimensional representation (about 20 to 30 dimensions): controlled accord vocabulary, Michael Edwards family as a versioned classification, note-family groups from the versioned alias and taxonomy layer, later D2 co-occurrence factors |
| Model class | Partially pooled (hierarchical) linear or ordinal models: shared coefficients fit across evaluators, per-evaluator deviations shrunk toward them |
| Metrics | Paired mean absolute error on the 0 to 10 scale and Spearman rank correlation over each evaluator's holdouts, per evaluator and pooled, each with n and an interval, quoted against the hidden-repeat noise ceiling; precision@k on interest is a funnel metric only |
| Splits | Development: baseline members. Validation: leave-one-out within the baseline. Final holdout: the assigned `HOLDOUT` members per evaluator, never tuned on |
| Decision rule | A candidate model replaces the default only if its pooled holdout error improves on the default by more than the repeat-estimated noise, on the same eligibility set |
| Baseline | The affinity heuristic with serialized, digested parameters (`fragrance_rater.ml.model`); the corrected `affinity-v2` is the default, `affinity-v1` is retained as a reference model |

Consequences: `PredictionSnapshot` rows are produced by `fragrance_rater.ml.predict` with a
server-built manifest, and `fragrance_rater.ml.evaluate` computes the metrics above. Reports that
omit the ceiling, the n, or the interval are not valid evidence under this ADR.

Related: [ML Structure Review 2026-09](../ml-structure-review-2026-09.md),
[ML Decisions 2026-09](../ml-decisions-2026-09.md).

## 2026-09-19 amendment: repeat-benchmark terminology

The metrics row above quotes holdout error "against the hidden-repeat noise ceiling." The
ADR-005 protocol-research-reconciliation amendment found that 6 repeats per evaluator (5 degrees
of freedom each) support only a pooled, wide-uncertainty measurement-error benchmark, not a
precise individual noise ceiling. Read "hidden-repeat noise ceiling" in the table above as
"repeat-derived measurement-error benchmark, pooled across all 24 family-wide repeat pairs with
wide reported uncertainty." Reports comparing holdout error to this benchmark must include the
pooled interval, not a bare point estimate.

This changes what "by more than the repeat-estimated noise" means in the Decision rule above
(line 62), since the benchmark is now an interval, not a point estimate. The predeclared
comparison rule: a candidate's pooled holdout-error improvement counts as exceeding the noise
benchmark only if it clears the upper bound of the pooled repeat-benchmark interval, not its
point estimate or midpoint. An improvement that falls inside the interval is not distinguishable
from measurement noise under this benchmark and must not trigger adoption; only an improvement
that clears the interval's upper bound triggers replacing the default. This is deliberately
conservative: the interval already pools cross-evaluator noise, so comparing against its upper
edge rather than its center avoids adopting a model whose apparent gain is an artifact of that
same pooled noise.

Related: [ADR-005](adr-005-controlled-calibration.md), 2026-09-19 amendment.

## 2026-09-21 amendment: mapping-holder evaluator excluded from training, retained in evaluation

For F1, the evaluator who also holds the blind-to-identity mapping cannot be made blind by
software (see `gates/f1.md`). Confirmed by the product owner 2026-09-26 (resolving the finding
recorded 2026-09-21 in `PROJECT-PLAN.md`'s risk table): that evaluator's rows are excluded from
blind-baseline model TRAINING, but remain in evaluation. Per-evaluator metrics (the Metrics row in
the declared-learning-problem table above) still report that evaluator's paired MAE and Spearman
correlation, so a reader can see how their non-blind rows compare to the three blind evaluators'.

This also changes how the pooled repeat benchmark (2026-09-19 amendment, above) is reported: it is
reported both ways, as 18 pairs pooled across the three blind evaluators and as all 24 pairs
including the mapping-holder's 6, so a reader can see whether including non-blind repeat pairs
moves the pooled benchmark.

Related: [PROJECT-PLAN.md](../PROJECT-PLAN.md), section 21 risk table; [F1 gate](../gates/f1.md).

## Related

- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [Authoritative Project Plan](../PROJECT-PLAN.md)
