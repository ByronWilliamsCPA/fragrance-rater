"""Write-time training-eligibility promotion (R8 PR 2, the owner's option C).

``training_eligibility`` (R8 PR 1, X-05) starts ``unreviewed`` on every
evidence row and only ``eligible`` rows reach ``v_training_rows``. The owner
decided (option C) that promotion is rule-based, at write time, in the service
layer; the database default stays ``unreviewed`` so a row written anywhere
else (an import, a backfill, raw SQL) never trains without a decision:

* An ordinary encounter becomes ``eligible`` when ``EvaluationService.create``
  saves it complete. The view screens worn-by, soft-deleted, holdout, and
  ADR-014 fragrance cases structurally, so the code says only "this encounter
  was captured by the product as designed".
* A controlled observation becomes ``eligible`` when its stage is locked and
  no quality flag is open against it, its presentation (the physical sample),
  or its session; with an open flag it is ``questionable``.
* Raising a flag moves the rows it covers from ``unreviewed`` or ``eligible``
  to ``questionable``. Closing a flag as ``invalidated`` (raised in error), or
  a manager resolving it with outcome ``eligible``, re-applies the rule to the
  rows it left ``questionable``. A manager resolving it with outcome
  ``withheld`` or ``invalidated`` sets those rows to that outcome.
* A manager may set any row to ``eligible``, ``withheld``, or ``invalidated``
  with a reason.

No automatic path ever changes a ``withheld`` or ``invalidated`` row: only a
manager's explicit decision does. Every change is an audit event
(``training_eligibility_set``) naming the row, both codes, the cause, and the
actor.

Flag linkage (R7b stores flags in ``calibration_quality_flags`` with exactly
one of ``session_id``, ``presentation_id``, ``observation_id``): a flag covers
an observation when it names the observation, the observation's presentation,
or that presentation's session. A flag is open while it is ``raised`` and no
later row supersedes it. No schema change was needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from sqlalchemy import String, and_, column, exists, or_, select, table
from sqlalchemy.orm import aliased

from fragrance_rater.core.vocabulary import (
    DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
    TRAINABLE_EVIDENCE_ELIGIBILITY,
)
from fragrance_rater.models.calibration import (
    Observation,
    Presentation,
    QualityFlag,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.utils.logging import get_logger, log_audit_event

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

QUESTIONABLE = "questionable"
WITHHELD = "withheld"
INVALIDATED = "invalidated"

#: Codes no automatic rule may change; only a manager decides them.
MANAGER_ONLY: frozenset[str] = frozenset({WITHHELD, INVALIDATED})
#: Codes a raised flag demotes to ``questionable``.
DEMOTABLE: frozenset[str] = frozenset(
    {DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY, TRAINABLE_EVIDENCE_ELIGIBILITY}
)

ManagerDecision = Literal["eligible", "withheld", "invalidated"]
"""What a manager may set directly or choose when resolving a flag."""

MANAGER_DECISIONS: tuple[ManagerDecision, ...] = ("eligible", "withheld", "invalidated")


@dataclass(frozen=True)
class Transition:
    """One evidence row's eligibility change.

    Attributes:
        table (str): ``evaluations`` or ``calibration_observations``.
        row_id (str): The row's id.
        previous (str): The code before.
        current (str): The code after.
    """

    table: str
    row_id: str
    previous: str
    current: str


def _audit(
    transitions: Iterable[Transition],
    *,
    actor: str | None,
    cause: str,
    reason: str | None = None,
    quality_flag_id: str | None = None,
) -> None:
    """Record each change as one ``training_eligibility_set`` audit event."""
    for change in transitions:
        log_audit_event(
            logger,
            action="training_eligibility_set",
            actor=actor,
            target_type=change.table,
            target_id=change.row_id,
            previous=change.previous,
            training_eligibility=change.current,
            cause=cause,
            reason=reason,
            quality_flag_id=quality_flag_id,
        )


def _change(row: Evaluation | Observation, code: str) -> Transition | None:
    """Set ``row``'s code, returning the transition, or ``None`` if unchanged."""
    previous = row.training_eligibility
    if previous == code:
        return None
    row.training_eligibility = code
    table = "evaluations" if isinstance(row, Evaluation) else "calibration_observations"
    return Transition(table, row.id, previous, code)


def _open_flag() -> ColumnElement[bool]:
    """``QualityFlag`` is a raised flag that no later row closes."""
    closing = aliased(QualityFlag)
    return and_(
        QualityFlag.action == "raised",
        ~exists().where(closing.supersedes_id == QualityFlag.id),
    )


