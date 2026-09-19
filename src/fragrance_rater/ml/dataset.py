"""Uniform training rows and array export over the frozen training manifest.

Before this module existed no code turned stored evidence into ``X, y``:
``PreferenceHistoryService.training_manifest`` returns heterogeneous dicts
whose ordinary and controlled rows have disjoint key sets, so two workflows
(let alone two evaluators) could not be concatenated (ML structure review
M-01, M-22).

``TrainingRow`` is that uniform row. It is built strictly *on top of* the
manifest, never beside it: every eligibility rule (holdout exclusion, hidden
repeats, pre-reveal phase, stage locks, worn-by exclusion, latest-encounter
selection) stays in the one place that already enforces it, and this module
adds only target selection, the split label, the feature vector, and the
"would affinity-v1 have used this row" flag.

Two things this module deliberately does *not* do:

- It never emits the manifest's ``role`` key. The manifest already excludes
  holdouts and hidden repeats, so the role is never a leak by value, but a
  role column on a training row is a leak vector by shape (X-06): a trainer
  that can read it can learn the experimental design.
- It never maps a controlled 0-10 liking onto the ordinary 1-5 scale, or the
  reverse. ``TrainingRow.scale`` states which scale a label is on and the
  caller decides what may be pooled (ADR-007; review Section 3).

The "primary" target is the ML structure review's *proposed* primary outcome
(Section 3): latest eligible pre-reveal ``liking`` for controlled rows, the
1-5 ``rating`` for ordinary rows. It is a parameter of this function, not a
decision this module makes; the decision belongs to an ADR-009 amendment
(finding L-01) and until that lands every caller states its own target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from sqlalchemy import select

from fragrance_rater.ml.feature_space import from_source_features
from fragrance_rater.models.calibration import Enrollment
from fragrance_rater.services.preference_history import PreferenceHistoryService

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.ml.feature_space import FeatureVector

Target = Literal[
    "rating",
    "liking",
    "opening_liking",
    "drydown_liking",
    "would_wear",
    "would_buy",
    "artistic_appreciation",
]
"""Supported label columns.

``rating`` is the ordinary 1-5 outcome; every other entry is a controlled
0-10 observation column. ``would_wear`` and ``would_buy`` here are always
the 0-10 observation columns, never the identically named booleans on
recommendation feedback, which must not be pooled with them (X-13).
"""

TARGETS: tuple[Target, ...] = (
    "rating",
    "liking",
    "opening_liking",
    "drydown_liking",
    "would_wear",
    "would_buy",
    "artistic_appreciation",
)
"""Every supported target, in declaration order."""

PRIMARY = "primary"
"""Sentinel target meaning "the proposed primary outcome for this workflow"."""

PRIMARY_ORDINARY_TARGET: Target = "rating"
"""Primary outcome for an ordinary row (proposed, review Section 3)."""

PRIMARY_CONTROLLED_TARGET: Target = "liking"
"""Primary outcome for a controlled row (proposed, review Section 3)."""

PERCEPTION_DIMENSIONS: tuple[str, ...] = (
    "confidence",
    "sweetness",
    "freshness",
    "density",
    "dryness",
    "clean_soapy",
    "earthy_rooty",
    "bodily_animalic",
    "discomfort",
)
"""The typed 0-5 perceptual dimensions used by the ``perception`` space.

