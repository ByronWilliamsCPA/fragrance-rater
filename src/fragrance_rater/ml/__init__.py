"""Machine-learning core: feature space, model objects, datasets, evaluation.

This package holds the parts of the recommendation and prospective-evaluation
pipeline that must be importable without FastAPI, without an event loop, and
(where possible) without a database session, so that a model can be trained,
frozen, scored, and compared in a notebook or a batch job using exactly the
same definitions the API uses.

Layout:

- ``feature_space``: the single definition of a fragrance version's feature
  vector (``FeatureVector``) and how it is produced from an ORM row or
  reconstructed from a frozen manifest.
- ``model``: ``ModelSpec`` (identity, version, serialized parameters and their
  digest), the ``Scorer`` protocol, and ``AffinityV1``, the deterministic
  weighted-affinity heuristic from ADR-004/ADR-007 extracted as a pure,
  synchronous model object.
- ``registry``: named lookup of registered scorers.
- ``dataset``: uniform training rows and array export built on the frozen
  training manifest.
- ``reliability`` and ``evaluate``: hidden-repeat agreement (the noise
  ceiling) and predicted-versus-observed holdout metrics.
- ``predict``: run a registered model over an eligible set and freeze
  ``PredictionSnapshot`` rows with a server-built manifest (ADR-009).

Nothing here changes the affinity-v1 ranking; the scorer is a
behavior-preserving extraction whose parameters are now serialized and
digested so that a change to any tunable is a recorded version change.

Exception hierarchy exemption: this package raises plain built-in exceptions
(``ValueError``, ``KeyError``) rather than ``fragrance_rater.core.exceptions``
types (``ValidationError``, ``BusinessLogicError``, and similar). That is
deliberate, not an oversight: the "importable without FastAPI, without an
event loop" goal above means this package must not depend on the API-facing
exception hierarchy's error-response shaping (``to_dict()``, ``error_code``),
which exists for HTTP handlers, not notebook/batch callers. API-layer callers
(``cli.py``, and any future route) are responsible for catching these plain
exceptions at their boundary and translating them into the centralized
hierarchy if an HTTP response needs one.
"""

from __future__ import annotations
