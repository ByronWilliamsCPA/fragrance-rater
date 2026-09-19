---
title: "ML Pipeline"
schema_type: common
status: published
owner: core-maintainer
purpose: "Explain the machine-learning core package: feature space, model objects, datasets, prospective prediction, and evaluation."
tags:
  - development
  - architecture
  - evaluation
---

The `fragrance_rater.ml` package holds the parts of the recommendation and prospective-evaluation
pipeline that can be imported without FastAPI or an event loop. It exists so a model can be
trained, frozen, scored, and compared in a notebook or batch job using the same definitions the
API uses. It was introduced by the
[ML Structure Review 2026-09](../planning/ml-structure-review-2026-09.md); the finding IDs below
refer to that document.

## What is fixed and what is a parameter

The declared learning problem (unit, primary target, feature basis, model class, metrics, splits,
decision rule) is recorded in ADR-009's 2026-09-19 amendment (ML Decisions Q1). The code still
treats the target as a parameter: `build_examples(..., target=...)` accepts any supported target
and defaults to the declared primary outcome, controlled `liking` on its original 0-10 scale
(ordinary rows keep `rating` on 1-5, never pooled).

The default scorer is `affinity-v2`, which corrects the three structural defects the review
found in the original heuristic (separate family and subfamily namespaces, accord intensity
applied once, evidence-count shrinkage with a stationary veto threshold; ADR-004 amendment
2026-09-19). `affinity-v1` is frozen exactly as it behaved before the extraction and stays
registered for reference comparisons. Both specs are digested; the pinned-digest tests fail when
any tunable changes without a version bump.

## Modules

| Module | Responsibility | Depends on |
| :--- | :--- | :--- |
| `ml.feature_space` | `FeatureVector`, `vectorize(fragrance)`, `from_source_features(dict)`, `FEATURE_SPACE_VERSION` | ORM models only |
| `ml.model` | `ModelSpec` (identity, version, params, digest), `Scorer` protocol, `ScoredResult`, `UserProfile`, `AffinityV1`, `AffinityV2` (default) | `feature_space` |
| `ml.registry` | `MODELS` (v1 and v2), `register`, `resolve`, `available`, `DEFAULT_MODEL_KEY` (`affinity-v2`) | `model` |
| `ml.dataset` | `TrainingRow`, `build_examples(session, reviewer_id, target=...)`, `to_arrays(rows, feature_space=...)`, `split_for(role)` | `PreferenceHistoryService` |
| `ml.reliability` | Hidden-repeat pairs, pooled agreement, bootstrap intervals: the noise ceiling | ORM models |
| `ml.evaluate` | Linked prediction outcomes, holdout scorecards (MAE, RMSE, Spearman with intervals), precision@k | `reliability` |
| `ml.predict` | `predict_and_freeze(...)`: run a registered model over the eligible set and write `PredictionSnapshot` rows with a server-built manifest | `registry`, services |

`RecommendationService` now delegates to the model object: it selects eligible evidence, calls
`vectorize`, and hands `(features, weights)` pairs to `Scorer.build_profile`; `calculate_match_score`
calls `Scorer.score`. `RecommendationMeasurementService.ALGORITHM_VERSION` is derived from
the default scorer's spec, so the label written on runs cannot drift from the code that scores.

## Feature space

`FeatureVector` carries the version identity, family labels, notes (each with `note_id`, `name`,
`position`) and accords (`name`, `intensity`), plus `feature_space_version`. The training manifest's
`source_features` is now produced by `FeatureVector.to_source_features()`, so a frozen manifest can
be turned back into scorer input with `from_source_features`. Manifests written before this change
carry no note ids; they rebuild as `fs-v0` vectors whose notes cannot be scored by an id-keyed
model, which is reported rather than guessed (review M-02).

Bump `FEATURE_SPACE_VERSION` whenever the set of fields, their meaning, or the vocabulary they draw
on changes. The vocabulary itself (note aliases, controlled accords, versioned families) is
still the review's Tier 1 work; the vectorizer is the single place that work plugs in.

## Adding a model

1. Implement the `Scorer` protocol: `spec: ModelSpec`, `controlled_affinity`, `build_profile`,
   `score`. Keep `build_profile` and `score` pure and synchronous.
2. Put every tunable in `spec.params`; the digest is your change detector.
3. `register(YourModel())` in `ml.registry` (or at import time in your module).
4. Freeze predictions with `predict_and_freeze(session, model_key=..., reviewer_id=...)` before the
   holdout outcomes exist, then compare with `ml.evaluate.scorecard` against the reliability
   ceiling from `ml.reliability`.

Prospective prediction refuses to run for a holdout that already has a pre-reveal observation,
mirrors the checkpoint-closure rule, and skips a fragrance that already has an unresolved
prediction for the same model version, so re-running is idempotent. The manifest is always built
server-side and checked against the reviewer's excluded versions before anything is written
(review M-09, X-18).

## Notebook use

```python
from fragrance_rater.core.database import get_session
from fragrance_rater.ml.dataset import build_examples, to_arrays

async with get_session() as session:
    rows = await build_examples(session, reviewer_id, target="liking")
X, y, groups, vocabulary = to_arrays(rows, feature_space="accords")
```

`to_arrays` is pure Python and returns lists; convert to arrays in the notebook. At the family
population size (about 33 labeled versions per evaluator) only partially pooled models on a reduced
basis are identifiable; see review Section 4 before choosing a model class.

## CLI

```bash
uv run fragrance-rater ml models
uv run fragrance-rater ml predict <reviewer_id> --model affinity-v2 --dry-run
```

## What this package deliberately does not do yet

- It does not fit anything. The first learned model is Tier 4 in the review and depends on the
  vocabulary work in Tier 1.
- It does not change checkpoint or run schemas; the review's M-07 columns (exclusions, filters,
  feature-space and taxonomy versions, params, input digest) are recorded in `PredictionSnapshot`
  explanations today and need a migration to become first-class.
- It does not enforce training eligibility in the database (review X-05); `build_examples` inherits
  the manifest's rules and strips the role field, but a raw-table join still bypasses them.