``familiarity`` is excluded: it is a 0-5 integer with no anchors and is
absent from ordinary evaluations altogether (X-14), so it is not comparable
across workflows.
"""

FEATURE_SPACES: tuple[str, ...] = ("notes", "accords", "families", "perception")
"""Feature spaces ``to_arrays`` can project a row set into."""


@dataclass(frozen=True)
class TrainingRow:
    """One evaluator's labeled encounter with one fragrance version.

    The key set is identical for ordinary and controlled rows so two
    workflows, or two evaluators, can be concatenated into one table
    (M-22). Workflow-specific payloads are carried in optional fields
    rather than by varying the keys.

    Attributes:
        reviewer_id (str): The evaluator this row belongs to.
        fragrance_id (str): Canonical fragrance version id.
        source_row_id (str): Id of the underlying ``Evaluation`` or
            ``Observation`` row the label came from.
        workflow (str): ``"ORDINARY"`` or ``"CONTROLLED"``.
        scale (str): ``"1-5"`` for ordinary ratings, ``"0-10"`` for
            controlled observation columns. Never converted between the two.
        label (float | None): The value of ``target`` on this row, or
            ``None`` when that column is NULL. Null-labeled rows are kept so
            the caller, not this module, decides whether to drop them.
        target (str): Which column ``label`` was read from.
        stage (str | None): ``"BLOTTER"`` or ``"SKIN"`` for controlled rows.
        phase (str | None): Always ``"PRE_REVEAL"`` for controlled rows that
            reach the manifest.
        program_id (str | None): Calibration program for controlled rows.
        observed_at (str): ISO-8601 timestamp of the underlying row.
        features (FeatureVector): Published catalog features of the version,
            rebuilt from the frozen manifest rather than re-read live.
        observation_features (dict[str, object] | None): The manifest's
            typed observation feature dict for controlled rows.
        notes_text (dict[str, object] | None): Free-text fields; the four
            controlled fields, or ``{"notes": ...}`` for an ordinary row.
        split (str): ``"DEV"``, ``"HOLDOUT"`` or ``"REPEAT"``. Always
            ``"DEV"`` today because the manifest has already removed the
            other two; ``split_for`` is the shared definition.
        contributed_to_affinity_v1 (bool): Whether affinity-v1 would have
            consumed this row as evidence. Ordinary rows always do;
            controlled rows only once their program is revealed.
    """

    reviewer_id: str
    fragrance_id: str
    source_row_id: str
    workflow: str
    scale: str
    label: float | None
    target: str
    stage: str | None
    phase: str | None
    program_id: str | None
    observed_at: str
    features: FeatureVector
    observation_features: dict[str, object] | None
    notes_text: dict[str, object] | None
    split: str
    contributed_to_affinity_v1: bool

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict with the same uniform key set.

        Returns:
            dict[str, object]: Every field, with ``features`` flattened into
                the manifest's ``source_features`` shape.
        """
        return {
            "reviewer_id": self.reviewer_id,
            "fragrance_id": self.fragrance_id,
            "source_row_id": self.source_row_id,
            "workflow": self.workflow,
            "scale": self.scale,
            "label": self.label,
            "target": self.target,
            "stage": self.stage,
            "phase": self.phase,
            "program_id": self.program_id,
            "observed_at": self.observed_at,
            "features": self.features.to_source_features(),
            "observation_features": self.observation_features,
            "notes_text": self.notes_text,
            "split": self.split,
            "contributed_to_affinity_v1": self.contributed_to_affinity_v1,
        }


