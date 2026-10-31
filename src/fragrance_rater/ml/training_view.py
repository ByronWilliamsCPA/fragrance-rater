"""Training input read from ``v_training_rows`` only (R8; review X-05, X-06).

Before R8 every trainer and manifest built its rows by joining the evidence
tables to the blind mapping (presentation, membership, session, enrollment),
so each reader re-implemented the eligibility rules and could see the
membership ``role`` a trainer must never learn. This module is the one reader
the training side uses instead:

* it selects from ``v_training_rows``, which already applies the per-row
  ``training_eligibility`` gate (only ``eligible``), the holdout, hidden-repeat,
  pre-reveal, stage-lock, worn-by, soft-delete, ADR-014 fragrance, and
  latest-observation rules;
* it then reads only the evidence row itself, by the view's ``row_id``, for the
  fields the view does not carry (an observation's typed features and free
  text, an evaluation's notes and receipt time), never the mapping tables;
* it applies the one rule the view leaves to its reader, the ordinary
  workflow's "latest encounter per version", among eligible rows only.

For a reviewer whose rows are all ``eligible`` the manifest equals what
``PreferenceHistoryService.training_manifest`` returns, minus the two keys the
view deliberately withholds (``role`` and ``program_id``, X-06) and plus
``revealed``. An ineligible row never reaches it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

from sqlalchemy import Boolean, DateTime, Integer, String, column, select, table
from sqlalchemy.orm import selectinload

from fragrance_rater.ml.feature_space import vectorize
from fragrance_rater.models.calibration import Observation
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.models.soft_delete import live

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.services.preference_history import (
        ObservationFeatures,
        ObservationNotesText,
    )

V_TRAINING_ROWS = table(
    "v_training_rows",
    column("row_id", String()),
    column("workflow", String()),
    column("reviewer_id", String()),
    column("fragrance_id", String()),
    column("stage", String()),
    column("scale", String()),
    column("rating", Integer()),
    column("observed_at", DateTime()),
    column("revealed", Boolean()),
)
"""The view as a lightweight Core table. Deliberately not on ``Base.metadata``:
the view is created by migrations, never by ``create_all``."""

SOURCE = "v_training_rows"
"""The ``filters["source"]`` a checkpoint records for rows read here."""

FILTERS: dict[str, object] = {
    "source": SOURCE,
    "training_eligibility": "eligible",
    "controlled_phase": "PRE_REVEAL",
    "controlled_selection": "latest locked pre-reveal answer per sample and stage",
    "controlled_rating": "liking present; status completed or unrecorded",
    "ordinary_selection": "latest eligible encounter per version, own wear only",
    "excluded_roles": ["HOLDOUT", "HIDDEN_REPEAT"],
}
"""What the view and this reader filter, recorded verbatim on a checkpoint."""


@dataclass(frozen=True)
class TrainingViewRow:
    """One row of ``v_training_rows``, exactly as read.

    Attributes:
        row_id (str): The ``Evaluation`` or ``Observation`` id.
        workflow (str): ``ORDINARY`` or ``CONTROLLED``.
        reviewer_id (str): Whose palate the label reflects.
        fragrance_id (str): The canonical version.
        stage (str | None): ``BLOTTER``/``SKIN`` for controlled rows.
        scale (str): ``1-5`` or ``0-10``; never converted.
        rating (int): The label on that scale.
        observed_at (datetime): When the encounter happened (naive UTC).
        revealed (bool): Whether identities were revealed to the evaluator
            (always true for an ordinary encounter).
    """

    row_id: str
    workflow: str
    reviewer_id: str
    fragrance_id: str
    stage: str | None
    scale: str
    rating: int
    observed_at: datetime
    revealed: bool

    def canonical(self) -> dict[str, object]:
        """Return a JSON-safe dict of every column, for hashing.

        Returns:
            dict[str, object]: Column name to value; ``observed_at`` as ISO-8601.
        """
        return {
            "row_id": self.row_id,
            "workflow": self.workflow,
            "reviewer_id": self.reviewer_id,
            "fragrance_id": self.fragrance_id,
            "stage": self.stage,
            "scale": self.scale,
            "rating": self.rating,
            "observed_at": self.observed_at.isoformat(),
            "revealed": self.revealed,
        }


@dataclass(frozen=True)
class TrainingRead:
    """Everything one read of the view produced.

    Attributes:
        rows (list[TrainingViewRow]): Every view row read for the reviewer,
            ordered by ``(workflow, row_id)``.
        manifest (list[dict[str, object]]): The manifest built from them.
        input_digest (str): ``rows_digest(rows)``.
    """

    rows: list[TrainingViewRow]
    manifest: list[dict[str, object]]
    input_digest: str


def _as_datetime(value: object) -> datetime:
    # SQLite returns a view's expression column as text; PostgreSQL as datetime.
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


async def read_rows(session: AsyncSession, reviewer_id: str) -> list[TrainingViewRow]:
    """Read every trainable row for one reviewer from ``v_training_rows``.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str): The evaluator.

    Returns:
        list[TrainingViewRow]: Rows ordered by ``(workflow, row_id)``.
    """
    result = await session.execute(
        select(V_TRAINING_ROWS)
        .where(V_TRAINING_ROWS.c.reviewer_id == reviewer_id)
        .order_by(V_TRAINING_ROWS.c.workflow, V_TRAINING_ROWS.c.row_id)
    )
    rows: list[TrainingViewRow] = []
    for raw in result:
        values = cast(
            "tuple[str, str, str, str, str | None, str, int, object, object]",
            tuple(raw),
        )
        (row_id, workflow, reviewer, fragrance_id, stage, scale, rating, at, seen) = (
            values
        )
        rows.append(
            TrainingViewRow(
                row_id=row_id,
                workflow=workflow,
                reviewer_id=reviewer,
                fragrance_id=fragrance_id,
                stage=stage,
                scale=scale,
                rating=rating,
                observed_at=_as_datetime(at),
                # SQLite has no boolean type and returns 0/1.
                revealed=bool(seen),
            )
        )
    return rows


def rows_digest(rows: Sequence[TrainingViewRow]) -> str:
    """Return a SHA-256 digest over the exact view rows read.

    Deterministic: rows are sorted by ``(workflow, row_id)`` and each is the
    canonical dict of its view columns, serialized with sorted keys and no
    whitespace. Any change to a column the view exposes (a rating, a time, a
    fragrance, eligibility admitting or removing a row) changes the digest.
    SHA-256 is FIPS 140-approved.

    Args:
        rows (Sequence[TrainingViewRow]): Rows as read from the view.

    Returns:
        str: Lowercase hex digest.
    """
    ordered = sorted(rows, key=lambda row: (row.workflow, row.row_id))
    canonical = json.dumps(
        [row.canonical() for row in ordered], sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _ordinary_manifest(
    session: AsyncSession, rows: list[TrainingViewRow]
) -> list[dict[str, object]]:
    """Latest eligible encounter per version, newest first."""
    if not rows:
        return []
    evaluations = list(
        await session.scalars(
            select(Evaluation).where(Evaluation.id.in_([row.row_id for row in rows]))
        )
    )
    evaluations.sort(key=lambda e: (e.evaluated_at, e.created_at, e.id), reverse=True)
    manifest: list[dict[str, object]] = []
    seen: set[str] = set()
    for evaluation in evaluations:
        if evaluation.fragrance_id in seen:
            continue
        seen.add(evaluation.fragrance_id)
        manifest.append(
            {
                "id": evaluation.id,
                "fragrance_id": evaluation.fragrance_id,
                "workflow": "ORDINARY",
                "scale": "1-5",
                "rating": evaluation.rating,
                "observed_at": evaluation.evaluated_at.isoformat(),
                "notes": evaluation.notes,
                "revealed": True,
            }
        )
    return manifest


async def _controlled_manifest(
    session: AsyncSession, rows: list[TrainingViewRow]
) -> list[dict[str, object]]:
    """Every controlled row the view admitted, newest receipt first."""
    if not rows:
        return []
    by_id = {row.row_id: row for row in rows}
    observations = list(
        await session.scalars(
            select(Observation)
            .where(Observation.id.in_(list(by_id)))
            .order_by(Observation.created_at.desc(), Observation.id.desc())
        )
    )
    manifest: list[dict[str, object]] = []
    for observation in observations:
        row = by_id[observation.id]
        features: ObservationFeatures = {
            "detected": observation.detected,
            "intensity": observation.intensity,
            "elapsed_minutes": observation.elapsed_minutes,
            "confidence": observation.confidence,
            "sweetness": observation.sweetness,
            "freshness": observation.freshness,
            "density": observation.density,
            "familiarity": observation.familiarity,
            "dryness": observation.dryness,
            "clean_soapy": observation.clean_soapy,
            "earthy_rooty": observation.earthy_rooty,
            "bodily_animalic": observation.bodily_animalic,
            "discomfort": observation.discomfort,
            "opening_liking": observation.opening_liking,
            "drydown_liking": observation.drydown_liking,
            "would_wear": observation.would_wear,
            "would_buy": observation.would_buy,
            "artistic_appreciation": observation.artistic_appreciation,
            "projection": observation.projection,
            "longevity_minutes": observation.longevity_minutes,
            "perceived_notes": observation.perceived_notes,
        }
        notes_text: ObservationNotesText = {
            "likes": observation.likes,
            "dislikes": observation.dislikes,
            "reminds_me_of": observation.reminds_me_of,
            "comments": observation.comments,
        }
        manifest.append(
            {
                "id": observation.id,
                "fragrance_id": row.fragrance_id,
                "workflow": "CONTROLLED",
                "stage": observation.stage,
                "phase": observation.phase,
                "scale": "0-10",
                "rating": row.rating,
                "features": features,
                "notes_text": notes_text,
                "observed_at": observation.created_at.isoformat(),
                "revealed": row.revealed,
            }
        )
    return manifest


async def read_training(session: AsyncSession, reviewer_id: str) -> TrainingRead:
    """Read the view once and build the manifest, rows, and input digest.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str): The evaluator.

    Returns:
        TrainingRead: The rows read, the manifest, and the digest of the rows.
    """
    rows = await read_rows(session, reviewer_id)
    manifest = await _ordinary_manifest(
        session, [row for row in rows if row.workflow == "ORDINARY"]
    )
    manifest += await _controlled_manifest(
        session, [row for row in rows if row.workflow == "CONTROLLED"]
    )
    fragrance_ids = {str(row["fragrance_id"]) for row in manifest}
    fragrances = {
        fragrance.id: fragrance
        for fragrance in await session.scalars(
            select(Fragrance)
            .where(Fragrance.id.in_(fragrance_ids), live(Fragrance))
            .options(
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.accords),
            )
        )
    }
    result: list[dict[str, object]] = []
    for row in manifest:
        fragrance = fragrances.get(str(row["fragrance_id"]))
        if fragrance is None:
            continue
        row["source_features"] = vectorize(fragrance).to_source_features()
        result.append(row)
    return TrainingRead(rows=rows, manifest=result, input_digest=rows_digest(rows))


async def training_manifest(
    session: AsyncSession, reviewer_id: str
) -> list[dict[str, object]]:
    """Return one reviewer's training manifest, built from the view only.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str): The evaluator.

    Returns:
        list[dict[str, object]]: Ordinary rows (latest eligible encounter per
            version, newest first), then controlled rows (newest receipt
            first), each with ``source_features``.
    """
    return (await read_training(session, reviewer_id)).manifest


__all__ = [
    "FILTERS",
    "SOURCE",
    "V_TRAINING_ROWS",
    "TrainingRead",
    "TrainingViewRow",
    "read_rows",
    "read_training",
    "rows_digest",
    "training_manifest",
]
