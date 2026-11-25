# ADR-009: Prospective Evaluation and Frozen Checkpoints

> **Status**: Accepted; amended 2026-09-19 (declared learning problem; repeat-benchmark
> terminology) and 2026-09-21 (mapping-holder evaluator excluded from training, retained in
> evaluation; `would_buy` as a post-reveal outcome), both confirmed by the product owner 2026-09-26;
> amended 2026-11-24 (`would_buy` stays on the blind skin form, pending owner confirmation; six-evaluator
> facilitated F1 format)
>
> **Date**: 2026-09-11 | **Amended**: 2026-09-19, 2026-09-21, 2026-11-24

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
| Secondary targets | `would_wear` and `would_buy` (0 to 10) from the same observation, reported beside liking in every scorecard; never pooled with the boolean recommendation-feedback fields of the same names. `would_buy` is superseded by the 2026-09-21 amendment below |
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

## 2026-09-21 amendment: `would_buy` as a post-reveal outcome

DEC-03 (`product-research-remediation-implementation-plan.md` section 4, confirmed by the product
owner 2026-09-26) moves `would_buy` out of the blind skin core in R7b, and R7b is a hard gate on
P6.3, so no F1 pre-reveal observation contains `would_buy`. The Secondary targets row above can
therefore no longer take it "from the same observation" as pre-reveal liking. `would_buy` becomes a
separately linked post-reveal outcome: one decision-block response per (evaluator, fragrance
version) pair, collected with its offer and scenario context fields (DC-06), eligible only when
that decision block is completed after reveal, and reported beside liking with its own n (completed
decision blocks) as its denominator. It is never pooled with the pre-reveal targets. `would_wear`
is unchanged: a same-observation secondary target at the skin stage. See ADR-005's 2026-09-21
amendment for why a blind `would_buy` cannot be recovered for the initial four evaluators.

## 2026-11-24 amendment: `would_buy` stays on the blind skin form (pending owner confirmation)

> **Status of this amendment: pending owner confirmation of the leakage and analysis implications.**

The 2026-09-21 amendment above states that R7b removes `would_buy` from the blind skin core, so that no F1
pre-reveal observation contains it. `PROJECT-PLAN.md` section 11a (R7b row) records an owner decision of
2026-10-30 that `would_buy` stays on the form and that the removal is not carried out;
`tests/unit/test_schemas/test_response_input_r7b.py` encodes it. The decision's own source document was not
found in the repository. That decision supersedes the statement above: a pre-reveal skin-stage observation
can carry a blind, price-free `would_buy`.

Consequences for this ADR, to be confirmed by the owner:

- The Secondary targets row above applies again to `would_buy` for any evaluator who has a skin stage,
  taken from the same observation and reported with its own n. It stays unpooled with liking.
- The post-reveal decision-block outcome (with offer and scenario context) stays a separate,
  offer-conditioned measurement; the repository does not establish whether it is still being built.
- In the six-evaluator facilitated format (below), only the non-blind mapping holder has a skin stage, so
  the only pre-reveal `would_buy` rows in F1 are non-blind and excluded from blind-baseline training.

## 2026-11-24 amendment: six-evaluator facilitated F1 format

The product owner decided on 2026-11-24 that F1 runs as a six-evaluator facilitated format; the protocol
side is in [ADR-005's 2026-11-24 amendment](adr-005-controlled-calibration.md#2026-11-24-amendment-six-evaluator-facilitated-f1-format).
This amendment records what changes for prospective evaluation. The Decision, the declared learning
problem and the decision rule are otherwise unchanged. No gate is marked passed by this amendment.

- **Evaluators and training.** Six evaluators, of whom five are blind and one is the non-blind mapping
  holder. The holder's rows stay flagged non-blind, excluded from blind-baseline model training and retained
  in evaluation (2026-09-21 amendment above). The holder also sprays, times, transcribes, verifies and
  controls the reveal, so the holder's observations are single-blind with observer cues.
- **Pooled repeat benchmark.** Each evaluator has 6 hidden repeats, so the pool is 6 x 6 = 36 pairs across
  six evaluators, or 5 x 6 = 30 excluding the holder. These replace the 24 (4 x 6) and 18 (3 x 6) of the
  four-evaluator amendments, which now apply only if the program reverts to four evaluators. Report it both
  ways, 30 and 36, with the pooled interval. The 2026-09-19 comparison rule (an improvement must clear the
  upper bound of the pooled interval) is unchanged. Six pairs per evaluator still give 5 degrees of freedom,
  so the pool remains a wide-uncertainty benchmark and not an individual reliability figure.
- **Repeat consistency and novices.** Three evaluators are new to fragrance. Everyone is included and repeat
  consistency is reported descriptively. No exclusion threshold is declared or applied, and it must not be
  added after seeing outcomes (the Decision forbids post-hoc tuning of this kind).
- **Checkpoints and holdouts.** A checkpoint is created per enrollment after that enrollment's baseline,
  repeat and planned skin stages are locked and the skin plan is finalized, and before any holdout response
  (checkpoint creation closes after the first holdout response, see the Decision). In the facilitated format
  holdouts are smelled before the household reveal, so holdout sessions must stay unavailable until the
  checkpoint exists. This is a requirement; the server-side gate that enforces it is a work item listed in
  [PROJECT-PLAN.md section 11a](../PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24), and
  until it merges nothing in the software prevents holdouts from being recorded first.
- **Household reveal.** Identities are revealed once, for the whole program, after every enrollment's
  holdouts are locked. A per-enrollment reveal would disclose to one evaluator what the shared triples still
  hide from the others. Per-enrollment reveal remains the default for existing programs. Holdout identity
  hiding (until their own stage is locked) is unchanged.
- **Skin-absent by design.** The five blind evaluators have no skin stage by design (see ADR-005). Their
  primary target is the locked blotter liking, because the 2026-09-19 rule only prefers skin where a skin
  stage exists. Reports declare denominators per stage: skin-stage fields are counted only for evaluators with
  a skin plan, so F1 completeness never counts skin for the five, and a missing skin value for one of them is
  reported as "absent by design", not as missing data. Blotter fields are counted across all six.
- **Holdout eligibility.** Holdout eligibility stays evaluator-specific (the H02 prior-exposure check in the
  [baseline evidence](../evidence/baseline-v3.1-universal-and-holdout.md)). With six evaluators the check is
  made for each of them, and an evaluator with prior exposure to a holdout is reported as ineligible for it,
  not silently dropped.
- **Consequence for blind skin evidence.** F1 produces no blind skin-stage training rows, because the only
  skin evidence is the holder's. Any claim about skin-stage prediction waits for a later program.

Related: [ADR-005](adr-005-controlled-calibration.md), 2026-11-24 amendment; [F1 gate](../gates/f1.md).

## Related

- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [Authoritative Project Plan](../PROJECT-PLAN.md)