def split_for(role: str) -> str:
    """Map a ``Membership.role`` onto the one shared split vocabulary.

    This is the single definition finding M-18 asks for: dataset building,
    scoring exclusion and reporting must all agree on what a row is for.
    Roles other than the two that carry a split meaning today
    (``ACTIVE_LEARNING``, ``RETEST``, ``OWNED_VALIDATION``,
    ``UNIVERSAL_BASELINE``) are development rows until an ADR says
    otherwise.

    Args:
        role (str): The membership role as stored.

    Returns:
        str: ``"HOLDOUT"``, ``"REPEAT"`` or ``"DEV"``.
    """
    if role == "HOLDOUT":
        return "HOLDOUT"
    if role == "HIDDEN_REPEAT":
        return "REPEAT"
    return "DEV"


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_dict(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def resolve_target(workflow: str, target: str) -> Target:
    """Resolve a requested target, expanding the ``"primary"`` sentinel.

    Args:
        workflow (str): ``"ORDINARY"`` or ``"CONTROLLED"``.
        target (str): One of ``TARGETS`` or ``"primary"``.

    Returns:
        Target: The concrete label column to read.

    Raises:
        ValueError: If ``target`` is neither ``"primary"`` nor a supported
            target.
    """
    if target == PRIMARY:
        if workflow == "ORDINARY":
            return PRIMARY_ORDINARY_TARGET
        return PRIMARY_CONTROLLED_TARGET
    if target not in TARGETS:
        msg = f"unsupported target {target!r}; expected one of {TARGETS} or 'primary'"
        raise ValueError(msg)
    return target


def _ordinary_row(
    reviewer_id: str, row: dict[str, object], target: str
) -> TrainingRow | None:
    """Build one ordinary training row, or ``None`` if it is not usable."""
    fragrance_id = _as_str(row.get("fragrance_id"))
    source_row_id = _as_str(row.get("id"))
    source_features = _as_dict(row.get("source_features"))
    if fragrance_id is None or source_row_id is None or source_features is None:
        return None
    column = resolve_target("ORDINARY", target)
    # An ordinary evaluation carries only the 1-5 `rating`; a caller that
    # explicitly asks for a controlled column gets the row with a NULL label
    # rather than a silently cross-scale value.
    label = _as_float(row.get("rating")) if column == "rating" else None
    return TrainingRow(
        reviewer_id=reviewer_id,
        fragrance_id=fragrance_id,
        source_row_id=source_row_id,
        workflow="ORDINARY",
        scale=_as_str(row.get("scale")) or "1-5",
        label=label,
        target=column,
        stage=None,
        phase=None,
        program_id=None,
        observed_at=_as_str(row.get("observed_at")) or "",
        features=from_source_features(fragrance_id, source_features),
        observation_features=None,
        notes_text={"notes": row.get("notes")},
        split="DEV",
        contributed_to_affinity_v1=True,
    )


def _controlled_row(
    reviewer_id: str,
    row: dict[str, object],
    target: str,
    revealed_program_ids: set[str],
) -> TrainingRow | None:
    """Build one controlled training row, or ``None`` if it is not usable."""
    fragrance_id = _as_str(row.get("fragrance_id"))
    source_row_id = _as_str(row.get("id"))
    source_features = _as_dict(row.get("source_features"))
    if fragrance_id is None or source_row_id is None or source_features is None:
        return None
    column = resolve_target("CONTROLLED", target)
    observation_features = _as_dict(row.get("features"))
    if column == "liking":
        label = _as_float(row.get("rating"))
    elif column == "rating":
        # The 1-5 ordinary outcome does not exist on a controlled
        # observation and is never derived from liking (ADR-007).
        label = None
    else:
        label = (
            None
            if observation_features is None
            else _as_float(observation_features.get(column))
        )
    program_id = _as_str(row.get("program_id"))
    return TrainingRow(
        reviewer_id=reviewer_id,
        fragrance_id=fragrance_id,
        source_row_id=source_row_id,
        workflow="CONTROLLED",
        scale=_as_str(row.get("scale")) or "0-10",
        label=label,
        target=column,
        stage=_as_str(row.get("stage")),
        phase=_as_str(row.get("phase")),
        program_id=program_id,
        observed_at=_as_str(row.get("observed_at")) or "",
        features=from_source_features(fragrance_id, source_features),
        observation_features=observation_features,
        notes_text=_as_dict(row.get("notes_text")),
        split="DEV",
        contributed_to_affinity_v1=program_id in revealed_program_ids,
    )


def rows_from_manifest(
    reviewer_id: str,
    manifest: Sequence[dict[str, object]],
    *,
    target: str = PRIMARY,
    revealed_program_ids: set[str] | None = None,
    include_ordinary: bool = True,
    include_controlled: bool = True,
) -> list[TrainingRow]:
    """Project a frozen training manifest onto uniform training rows.

    Pure and synchronous, so a frozen ``ModelCheckpoint.manifest`` can be
    replayed into the same rows a live session would produce.

    Args:
        reviewer_id (str): The evaluator the manifest belongs to.
        manifest (Sequence[dict[str, object]]): Manifest rows as returned by
            ``PreferenceHistoryService.training_manifest``.
        target (str): A member of ``TARGETS`` or ``"primary"``.
        revealed_program_ids (set[str] | None): Programs whose reveal gate
            has opened, used only for ``contributed_to_affinity_v1``.
        include_ordinary (bool): Include ``ORDINARY`` rows.
        include_controlled (bool): Include ``CONTROLLED`` rows.

    Returns:
        list[TrainingRow]: Rows in manifest order. Rows whose requested
            target is NULL are kept with ``label=None``.
    """
    revealed = revealed_program_ids or set()
    rows: list[TrainingRow] = []
    for raw in manifest:
        workflow = _as_str(raw.get("workflow"))
        built: TrainingRow | None = None
        if workflow == "ORDINARY" and include_ordinary:
            built = _ordinary_row(reviewer_id, raw, target)
        elif workflow == "CONTROLLED" and include_controlled:
            built = _controlled_row(reviewer_id, raw, target, revealed)
        if built is not None:
            rows.append(built)
    return rows


async def revealed_program_ids(session: AsyncSession, reviewer_id: str) -> set[str]:
    """Return the programs this evaluator has already been un-blinded to.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str): The evaluator.

    Returns:
        set[str]: Program ids whose enrollment has a ``revealed_at``.
    """
    return set(
        await session.scalars(
            select(Enrollment.program_id).where(
                Enrollment.reviewer_id == reviewer_id,
                Enrollment.revealed_at.is_not(None),
            )
        )
    )


async def build_examples(
    session: AsyncSession,
    reviewer_id: str,
    *,
    target: str = PRIMARY,
    include_ordinary: bool = True,
    include_controlled: bool = True,
) -> list[TrainingRow]:
    """Build one evaluator's training rows from the eligibility-correct source.

    Delegates every eligibility rule to
    ``PreferenceHistoryService.training_manifest`` and adds only target
    selection, the split label, the rebuilt feature vector, and the
    affinity-v1 contribution flag.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str): The evaluator to build rows for.
        target (str): A member of ``TARGETS`` or ``"primary"``.
        include_ordinary (bool): Include ordinary 1-5 rows.
        include_controlled (bool): Include controlled 0-10 rows.

    Returns:
        list[TrainingRow]: Uniform rows, null labels retained.
    """
    manifest = await PreferenceHistoryService(session).training_manifest(reviewer_id)
    revealed = await revealed_program_ids(session, reviewer_id)
    return rows_from_manifest(
        reviewer_id,
        manifest,
        target=target,
        revealed_program_ids=revealed,
        include_ordinary=include_ordinary,
        include_controlled=include_controlled,
    )


def _note_terms(row: TrainingRow) -> dict[str, float]:
    return dict.fromkeys(row.features.note_ids(), 1.0)


def _accord_terms(row: TrainingRow) -> dict[str, float]:
    terms: dict[str, float] = {}
    for accord in row.features.accords:
        if not accord.name:
            continue
        terms[accord.name] = max(terms.get(accord.name, 0.0), float(accord.intensity))
    return terms


def _family_terms(row: TrainingRow) -> dict[str, float]:
    # Namespaced so a subfamily string that collides with a family string is
    # two features rather than one double-counted feature (M-12).
    terms: dict[str, float] = {}
    if row.features.primary_family:
        terms[f"family:{row.features.primary_family}"] = 1.0
    if row.features.subfamily:
        terms[f"subfamily:{row.features.subfamily}"] = 1.0
    return terms


def _perception_terms(row: TrainingRow) -> dict[str, float]:
    features = row.observation_features or {}
    terms: dict[str, float] = {}
    for dimension in PERCEPTION_DIMENSIONS:
        value = _as_float(features.get(dimension))
        if value is not None:
            terms[dimension] = value
    return terms


_TERMS = {
    "notes": _note_terms,
    "accords": _accord_terms,
    "families": _family_terms,
    "perception": _perception_terms,
}


def to_arrays(
    rows: Sequence[TrainingRow], *, feature_space: str = "notes"
) -> tuple[list[list[float]], list[float], list[str], list[str]]:
    """Project labeled rows into dense design arrays, in pure Python.

    Rows whose ``label`` is ``None`` are excluded here rather than in
    ``build_examples``, so the same row set can be used for a descriptive
    pass that keeps them (review M-20).

    Feature spaces:

    - ``notes``: one-hot over canonical ``Note.id``.
    - ``accords``: accord label weighted by its reported intensity. The
        schema does not yet distinguish a measured intensity from one
        fabricated out of list position (X-04), so a caller that needs only
        measured weights must filter upstream.
    - ``families``: one-hot over namespaced ``family:`` and ``subfamily:``
        labels. Both draw on three uncontrolled vocabularies today (X-10,
        X-11).
    - ``perception``: the typed 0-5 perceptual dimensions from the
        observation itself, in ``PERCEPTION_DIMENSIONS`` order rather than
        sorted, since they are a fixed declared basis and not a discovered
        vocabulary. A NULL dimension, and every ordinary row (which has no
        observation at all), becomes ``0.0``. No parallel missing-indicator
        column is emitted: at this sample size it would double a 9-column
        basis for little gain, so a caller that must distinguish "reported
        zero" from "not reported" reads ``observation_features`` directly.

    Args:
        rows (Sequence[TrainingRow]): Rows to project.
        feature_space (str): One of ``FEATURE_SPACES``.

    Returns:
        tuple[list[list[float]], list[float], list[str], list[str]]:
            ``X`` (one row per labeled row, one column per vocabulary
            entry), ``y`` (labels), ``groups`` (reviewer ids, for grouped
            cross-validation), and the vocabulary itself.

    Raises:
        ValueError: If ``feature_space`` is not supported.
    """
    if feature_space not in _TERMS:
        msg = f"unsupported feature_space {feature_space!r}; expected {FEATURE_SPACES}"
        raise ValueError(msg)
    terms_for = _TERMS[feature_space]
    labeled = [row for row in rows if row.label is not None]
    per_row = [terms_for(row) for row in labeled]
    if feature_space == "perception":
        vocabulary = list(PERCEPTION_DIMENSIONS)
    else:
        vocabulary = sorted({key for terms in per_row for key in terms})
    matrix = [[terms.get(key, 0.0) for key in vocabulary] for terms in per_row]
    labels = [float(row.label) for row in labeled if row.label is not None]
    groups = [row.reviewer_id for row in labeled]
    return matrix, labels, groups, vocabulary


__all__ = [
    "FEATURE_SPACES",
    "PERCEPTION_DIMENSIONS",
    "PRIMARY",
    "PRIMARY_CONTROLLED_TARGET",
    "PRIMARY_ORDINARY_TARGET",
    "TARGETS",
    "Target",
    "TrainingRow",
    "build_examples",
    "resolve_target",
    "revealed_program_ids",
    "rows_from_manifest",
    "split_for",
    "to_arrays",
]