class TrainingEligibilityService:
    """Apply option C's promotion rules within the caller's transaction."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- ordinary encounters ------------------------------------------------

    @staticmethod
    def evaluation_saved(evaluation: Evaluation, *, actor: str | None) -> None:
        """Promote a newly saved, complete ordinary encounter to ``eligible``.

        Called only by ``EvaluationService.create``: an encounter saved there
        has passed the request schema (a 1-5 rating, a reviewer, a fragrance),
        which is what "complete" means for this workflow. Updates never call
        it, so a manager's ``withheld`` survives an edit.

        Args:
            evaluation (Evaluation): The row just created (still unreviewed).
            actor (str | None): Who saved it.
        """
        if evaluation.training_eligibility != DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY:
            return
        change = _change(evaluation, TRAINABLE_EVIDENCE_ELIGIBILITY)
        _audit([change] if change else [], actor=actor, cause="evaluation_saved")

    # --- controlled observations ------------------------------------------

    async def _covering_open_flags(self, observation: Observation) -> list[str]:
        """Return the ids of open flags covering ``observation``."""
        presentation = await self.db.get(Presentation, observation.presentation_id)
        assert presentation is not None
        return list(
            await self.db.scalars(
                select(QualityFlag.id).where(
                    _open_flag(),
                    or_(
                        QualityFlag.observation_id == observation.id,
                        QualityFlag.presentation_id == presentation.id,
                        QualityFlag.session_id == presentation.session_id,
                    ),
                )
            )
        )

    async def _rule_state(self, observation: Observation) -> str:
        """What option C says an observation's code is, ignoring manager codes."""
        if await self._covering_open_flags(observation):
            return QUESTIONABLE
        presentation = await self.db.get(Presentation, observation.presentation_id)
        assert presentation is not None
        locked = (
            presentation.skin_locked_at
            if observation.stage == "SKIN"
            else presentation.blotter_locked_at
        )
        if locked is not None:
            return TRAINABLE_EVIDENCE_ELIGIBILITY
        return DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY

    async def observation_written(
        self, observation: Observation, *, actor: str
    ) -> Transition | None:
        """Apply the rule to a just-appended observation.

        A new observation is ``unreviewed`` unless its stage is already locked
        (an informed post-reveal entry is written after the lock) or a flag
        already covers it.

        Args:
            observation (Observation): The flushed new row.
            actor (str): Who submitted it.

        Returns:
            Transition | None: The change made, if any.
        """
        if observation.training_eligibility != DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY:
            return None
        change = _change(observation, await self._rule_state(observation))
        _audit([change] if change else [], actor=actor, cause="observation_written")
        return change

    async def stage_locked(
        self, presentation: Presentation, stage: str, *, actor: str
    ) -> list[Transition]:
        """Promote a just-locked stage's ``unreviewed`` observations.

        Each becomes ``eligible``, or ``questionable`` while a flag covers it.
        Rows already ``questionable``, ``withheld``, or ``invalidated`` keep
        their code.

        Args:
            presentation (Presentation): The sample whose stage was locked.
            stage (str): ``BLOTTER`` or ``SKIN``.
            actor (str): Who locked it.

        Returns:
            list[Transition]: The changes made.
        """
        rows = await self.db.scalars(
            select(Observation).where(
                Observation.presentation_id == presentation.id,
                Observation.stage == stage,
                Observation.training_eligibility
                == DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY,
            )
        )
        changes = [
            change
            for row in list(rows)
            if (change := _change(row, await self._rule_state(row))) is not None
        ]
        _audit(changes, actor=actor, cause="stage_locked")
        return changes

    async def flagged_observations(self, flag: QualityFlag) -> list[Observation]:
        """Return every observation a flag (or a row closing it) covers.

        Args:
            flag (QualityFlag): A raised flag or one of its closing rows; both
                name the same target.

        Returns:
            list[Observation]: The covered observations.
        """
        if flag.observation_id is not None:
            condition = Observation.id == flag.observation_id
        elif flag.presentation_id is not None:
            condition = Observation.presentation_id == flag.presentation_id
        else:
            condition = Observation.presentation_id.in_(
                select(Presentation.id).where(
                    Presentation.session_id == flag.session_id
                )
            )
        return list(await self.db.scalars(select(Observation).where(condition)))

    async def flag_raised(self, flag: QualityFlag, *, actor: str) -> list[Transition]:
        """Demote every covered ``unreviewed`` or ``eligible`` row.

        Args:
            flag (QualityFlag): The flushed ``raised`` row.
            actor (str): Who raised it.

        Returns:
            list[Transition]: The changes made; ``withheld`` and
                ``invalidated`` rows are never among them.
        """
        changes = [
            change
            for row in await self.flagged_observations(flag)
            if row.training_eligibility in DEMOTABLE
            and (change := _change(row, QUESTIONABLE)) is not None
        ]
        _audit(
            changes, actor=actor, cause="quality_flag_raised", quality_flag_id=flag.id
        )
        return changes

    async def flag_closed(
        self,
        closing: QualityFlag,
        *,
        outcome: ManagerDecision | None,
        actor: str,
    ) -> list[Transition]:
        """Settle the rows a just-closed flag left ``questionable``.

        * ``invalidated`` closing row (raised in error), or a resolution with
          outcome ``eligible``: each row goes back to what the rule says now
          (``eligible`` when its stage is locked and no other flag covers it).
        * A resolution with outcome ``withheld`` or ``invalidated``: each row
          takes the outcome.
        * A resolution without an outcome: nothing changes; the rows stay
          ``questionable`` until a manager decides.

        Only ``questionable`` rows are touched, so a manager's earlier
        ``withheld``/``invalidated``/``eligible`` decision on a row stands.

        Args:
            closing (QualityFlag): The flushed ``resolved``/``invalidated`` row.
            outcome (ManagerDecision | None): The manager's chosen outcome.
            actor (str): Who closed it.

        Returns:
            list[Transition]: The changes made.
        """
        if closing.action == "resolved" and outcome is None:
            return []
        changes: list[Transition] = []
        for row in await self.flagged_observations(closing):
            if row.training_eligibility != QUESTIONABLE:
                continue
            if closing.action == "invalidated" or outcome == "eligible":
                target = await self._rule_state(row)
            else:
                assert outcome is not None
                target = outcome
            change = _change(row, target)
            if change is not None:
                changes.append(change)
        _audit(
            changes,
            actor=actor,
            cause=f"quality_flag_{closing.action}",
            reason=closing.explanation,
            quality_flag_id=closing.supersedes_id,
        )
        return changes

    # --- manager decisions -------------------------------------------------

    async def set_by_manager(
        self,
        target_type: Literal["evaluation", "observation"],
        target_id: str,
        decision: ManagerDecision,
        *,
        reason: str,
        actor: str,
    ) -> Transition:
        """Set one row's code by a manager's explicit decision.

        Args:
            target_type (Literal["evaluation", "observation"]): Which table.
            target_id (str): The row id.
            decision (ManagerDecision): ``eligible``, ``withheld``, or
                ``invalidated``.
            reason (str): Why; recorded in the audit event.
            actor (str): The manager.

        Returns:
            Transition: The change (``previous == current`` when the row
                already had that code; nothing is written then).

        Raises:
            LookupError: When the row does not exist.
        """
        row: Evaluation | Observation | None
        if target_type == "evaluation":
            row = await self.db.get(Evaluation, target_id, with_for_update=True)
            table = "evaluations"
        else:
            row = await self.db.get(Observation, target_id, with_for_update=True)
            table = "calibration_observations"
        if row is None:
            message = f"{target_type} {target_id} not found"
            raise LookupError(message)
        change = _change(row, decision)
        await self.db.flush()
        _audit(
            [change] if change else [],
            actor=actor,
            cause="manager_decision",
            reason=reason,
        )
        return change or Transition(table, row.id, decision, decision)


