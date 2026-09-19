"""Named lookup of registered scorers, keyed by ``algorithm_version``.

Before this module existed, a model was named by free caller text: the
measurement service carried one hard-coded ``algorithm_version`` string, the
checkpoint route accepted whatever version a manager typed, and the
candidate-strategy schema was a one-value ``Literal`` (ML structure review,
M-04/M-11). None of those names was validated against code that could
actually score.

The registry makes the name resolvable. A key is exactly a model's
``ModelSpec.algorithm_version`` (``"<model_id>-<version>"``), so a key
uniquely identifies both the family and the version, and a caller that
resolves a key gets an object that can score under that name. Reports group
by ``(model_id, version)`` read off the resolved spec rather than by a
string a caller supplied.

Registration is deliberately explicit and duplicate-hostile: silently
replacing ``"affinity-v1"`` with a differently-parameterized object would
reintroduce exactly the drift ``ModelSpec.digest`` exists to detect.
"""

from __future__ import annotations

from fragrance_rater.ml.model import AffinityV1, Scorer

DEFAULT_MODEL_KEY = "affinity-v1"
"""Key of the baseline every candidate model is compared against (ADR-009)."""

MODELS: dict[str, Scorer] = {AffinityV1.spec.algorithm_version: AffinityV1()}
"""Registered scorers keyed by ``ModelSpec.algorithm_version``."""


def register(scorer: Scorer) -> None:
    """Register a scorer under its own ``algorithm_version``.

    Args:
        scorer (Scorer): The model object to register. Its key is taken from
            ``scorer.spec.algorithm_version``; callers do not choose it.

    Raises:
        ValueError: If a scorer is already registered under that key. A
            model whose parameters changed must bump ``ModelSpec.version``
            rather than overwrite the registered baseline.
    """
    key = scorer.spec.algorithm_version
    if key in MODELS:
        message = (
            f"model {key!r} is already registered; bump ModelSpec.version "
            "instead of replacing a registered model"
        )
        raise ValueError(message)
    MODELS[key] = scorer


def resolve(key: str) -> Scorer:
    """Return the scorer registered under ``key``.

    Args:
        key (str): An ``algorithm_version`` such as ``"affinity-v1"``.

    Returns:
        Scorer: The registered model object.

    Raises:
        KeyError: If nothing is registered under ``key``. The message names
            every known key so a caller (or a CLI user) can correct it
            without reading this module.
    """
    try:
        return MODELS[key]
    except KeyError:
        message = f"unknown model {key!r}; known models: {', '.join(available())}"
        raise KeyError(message) from None


def available() -> list[str]:
    """Return every registered model key, sorted.

    Returns:
        list[str]: Registered ``algorithm_version`` keys in sorted order, so
            CLI output and report groupings are stable across processes.
    """
    return sorted(MODELS)


__all__ = ["DEFAULT_MODEL_KEY", "MODELS", "available", "register", "resolve"]
