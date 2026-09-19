"""Run a registered model over an eligible set and freeze its predictions.

This is ADR-009's prospective-evaluation principle expressed as code. Until
now no code path in this system produced a prediction: ``ModelCheckpoint.
predictions`` and every ``PredictionSnapshot`` field were caller-supplied
JSON typed by a manager into a request body, so neither affinity-v1 nor
affinity-v2 (the model the product actually ships; see
``ml.registry.DEFAULT_MODEL_KEY``) had a prospective record of its own to be
judged on, and a snapshot's ``input_manifest`` was accepted verbatim and
could contain the very holdout evidence the prediction was meant to be
blind to (ML structure review, M-09 and X-18).

``predict_and_freeze`` closes both. It builds the evidence exactly once --
one exclusion set, one training manifest, one profile, one input digest,
the single ``ScoringContext`` the review asks for (M-05) -- checks that
manifest for leakage, and writes one ``PredictionSnapshot`` per eligible
fragrance with the server-built manifest, the model's serialized parameter
digest, and the digest of the inputs it scored from.

What the frozen number is *not*: a calibrated liking prediction. affinity-v1
returns a bounded, uncalibrated affinity in ``[0, 1]`` (ADR-007), and this
module maps it onto the declared outcome scale with a fixed, monotone
rescaling. The rescaling preserves ranking and nothing else; there is no
inverse map and no claim that a predicted ``7.4`` means the evaluator will
report a liking of 7.4. It exists so the heuristic has a prospective record
that paired error and rank correlation can be computed against.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.ml.feature_space import vectorize
from fragrance_rater.ml.registry import resolve
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
)
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.schemas.prediction import PredictionCreate
from fragrance_rater.services.prediction_service import PredictionService
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.services.recommendation_service import RecommendationService

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.ml.model import ModelSpec

SKIP_MISSING = "fragrance-missing-or-deleted"
"""The catalog row is absent or soft-deleted, so it cannot be scored."""

SKIP_HOLDOUT_OBSERVED = "holdout-observation-exists"
"""A pre-reveal response for this holdout exists; prediction is retrospective."""

SKIP_EXISTING = "existing-prediction"
"""An outcome-free snapshot from this model/version already exists."""

EXPLANATION_NOTE = (
    "Monotone rescaling of an uncalibrated affinity onto the declared "
    "scale, not a calibrated liking prediction (ADR-007): ranking is "
    "preserved, the numeric value is not an expected rating and has no "
    "inverse map. Frozen so the heuristic has a prospective record to be "
    "judged against (ADR-009)."
)
"""Carried on every snapshot so a reader cannot mistake the number's meaning."""


def _rescale_0_10(score: float) -> float:
    return round(score * 10, 3)


def _rescale_1_5(score: float) -> float:
    return round(1 + score * 4, 3)


# Declared outcome scale -> the monotone map from a bounded [0, 1] affinity
# onto it. "0-10" matches Observation.liking, "1-5" matches Evaluation.rating;
# PredictionService only accepts an outcome link whose workflow scale equals
# the snapshot's own predicted_scale, so an unknown scale is rejected here
# rather than frozen into a snapshot no outcome could ever be linked to.
_SCALES = {"0-10": _rescale_0_10, "1-5": _rescale_1_5}


@dataclass(frozen=True)
class PredictionRunResult:
    """What one ``predict_and_freeze`` run produced, for audit and display.

    Attributes:
        model_key (str): Registry key the run resolved.
        algorithm_version (str): The resolved model's ``algorithm_version``.
        param_digest (str): Digest of the model's serialized parameters, so
            a later reader can tell whether a tunable changed.
        feature_space_version (str): Feature space the scores were computed in.
        reviewer_id (str): The evaluator predicted for.
        created (list[str]): Ids of the ``PredictionSnapshot`` rows written.
        skipped (list[tuple[str, str]]): ``(fragrance_id, reason)`` pairs;
            reasons are the ``SKIP_*`` constants in this module.
        n_evidence (int): Distinct fragrance versions contributing to the
            profile the scores came from.
        input_digest (str): SHA-256 over the canonical JSON of the frozen
            training manifest; identifies the exact inputs scored from.
    """

    model_key: str
    algorithm_version: str
    param_digest: str
    feature_space_version: str
    reviewer_id: str
    created: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    n_evidence: int = 0
    input_digest: str = ""