def summarize(transitions: Sequence[Transition]) -> list[dict[str, str]]:
    """Serialize transitions for an API response.

    Args:
        transitions (Sequence[Transition]): Changes made.

    Returns:
        list[dict[str, str]]: One dict per change.
    """
    return [
        {
            "table": change.table,
            "row_id": change.row_id,
            "previous": change.previous,
            "training_eligibility": change.current,
        }
        for change in transitions
    ]


V_MANAGER_LINKAGE = table(
    "v_manager_linkage",
    column("row_id", String()),
    column("reviewer_id", String()),
    column("enrollment_id", String()),
    column("program_id", String()),
    column("session_id", String()),
    column("presentation_id", String()),
    column("blind_code", String()),
    column("membership_id", String()),
    column("fragrance_id", String()),
    column("role", String()),
    column("repeat_of_membership_id", String()),
    column("stage", String()),
    column("phase", String()),
    column("training_eligibility", String()),
)
"""The manager-only linkage view (X-06), as a lightweight Core table."""


async def manager_linkage(
    db: AsyncSession, enrollment_id: str
) -> list[dict[str, object]]:
    """Read one enrollment's role and repeat linkage from ``v_manager_linkage``.

    #CRITICAL: security: this returns membership roles and the hidden-repeat
    link, the blind mapping a trainer and a participant must never see.
    #VERIFY: its only caller is the manager-only linkage route, which the
    authorization matrix tests for 401/403.

    Args:
        db (AsyncSession): Database session.
        enrollment_id (str): The enrollment.

    Returns:
        list[dict[str, object]]: One dict per observation, keyed by the same
            ``row_id`` as ``v_training_rows``.
    """
    result = await db.execute(
        select(V_MANAGER_LINKAGE)
        .where(V_MANAGER_LINKAGE.c.enrollment_id == enrollment_id)
        .order_by(V_MANAGER_LINKAGE.c.session_id, V_MANAGER_LINKAGE.c.row_id)
    )
    return [cast("dict[str, object]", dict(row)) for row in result.mappings()]
