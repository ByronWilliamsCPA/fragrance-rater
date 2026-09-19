"""The single definition of a fragrance version's feature vector.

Before this module existed the scorer keyed note affinities by ``Note.id``
while the frozen training manifest recorded notes by name only, so a frozen
manifest could not reconstruct the scorer's own keys and a note rename
silently broke the join. ``FeatureVector`` is now produced in one place from
an ORM ``Fragrance`` (``vectorize``) and can be rebuilt from a manifest's
``source_features`` dict (``from_source_features``); both the scorer and the
manifest builder use it.

``FEATURE_SPACE_VERSION`` names the shape of this representation. Bump it
whenever the set of fields, their meaning, or the vocabulary they draw on
changes, so that a frozen checkpoint or prediction can state which feature
space it was computed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fragrance_rater.models.fragrance import Fragrance

FEATURE_SPACE_VERSION = "fs-v1"
"""Identifier for the current feature representation (see module docstring)."""


@dataclass(frozen=True)
class NoteFeature:
    """One published note on a fragrance version.

    Attributes:
        note_id (str | None): Canonical ``Note.id``. ``None`` only when
            rebuilt from a legacy manifest written before note ids were
            frozen; such a vector cannot be scored by an id-keyed model.
        name (str): The note's catalog name at the time of vectorization.
        position (str): Pyramid position (``top``, ``heart``, ``base``,
            ``flat``) as recorded by the source.
    """

    note_id: str | None
    name: str
    position: str


@dataclass(frozen=True)
class AccordFeature:
    """One published accord on a fragrance version.

    Attributes:
        name (str): Accord label as stored on ``FragranceAccord.accord_type``.
        intensity (float): Source-reported or positional intensity in
            ``[0, 1]``; the current schema does not distinguish the two
            (see the ML structure review, X-04).
    """

    name: str
    intensity: float


@dataclass(frozen=True)
class FeatureVector:
    """A fragrance version's published features in the current feature space.

    Attributes:
        fragrance_id (str | None): Canonical version id when known.
        version_key (str | None): ADR-006 version key when known.
        concentration (str | None): Concentration label when known.
        primary_family (str | None): Family label as stored on the catalog.
        subfamily (str | None): Subfamily label as stored on the catalog;
            empty or ``None`` means unknown.
        notes (tuple[NoteFeature, ...]): Published notes in source order.
        accords (tuple[AccordFeature, ...]): Published accords in source order.
        feature_space_version (str): The feature-space identifier this
            vector was produced under.
    """

    fragrance_id: str | None
    version_key: str | None
    concentration: str | None
    primary_family: str | None
    subfamily: str | None
    notes: tuple[NoteFeature, ...] = ()
    accords: tuple[AccordFeature, ...] = ()
    feature_space_version: str = FEATURE_SPACE_VERSION

    def note_ids(self) -> list[str]:
        """Return the canonical note ids present on this vector, in order.

        Returns:
            list[str]: Note ids, omitting entries whose id is unknown.
        """
        return [note.note_id for note in self.notes if note.note_id is not None]

    def to_source_features(self) -> dict[str, object]:
        """Serialize to the manifest's ``source_features`` shape.

        Returns:
            dict[str, object]: JSON-serializable dict carrying the version
                identity, family labels, notes (with ``note_id``, ``name`` and
                ``position``), accords (``name`` and ``intensity``) and the
                feature-space version.
        """
        return {
            "feature_space_version": self.feature_space_version,
            "version_key": self.version_key,
            "concentration": self.concentration,
            "primary_family": self.primary_family,
            "subfamily": self.subfamily,
            "notes": [
                {"note_id": n.note_id, "name": n.name, "position": n.position}
                for n in self.notes
            ],
            "accords": [
                {"name": a.name, "intensity": a.intensity} for a in self.accords
            ],
        }


def vectorize(fragrance: Fragrance) -> FeatureVector:
    """Build the feature vector for an ORM fragrance row.

    The ``notes`` (with each ``FragranceNote.note``) and ``accords``
    relationships must already be loaded; this function never issues a
    query, so it is safe to call inside a scoring loop or a batch job.

    Args:
        fragrance (Fragrance): Catalog row with relationships loaded.

    Returns:
        FeatureVector: The row's published features in the current space.
    """
    return FeatureVector(
        fragrance_id=fragrance.id,
        version_key=fragrance.version_key,
        concentration=fragrance.concentration,
        primary_family=fragrance.primary_family,
        subfamily=fragrance.subfamily,
        notes=tuple(
            NoteFeature(note_id=fn.note.id, name=fn.note.name, position=fn.position)
            for fn in fragrance.notes
        ),
        accords=tuple(
            AccordFeature(name=acc.accord_type, intensity=float(acc.intensity))
            for acc in fragrance.accords
        ),
    )


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def from_source_features(
    fragrance_id: str | None, features: dict[str, object]
) -> FeatureVector:
    """Rebuild a feature vector from a frozen manifest ``source_features`` dict.

    Tolerates manifests written before ``note_id`` and
    ``feature_space_version`` were recorded: missing ids become ``None`` and
    a missing version is reported as ``"fs-v0"`` so the caller can tell the
    vector predates the versioned feature space.

    Args:
        fragrance_id (str | None): The manifest row's fragrance id, if any.
        features (dict[str, object]): The ``source_features`` payload.

    Returns:
        FeatureVector: The reconstructed vector.
    """
    raw_notes = features.get("notes")
    raw_accords = features.get("accords")
    notes: list[NoteFeature] = []
    if isinstance(raw_notes, list):
        for entry in raw_notes:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(entry, dict):
                continue
            entry_dict: dict[str, object] = entry  # pyright: ignore[reportUnknownVariableType]
            notes.append(
                NoteFeature(
                    note_id=_as_str(entry_dict.get("note_id")),
                    name=_as_str(entry_dict.get("name")) or "",
                    position=_as_str(entry_dict.get("position")) or "",
                )
            )
    accords: list[AccordFeature] = []
    if isinstance(raw_accords, list):
        for entry in raw_accords:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(entry, dict):
                continue
            entry_dict_a: dict[str, object] = entry  # pyright: ignore[reportUnknownVariableType]
            accords.append(
                AccordFeature(
                    name=_as_str(entry_dict_a.get("name")) or "",
                    intensity=_as_float(entry_dict_a.get("intensity")),
                )
            )
    version = _as_str(features.get("feature_space_version")) or "fs-v0"
    return FeatureVector(
        fragrance_id=fragrance_id,
        version_key=_as_str(features.get("version_key")),
        concentration=_as_str(features.get("concentration")),
        primary_family=_as_str(features.get("primary_family")),
        subfamily=_as_str(features.get("subfamily")),
        notes=tuple(notes),
        accords=tuple(accords),
        feature_space_version=version,
    )


__all__ = [
    "FEATURE_SPACE_VERSION",
    "AccordFeature",
    "FeatureVector",
    "NoteFeature",
    "from_source_features",
    "vectorize",
]