def _manifest_digest(manifest: Sequence[dict[str, object]]) -> str:
    """Return a SHA-256 digest over the manifest's canonical JSON.

    Args:
        manifest (Sequence[dict[str, object]]): The frozen training manifest.

    Returns:
        str: Hex digest; stable across processes because keys are sorted and
            non-JSON values are stringified deterministically.
    """
    canonical = json.dumps(list(manifest), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def leakage_check(
    excluded: set[str], manifest: Sequence[dict[str, object]]
) -> list[str]:
    """Return manifest row ids whose fragrance is an assigned holdout.

    Cheap insurance for ML structure review X-18: the manifest this module
    freezes is server-built and ``PreferenceHistoryService`` already filters
    holdouts, so a non-empty result means the exclusion rule regressed or a
    caller substituted a manifest. Either way the run must not proceed.

    # #CRITICAL: data integrity: ``excluded`` must be the exact set the
    # manifest was built from, not a fresh re-query. A separate query run in
    # the same transaction should return identical rows, but re-deriving it
    # here would check the manifest against a set that only coincidentally
    # matches the one it was actually built from, and would reopen a narrow
    # TOCTOU window if exclusion state changes mid-transaction.
    # #VERIFY: callers must pass the same ``excluded`` set used to build
    # ``manifest`` (see ``predict_and_freeze``); do not reintroduce an
    # internal re-query of ``excluded_versions``.

    Args:
        excluded (set[str]): The exclusion set the manifest was built from.
        manifest (Sequence[dict[str, object]]): Rows to audit.

    Returns:
        list[str]: Ids of offending rows, in manifest order; empty when clean.
    """
    return [
        str(row.get("id"))
        for row in manifest
        if str(row.get("fragrance_id")) in excluded
    ]


async def _holdout_observed(
    session: AsyncSession, reviewer_id: str, targets: Sequence[str]
) -> set[str]:
    """Return target ids that are holdouts with an existing pre-reveal response.

    Mirrors the checkpoint-closure rule in ``api/calibration.py``: once the
    evaluator has responded to a holdout, a prediction for it is no longer
    prospective and freezing one would be a retrospective fit.

    # #CRITICAL: timing dependency: this check and the snapshot write it
    # gates happen in separate statements within the same caller
    # transaction. A PRE_REVEAL observation recorded between this query and
    # ``predict_and_freeze``'s snapshot write would not be caught, so a
    # prediction could still be frozen against a holdout that was observed
    # moments earlier.
    # #VERIFY: no code path currently lets a reviewer submit an observation
    # concurrently with an in-flight prediction run; if one is added
    # (e.g. a background job or a second API worker), re-check this
    # assumption or move the check inside the same statement as the write.

    Args:
        session (AsyncSession): Database session.
        reviewer_id (str): The evaluator whose enrollments are searched.
        targets (Sequence[str]): Candidate fragrance ids.

    Returns:
        set[str]: Fragrance ids to skip.
    """
    return set(
        await session.scalars(
            select(Membership.fragrance_id)
            .join(Presentation, Presentation.membership_id == Membership.id)
            .join(CalibrationSession, CalibrationSession.id == Presentation.session_id)
            .join(Enrollment, Enrollment.id == CalibrationSession.enrollment_id)
            .join(Observation, Observation.presentation_id == Presentation.id)
            .where(
                Enrollment.reviewer_id == reviewer_id,
                Membership.role == "HOLDOUT",
                Observation.phase == "PRE_REVEAL",
                Membership.fragrance_id.in_(targets),
            )
        )
    )


async def _already_predicted(
    session: AsyncSession, reviewer_id: str, spec: ModelSpec, targets: Sequence[str]
) -> set[str]:
    """Return target ids this model/version already has an open prediction for.

    Idempotency: re-running the same model for the same evaluator must not
    accumulate duplicate outcome-free snapshots that would each demand their
    own outcome link. A snapshot whose outcome is already linked does not
    block a fresh prospective prediction.

    # #CRITICAL: concurrency: this is a check-then-act race. Two concurrent
    # ``predict_and_freeze`` runs for the same reviewer/model/version could
    # both read an empty result here and then both call ``service.create()``
    # for the same fragrance, producing duplicate outcome-free snapshots --
    # exactly what this function's docstring says must not happen.
    # ``PredictionSnapshot`` has no unique constraint on
    # (reviewer_id, fragrance_id, model_id, model_version,
    # outcome_linked_at IS NULL) to back this at the database layer.
    # #VERIFY: single-writer usage (CLI/one API worker at a time) makes this
    # safe today; before this runs under concurrent callers, add a unique
    # partial index or a transaction-level lock rather than relying on this
    # read-then-write check alone.

    Args:
        session (AsyncSession): Database session.
        reviewer_id (str): The evaluator predicted for.
        spec (ModelSpec): Identity of the model being run.
        targets (Sequence[str]): Candidate fragrance ids.

    Returns:
        set[str]: Fragrance ids to skip.
    """
    return set(
        await session.scalars(
            select(PredictionSnapshot.fragrance_id).where(
                PredictionSnapshot.reviewer_id == reviewer_id,
                PredictionSnapshot.model_id == spec.model_id,
                PredictionSnapshot.model_version == spec.version,
                PredictionSnapshot.fragrance_id.in_(targets),
                PredictionSnapshot.outcome_linked_at.is_(None),
            )
        )
    )


async def _load_fragrances(
    session: AsyncSession, targets: Sequence[str]
) -> dict[str, Fragrance]:
    """Load live catalog rows with notes and accords in one batched query.

    Mirrors ``preference_history.py``'s ``WHERE id IN (...)`` load so the
    scoring loop issues no further queries (``vectorize`` never queries).

    Args:
        session (AsyncSession): Database session.
        targets (Sequence[str]): Candidate fragrance ids.

    Returns:
        dict[str, Fragrance]: Live rows keyed by id; soft-deleted and absent
            ids are simply missing.
    """
    return {
        fragrance.id: fragrance
        for fragrance in await session.scalars(
            select(Fragrance)
            .where(Fragrance.id.in_(targets), Fragrance.deleted_at.is_(None))
            .options(
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.accords),
            )
        )
    }


