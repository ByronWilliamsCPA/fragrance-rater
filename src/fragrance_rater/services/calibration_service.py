"""Transactional controlled evaluations and identity-safe participant views."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NoReturn, cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from fragrance_rater import __version__
from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    FitChoice,
    Membership,
    Observation,
    Presentation,
    Program,
    QualityFlag,
    SessionContext,
    SourceSnapshot,
)
from fragrance_rater.models.fragrance import Fragrance, FragranceGtin
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.models.soft_delete import is_live
from fragrance_rater.services.consent import ConsentService
from fragrance_rater.services.disclosure_gate import (
    DisclosureGate,
    require_household_for_shared_labels,
)
from fragrance_rater.services.group_blotter import (
    GROUP_SHARED_BLOTTER_CODE,
    GROUP_SHARED_BLOTTER_RULE_VERSION,
)
from fragrance_rater.services.llm_service import get_llm_service
from fragrance_rater.services.shared_triples import (
    GROUP_BLOTTER_ALGORITHM,
    SHARED_TRIPLES_ALGORITHM,
    TEMPLATE_ALGORITHMS,
    TemplateError,
    TemplateMember,
    evaluator_order,
    generate_template,
    parse_randomization_record,
    randomization_record,
    recover_template,
    template_digest,
    validate_template,
)
from fragrance_rater.services.training_eligibility import TrainingEligibilityService
from fragrance_rater.services.transcription_timing import (
    check_instant,
    raise_ceiling_flag,
    seconds_over_ceiling,
)
from fragrance_rater.utils.gtin import normalize_gtin
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.calibration import (
        EnrollmentInput,
        ExposureInput,
        MembershipInput,
        ResponseInput,
        SessionEndInput,
        SessionStartInput,
        SharedTemplateInput,
    )
    from fragrance_rater.schemas.consent import SessionContextInput
    from fragrance_rater.services.shared_triples import Template


def reject(message: str, status: int = 409) -> NoReturn:
    """Raise a public domain error without disclosing hidden identity."""
    raise HTTPException(status_code=status, detail=message)


UNPINNED_INSTRUMENT_PREFIX = "unpinned-app-"

_SHARED_CODES_NEED_MAP = (
    "The program's first shared enrollment needs membership_codes: one blind "
    "code for every membership"
)
_SHARED_CODES_COVERAGE = (
    "membership_codes must cover every membership of this program, and only those"
)
_SHARED_CODES_DIFFER = (
    "membership_codes differ from the blind codes already recorded for this program"
)
_SHARED_CODES_NOT_SHARED = (
    "Earlier enrollments in this program use random blind codes, so shared "
    "codes cannot be inherited; enroll a new program for shared labels"
)
_SHARED_CODES_DISAGREE = (
    "The program's earlier enrollments disagree on the blind codes of its samples"
)
_SHARED_CODES_UNCOVERED = (
    "The program's recorded blind codes do not cover exactly the samples of its "
    "session template, so they cannot be inherited"
)
_SHARED_CODES_REUSED = (
    "The program's recorded blind codes give one code to more than one sample"
)
_SHARED_CODES_EXIST = (
    "This program already uses shared blind codes; enroll with label_scheme 'shared'"
)
_SHARED_CODES_TAKEN = "These blind codes are already used by individual presentations: "

_MODE_ALGORITHM_MISMATCH = (
    "A SHARED_GROUP program enrolls with shared-triples-group-blotter-v1 "
    "and no other program may use it"
)
_KEY_REUSED = "This idempotency key was already used for a different submission"
_TEMPLATE_DIFFERS = (
    "The session template differs from the one this program's earlier "
    "evaluators received"
)

# What enroll() actually does: a system-entropy shuffle of the baseline block,
# concealed repeats inserted with at least one session of separation, then a
# shuffle of the holdout block. Bump the suffix if that procedure changes.
RANDOMIZATION_ALGORITHM = "system-random-shuffle-v1"

# Facts about the physical sample, recorded when the sample is first exposed.
_SAMPLE_FACTS = (
    "sample_source_type",
    "sample_container",
    "sample_volume_ml",
    "sample_acquired_on",
    "sample_decanted_on",
    "sample_opened_on",
    "sample_batch_code",
    "physical_sample_confirmed",
)


# Request-only fields of a transcribed column: they validate or derive stored
# values (elapsed minutes, the exposure flag) but are not stored themselves.
_TRANSIENT_RESPONSE_FIELDS = {"sprayed_at", "confirmed_blind_code"}


def confirm_blind_code(presentation: Presentation, confirmed: str | None) -> None:
    """Refuse a write whose confirmed blind code is not this sample's code.

    The facilitator reads the code off the paper column; a mismatch means the
    column is open on the wrong sample. Under per-evaluator codes it also meant
    the wrong evaluator's enrollment; shared codes no longer carry that signal.

    Args:
        presentation (Presentation): The sample being written.
        confirmed (str | None): The code the caller read, or ``None`` when the
            caller does not confirm (ordinary, non-transcribed entry).
    """
    # #CRITICAL: data-integrity: a transcribed column keyed to the wrong sample
    # is silent corruption (observations are append-only and locked).
    # With label_scheme "shared" the code names the sample, not the evaluator:
    # every evaluator's enrollment holds the same code, so this check still
    # catches the wrong sample but no longer catches a column typed into the
    # wrong evaluator's enrollment. Do not rely on it for that.
    # #VERIFY: a transcription client always sends confirmed_blind_code; tests
    # cover a mismatch (409), a case-insensitive match, and omission. The
    # wrong-evaluator guard is procedural (docs/planning/gates/f1.md, sign-off
    # 19, consequence (a)): one recorder, one evaluator's sheets at a time, and
    # the name and paper record ID on the sheet checked against the enrollment
    # on screen before saving.
    if confirmed is not None and (
        confirmed.strip().upper() != presentation.blind_code.strip().upper()
    ):
        reject("The blind code entered does not match this sample")


def activation_instrument_version(configured: str | None) -> str:
    """Return the instrument version to record on a program at activation.

    The configured value (``INSTRUMENT_VERSION``: the frontend build SHA or an
    instrument release tag) is used when it is set and not blank. Otherwise
    the fallback is ``unpinned-app-<package version>``: a true statement of
    which application release activated the program, prefixed so an export or
    the F1 gate can tell it from a pinned instrument build.

    Args:
        configured (str | None): ``settings.instrument_version``.

    Returns:
        str: The value to store in ``Program.instrument_version``.
    """
    # #ASSUME: external-resources: the deployment sets INSTRUMENT_VERSION to
    # the build of the participant UI it serves. Nothing here can verify that
    # the browser actually loaded that build.
    # #VERIFY: the F1 gate (gates/f1.md, "Blind-baseline instrument
    # completeness") refuses a program whose value starts with
    # UNPINNED_INSTRUMENT_PREFIX.
    if configured is not None and configured.strip():
        return configured.strip()
    return f"{UNPINNED_INSTRUMENT_PREFIX}{__version__}"


def post_reveal_entry(
    enrollment: Enrollment, member: Membership, presentation: Presentation
) -> bool:
    """Whether new responses to this sample are post-reveal, not blind.

    True once the enrollment is revealed, except for a holdout whose own
    blind response is not yet locked: it stays concealed until then.
    """
    return enrollment.revealed_at is not None and (
        member.role != "HOLDOUT" or presentation.blotter_locked_at is not None
    )


def observation_payload(o: Observation) -> dict[str, object]:
    """Serialize one submitted observation's typed fields for a participant view.

    Field set matches what the previous ``**o.responses`` spread exposed
    (every ``ResponseInput`` field, plus ``id``/``phase``/``created_at``),
    so this is a like-for-like replacement of the JSON-blob spread with
    named, typed columns: no API/frontend contract change.
    """
    return {
        "id": o.id,
        "phase": o.phase,
        "created_at": o.created_at.isoformat(),
        "stage": o.stage,
        "elapsed_minutes": o.elapsed_minutes,
        "detected": o.detected,
        "intensity": o.intensity,
        "liking": o.liking,
        "confidence": o.confidence,
        "sweetness": o.sweetness,
        "freshness": o.freshness,
        "density": o.density,
        "familiarity": o.familiarity,
        "dryness": o.dryness,
        "clean_soapy": o.clean_soapy,
        "earthy_rooty": o.earthy_rooty,
        "bodily_animalic": o.bodily_animalic,
        "discomfort": o.discomfort,
        "opening_liking": o.opening_liking,
        "drydown_liking": o.drydown_liking,
        "would_wear": o.would_wear,
        "would_buy": o.would_buy,
        "artistic_appreciation": o.artistic_appreciation,
        "projection": o.projection,
        "observed_at": o.observed_at.isoformat() if o.observed_at else None,
        "response_status": o.response_status,
        "recognition": o.recognition,
        "owned_or_worn": o.owned_or_worn,
        "scrubbed_off": o.scrubbed_off,
        "time_to_scrub_minutes": o.time_to_scrub_minutes,
        "last_detected_elapsed_min": o.last_detected_elapsed_min,
        "first_not_detected_elapsed_min": o.first_not_detected_elapsed_min,
        "longevity_minutes": o.longevity_minutes,
        "perceived_notes": o.perceived_notes,
        "likes": o.likes,
        "dislikes": o.dislikes,
        "reminds_me_of": o.reminds_me_of,
        "comments": o.comments,
    }


class CalibrationService:
    """Serialize all mutations on an evaluator's enrollment row."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def program(self, program_id: str) -> Program:
        """Fetch and lock a definition before edits or activation."""
        obj = await self.db.scalar(
            select(Program).where(Program.id == program_id).with_for_update()
        )
        if obj is None:
            reject("Program not found", 404)
        assert obj is not None
        return obj

    async def _check_gtin_against_source_evidence(
        self, fragrance_id: str, gtin: str
    ) -> None:
        """Reject an operator-entered GTIN that contradicts scraped source evidence.

        # #CRITICAL: data-integrity: this is the actual gap-closing
        # mechanism a barcode is meant to provide - if the physical
        # bottle's scanned GTIN does not match a GTIN already recorded in
        # any of this fragrance's source snapshots (e.g. its Parfumo
        # page), that is a strong, mechanical signal the wrong catalog
        # version is about to be assigned, independent of any text-based
        # ambiguity. Silently accepting the operator's value in that case
        # would defeat the entire point of capturing a barcode.
        # `ParfumoScraper._save_source` appends a new snapshot on every
        # re-scrape rather than updating one in place, so a fragrance can
        # accumulate several snapshots over time - checking only the
        # newest would miss a conflict an older refresh recorded but a
        # later, GTIN-less refresh silently dropped. Absence of a
        # recorded source GTIN in a given snapshot is not evidence of
        # anything (many pages simply do not publish one - see
        # `ParfumoScraper._extract_gtin`) and is not treated as a
        # conflict.
        # #VERIFY: covered by a test asserting a mismatched GTIN is
        # rejected and a matching or absent one is accepted, including
        # when the conflict is on an older, non-latest snapshot.

        Args:
            fragrance_id (str): Catalog version being assigned.
            gtin (str): The operator-entered, already check-digit-valid GTIN.
        """
        # A snapshot whose permission is ``excluded_no_new_writes`` (the legacy
        # Parfumo rows, ADR-012) is not evidence this project may act on, so it
        # cannot veto an operator-entered GTIN; the physical bottle is the check.
        snapshots = await self.db.scalars(
            select(SourceSnapshot).where(
                SourceSnapshot.fragrance_id == fragrance_id,
                SourceSnapshot.permission_state != "excluded_no_new_writes",
            )
        )
        normalized_gtin = normalize_gtin(gtin)
        # #ASSUME: data-integrity: a GTIN names exactly one SKU, so a barcode
        # already linked (FragranceGtin, written by manufacturer adoption) to a
        # different version means the wrong version is about to be assigned. This
        # holds even when the only snapshot that would have said so is excluded.
        # #VERIFY: test_a_barcode_linked_to_another_version_is_rejected.
        holder = await self.db.get(FragranceGtin, normalized_gtin)
        if holder is not None and holder.fragrance_id != fragrance_id:
            reject("Entered GTIN is already linked to a different catalog version")
        for snapshot in snapshots:
            source_gtin = snapshot.payload.get("gtin")
            if not isinstance(source_gtin, str) or not source_gtin:
                continue
            # Normalize both sides to GTIN-14 (zero-padded) before
            # comparing: a UPC-A (GTIN-12) and the EAN-13/GTIN-14
            # encoding of the exact same product are different-length
            # strings for the identical item, and a raw string compare
            # would reject a legitimate match as a false conflict. Only
            # normalize a source value that is itself all-ASCII digits;
            # anything else falls back to the raw compare rather than
            # risk padding non-numeric scraped text into a misleading
            # match.
            normalized_source = (
                normalize_gtin(source_gtin)
                if source_gtin.isascii() and source_gtin.isdigit()
                else source_gtin
            )
            if normalized_source != normalized_gtin:
                reject(
                    "Entered GTIN does not match this fragrance's recorded "
                    "source evidence - re-check the physical bottle and the "
                    "catalog entry before assigning it"
                )

    async def add_member(self, program_id: str, data: MembershipInput) -> Membership:
        """Require explicit version evidence and consistent hidden-repeat linkage."""
        program = await self.program(program_id)
        if program.status != "draft":
            reject("Program definition is locked")
        fragrance = await self.db.scalar(
            select(Fragrance).where(Fragrance.id == data.fragrance_id).with_for_update()
        )
        if not is_live(fragrance):
            reject("Catalog version not found", 404)
        assert fragrance is not None
        if fragrance.concentration in {"", "Unknown"}:
            reject("Resolve concentration before assignment")
        if data.role == "HIDDEN_REPEAT":
            original = (
                await self.db.get(Membership, data.repeat_of_id)
                if data.repeat_of_id
                else None
            )
            if (
                original is None
                or original.program_id != program_id
                or original.fragrance_id != data.fragrance_id
                or original.role != "UNIVERSAL_BASELINE"
            ):
                reject("Hidden repeat must link to its baseline version")
        elif data.repeat_of_id is not None:
            reject("Only hidden repeats may link to an original")
        existing = list(
            await self.db.scalars(
                select(Membership).where(
                    Membership.program_id == program_id,
                    Membership.fragrance_id == data.fragrance_id,
                )
            )
        )
        if (data.role == "HOLDOUT" and existing) or any(
            x.role == "HOLDOUT" for x in existing
        ):
            reject("Holdout version cannot also be a training member")
        if data.gtin is not None:
            await self._check_gtin_against_source_evidence(data.fragrance_id, data.gtin)
        selection = dict(data.selection)
        # `selection` is a client-controlled free-form dict; never let a
        # raw "gtin" key inside it stand in for the validated, cross-
        # checked top-level `data.gtin` field, or both the check-digit
        # validation and the source-evidence conflict check above can be
        # bypassed by putting the value under "selection" instead.
        selection.pop("gtin", None)
        selection["identity_evidence"] = data.identity_evidence
        if data.gtin is not None:
            selection["gtin"] = data.gtin
        member = Membership(
            program_id=program_id,
            fragrance_id=data.fragrance_id,
            role=data.role,
            repeat_of_id=data.repeat_of_id,
            group_name=data.group_name,
            selection=selection,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def set_blotter_mode(self, program_id: str, mode: str) -> Program:
        """Choose individual or shared-group blotters before anyone is enrolled.

        Args:
            program_id (str): The program.
            mode (str): ``INDIVIDUAL`` or ``SHARED_GROUP``.

        Returns:
            Program: The updated program.
        """
        program = await self.program(program_id)
        # #CRITICAL: data-integrity: blind codes and orders are generated at
        # enrollment from this mode, so changing it afterwards would leave a
        # program with two incompatible schedules.
        # #VERIFY: test_blotter_mode_locks_after_first_enrollment (test_group_blotter_enrollment.py).
        if await self.db.scalar(
            select(Enrollment.id).where(Enrollment.program_id == program_id).limit(1)
        ):
            reject("The blotter mode is locked once an evaluator is enrolled")
        program.blotter_mode = mode
        if mode == "SHARED_GROUP":
            # #CRITICAL: security: one shared blind code per sample means one
            # evaluator's own reveal unblinds it for all, so a group program
            # reveals only as a household (DisclosureGate.effective_reveal_policy
            # enforces the same at read time for rows that predate this).
            # #VERIFY: test_setting_shared_group_forces_household_reveal.
            program.reveal_policy = "HOUSEHOLD"
        await self.db.flush()
        return program

    async def enroll(
        self, program_id: str, data: EnrollmentInput, actor: str = "system"
    ) -> Enrollment:
        """Assign blind codes and an order for one evaluator.

        Independent per evaluator by default; shared by every evaluator when
        the program's blotter mode is ``SHARED_GROUP``.

        Args:
            program_id (str): The program.
            data (EnrollmentInput): The evaluator and schedule options.
            actor (str): Who enrolled, recorded on automatic flags.

        Returns:
            Enrollment: The new enrollment with its whole schedule.
        """
        program = await self.program(program_id)
        if program.status != "active":
            reject("Activate the definition before enrollment")
        reviewer = await self.db.get(Reviewer, data.reviewer_id)
        if not is_live(reviewer):
            reject("Reviewer not found", 404)
        if await self.db.scalar(
            select(Enrollment.id).where(
                Enrollment.program_id == program_id,
                Enrollment.reviewer_id == data.reviewer_id,
            )
        ):
            reject("Reviewer already enrolled")
        await self._require_one_algorithm(program_id, data.randomization_algorithm)
        grouped = self._require_matching_mode(program, data.randomization_algorithm)
        self._require_label_scheme_allowed(program, data)
        get_llm_service().invalidate_reviewer_cache(data.reviewer_id)
        if grouped:
            return await self._enroll_group_blotter(program_id, data, actor)
        if data.randomization_algorithm == SHARED_TRIPLES_ALGORITHM:
            return await self._enroll_shared_triples(program_id, data)
        # #ASSUME: data-integrity: the schedule is drawn from the operating
        # system's entropy (SystemRandom, randbelow), which cannot be seeded, so
        # no seed is recorded. A seeded algorithm would store its seed here.
        # #VERIFY: randomization_seed stays NULL while this algorithm is used.
        enrollment = Enrollment(
            program_id=program_id,
            reviewer_id=data.reviewer_id,
            recorder_usernames=data.recorder_usernames,
            randomization_algorithm=RANDOMIZATION_ALGORITHM,
        )
        self.db.add(enrollment)
        await self.db.flush()
        members = list(
            await self.db.scalars(
                select(Membership).where(Membership.program_id == program_id)
            )
        )
        # Mix concealed repeats into the baseline with at least one session's
        # separation when enough stimuli exist. Holdouts remain a later block.
        baseline = [m for m in members if m.role not in {"HIDDEN_REPEAT", "HOLDOUT"}]
        secrets.SystemRandom().shuffle(baseline)
        for repeat in [m for m in members if m.role == "HIDDEN_REPEAT"]:
            original_index = next(
                i for i, m in enumerate(baseline) if m.id == repeat.repeat_of_id
            )
            earliest = min(original_index + 2 * data.session_size, len(baseline))
            position = earliest + secrets.randbelow(len(baseline) - earliest + 1)
            baseline.insert(position, repeat)
        holdouts = [m for m in members if m.role == "HOLDOUT"]
        secrets.SystemRandom().shuffle(holdouts)
        blocks = [baseline, holdouts]
        # #CRITICAL: timing-dependency: presentations() orders sessions by
        # (created_at, id) so the manager-facing mapping sheet reflects block
        # order (baseline before holdout). `id` is a random UUID (identifier()
        # below), which carries no creation-order signal, so a created_at tie
        # between two sessions created back-to-back in this loop makes block
        # order nondeterministic. Ties are rare but not impossible: some CI
        # runners (observed on Windows) have wall-clock resolution coarse
        # enough that two now_naive_utc() calls a few statements apart return
        # the same value. #VERIFY: tests/unit/test_api/test_calibration.py's
        # test_controlled_lifecycle_authorization_and_reveal asserts the
        # mapping's first row is the baseline fragrance, not the holdout.
        session_created_at = now_naive_utc()
        # #ASSUME: Concurrency: the enrollment ordinal below is a row count, so
        # two simultaneous standard-scheme enrollments could compute the same
        # prefix. #VERIFY: an individual (shared_blind_code false) code is
        # globally UNIQUE through a partial unique index, so a collision fails
        # the transaction loudly instead of duplicating labels. Shared codes
        # are unique per session only and do not use this prefix.
        enrollment_ordinal = (
            await self.db.scalar(select(func.count()).select_from(Enrollment)) or 1
        )
        session_number = 0
        for block in blocks:
            for offset in range(0, len(block), data.session_size):
                session_number += 1
                session = CalibrationSession(
                    enrollment_id=enrollment.id,
                    context={},
                    created_at=session_created_at,
                )
                self.db.add(session)
                await self.db.flush()
                session_created_at += timedelta(microseconds=1)
                for position, member in enumerate(
                    block[offset : offset + data.session_size], start=1
                ):
                    self.db.add(
                        Presentation(
                            session_id=session.id,
                            membership_id=member.id,
                            blind_code=(
                                f"E{enrollment_ordinal:02d}-S{session_number}-{position}"
                                if data.uses_standard_labels
                                else secrets.token_hex(4).upper()
                            ),
                            position=position,
                            intended_position=position,
                        )
                    )
        await self.db.flush()
        return enrollment

    @staticmethod
    def _require_label_scheme_allowed(program: Program, data: EnrollmentInput) -> None:
        """Refuse a label scheme the program's disclosure policy cannot protect.

        Args:
            program (Program): The program being enrolled into.
            data (EnrollmentInput): The enrollment request.
        """
        if data.label_scheme == "shared":
            require_household_for_shared_labels(program)

    @staticmethod
    def _require_matching_mode(program: Program, algorithm: str) -> bool:
        """Tie the enrollment algorithm to the program's blotter mode.

        Args:
            program (Program): The program being enrolled into.
            algorithm (str): The requested randomization algorithm.

        Returns:
            bool: Whether the program is ``SHARED_GROUP``.
        """
        grouped = program.blotter_mode == "SHARED_GROUP"
        if grouped != (algorithm == GROUP_BLOTTER_ALGORITHM):
            reject(_MODE_ALGORITHM_MISMATCH)
        return grouped

    async def _require_one_algorithm(self, program_id: str, algorithm: str) -> None:
        """Refuse to mix shared-session and independent schedules in one program.

        Shared sessions only mean something when every evaluator in the
        program follows the same template, so a program that has one kind of
        enrollment refuses the other. Programs without shared enrollments
        (every existing one) are unaffected.
        """
        existing = set(
            await self.db.scalars(
                select(Enrollment.randomization_algorithm).where(
                    Enrollment.program_id == program_id
                )
            )
        )
        shared = algorithm in TEMPLATE_ALGORITHMS
        if (shared and existing - {algorithm}) or (
            not shared and existing & TEMPLATE_ALGORITHMS
        ):
            reject("Every evaluator in a program must use the same randomization")

    async def _template_members(
        self, program_id: str, persistent_ids: list[str]
    ) -> list[TemplateMember]:
        """Load the program's memberships as template inputs."""
        members = list(
            await self.db.scalars(
                select(Membership)
                .where(Membership.program_id == program_id)
                .order_by(Membership.id)
            )
        )
        if set(persistent_ids) - {m.id for m in members}:
            reject("A persistent stimulus is not in this program", 422)
        # #ASSUME: data-integrity: no catalog or membership column records
        # whether a stimulus is exceptionally persistent or animalic, so the
        # ADR-005 "at most one per session" rule runs on what the manager
        # declares: the request's ids, or a membership selection flag.
        # #VERIFY: test_persistent_limit_rejects_two_in_one_session and
        # test_selection_flag_marks_a_persistent_stimulus.
        persistent = {
            m.id
            for m in members
            if m.id in persistent_ids
            or m.selection.get("persistent_or_animalic") in (1, "true")
        }
        # A hidden repeat is the same physical juice as its original, so it
        # is exactly as persistent.
        persistent |= {m.id for m in members if m.repeat_of_id in persistent}
        return [
            TemplateMember(
                id=m.id,
                fragrance_id=m.fragrance_id,
                role=m.role,
                repeat_of_id=m.repeat_of_id,
                persistent=m.id in persistent,
            )
            for m in members
        ]

    async def _recorded_template(
        self, program_id: str, algorithm: str = SHARED_TRIPLES_ALGORITHM
    ) -> tuple[Template, int, str]:
        """Recover the program's shared template from its enrollments.

        Args:
            program_id (str): The program.
            algorithm (str): The template algorithm the enrollments used.
                The group-blotter variant has no rotation, so each
                evaluator's order is the template itself.

        Returns:
            tuple[Template, int, str]: The canonical template, the next free
            rotation, and the first enrollment's generation seed (or "").
        """
        enrollments = list(
            await self.db.scalars(
                select(Enrollment).where(
                    Enrollment.program_id == program_id,
                    Enrollment.randomization_algorithm == algorithm,
                )
            )
        )
        if not enrollments:
            return [], 0, ""
        records = [
            (parse_randomization_record(e.randomization_seed), e) for e in enrollments
        ]
        (rotation, digest, generated), first = min(records, key=lambda r: r[0][0])
        sessions: dict[str, list[str]] = {}
        for row in await self.presentations(first.id):
            sessions.setdefault(row.session_id, []).append(row.membership_id)
        if algorithm == GROUP_BLOTTER_ALGORITHM:
            template = [list(ids) for ids in sessions.values()]
        else:
            template = recover_template(list(sessions.values()), rotation)
        # #CRITICAL: data-integrity: every later evaluator must receive exactly
        # the template the first one did. A recorded digest that no longer
        # matches the stored presentations means the schedule was altered, so
        # enrollment stops rather than propagating a different composition.
        # #VERIFY: test_tampered_recorded_template_fails_loudly.
        if template_digest(template) != digest or any(
            record[1] != digest for record, _ in records
        ):
            reject("The program's recorded session template is inconsistent", 500)
        next_rotation = max(record[0] for record, _ in records) + 1
        return template, next_rotation, generated or ""

    async def shared_template(
        self,
        program_id: str,
        data: SharedTemplateInput,
        *,
        group: bool | None = None,
    ) -> tuple[Template, list[TemplateMember], int, str | None, str]:
        """Resolve and validate the template the next shared enrollment uses.

        Order of precedence: the template already recorded for the program
        (a supplied one must match it), then a manager-supplied template,
        then a newly generated one.

        Args:
            program_id (str): The program.
            data (SharedTemplateInput): Session size, optional template, and
                persistent stimuli.
            group (bool | None): ``True`` for the group-blotter variant (one
                shared order, no rotation); ``None`` reads it from the
                program's blotter mode.

        Returns:
            tuple[Template, list[TemplateMember], int, str | None, str]: The
            template, members, next rotation (the evaluator's ordinal in the
            group-blotter variant), generation seed (None when supplied), and
            the source (recorded/supplied/generated).
        """
        if group is None:
            program = await self.db.get(Program, program_id)
            if program is None:
                reject("Program not found", 404)
            group = program.blotter_mode == "SHARED_GROUP"
        rotate = not group
        members = await self._template_members(
            program_id, data.persistent_membership_ids
        )
        recorded, rotation, recorded_seed = await self._recorded_template(
            program_id, GROUP_BLOTTER_ALGORITHM if group else SHARED_TRIPLES_ALGORITHM
        )
        generated: str | None = None
        if recorded:
            if data.session_template is not None and data.session_template != recorded:
                reject(_TEMPLATE_DIFFERS)
            template, source = recorded, "recorded"
            generated = recorded_seed or None
        elif data.session_template is not None:
            template, source = data.session_template, "supplied"
        else:
            # Not a secret: the seed only makes the generated order
            # reproducible, and it is stored on the enrollment for audit.
            generated = secrets.token_hex(8)
            try:
                template = generate_template(
                    members, data.session_size, generated, rotate=rotate
                )
            except TemplateError as error:
                reject(str(error), 422)
            source = "generated"
        try:
            validate_template(template, members, data.session_size, rotate=rotate)
        except TemplateError as error:
            reject(str(error), 422)
        return template, members, rotation, generated, source

    async def _unique_codes(self, count: int) -> list[str]:
        """Draw random blind codes unused anywhere, retrying on collision."""
        codes: set[str] = set()
        for _ in range(20):
            while len(codes) < count:
                codes.add(secrets.token_hex(4).upper())
            taken = set(
                await self.db.scalars(
                    select(Presentation.blind_code).where(
                        Presentation.blind_code.in_(codes)
                    )
                )
            )
            if not taken:
                return list(codes)
            codes -= taken
        reject("Could not draw unique blind codes; retry the enrollment", 503)

    async def _recorded_shared_codes(self, program_id: str) -> dict[str, str] | None:
        """Return the blind code every earlier enrollment gave each membership.

        Args:
            program_id (str): The program.

        Returns:
            dict[str, str] | None: Membership id to its one recorded code, or
            ``None`` when the program has no presentations yet.
        """
        rows = (
            await self.db.execute(
                select(
                    Presentation.membership_id,
                    Presentation.blind_code,
                    Presentation.shared_blind_code,
                )
                .join(CalibrationSession)
                .join(Enrollment)
                .where(Enrollment.program_id == program_id)
            )
        ).all()
        if not rows:
            return None
        # #CRITICAL: data-integrity: a shared code is only meaningful if every
        # evaluator holds the same one for a sample. Earlier rows that are
        # non-shared, or that disagree, are refused instead of guessed at.
        # #VERIFY: test_earlier_non_shared_codes_block_a_shared_enrollment and
        # test_earlier_enrollments_that_disagree_are_refused_not_guessed.
        if not all(shared for _, _, shared in rows):
            reject(_SHARED_CODES_NOT_SHARED)
        recorded: dict[str, set[str]] = {}
        for membership_id, code, _ in rows:
            recorded.setdefault(membership_id, set()).add(code)
        if any(len(codes) != 1 for codes in recorded.values()):
            reject(_SHARED_CODES_DISAGREE)
        assigned = {mid: next(iter(codes)) for mid, codes in recorded.items()}
        if len(set(assigned.values())) != len(assigned):
            reject(_SHARED_CODES_REUSED)
        return assigned

    async def _shared_label_codes(
        self,
        program_id: str,
        template: Template,
        supplied: dict[str, str] | None,
    ) -> dict[str, str]:
        """Resolve the one blind code per membership for a shared-label enrollment.

        Later enrollments reuse the recorded codes exactly. The first one must
        supply a code for every membership, none of which may already be an
        individual code.

        Args:
            program_id (str): The program.
            template (Template): The program's shared session template.
            supplied (dict[str, str] | None): The request's ``membership_codes``.

        Returns:
            dict[str, str]: Membership id to its shared blind code.
        """
        ids = {mid for session in template for mid in session}
        recorded = await self._recorded_shared_codes(program_id)
        if recorded is not None:
            if set(recorded) != ids:
                reject(_SHARED_CODES_UNCOVERED)
            if supplied is not None and supplied != recorded:
                reject(_SHARED_CODES_DIFFER)
            return recorded
        if supplied is None:
            reject(_SHARED_CODES_NEED_MAP, 422)
        if set(supplied) != ids:
            reject(_SHARED_CODES_COVERAGE, 422)
        # #ASSUME: data-integrity: the schema already made the codes distinct
        # and well formed; the only collision left is with another program's
        # individual (non-shared) code, which the partial unique index would
        # otherwise surface as an opaque IntegrityError at flush.
        # #VERIFY: test_a_code_colliding_with_an_existing_individual_code_is_refused.
        taken = sorted(
            await self.db.scalars(
                select(Presentation.blind_code).where(
                    Presentation.blind_code.in_(set(supplied.values())),
                    Presentation.shared_blind_code.is_(False),
                )
            )
        )
        if taken:
            reject(_SHARED_CODES_TAKEN + ", ".join(taken))
        return dict(supplied)

    async def _enroll_shared_triples(
        self, program_id: str, data: EnrollmentInput
    ) -> Enrollment:
        """Enroll one evaluator on the program's shared session template.

        Every evaluator gets the same sessions in the same order; inside each
        session the order follows a balanced Latin-square row chosen by the
        evaluator's rotation and the session number. Codes are random and
        evaluator-specific, except with ``label_scheme="shared"``, where each
        membership carries one code for every evaluator (see
        ``_shared_label_codes``).
        """
        # #ASSUME: concurrency: enroll() holds the program row lock
        # (SELECT ... FOR UPDATE in program()) for the whole transaction, so
        # two first enrollments cannot generate two different templates and
        # two later ones cannot take the same rotation.
        # #VERIFY: on SQLite the lock is a no-op; production runs PostgreSQL.
        # #CRITICAL: concurrency: a shared-label enrollment reads the codes the
        # program's earlier enrollments recorded and then writes the same ones.
        # The program row lock above serializes two enrollments of one program,
        # so the second reads the first's committed presentations (READ
        # COMMITTED re-reads after the lock) and cannot record a different code.
        # #VERIFY: PostgreSQL only; on SQLite the lock is a no-op and the unit
        # tests exercise the same reads sequentially (test_shared_label_enrollment.py).
        template, _, rotation, generated, _ = await self.shared_template(
            program_id, data
        )
        shared_codes: dict[str, str] | None = None
        if data.label_scheme == "shared":
            shared_codes = await self._shared_label_codes(
                program_id, template, data.membership_codes
            )
        elif await self.db.scalar(
            select(Presentation.id)
            .join(CalibrationSession)
            .join(Enrollment)
            .where(
                Enrollment.program_id == program_id,
                Presentation.shared_blind_code.is_(True),
            )
            .limit(1)
        ):
            reject(_SHARED_CODES_EXIST)
        enrollment = Enrollment(
            program_id=program_id,
            reviewer_id=data.reviewer_id,
            recorder_usernames=data.recorder_usernames,
            randomization_algorithm=SHARED_TRIPLES_ALGORITHM,
            randomization_seed=randomization_record(
                rotation, template_digest(template), generated
            ),
        )
        self.db.add(enrollment)
        await self.db.flush()
        order = evaluator_order(template, rotation)
        codes = iter(
            await self._unique_codes(sum(len(s) for s in order))
            if shared_codes is None
            else []
        )
        # Same created_at tie-break as enroll(): presentations() orders
        # sessions by (created_at, id), so each session is one microsecond
        # later than the previous one.
        session_created_at = now_naive_utc()
        for session_ids in order:
            session = CalibrationSession(
                enrollment_id=enrollment.id, context={}, created_at=session_created_at
            )
            self.db.add(session)
            await self.db.flush()
            session_created_at += timedelta(microseconds=1)
            for position, membership_id in enumerate(session_ids, start=1):
                self.db.add(
                    Presentation(
                        session_id=session.id,
                        membership_id=membership_id,
                        blind_code=(
                            next(codes)
                            if shared_codes is None
                            else shared_codes[membership_id]
                        ),
                        shared_blind_code=shared_codes is not None,
                        position=position,
                        intended_position=position,
                    )
                )
        await self.db.flush()
        return enrollment

    async def _group_codes(self, program_id: str, template: Template) -> dict[str, str]:
        """Return the one blind code each stimulus carries for the whole group.

        The first group enrollment draws a fresh random code per stimulus
        (unused anywhere else); later enrollments reuse exactly those codes.

        Args:
            program_id (str): The program.
            template (Template): The program's shared session template.

        Returns:
            dict[str, str]: Membership id to its shared blind code.
        """
        rows = (
            await self.db.execute(
                select(Presentation.membership_id, Presentation.blind_code)
                .join(CalibrationSession)
                .join(Enrollment)
                .where(
                    Enrollment.program_id == program_id,
                    Enrollment.randomization_algorithm == GROUP_BLOTTER_ALGORITHM,
                )
            )
        ).all()
        recorded: dict[str, set[str]] = {}
        for membership_id, code in rows:
            recorded.setdefault(membership_id, set()).add(code)
        ids = [mid for session in template for mid in session]
        if not recorded:
            return dict(zip(ids, await self._unique_codes(len(ids)), strict=True))
        # #CRITICAL: data-integrity: every evaluator must hold the same code
        # for a sample, or the facilitator's one blotter would match a
        # different code on each paper sheet.
        # #VERIFY: test_group_codes_tamper_fails_loudly.
        if set(recorded) != set(ids) or any(len(c) != 1 for c in recorded.values()):
            reject("The program's recorded group blind codes are inconsistent", 500)
        return {mid: next(iter(codes)) for mid, codes in recorded.items()}

    async def _enroll_group_blotter(
        self, program_id: str, data: EnrollmentInput, actor: str
    ) -> Enrollment:
        """Enroll one evaluator on a SHARED_GROUP program's one shared schedule.

        Every evaluator gets the same sessions, the same order inside each
        session, and the same blind code per sample (one blotter per sample is
        passed around the group). Each session is flagged
        ``group_shared_blotter`` automatically; the flag is informational and
        never changes training eligibility.
        """
        # #ASSUME: concurrency: enroll() holds the program row lock (SELECT ...
        # FOR UPDATE in program()) for the whole transaction, so two first
        # enrollments cannot draw two code sets or generate two templates.
        # #VERIFY: on SQLite the lock is a no-op; production runs PostgreSQL.
        template, _, ordinal, generated, _ = await self.shared_template(
            program_id, data, group=True
        )
        codes = await self._group_codes(program_id, template)
        enrollment = Enrollment(
            program_id=program_id,
            reviewer_id=data.reviewer_id,
            recorder_usernames=data.recorder_usernames,
            randomization_algorithm=GROUP_BLOTTER_ALGORITHM,
            randomization_seed=randomization_record(
                ordinal, template_digest(template), generated
            ),
        )
        self.db.add(enrollment)
        await self.db.flush()
        # Same created_at tie-break as enroll().
        session_created_at = now_naive_utc()
        for session_ids in template:
            session = CalibrationSession(
                enrollment_id=enrollment.id, context={}, created_at=session_created_at
            )
            self.db.add(session)
            await self.db.flush()
            session_created_at += timedelta(microseconds=1)
            for position, membership_id in enumerate(session_ids, start=1):
                self.db.add(
                    Presentation(
                        session_id=session.id,
                        membership_id=membership_id,
                        blind_code=codes[membership_id],
                        shared_blind_code=True,
                        position=position,
                        intended_position=position,
                    )
                )
            self.db.add(
                QualityFlag(
                    session_id=session.id,
                    action="raised",
                    code=GROUP_SHARED_BLOTTER_CODE,
                    severity="info",
                    source="automatic_validation",
                    disposition="include",
                    rule_version=GROUP_SHARED_BLOTTER_RULE_VERSION,
                    explanation=(
                        "Group blotter: one blotter per sample was passed around "
                        "the group, so the blind code and the sample order are "
                        "shared with the other evaluators. Informational only; "
                        "training eligibility is unchanged."
                    ),
                    recorded_by=actor,
                )
            )
        await self.db.flush()
        return enrollment

    async def _blotter_mode(self, program_id: str) -> str:
        """Return a program's blotter mode (``INDIVIDUAL`` when it is gone)."""
        program = await self.db.get(Program, program_id)
        return program.blotter_mode if program is not None else "INDIVIDUAL"

    async def enrollment(
        self, enrollment_id: str, username: str, admin: bool
    ) -> Enrollment:
        """Enforce explicit recorder grants; never infer reviewer from username."""
        obj = await self.db.scalar(
            select(Enrollment).where(Enrollment.id == enrollment_id).with_for_update()
        )
        if obj is None:
            reject("Enrollment not found", 404)
        assert obj is not None
        if not admin and username not in obj.recorder_usernames:
            reject("Recorder is not assigned to this evaluator", 403)
        return obj

    async def presentations(self, enrollment_id: str) -> list[Presentation]:
        """List presentation records for internal use only."""
        return list(
            await self.db.scalars(
                select(Presentation)
                .join(CalibrationSession)
                .where(CalibrationSession.enrollment_id == enrollment_id)
                .order_by(
                    CalibrationSession.created_at,
                    CalibrationSession.id,
                    Presentation.position,
                )
            )
        )

    async def has_started(self, presentation_ids: set[str]) -> bool:
        """True if any Observation exists for any of the given presentations.

        Reports raw participation regardless of lock state, distinct from
        `blotter_locked_at`/`skin_locked_at`: an evaluator who has answered
        but not yet locked a sample has still "started."
        """
        if not presentation_ids:
            return False
        return (
            await self.db.scalar(
                select(Observation.id).where(
                    Observation.presentation_id.in_(presentation_ids)
                )
            )
        ) is not None

    async def target(
        self, presentation_id: str, username: str, admin: bool
    ) -> tuple[Presentation, Enrollment]:
        """Resolve a target through enrollment authorization and locking."""
        obj = await self.db.get(Presentation, presentation_id)
        if obj is None:
            reject("Presentation not found", 404)
        assert obj is not None
        session = await self.db.get(CalibrationSession, obj.session_id)
        assert session is not None
        enrollment = await self.enrollment(session.enrollment_id, username, admin)
        # Refresh after acquiring the enrollment lock: another transaction may have locked it.
        await self.db.refresh(obj)
        return obj, enrollment

    async def observe(
        self,
        presentation_id: str,
        data: ResponseInput,
        username: str,
        admin: bool,
        post_reveal: bool = False,
    ) -> Observation:
        """Append responses only; no update route exists for submitted observations.

        Args:
            presentation_id (str): The presentation answered.
            data (ResponseInput): The submitted answers.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.
            post_reveal (bool): Whether this is an informed post-reveal entry.

        Returns:
            Observation: The appended row, or the earlier row a same-key replay
                names.
        """
        observation, _ = await self.observe_once(
            presentation_id, data, username, admin, post_reveal=post_reveal
        )
        return observation

    async def _replayed(
        self,
        presentation: Presentation,
        data: ResponseInput,
        post_reveal: bool,
    ) -> Observation | None:
        """Return the row an idempotency key already names, or ``None``.

        D-22/Q18: a retried POST (a flaky phone connection, a double tap)
        carries the same key and must not append a second row. The same key
        with a different payload is not a retry: it is refused with 409 rather
        than silently answered with a row that does not match the request.

        Args:
            presentation (Presentation): The presentation, already authorized.
            data (ResponseInput): The submitted answers.
            post_reveal (bool): Which endpoint the request came through.

        Returns:
            Observation | None: The earlier row, when this is a faithful replay.
        """
        if data.idempotency_key is None:
            return None
        existing = await self.db.scalar(
            select(Observation).where(
                Observation.presentation_id == presentation.id,
                Observation.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            return None
        submitted = cast(
            "dict[str, object]",
            data.model_dump(
                exclude={
                    "idempotency_key",
                    "observed_at",
                    "season_fit",
                    "setting_fit",
                    *_TRANSIENT_RESPONSE_FIELDS,
                }
            ),
        )
        same = all(
            cast("object", getattr(existing, name)) == value
            for name, value in submitted.items()
        )
        # A request without observed_at was stamped with the server's receipt
        # time on first write, so only an explicit time must match.
        same = same and (
            data.observed_at is None or data.observed_at == existing.observed_at
        )
        same = same and (existing.phase == "POST_REVEAL") == post_reveal
        fit = {
            (choice.dimension, choice.code)
            for choice in await self.db.scalars(
                select(FitChoice).where(FitChoice.observation_id == existing.id)
            )
        }
        sent = {("season", code) for code in data.season_fit or []} | {
            ("setting", code) for code in data.setting_fit or []
        }
        if not same or fit != sent:
            reject(_KEY_REUSED, 409)
        return existing

    async def observe_once(
        self,
        presentation_id: str,
        data: ResponseInput,
        username: str,
        admin: bool,
        post_reveal: bool = False,
    ) -> tuple[Observation, bool]:
        """Append one observation, or answer a same-key replay with the original.

        Args:
            presentation_id (str): The presentation answered.
            data (ResponseInput): The submitted answers.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.
            post_reveal (bool): Whether this is an informed post-reveal entry.

        Returns:
            tuple[Observation, bool]: The row, and ``True`` when it already
                existed (a replay; nothing was written).
        """
        obj, enrollment = await self.target(presentation_id, username, admin)
        confirm_blind_code(obj, data.confirmed_blind_code)
        # #ASSUME: concurrency: target() holds the enrollment row lock, so two
        # concurrent requests with one key run this check one after the other
        # and the second sees the first's committed row.
        # #VERIFY: the unique constraint (presentation_id, idempotency_key)
        # is the backstop; tests/integration/test_r8_hardening_postgres.py
        # proves PostgreSQL rejects a second row with the same key.
        replay = await self._replayed(obj, data, post_reveal)
        if replay is not None:
            return replay, True
        member = await self.db.get(Membership, obj.membership_id)
        assert member is not None
        await DisclosureGate(self.db).require_open(
            enrollment,
            [member.role],
            instants=[
                ("The column-finished time", data.observed_at),
                ("The spray time", data.sprayed_at),
            ],
        )
        identity_visible = post_reveal_entry(enrollment, member, obj)
        if post_reveal:
            if not identity_visible:
                reject("Identity has not been revealed")
        else:
            if identity_visible:
                reject("Blind collection ended at reveal")
            if data.stage == "SKIN" and obj.skin_reason is None:
                reject("Skin test must be planned")
            if (data.stage == "BLOTTER" and obj.blotter_locked_at) or (
                data.stage == "SKIN" and obj.skin_locked_at
            ):
                reject("Stage is locked; original responses are retained")
            await self._check_observation_times(obj, data)
        prior_exposure = await self.db.scalar(
            select(Enrollment.id)
            .join(CalibrationSession, CalibrationSession.enrollment_id == Enrollment.id)
            .join(Presentation, Presentation.session_id == CalibrationSession.id)
            .join(Membership, Presentation.membership_id == Membership.id)
            .where(
                Enrollment.reviewer_id == enrollment.reviewer_id,
                Enrollment.revealed_at.is_not(None),
                Membership.fragrance_id == member.fragrance_id,
                Enrollment.id != enrollment.id,
                or_(
                    Membership.role != "HOLDOUT",
                    Presentation.blotter_locked_at.is_not(None),
                ),
            )
        )
        phase = (
            "POST_REVEAL"
            if post_reveal
            else ("PREVIOUSLY_REVEALED" if prior_exposure else "PRE_REVEAL")
        )
        # `data` already carries one field per typed Observation column below
        # it (see the Observation docstring), so the remaining perceptual/
        # temporal/free-text fields are splatted rather than repeated here.
        typed_fields = data.model_dump(
            exclude={
                "stage",
                "elapsed_minutes",
                "detected",
                "intensity",
                "liking",
                "season_fit",
                "setting_fit",
                *_TRANSIENT_RESPONSE_FIELDS,
            }
        )
        # #ASSUME: timing-dependency: observed_at is the client's clock at submit
        # (or the recorder's explicit transcription time). When the client sends
        # none, the server's receipt time stands in, which is what the column
        # held implicitly before R7b via created_at, so it is never NULL for new
        # rows. #VERIFY: a recorder transcribing late sends observed_at; the
        # schema rejects stamps in the future.
        if typed_fields["observed_at"] is None:
            typed_fields["observed_at"] = now_naive_utc()
        observation = Observation(
            presentation_id=obj.id,
            stage=data.stage,
            phase=phase,
            elapsed_minutes=data.elapsed_minutes,
            detected=data.detected,
            intensity=data.intensity,
            liking=data.liking,
            recorded_by=username,
            **typed_fields,
        )
        self.db.add(observation)
        await self.db.flush()
        for dimension, choices in (
            ("season", data.season_fit),
            ("setting", data.setting_fit),
        ):
            for code in choices or []:
                self.db.add(
                    FitChoice(
                        observation_id=observation.id, dimension=dimension, code=code
                    )
                )
        await self.db.flush()
        # R8 option C: eligible once its stage is locked and no flag covers it.
        await TrainingEligibilityService(self.db).observation_written(
            observation, actor=username
        )
        await self.db.flush()
        return observation, False

    async def _check_observation_times(
        self, presentation: Presentation, data: ResponseInput
    ) -> None:
        """Validate the explicit times of a transcribed blotter column.

        Only times the caller supplied are checked (a missing ``observed_at``
        is stamped with the server's receipt time, which is always in range).
        The column cannot finish before the blotter was first smelled.
        """
        session = await self.db.get(CalibrationSession, presentation.session_id)
        if session is None:
            reject("Session not found", 404)
        for label, instant in (
            ("The column-finished time", data.observed_at),
            ("The spray time", data.sprayed_at),
        ):
            if instant is not None:
                check_instant(instant, session, label)
        # #ASSUME: timing-dependency: presented_at (first smell) was stamped from
        # the same paper sheet, so a later column cannot end before it.
        # #VERIFY: tests/unit/test_services/test_transcription_timing.py.
        if (
            data.stage == "BLOTTER"
            and data.observed_at is not None
            and presentation.presented_at is not None
            and data.observed_at < presentation.presented_at
        ):
            message = "The column cannot finish before the blotter was first smelled"
            raise HTTPException(status_code=422, detail=message)

    async def session_target(
        self, session_id: str, username: str, admin: bool
    ) -> tuple[CalibrationSession, Enrollment]:
        """Resolve a session through enrollment authorization.

        Args:
            session_id (str): The calibration session.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            tuple[CalibrationSession, Enrollment]: The session and its enrollment.
        """
        session = await self.db.get(CalibrationSession, session_id)
        if session is None:
            reject("Session not found", 404)
        assert session is not None
        enrollment = await self.enrollment(session.enrollment_id, username, admin)
        return session, enrollment

    async def start_session(
        self, session_id: str, data: SessionStartInput, username: str, admin: bool
    ) -> CalibrationSession:
        """Record when and where a session actually began.

        Args:
            session_id (str): The calibration session.
            data (SessionStartInput): Zone and optional client start time.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            CalibrationSession: The session with its timing set.
        """
        session, enrollment = await self.session_target(session_id, username, admin)
        gate = DisclosureGate(self.db)
        await gate.require_open(enrollment, await gate.session_roles(session.id))
        if session.started_at is not None:
            reject("Session already started")
        if data.started_at is not None:
            check_instant(data.started_at, session, "The session start time")
        started = data.started_at or now_naive_utc()
        session.started_at = started
        session.evaluator_timezone = data.evaluator_timezone
        # The local calendar date, so a session that crosses midnight UTC still
        # has the day the evaluator experienced it on.
        session.occurred_on = (
            started.replace(tzinfo=UTC)
            .astimezone(ZoneInfo(data.evaluator_timezone))
            .date()
        )
        await self.db.flush()
        return session

    async def end_session(
        self, session_id: str, data: SessionEndInput, username: str, admin: bool
    ) -> CalibrationSession:
        """Record when a started session actually ended.

        Args:
            session_id (str): The calibration session.
            data (SessionEndInput): Optional client end time.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            CalibrationSession: The session with its end time set.
        """
        session, _ = await self.session_target(session_id, username, admin)
        if session.started_at is None:
            reject("Start the session before ending it")
        if session.ended_at is not None:
            reject("Session already ended")
        # #ASSUME: timing-dependency: an end before the start can only come from a
        # wrong client clock. Capture assessment 13.3 keeps mistimed evidence and
        # flags it rather than refusing it, so it is stored as given.
        # #VERIFY: a quality flag (timestamp_inconsistent) is how a reviewer marks it.
        if data.ended_at is not None:
            check_instant(data.ended_at, session, "The session end time")
        session.ended_at = data.ended_at or now_naive_utc()
        await self.db.flush()
        return session

    async def record_session_context(
        self,
        session_id: str,
        data: SessionContextInput,
        username: str,
        admin: bool,
    ) -> SessionContext:
        """Record self-reported conditions, only while consent for them stands.

        Args:
            session_id (str): The calibration session.
            data (SessionContextInput): The refusable answers.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            SessionContext: The stored answers.
        """
        session, enrollment = await self.session_target(session_id, username, admin)
        await ConsentService(self.db).require_granted(
            enrollment.reviewer_id, "session_context"
        )
        if await self.db.scalar(
            select(SessionContext.id).where(SessionContext.session_id == session.id)
        ):
            reject("Session context is already recorded")
        context = SessionContext(
            session_id=session.id, recorded_by=username, **data.model_dump()
        )
        self.db.add(context)
        await self.db.flush()
        return context

    async def session_context(
        self, session_id: str, username: str, admin: bool
    ) -> SessionContext | None:
        """Read a session's recorded conditions, or ``None`` if none were recorded.

        Args:
            session_id (str): The calibration session.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            SessionContext | None: The answers, if any.
        """
        session, _ = await self.session_target(session_id, username, admin)
        return await self.db.scalar(
            select(SessionContext).where(SessionContext.session_id == session.id)
        )

    async def record_exposure(
        self, presentation_id: str, data: ExposureInput, username: str, admin: bool
    ) -> Presentation:
        """Stamp the first blotter smell or skin application of a sample.

        Args:
            presentation_id (str): The presentation.
            data (ExposureInput): The stage, instant, and sample facts.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            Presentation: The presentation with its exposure facts set.
        """
        obj, _ = await self.record_exposure_checked(
            presentation_id, data, username, admin
        )
        return obj

    async def record_exposure_checked(
        self, presentation_id: str, data: ExposureInput, username: str, admin: bool
    ) -> tuple[Presentation, QualityFlag | None]:
        """Stamp an exposure and report a spray-to-first-smell deviation.

        With ``data.sprayed_at`` set, a first smell later than the ceiling is
        recorded and flagged ``spray_to_smell_ceiling_exceeded`` in the same
        transaction; the exposure is never refused or dropped for it.

        Args:
            presentation_id (str): The presentation.
            data (ExposureInput): The stage, instants, and sample facts.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            tuple[Presentation, QualityFlag | None]: The presentation, and the
                ceiling flag when this exposure breached the ceiling.
        """
        obj, enrollment = await self.target(presentation_id, username, admin)
        confirm_blind_code(obj, data.confirmed_blind_code)
        member = await self.db.get(Membership, obj.membership_id)
        assert member is not None
        await DisclosureGate(self.db).require_open(
            enrollment,
            [member.role],
            instants=[
                ("The first-smell time", data.at),
                ("The spray time", data.sprayed_at),
            ],
        )
        if post_reveal_entry(enrollment, member, obj):
            reject("Blind collection ended at reveal")
        session = await self.db.get(CalibrationSession, obj.session_id)
        assert session is not None
        for label, instant in (
            ("The first-smell time", data.at),
            ("The spray time", data.sprayed_at),
        ):
            if instant is not None:
                check_instant(instant, session, label)
        at = data.at or now_naive_utc()
        flag: QualityFlag | None = None
        if data.stage == "BLOTTER":
            flag = await self._stamp_blotter(obj, data, at, username)
        else:
            if obj.skin_reason is None:
                reject("Skin test must be planned")
            if obj.applied_at is not None:
                reject("Skin application already recorded")
            obj.applied_at = at
            obj.application_timezone = data.timezone or session.evaluator_timezone
            obj.application_method = data.application_method
            obj.application_dose_sprays = data.application_dose_sprays
        for name in _SAMPLE_FACTS:
            value = cast("object", getattr(data, name))
            if value is None:
                continue
            current = cast("object", getattr(obj, name))
            if current is not None and current != value:
                reject(f"{name} is already recorded for this sample")
            setattr(obj, name, value)
        await self.db.flush()
        return obj, flag

    async def _stamp_blotter(
        self, presentation: Presentation, data: ExposureInput, at: datetime, actor: str
    ) -> QualityFlag | None:
        """Set the first-smell time once; flag a breach of the spray ceiling."""
        if presentation.presented_at is not None:
            reject("Blotter exposure already recorded")
        presentation.presented_at = at
        if data.sprayed_at is None or seconds_over_ceiling(data.sprayed_at, at) <= 0:
            return None
        await self.db.flush()
        return await raise_ceiling_flag(
            self.db,
            presentation,
            sprayed_at=data.sprayed_at,
            smelled_at=at,
            actor=actor,
        )

    async def lock_stage(
        self, presentation_id: str, stage: str, username: str, admin: bool
    ) -> None:
        """Lock a stage only after at least one detection answer is submitted."""
        obj, enrollment = await self.target(presentation_id, username, admin)
        member = await self.db.get(Membership, obj.membership_id)
        assert member is not None
        await DisclosureGate(self.db).require_open(enrollment, [member.role])
        if enrollment.revealed_at is not None and member.role != "HOLDOUT":
            reject("Blind collection ended at reveal")
        if stage not in {"BLOTTER", "SKIN"} or (
            stage == "SKIN" and not obj.skin_reason
        ):
            reject("Invalid stage")
        answered = await self.db.scalar(
            select(Observation.id).where(
                Observation.presentation_id == obj.id,
                Observation.stage == stage,
                Observation.phase.in_(["PRE_REVEAL", "PREVIOUSLY_REVEALED"]),
                Observation.detected.is_not(None),
            )
        )
        if answered is None:
            reject("Submit a detection response before locking")
        if stage == "BLOTTER":
            obj.blotter_locked_at = obj.blotter_locked_at or now_naive_utc()
        else:
            obj.skin_locked_at = obj.skin_locked_at or now_naive_utc()
        await self.db.flush()
        # R8 option C: a locked stage's unflagged observations become eligible.
        await TrainingEligibilityService(self.db).stage_locked(
            obj, stage, actor=username
        )
        await self.db.flush()

    async def reveal(self, enrollment_id: str, username: str, admin: bool) -> None:
        """Reveal only after baseline, repeats, and the finalized skin plan are locked.

        ``HOUSEHOLD`` programs refuse this per-evaluator reveal; their manager
        reveals every enrollment together (``DisclosureGate.reveal_household``).
        """
        enrollment = await self.enrollment(enrollment_id, username, admin)
        await DisclosureGate(self.db).require_enrollment_reveal_allowed(enrollment)
        if enrollment.revealed_at:
            return
        presentations = await self.presentations(enrollment_id)
        members = {
            member.id: member
            for member in await self.db.scalars(
                select(Membership).where(
                    Membership.id.in_({obj.membership_id for obj in presentations})
                )
            )
        }
        blocker = self.reveal_blocker(enrollment, presentations, members)
        if blocker == "SKIN_PLAN":
            reject("Finalize the planned skin tests before reveal")
        if blocker == "BLOTTER":
            reject("All blind blotter responses must be locked")
        if blocker == "SKIN":
            reject("All planned blind skin tests must be locked")
        enrollment.revealed_at = now_naive_utc()
        enrollment.revealed_by = username
        get_llm_service().invalidate_reviewer_cache(enrollment.reviewer_id)
        await self.db.flush()

    @staticmethod
    def reveal_blocker(
        enrollment: Enrollment,
        presentations: list[Presentation],
        members: dict[str, Membership],
    ) -> str | None:
        """Return a disclosure-safe reason that currently prevents reveal."""
        if enrollment.skin_plan_locked_at is None:
            return "SKIN_PLAN"
        if any(
            members[obj.membership_id].role != "HOLDOUT"
            and obj.blotter_locked_at is None
            for obj in presentations
        ):
            return "BLOTTER"
        if any(obj.skin_reason and obj.skin_locked_at is None for obj in presentations):
            return "SKIN"
        return None

    async def participant_view(self, enrollment: Enrollment) -> dict[str, object]:
        """Build an allowlisted payload; never serialize hidden ORM rows."""
        presentations = await self.presentations(enrollment.id)
        membership_ids = {obj.membership_id for obj in presentations}
        members = {
            member.id: member
            for member in await self.db.scalars(
                select(Membership).where(Membership.id.in_(membership_ids))
            )
        }
        presentation_ids = {obj.id for obj in presentations}
        gate = DisclosureGate(self.db)
        holdouts_open = await gate.holdouts_open(enrollment)
        observations_by_presentation: dict[str, list[Observation]] = {
            presentation_id: [] for presentation_id in presentation_ids
        }
        for observation in await self.db.scalars(
            select(Observation)
            .where(Observation.presentation_id.in_(presentation_ids))
            .order_by(Observation.created_at, Observation.id)
        ):
            observations_by_presentation[observation.presentation_id].append(
                observation
            )
        fragrance_ids = {member.fragrance_id for member in members.values()}
        fragrances = (
            {
                fragrance.id: fragrance
                for fragrance in await self.db.scalars(
                    select(Fragrance)
                    .where(Fragrance.id.in_(fragrance_ids))
                    # Required, not an optimisation: this session is async, so a
                    # lazy load of `perfumers` while building the payload raises
                    # MissingGreenlet rather than issuing a query.
                    .options(selectinload(Fragrance.perfumers))
                )
            }
            if enrollment.revealed_at
            else {}
        )
        result: list[dict[str, object]] = []
        for obj in presentations:
            row: dict[str, object] = {
                "id": obj.id,
                "session_id": obj.session_id,
                "blind_code": obj.blind_code,
                "position": obj.position,
                "skin_planned": obj.skin_reason is not None,
                "blotter_locked": obj.blotter_locked_at is not None,
                "skin_locked": obj.skin_locked_at is not None,
                # When the blotter was first smelled (the paper's time, set by
                # the exposure call); null until then. Lets a transcribing
                # client resume a column without stamping the exposure twice.
                "presented_at": obj.presented_at.isoformat()
                if obj.presented_at
                else None,
            }
            observations = observations_by_presentation[obj.id]
            row["observations"] = [observation_payload(o) for o in observations]
            member = members[obj.membership_id]
            # False only while the holdout gate holds this sample closed; the
            # client must not offer it. Says nothing about lock state.
            row["available"] = holdouts_open or member.role != "HOLDOUT"
            # The server, not the client, says which entry form applies
            # (architecture review F-15); it is true exactly when the identity
            # below is disclosed, so it carries no information beyond it.
            row["post_reveal_entry"] = post_reveal_entry(enrollment, member, obj)
            # Holdout identities stay concealed until their own blind response is locked.
            if row["post_reveal_entry"]:
                fragrance = fragrances[member.fragrance_id]
                # #CRITICAL: security: perfumer belongs inside this block and
                # nowhere else in the participant payload. An attribution
                # narrows a fragrance as sharply as its name does -- a family
                # member who knows the perfumer can often identify the sample
                # outright -- so it is disclosed on exactly the same condition
                # as brand, name and concentration (ADR-005), never alongside
                # a blind code.
                # #VERIFY: e2e-smoke/disclosure-and-authorization.spec.ts
                # asserts the pre-reveal payload carries no perfumer, against a
                # real backend rather than a mock.
                row["identity"] = {
                    "fragrance_id": fragrance.id,
                    "name": fragrance.name,
                    "brand": fragrance.brand,
                    "concentration": fragrance.concentration,
                    "perfumers": [
                        {"name": attribution.name, "source_url": attribution.source_url}
                        for attribution in fragrance.perfumers
                    ],
                }
            result.append(row)
        reveal_blocker = (
            None if enrollment.revealed_at else await gate.reveal_blocker(enrollment)
        )
        return {
            "id": enrollment.id,
            "program_id": enrollment.program_id,
            "reviewer_id": enrollment.reviewer_id,
            "revealed": enrollment.revealed_at is not None,
            "reveal_eligible": reveal_blocker is None
            and enrollment.revealed_at is None,
            "reveal_blocker": reveal_blocker,
            "skin_plan_locked": enrollment.skin_plan_locked_at is not None,
            "reveal_policy": await gate.policy(enrollment.program_id),
            "blotter_mode": await self._blotter_mode(enrollment.program_id),
            "presentations": result,
        }
