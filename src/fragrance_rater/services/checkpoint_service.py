"""Freeze a reproducible calibration checkpoint (R8 PR 2; M-07, M-08, X-17).

A ``ModelCheckpoint`` used to store only the manifest and the caller's
free-form predictions, so the training set behind it could not be rebuilt or
compared (ML structure review M-07) and a prediction had no join key to it
(M-08). This service fills every reproduction column R8 PR 1 added:

* ``manifest`` and ``input_digest`` from one read of ``v_training_rows``
  (``ml.training_view``); the digest is SHA-256 over the exact view rows read,
  so the same rows always give the same digest and any change to one changes
  it;
* ``exclusions``: every version withheld as a holdout for the reviewer, in any
  program (the view's own holdout rule);
* ``filters``: the view and reader rules, verbatim (``training_view.FILTERS``);
* ``feature_space_version``, ``taxonomy_version`` (NULL: no versioned taxonomy
  exists yet, ADR-010), ``model_params`` (the registered model's parameters
  when ``algorithm_version`` names one, else NULL);
* ``feature_snapshot_id``: a content-addressed ``FeatureSnapshot`` of the
  feature vectors of every version in the manifest, shared by every
  checkpoint that froze identical content;
* one typed ``CheckpointPrediction`` per submitted prediction, each required
  to target a holdout of this enrollment's program on its target's own scale.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

from fragrance_rater.ml.feature_space import FEATURE_SPACE_VERSION
from fragrance_rater.ml.registry import MODELS
from fragrance_rater.ml.training_view import FILTERS, read_training
from fragrance_rater.models.calibration import (
    CHECKPOINT_TARGET_SCALES,
    CheckpointPrediction,
    Membership,
    ModelCheckpoint,
)
from fragrance_rater.models.feature_snapshot import FeatureSnapshot
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.services.vocabulary import NOTE_MAPPING_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.models.calibration import Enrollment

_SCALE_FOR_TARGET = dict(CHECKPOINT_TARGET_SCALES)
_SCALE_BOUNDS = {"0-10": (0.0, 10.0), "1-5": (1.0, 5.0)}
TAXONOMY_VERSION: str | None = None
"""No versioned family/accord taxonomy exists yet (ADR-010, ADR-017)."""


@dataclass(frozen=True)
class TypedPrediction:
    """One validated checkpoint prediction.

    Attributes:
        fragrance_id (str): A holdout version of the enrollment's program.
        target (str): One of ``CHECKPOINT_TARGETS``.
        scale (str): The target's own scale.
        value (float): On that scale.
        uncertainty (float | None): Non-negative, when given.
    """

    fragrance_id: str
    target: str
    scale: str
    value: float
    uncertainty: float | None


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def _number(raw: dict[str, str | float | None], key: str) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = f"prediction {key} must be a number"
        raise _unprocessable(msg)
    if not math.isfinite(value):
        msg = f"prediction {key} must be finite"
        raise _unprocessable(msg)
    return float(value)


def typed_predictions(
    raw_predictions: Sequence[dict[str, str | float | None]], holdouts: set[str]
) -> list[TypedPrediction]:
    """Validate the caller's predictions into typed rows (M-08).

    Args:
        raw_predictions (Sequence[dict[str, str | float | None]]): As posted;
            each needs ``fragrance_id``, ``target``, ``value``, and may carry
            ``scale`` (must match the target's) and ``uncertainty``.
        holdouts (set[str]): The enrollment program's holdout versions.

    Returns:
        list[TypedPrediction]: One per posted prediction.

    Raises:
        HTTPException: 422 naming the first prediction that is malformed,
            off-scale, duplicated, or not a holdout of this enrollment.
    """
    typed: list[TypedPrediction] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_predictions:
        fragrance_id = raw.get("fragrance_id")
        target = raw.get("target")
        if not isinstance(fragrance_id, str) or not isinstance(target, str):
            msg = "each prediction needs a fragrance_id and a target"
            raise HTTPException(status_code=422, detail=msg)
        scale = _SCALE_FOR_TARGET.get(target)
        if scale is None:
            msg = f"unknown prediction target {target!r}"
            raise HTTPException(status_code=422, detail=msg)
        if raw.get("scale") not in (None, scale):
            msg = f"target {target!r} is predicted on its own {scale} scale"
            raise HTTPException(status_code=422, detail=msg)
        if fragrance_id not in holdouts:
            msg = "predictions must target this enrollment's holdout versions"
            raise HTTPException(status_code=422, detail=msg)
        value = _number(raw, "value")
        low, high = _SCALE_BOUNDS[scale]
        if value is None or not low <= value <= high:
            msg = f"prediction value must lie on the {scale} scale"
            raise HTTPException(status_code=422, detail=msg)
        uncertainty = _number(raw, "uncertainty")
        if uncertainty is not None and uncertainty < 0:
            msg = "prediction uncertainty must not be negative"
            raise HTTPException(status_code=422, detail=msg)
        if (fragrance_id, target) in seen:
            msg = "one prediction per holdout version and target"
            raise HTTPException(status_code=422, detail=msg)
        seen.add((fragrance_id, target))
        typed.append(TypedPrediction(fragrance_id, target, scale, value, uncertainty))
    return typed


def feature_content_hash(
    features: dict[str, object],
    *,
    feature_space_version: str,
    taxonomy_version: str | None,
    alias_version: str | None,
    parser_version: str | None,
) -> str:
    """Return the SHA-256 that content-addresses a feature snapshot.

    Args:
        features (dict[str, object]): Vectors keyed by fragrance version id.
        feature_space_version (str): ``FEATURE_SPACE_VERSION``.
        taxonomy_version (str | None): Taxonomy version, if any.
        alias_version (str | None): Note alias layer version, if any.
        parser_version (str | None): Source parser version, if any.

    Returns:
        str: Lowercase hex digest over the canonical JSON of all five.
    """
    canonical = json.dumps(
        {
            "features": features,
            "feature_space_version": feature_space_version,
            "taxonomy_version": taxonomy_version,
            "alias_version": alias_version,
            "parser_version": parser_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CheckpointService:
    """Create checkpoints with every R8 reproduction column filled."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _holdouts(self, program_id: str) -> set[str]:
        return set(
            await self.db.scalars(
                select(Membership.fragrance_id).where(
                    Membership.program_id == program_id,
                    Membership.role == "HOLDOUT",
                )
            )
        )

    async def feature_snapshot(
        self, manifest: Sequence[dict[str, object]], recorded_by: str | None
    ) -> FeatureSnapshot:
        """Return the snapshot of the manifest's feature vectors, reusing a twin.

        Args:
            manifest (Sequence[dict[str, object]]): Rows with ``source_features``.
            recorded_by (str | None): Who froze it.

        Returns:
            FeatureSnapshot: A new row, or the existing row with the same hash.
        """
        features: dict[str, object] = {
            str(row["fragrance_id"]): row["source_features"]
            for row in manifest
            if "source_features" in row
        }
        content_hash = feature_content_hash(
            features,
            feature_space_version=FEATURE_SPACE_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            alias_version=NOTE_MAPPING_VERSION,
            parser_version=None,
        )
        existing = await self.db.scalar(
            select(FeatureSnapshot).where(FeatureSnapshot.content_hash == content_hash)
        )
        if existing is not None:
            return existing
        snapshot = FeatureSnapshot(
            feature_space_version=FEATURE_SPACE_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            alias_version=NOTE_MAPPING_VERSION,
            parser_version=None,
            content_hash=content_hash,
            features=features,
            recorded_by=recorded_by,
        )
        # #ASSUME: concurrency: two checkpoints freezing identical content at
        # the same instant would both miss the lookup above; the unique
        # content_hash then fails the second transaction (a 500 the manager
        # retries, and the retry reuses the winner). Checkpoints are rare,
        # manager-only writes, so no savepoint dance is attempted.
        # #VERIFY: tests/unit/test_services/test_checkpoint_service.py reuses
        # an existing snapshot instead of inserting a twin.
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def create(
        self,
        enrollment: Enrollment,
        algorithm_version: str,
        predictions: Sequence[dict[str, str | float | None]],
        recorded_by: str,
    ) -> ModelCheckpoint:
        """Freeze one checkpoint for an enrollment.

        The caller has already authorized the manager, locked the enrollment,
        and refused a checkpoint once a holdout has been observed.

        Args:
            enrollment (Enrollment): The locked enrollment.
            algorithm_version (str): The model the predictions came from.
            predictions (Sequence[dict[str, str | float | None]]): As posted.
            recorded_by (str): The manager.

        Returns:
            ModelCheckpoint: The flushed checkpoint.
        """
        typed = typed_predictions(
            predictions, await self._holdouts(enrollment.program_id)
        )
        read = await read_training(self.db, enrollment.reviewer_id)
        exclusions = sorted(
            await PreferenceHistoryService(self.db).excluded_versions(
                enrollment.reviewer_id
            )
        )
        snapshot = await self.feature_snapshot(read.manifest, recorded_by)
        model = MODELS.get(algorithm_version)
        checkpoint = ModelCheckpoint(
            enrollment_id=enrollment.id,
            algorithm_version=algorithm_version,
            manifest=read.manifest,
            predictions=list(predictions),
            exclusions=exclusions,
            filters=dict(FILTERS),
            feature_space_version=FEATURE_SPACE_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            model_params=None if model is None else dict(model.spec.params),
            input_digest=read.input_digest,
            feature_snapshot_id=snapshot.id,
        )
        self.db.add(checkpoint)
        await self.db.flush()
        for prediction in typed:
            self.db.add(
                CheckpointPrediction(
                    checkpoint_id=checkpoint.id,
                    fragrance_id=prediction.fragrance_id,
                    target=prediction.target,
                    scale=prediction.scale,
                    value=prediction.value,
                    uncertainty=prediction.uncertainty,
                )
            )
        await self.db.flush()
        return checkpoint