def _ordered_unique(values: Iterable[str]) -> list[str]:
    """Return ``values`` with duplicates removed, first occurrence kept."""
    return list(dict.fromkeys(values))


async def predict_and_freeze(
    session: AsyncSession,
    *,
    model_key: str,
    reviewer_id: str,
    fragrance_ids: list[str] | None = None,
    checkpoint_id: str | None = None,
    recorded_by: str | None,
    predicted_scale: str = "0-10",
) -> PredictionRunResult:
    """Score an eligible set with a registered model and freeze the results.

    The evidence is built once and reused for every target: one exclusion
    set, one server-built training manifest, one profile, one input digest.
    Nothing is recomputed per fragrance, so the record and the result cannot
    desynchronize (ML structure review, M-05).

    The frozen ``predicted_rating`` is a monotone rescaling of the model's
    bounded, uncalibrated affinity onto ``predicted_scale`` -- it preserves
    ranking and asserts nothing about the magnitude an evaluator would
    report (ADR-007). The same caveat is written into every snapshot's
    ``explanation`` so it travels with the data.

    Targets default to every fragrance ever assigned HOLDOUT for this
    evaluator (``PreferenceHistoryService.excluded_versions``, deliberately
    conservative across all workflows and enrollments, not scoped to the
    currently-open one), because holdouts are what prospective prediction
    exists for. An explicit ``fragrance_ids`` list is used as given -- any
    fragrance may be predicted, not only a holdout. A default-target
    holdout from a closed-out program is not distinguished from one in the
    current program; it either gets skipped via
    ``holdout-observation-exists`` if it was actually observed pre-reveal,
    or a prediction is frozen for it like any other holdout.

    A target is skipped, rather than failing the run, when:

    - ``fragrance-missing-or-deleted``: no live catalog row.
    - ``holdout-observation-exists``: it is a holdout for this evaluator and
      a ``PRE_REVEAL`` observation already exists, so a prediction would no
      longer be prospective.
    - ``existing-prediction``: this model and version already hold an
      outcome-free snapshot for the pair.

    This function does not commit; the caller owns the unit of work.

    Args:
        session (AsyncSession): Database session.
        model_key (str): Registry key, e.g. ``"affinity-v1"``.
        reviewer_id (str): The evaluator to predict for.
        fragrance_ids (list[str] | None): Explicit targets, or ``None`` for
            the evaluator's assigned holdouts.
        checkpoint_id (str | None): Calibration checkpoint to attach to.
        recorded_by (str | None): Actor recorded on each snapshot.
        predicted_scale (str): Declared outcome scale, ``"0-10"`` or ``"1-5"``.

    Returns:
        PredictionRunResult: Model identity, created ids, skips with reasons,
            evidence count, and the input digest.

    Raises:
        ValueError: If ``predicted_scale`` is not a supported scale, or if
            the server-built manifest contains holdout evidence.
    """
    rescale = _SCALES.get(predicted_scale)
    if rescale is None:
        message = (
            f"unsupported predicted_scale {predicted_scale!r}; "
            f"supported: {', '.join(sorted(_SCALES))}"
        )
        raise ValueError(message)

    scorer = resolve(model_key)
    spec = scorer.spec

    history = PreferenceHistoryService(session)
    excluded = await history.excluded_versions(reviewer_id)
    manifest = await history.training_manifest(reviewer_id, excluded=excluded)
    # #CRITICAL: data integrity: the manifest is server-built from `excluded`
    # immediately above, so this should never fire in normal operation. It
    # exists as insurance against the exclusion rule regressing or a future
    # caller substituting a manifest (ML structure review X-18); a non-empty
    # result means that guarantee already broke somewhere upstream.
    # #VERIFY: this raises ValueError rather than a SQLAlchemyError, so it
    # bypasses a narrowly-scoped rollback in the caller's session context
    # manager; see core/database.py's get_session for why that except clause
    # is not narrowed to SQLAlchemyError.
    leaked = leakage_check(excluded, manifest)
    if leaked:
        message = (
            f"training manifest for reviewer {reviewer_id!r} contains holdout "
            f"evidence in rows {leaked}; refusing to freeze a prediction"
        )
        raise ValueError(message)
    profile = await RecommendationService(
        session, model=scorer
    ).build_preference_profile(reviewer_id, excluded=excluded)
    input_digest = _manifest_digest(manifest)

    result = PredictionRunResult(
        model_key=model_key,
        algorithm_version=spec.algorithm_version,
        param_digest=spec.digest,
        feature_space_version=spec.feature_space_version,
        reviewer_id=reviewer_id,
        n_evidence=profile.evaluation_count,
        input_digest=input_digest,
    )

    targets = (
        sorted(excluded) if fragrance_ids is None else _ordered_unique(fragrance_ids)
    )
    if not targets:
        return result

    live = await _load_fragrances(session, targets)
    observed = await _holdout_observed(session, reviewer_id, targets)
    predicted = await _already_predicted(session, reviewer_id, spec, targets)

    service = PredictionService(session)
    for fragrance_id in targets:
        fragrance = live.get(fragrance_id)
        if fragrance is None:
            result.skipped.append((fragrance_id, SKIP_MISSING))
            continue
        if fragrance_id in observed:
            result.skipped.append((fragrance_id, SKIP_HOLDOUT_OBSERVED))
            continue
        if fragrance_id in predicted:
            result.skipped.append((fragrance_id, SKIP_EXISTING))
            continue
        scored = scorer.score(profile, vectorize(fragrance))
        snapshot = await service.create(
            PredictionCreate(
                reviewer_id=reviewer_id,
                fragrance_id=fragrance_id,
                checkpoint_id=checkpoint_id,
                model_id=spec.model_id,
                model_version=spec.version,
                feature_snapshot_version=spec.feature_space_version,
                predicted_scale=predicted_scale,
                predicted_rating=rescale(scored.score),
                uncertainty=scored.uncertainty,
                input_manifest=manifest,
                explanation={
                    "score": scored.score,
                    "score_type": "uncalibrated-affinity",
                    "components": dict(scored.components),
                    "vetoed": scored.vetoed,
                    "veto_note": scored.veto_note,
                    "n_evidence": scored.n_evidence,
                    "param_digest": spec.digest,
                    "input_digest": input_digest,
                    "note": EXPLANATION_NOTE,
                },
            ),
            recorded_by=recorded_by,
        )
        result.created.append(snapshot.id)
    return result


__all__ = [
    "EXPLANATION_NOTE",
    "SKIP_EXISTING",
    "SKIP_HOLDOUT_OBSERVED",
    "SKIP_MISSING",
    "PredictionRunResult",
    "leakage_check",
    "predict_and_freeze",
]
