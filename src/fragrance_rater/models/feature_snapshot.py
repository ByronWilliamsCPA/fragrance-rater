"""Frozen fragrance feature vectors that predictions and checkpoints score from.

Architecture review X-17: ``PredictionSnapshot.feature_snapshot_version`` was a
free string pointing at nothing, so a manifest could not be rebuilt bit for
bit. A ``FeatureSnapshot`` row freezes the feature vectors one run used,
together with the versions that shaped them (feature space, taxonomy, note
alias layer, source parser) and a digest of the whole, and predictions and
checkpoints reference the row (ADR-009: "freeze ... source-feature snapshot").
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import SchemaItem

from fragrance_rater.core.database import Base, portable_json
from fragrance_rater.models.calibration import sha256_hex_check
from fragrance_rater.utils.timestamps import now_naive_utc


def identifier() -> str:
    """Return a new opaque identifier."""
    return str(uuid4())


class FeatureSnapshot(Base):
    """An immutable, content-addressed set of fragrance feature vectors.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        feature_space_version (Mapped[str]): ``ml.feature_space``'s
            ``FEATURE_SPACE_VERSION`` the vectors were built in.
        taxonomy_version (Mapped[str | None]): Version of the family/accord
            taxonomy the vectors used; NULL until a versioned taxonomy exists
            (ADR-010's ``ClassificationSystem``).
        alias_version (Mapped[str | None]): Version of the note alias layer
            that normalized note names; NULL when none applied.
        parser_version (Mapped[str | None]): Version of the source parser or
            mapping that produced the underlying catalog facts.
        content_hash (Mapped[str]): Lowercase SHA-256 hex over the canonical
            JSON of ``features`` and the four version fields. Unique, so the
            same frozen content is stored once and referenced by every run
            that used it.
        features (Mapped[dict[str, object]]): The frozen vectors, keyed by
            fragrance version id (``FeatureVector.to_source_features()``).
        created_at (Mapped[datetime]): When the snapshot was frozen.
        recorded_by (Mapped[str | None]): Username of whoever froze it;
            NULL for system runs.
    """

    __tablename__ = "feature_snapshots"
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(sha256_hex_check("content_hash"), name="content_hash_sha256"),
        # NOT NULL column, so no NULL branch: a JSON ``null`` fails here.
        CheckConstraint(
            "ltrim(CAST(features AS TEXT)) LIKE '{%'", name="features_is_object"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    feature_space_version: Mapped[str] = mapped_column(String(100))
    taxonomy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alias_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    features: Mapped[dict[str, object]] = mapped_column(portable_json())
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
