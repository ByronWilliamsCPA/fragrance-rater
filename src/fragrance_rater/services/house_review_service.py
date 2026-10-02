"""Manager review: turn a submitted house record into manufacturer evidence.

Adoption writes, in one transaction:

- a ``SourceSnapshot`` (``source_type="manufacturer_provided"``) whose
  ``permission_state`` is the house's own choice and whose ``fields`` lists
  exactly the facts the manager accepted (ADR-012's per-field provenance);
- the catalog changes the manager accepted (launch year, gender target), or a
  new catalog version built from the house's values;
- perfumer attributions citing the submission, when the manager asks for them.

The house's notes, accords, family, and description travel verbatim in the
snapshot payload. They are not written to ``fragrance_notes``: mapping a
house's words onto catalog notes is ADR-017 layers 2 and 3, gated to D1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.calibration import Perfumer, SourceSnapshot, VersionPerfumer
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.house_intake import HouseSubmission
from fragrance_rater.schemas.house_intake import (
    HouseSubmissionPayload,
    HouseSubmissionResponse,
)
from fragrance_rater.schemas.house_review import (
    CONFIRMABLE_FIELDS,
    IDENTITY_FIELDS,
    AdoptInput,
    CatalogCandidate,
    Comparison,
    ConfirmableField,
    DeclineInput,
    ExistingTarget,
    ProposedFacts,
    ReviewContext,
    UpdatableField,
)
from fragrance_rater.services.house_intake_service import HouseIntakeService
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.core.vocabulary import GenderTarget

#: House concentration codes in the short form the catalog already uses.
CATALOG_CONCENTRATION: dict[str, str] = {
    "EDC": "EDC",
    "EDT": "EDT",
    "EDP": "EDP",
    "PARFUM": "Parfum",
    "EXTRAIT": "Extrait",
    "OIL": "Oil",
    "SOLID": "Solid",
}

# Spellings that name the same concentration, so "Eau de Parfum" in the
# catalog matches a house's EDP rather than reading as a different version.
_CONCENTRATION_SYNONYMS: dict[str, str] = {
    "eau de cologne": "edc",
    "cologne": "edc",
    "eau de toilette": "edt",
    "eau de parfum": "edp",
    "extrait de parfum": "extrait",
    "perfume oil": "oil",
    "attar": "oil",
    "solid perfume": "solid",
}

MAX_CANDIDATES = 20
MAX_REFERENCE = 500
#: Width of ``Fragrance.concentration``.
MAX_CONCENTRATION = 50
NOT_PENDING = "NOT_PENDING"
CANNOT_CONFIRM = "CANNOT_CONFIRM"
CATALOG_CONFLICT = "CATALOG_CONFLICT"
UNKNOWN_FRAGRANCE = "UNKNOWN_FRAGRANCE"
GENDER_TARGET_REQUIRED = "GENDER_TARGET_REQUIRED"
_NOT_PENDING_MESSAGE = (
    "This record is no longer awaiting review: it was already reviewed, or the "
    "house has since submitted a correction."
)


def _text_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _concentration_key(value: str) -> str:
    key = _text_key(value)
    return _CONCENTRATION_SYNONYMS.get(key, key)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def proposed_facts(house: str, payload: HouseSubmissionPayload) -> ProposedFacts:
    """Express the house's facts in the catalog's terms.

    Args:
        house (str): The submitting house, which is the catalog brand.
        payload (HouseSubmissionPayload): The submitted content.

    Returns:
        ProposedFacts: What the catalog would hold if every fact were accepted.
    """
    concentration: str | None = None
    if payload.concentration == "OTHER":
        concentration = payload.concentration_other
    elif payload.concentration is not None:
        concentration = CATALOG_CONCENTRATION[payload.concentration]
    gender: GenderTarget | None = (
        None
        if payload.marketed_for in (None, "not_specified")
        else payload.marketed_for
    )
    return ProposedFacts(
        name=payload.fragrance_name,
        brand=house,
        concentration=concentration,
        launch_year=payload.launch_year,
        gender_target=gender,
    )


def compare(
    proposed: ProposedFacts, fragrance: Fragrance
) -> dict[ConfirmableField, Comparison]:
    """Compare each house fact with a catalog version.

    Args:
        proposed (ProposedFacts): The house's facts in catalog terms.
        fragrance (Fragrance): The catalog version.

    Returns:
        dict[ConfirmableField, Comparison]: ``same``, ``differs``, or
            ``house_silent`` (the house gave no value) per fact.
    """
    result: dict[ConfirmableField, Comparison] = {
        "name": "same"
        if _text_key(proposed.name) == _text_key(fragrance.name)
        else "differs",
        "brand": "same"
        if _text_key(proposed.brand) == _text_key(fragrance.brand)
        else "differs",
    }
    if proposed.concentration is None:
        result["concentration"] = "house_silent"
    else:
        result["concentration"] = (
            "same"
            if _concentration_key(proposed.concentration)
            == _concentration_key(fragrance.concentration)
            else "differs"
        )
    if proposed.launch_year is None:
        result["launch_year"] = "house_silent"
    else:
        result["launch_year"] = (
            "same" if proposed.launch_year == fragrance.launch_year else "differs"
        )
    if proposed.gender_target is None:
        result["gender_target"] = "house_silent"
    else:
        result["gender_target"] = (
            "same" if proposed.gender_target == fragrance.gender_target else "differs"
        )
    return result


def _unprocessable(error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error": error, "message": message},
    )


def _conflict(error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": error, "message": message},
    )


class HouseReviewService:
    """Adopt or decline submitted house records. Managers only.

    Args:
        db (AsyncSession): Request-scoped session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.intake = HouseIntakeService(db)

    async def context(self, submission_id: str, query: str | None) -> ReviewContext:
        """Gather the submission, its facts, and likely catalog matches.

        Args:
            submission_id (str): A submitted record.
            query (str | None): Optional extra catalog search term.

        Returns:
            ReviewContext: What the review screen shows.
        """
        response = await self.intake.get(submission_id, None)
        proposed = proposed_facts(response.house, response.payload)
        conditions = [
            func.lower(Fragrance.brand) == response.house.casefold(),
            Fragrance.name.ilike(
                f"%{_escape_like(response.payload.fragrance_name)}%", escape="\\"
            ),
        ]
        if query and query.strip():
            term = f"%{_escape_like(query.strip())}%"
            conditions = [
                Fragrance.name.ilike(term, escape="\\"),
                Fragrance.brand.ilike(term, escape="\\"),
            ]
        rows = await self.db.scalars(
            select(Fragrance)
            .where(Fragrance.deleted_at.is_(None), or_(*conditions))
            .order_by(Fragrance.brand, Fragrance.name, Fragrance.concentration)
            .limit(MAX_CANDIDATES)
        )
        candidates = [
            CatalogCandidate(
                id=row.id,
                name=row.name,
                brand=row.brand,
                concentration=row.concentration,
                version_key=row.version_key,
                launch_year=row.launch_year,
                gender_target=row.gender_target,
                primary_family=row.primary_family,
                subfamily=row.subfamily,
                comparison=compare(proposed, row),
            )
            for row in rows
        ]
        # Closest matches first: the most identity facts in agreement.
        candidates.sort(
            key=lambda candidate: (
                -sum(candidate.comparison[field] == "same" for field in IDENTITY_FIELDS)
            )
        )
        return ReviewContext(
            submission=response, proposed=proposed, candidates=candidates
        )

    async def adopt(
        self, submission_id: str, manager: str, decision: AdoptInput
    ) -> HouseSubmissionResponse:
        """Adopt a submission as manufacturer-provided evidence.

        Args:
            submission_id (str): A pending submitted record.
            manager (str): The reviewing manager's username.
            decision (AdoptInput): Target version and accepted facts.

        Returns:
            HouseSubmissionResponse: The adopted record, manager view. A fact
                that cannot be accepted as given is refused with a 422; a record
                already reviewed, or a new version that would duplicate one in
                the catalog, with a 409 (raised by the helpers it calls).
        """
        row = await self._pending(submission_id)
        payload = HouseSubmissionPayload.model_validate(row.payload)
        proposed = proposed_facts(row.house, payload)

        if isinstance(decision.target, ExistingTarget):
            fragrance = await self._live_fragrance(decision.target.fragrance_id)
            fields = self._accepted_fields(
                compare(proposed, fragrance),
                decision.confirmed_fields,
                decision.apply_updates,
            )
            if "launch_year" in decision.apply_updates:
                fragrance.launch_year = proposed.launch_year
            if "gender_target" in decision.apply_updates and proposed.gender_target:
                fragrance.gender_target = proposed.gender_target
        else:
            fragrance = await self._new_fragrance(proposed, decision)
            # Built from the house's own values, so every fact the house gave
            # is, by construction, the value the new row holds.
            fields = [
                field
                for field, outcome in compare(proposed, fragrance).items()
                if outcome == "same"
            ]

        snapshot = SourceSnapshot(
            fragrance_id=fragrance.id,
            source_type="manufacturer_provided",
            # #ASSUME: data-integrity: the house chose this scope explicitly
            # at submission (HouseIntakeService.submit); the manager cannot
            # widen it, and nothing here defaults it.
            # #VERIFY: test_adopt_writes_snapshot_with_house_permission.
            permission_state=row.permission_state,
            fields=sorted(fields, key=CONFIRMABLE_FIELDS.index),
            source_url=payload.product_url,
            source_reference=self._reference(row, payload),
            verification_status="verified",
            payload={
                "house_submission_id": row.id,
                "house": row.house,
                "submitted_by": row.submitted_by,
                "submitted_at": row.submitted_at.isoformat()
                if row.submitted_at
                else None,
                "reviewed_by": manager,
                "declared": payload.model_dump(mode="json"),
            },
        )
        self.db.add(snapshot)
        await self.db.flush()

        if decision.record_perfumers:
            await self._attribute_perfumers(fragrance.id, row.id, payload)

        row = await self._claim(
            submission_id,
            "adopted",
            manager,
            decision.review_note,
            fragrance_id=fragrance.id,
            source_snapshot_id=snapshot.id,
        )
        return self.intake.to_response(row, None, manager=True)

    async def decline(
        self, submission_id: str, manager: str, decision: DeclineInput
    ) -> HouseSubmissionResponse:
        """Decline a submission with a reason the house will see.

        Args:
            submission_id (str): A pending submitted record.
            manager (str): The reviewing manager's username.
            decision (DeclineInput): The reason.

        Returns:
            HouseSubmissionResponse: The declined record, manager view.
        """
        await self._pending(submission_id)
        row = await self._claim(submission_id, "declined", manager, decision.reason)
        return self.intake.to_response(row, None, manager=True)

    async def _pending(self, submission_id: str) -> HouseSubmission:
        # Raises the same 404 a house or manager would see for a hidden row.
        await self.intake.get(submission_id, None)
        row = await self.db.get(HouseSubmission, submission_id)
        if row is None or row.review_status != "pending":
            raise _conflict(NOT_PENDING, _NOT_PENDING_MESSAGE)
        return row

    async def _claim(
        self,
        submission_id: str,
        outcome: str,
        manager: str,
        note: str | None,
        *,
        fragrance_id: str | None = None,
        source_snapshot_id: str | None = None,
    ) -> HouseSubmission:
        # #CRITICAL: concurrency: two managers reviewing the same record at
        # once must not both record an outcome (for adoption, two snapshots
        # for one statement). `_pending` above is only a fast, friendly
        # check; this conditional UPDATE is the guard. It sets the outcome
        # and its links in one statement, so exactly one transaction moves
        # the row out of `pending`; the other matches zero rows, raises 409,
        # and rolls back everything it wrote. Setting them together also
        # satisfies ck_house_submissions_adopted_complete at every step.
        # #VERIFY: test_record_can_be_reviewed_only_once.
        result = await self.db.execute(
            update(HouseSubmission)
            .where(
                HouseSubmission.id == submission_id,
                HouseSubmission.review_status == "pending",
            )
            .values(
                review_status=outcome,
                reviewed_by=manager,
                reviewed_at=now_naive_utc(),
                review_note=note.strip() if note and note.strip() else None,
                fragrance_id=fragrance_id,
                source_snapshot_id=source_snapshot_id,
            )
            .execution_options(synchronize_session=False)
            .returning(HouseSubmission.id)
        )
        if result.scalar_one_or_none() is None:
            raise _conflict(NOT_PENDING, _NOT_PENDING_MESSAGE)
        row = await self.db.get(HouseSubmission, submission_id, populate_existing=True)
        if row is None:  # pragma: no cover - the UPDATE above just matched it
            raise _conflict(NOT_PENDING, _NOT_PENDING_MESSAGE)
        return row

    async def _live_fragrance(self, fragrance_id: str) -> Fragrance:
        fragrance = await self.db.scalar(
            select(Fragrance).where(
                Fragrance.id == fragrance_id, Fragrance.deleted_at.is_(None)
            )
        )
        if fragrance is None:
            msg = "That catalog version does not exist or has been archived."
            raise _unprocessable(UNKNOWN_FRAGRANCE, msg)
        return fragrance

    @staticmethod
    def _accepted_fields(
        comparison: dict[ConfirmableField, Comparison],
        confirmed: list[ConfirmableField],
        updates: list[UpdatableField],
    ) -> list[ConfirmableField]:
        for field in updates:
            if field not in confirmed:
                msg = f"Accept {field} before applying it to the catalog."
                raise _unprocessable(CANNOT_CONFIRM, msg)
        for field in dict.fromkeys(confirmed):
            outcome = comparison[field]
            if outcome == "house_silent":
                msg = f"The house did not give a {field}, so it cannot be confirmed."
                raise _unprocessable(CANNOT_CONFIRM, msg)
            if outcome == "differs" and field in IDENTITY_FIELDS:
                msg = (
                    f"The house's {field} differs from this catalog version, which "
                    "usually means it is a different version. Match another version "
                    "or add a new one; fix a typo in the catalog first if that is all "
                    "it is."
                )
                raise _unprocessable(CANNOT_CONFIRM, msg)
            if outcome == "differs" and field not in updates:
                # Evidence must never claim a value the catalog does not hold.
                msg = f"The house's {field} differs; apply it to accept it."
                raise _unprocessable(CANNOT_CONFIRM, msg)
        return list(dict.fromkeys(confirmed))

    async def _new_fragrance(
        self, proposed: ProposedFacts, decision: AdoptInput
    ) -> Fragrance:
        target = decision.target
        if isinstance(target, ExistingTarget):  # pragma: no cover - caller checks
            msg = "Expected a new catalog version"
            raise TypeError(msg)
        if (
            proposed.concentration is None
            or len(proposed.concentration) > MAX_CONCENTRATION
        ):
            msg = "The concentration must be 50 characters or fewer for the catalog."
            raise _unprocessable(CANNOT_CONFIRM, msg)
        gender = proposed.gender_target or target.gender_target
        if gender is None:
            msg = (
                "The house did not say who it is marketed for; choose a gender target."
            )
            raise _unprocessable(GENDER_TARGET_REQUIRED, msg)
        fragrance = Fragrance(
            name=proposed.name,
            brand=proposed.brand,
            concentration=proposed.concentration,
            version_key=target.version_key,
            launch_year=proposed.launch_year,
            gender_target=gender,
            primary_family=target.primary_family,
            subfamily=target.subfamily,
            data_source="manufacturer",
        )
        self.db.add(fragrance)
        try:
            async with self.db.begin_nested():
                await self.db.flush()
        except IntegrityError as error:
            msg = (
                "That exact version (name, brand, concentration, version key) is "
                "already in the catalog. Match it instead, or use another version key."
            )
            raise _conflict(CATALOG_CONFLICT, msg) from error
        return fragrance

    async def _attribute_perfumers(
        self, fragrance_id: str, submission_id: str, payload: HouseSubmissionPayload
    ) -> None:
        citation = (
            payload.product_url
            or f"urn:fragrance-rater:house-submission:{submission_id}"
        )
        for name in dict.fromkeys(payload.perfumers):
            perfumer = await self.db.scalar(
                select(Perfumer).where(Perfumer.name == name)
            )
            if perfumer is None:
                perfumer = Perfumer(name=name)
                self.db.add(perfumer)
                await self.db.flush()
            existing = await self.db.get(VersionPerfumer, (fragrance_id, perfumer.id))
            if existing is None:
                self.db.add(
                    VersionPerfumer(
                        fragrance_id=fragrance_id,
                        perfumer_id=perfumer.id,
                        source_url=citation,
                    )
                )
        await self.db.flush()

    @staticmethod
    def _reference(row: HouseSubmission, payload: HouseSubmissionPayload) -> str:
        submitted = (
            row.submitted_at.date().isoformat() if row.submitted_at else "unknown date"
        )
        reference = (
            f"House submission {row.id} from {payload.contact_name}, "
            f"{payload.contact_role}, {row.house}, submitted {submitted}"
        )
        return reference[:MAX_REFERENCE]
