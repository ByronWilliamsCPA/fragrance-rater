"""P1.4 PostgreSQL concurrency gate for calibration membership and enrollment.

Exercises the two mutation races the P1 release-readiness runbook names under
"Concurrency and disclosure": simultaneous membership mutation attempts (here,
two managers racing to assign the same fragrance as a program's holdout) and
simultaneous enrollment attempts (two recorders racing to enroll the same
reviewer). Both rely on real PostgreSQL row locking (``SELECT ... FOR UPDATE``
and a unique constraint) that SQLite's test suite cannot exercise under true
concurrency, so this only runs against the target engine.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fragrance_rater.models.calibration import Enrollment, Membership, Program
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.calibration import EnrollmentInput, MembershipInput
from fragrance_rater.services.calibration_service import CalibrationService
from fragrance_rater.services.disclosure_gate import HOUSEHOLD, DisclosureGate
from fragrance_rater.utils.timestamps import now_naive_utc

DATABASE_URL = os.getenv("P1_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(not DATABASE_URL, reason="P1_DATABASE_URL is not configured"),
]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_holdout_assignment_leaves_exactly_one_membership() -> None:
    """Two managers racing to add the same fragrance as HOLDOUT: only one wins.

    ``add_member`` locks the target ``Fragrance`` row with
    ``with_for_update()`` before checking whether the fragrance already has a
    holdout membership. Under true concurrency (two separate connections,
    not two calls on one session) the second transaction must block on that
    lock, then see the first transaction's committed row and reject rather
    than racing past the check-then-act gap and creating two holdout rows
    for the same fragrance.
    """
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex

    try:
        async with session_factory() as setup_session:
            fragrance = Fragrance(
                name=f"P1.4 concurrency scent {suffix}",
                brand="P1 gate house",
                concentration="EDP",
                version_key=f"p1-4-{suffix}",
                gender_target="Unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="p1-gate",
            )
            program = Program(
                name=f"P1.4 concurrency program {suffix}",
                version="v1",
                description=None,
                status="draft",
            )
            setup_session.add_all([fragrance, program])
            await setup_session.commit()
            fragrance_id, program_id = fragrance.id, program.id

        # #CRITICAL: timing-dependency: asyncio.gather schedules both
        # coroutines but does not guarantee either has opened its session
        # before the other starts racing for the lock; without a rendezvous,
        # one attempt can run to completion before the second even begins,
        # silently degrading this into two sequential calls instead of a
        # true concurrent race.
        # #VERIFY: the barrier forces both attempts to have their session
        # open and be ready to issue the locking call before either
        # proceeds, so the second write() always finds the first's `SELECT
        # ... FOR UPDATE` already in flight.
        barrier = asyncio.Barrier(2)

        async def attempt() -> str:
            async with session_factory() as session:
                service = CalibrationService(session)
                await barrier.wait()
                member = await service.add_member(
                    program_id,
                    MembershipInput(
                        fragrance_id=fragrance_id,
                        role="HOLDOUT",
                        identity_evidence="P1.4 concurrency gate",
                    ),
                )
                await session.commit()
                return member.id

        try:
            # #CRITICAL: timing-dependency: this test assumes PostgreSQL's
            # default READ COMMITTED isolation level, under which the second
            # transaction's `with_for_update()` blocks on the first
            # transaction's row lock and then sees the first transaction's
            # just-committed row once that lock releases. A session or
            # database configured for a stricter isolation level
            # (REPEATABLE READ/SERIALIZABLE) could instead let the blocked
            # transaction re-read pre-commit state or raise a serialization
            # failure, neither of which is the clean single-winner/
            # single-409 outcome asserted below.
            # #VERIFY: DATABASE_URL must point at a database left on
            # PostgreSQL's default READ COMMITTED isolation with no
            # session-level override; this test would need revisiting if
            # that default ever changes.
            results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
            successes: list[str] = []
            rejections: list[HTTPException] = []
            for result in results:
                if isinstance(result, str):
                    successes.append(result)
                elif isinstance(result, HTTPException):
                    rejections.append(result)
                else:
                    pytest.fail(
                        "unexpected result type "
                        f"{type(result).__name__}: {result!r} "
                        f"(full results: {results!r})"
                    )
            assert len(successes) == 1, f"expected exactly one winner, got {results!r}"
            assert len(rejections) == 1, (
                f"expected exactly one rejection, got {results!r}"
            )
            assert rejections[0].status_code == 409, (
                f"expected a 409 Conflict rejection, got {results!r}"
            )

            async with session_factory() as verify_session:
                rows = list(
                    await verify_session.scalars(
                        select(Membership).where(
                            Membership.program_id == program_id,
                            Membership.fragrance_id == fragrance_id,
                        )
                    )
                )
            assert len(rows) == 1, "the race must not leave two holdout memberships"
        finally:
            # #CRITICAL: concurrency: this suite shares a database with other
            # PostgreSQL-gated tests within one CI run (each test creates its
            # own uniquely-suffixed rows, but nothing recreates the database
            # between files). The recommendation measurement gate queries the
            # whole fragrance catalog for a reviewer, so a fragrance left
            # behind here would silently become a candidate in that unrelated
            # test. Clean up rather than relying on run order.
            # #VERIFY: cleanup runs inside this `finally` block so it executes
            # even when an assertion above (results classification or row
            # verification) fails; without it, a failed assertion would skip
            # straight past the deletes and leak the row.
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(Membership).where(Membership.program_id == program_id)
                )
                await cleanup_session.execute(
                    delete(Program).where(Program.id == program_id)
                )
                await cleanup_session.execute(
                    delete(Fragrance).where(Fragrance.id == fragrance_id)
                )
                await cleanup_session.commit()
    finally:
        # #CRITICAL: concurrency: engine.dispose() must run even if setup,
        # the attempts, or an assertion raises, or this engine's connection
        # pool leaks for the rest of the test session.
        # #VERIFY: this outer `finally` always runs regardless of where in
        # the try block an exception originates.
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_duplicate_enrollment_leaves_exactly_one_enrollment() -> None:
    """Two recorders racing to enroll the same reviewer: only one row persists.

    ``enroll`` takes a ``SELECT ... FOR UPDATE`` lock on the parent
    ``Program`` row (via ``CalibrationService.program``) before its
    existing-enrollment check, so under real PostgreSQL locking the two
    attempts fully serialize on that row: the second transaction blocks
    until the first commits, then sees the first's already-committed
    ``Enrollment`` row and takes the clean 409 path. That means this race is
    decided by the Program lock, not by the ``UniqueConstraint("program_id",
    "reviewer_id")`` on ``Enrollment`` itself; this test still classifies an
    ``IntegrityError`` as an acceptable loser outcome, since that is what
    would surface if the Program lock were ever removed or narrowed, but the
    409-from-app-check path is what this test actually exercises today.
    """
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex

    try:
        async with session_factory() as setup_session:
            reviewer = Reviewer(name=f"P1.4 concurrency reviewer {suffix}")
            program = Program(
                name=f"P1.4 concurrency enroll program {suffix}",
                version="v1",
                description=None,
                status="active",
            )
            setup_session.add_all([reviewer, program])
            await setup_session.commit()
            reviewer_id, program_id = reviewer.id, program.id

        # #CRITICAL: timing-dependency: without a rendezvous, asyncio.gather
        # does not guarantee both attempts have opened their session before
        # either races for the Program lock; the barrier below forces both
        # to be ready before either issues its locking call. See the
        # matching comment in
        # test_concurrent_holdout_assignment_leaves_exactly_one_membership.
        barrier = asyncio.Barrier(2)

        async def attempt() -> str:
            async with session_factory() as session:
                service = CalibrationService(session)
                await barrier.wait()
                enrollment = await service.enroll(
                    program_id,
                    EnrollmentInput(
                        reviewer_id=reviewer_id,
                        recorder_usernames=["p1-gate"],
                    ),
                )
                await session.commit()
                return enrollment.id

        try:
            results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
            successes: list[str] = []
            failures: list[HTTPException | IntegrityError] = []
            for result in results:
                if isinstance(result, str):
                    successes.append(result)
                elif isinstance(result, HTTPException):
                    # #CRITICAL: concurrency: only a 409 Conflict is the
                    # documented app-level rejection this race can produce
                    # (`CalibrationService.enroll`'s pre-insert existence
                    # check calls `reject("Reviewer already enrolled")`,
                    # which defaults to 409). Any other status here means
                    # something unrelated to the race went wrong (e.g. a 404
                    # from a bad reviewer_id, a 403, or a 500) and must not
                    # be mistaken for the expected loser outcome.
                    # #VERIFY: fail loudly instead of silently accepting it.
                    if result.status_code != 409:
                        pytest.fail(
                            "expected the loser to be rejected with a 409 "
                            f"Conflict, but got HTTPException(status_code="
                            f"{result.status_code}, detail={result.detail!r}) "
                            f"(full results: {results!r})"
                        )
                    failures.append(result)
                elif isinstance(result, IntegrityError):
                    # #CRITICAL: concurrency: `IntegrityError` is what
                    # SQLAlchemy raises for the `UniqueConstraint("program_id",
                    # "reviewer_id")` violation on `Enrollment` when both
                    # transactions pass the app-level existence check before
                    # either commits (asyncpg surfaces this as a
                    # UniqueViolationError wrapped in IntegrityError). This is
                    # deliberately narrower than `DBAPIError`, which also
                    # covers unrelated failures (timeouts, connection drops,
                    # deadlocks) that must not be mistaken for the expected
                    # loser outcome.
                    # #VERIFY: the sibling `elif isinstance(result,
                    # DBAPIError)` branch below fails loudly on any other
                    # DBAPIError subtype instead of silently accepting it.
                    failures.append(result)
                elif isinstance(result, DBAPIError):
                    pytest.fail(
                        "expected a unique-constraint IntegrityError from "
                        f"the race, but got {type(result).__name__}: "
                        f"{result!r} (full results: {results!r})"
                    )
                else:
                    pytest.fail(
                        "unexpected result type "
                        f"{type(result).__name__}: {result!r} "
                        f"(full results: {results!r})"
                    )
            assert len(successes) == 1, f"expected exactly one winner, got {results!r}"
            assert len(failures) == 1, f"expected exactly one failure, got {results!r}"

            async with session_factory() as verify_session:
                rows = list(
                    await verify_session.scalars(
                        select(Enrollment).where(
                            Enrollment.program_id == program_id,
                            Enrollment.reviewer_id == reviewer_id,
                        )
                    )
                )
            assert len(rows) == 1, (
                "the unique constraint must prevent a duplicate enrollment"
            )
        finally:
            # #CRITICAL: concurrency: this suite shares a database with
            # other PostgreSQL-gated tests within one CI run, so a row left
            # behind by a failed assertion above could leak into an
            # unrelated test the same way a leftover Fragrance would (see
            # the matching comment in
            # test_concurrent_holdout_assignment_leaves_exactly_one_membership).
            # #VERIFY: cleanup runs inside this `finally` block so it
            # executes even when an assertion above fails.
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(Enrollment).where(Enrollment.program_id == program_id)
                )
                await cleanup_session.execute(
                    delete(Program).where(Program.id == program_id)
                )
                await cleanup_session.execute(
                    delete(Reviewer).where(Reviewer.id == reviewer_id)
                )
                await cleanup_session.commit()
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrollment_waits_for_a_household_reveal() -> None:
    """A new enrollment cannot slip into a household mid-reveal.

    ``reveal_household`` locks the program row before it reads and reveals the
    enrollments. ``DisclosureGate.require_enrollment_open`` must take the same
    lock before its own read: it then blocks until the reveal commits, sees
    ``revealed_at``, and refuses with 409. Without the lock it would read the
    pre-reveal state and let an unrevealed evaluator into a disclosed household.
    """
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex

    try:
        async with session_factory() as setup_session:
            reviewer = Reviewer(name=f"F1 household reviewer {suffix}")
            program = Program(
                name=f"F1 household program {suffix}",
                version="v1",
                description=None,
                status="active",
                reveal_policy=HOUSEHOLD,
            )
            setup_session.add_all([reviewer, program])
            await setup_session.commit()
            reviewer_id, program_id = reviewer.id, program.id
            enrollment = await CalibrationService(setup_session).enroll(
                program_id,
                EnrollmentInput(reviewer_id=reviewer_id, recorder_usernames=["f1"]),
            )
            await setup_session.commit()
            enrollment_id = enrollment.id

        locked = asyncio.Event()
        release = asyncio.Event()

        async def reveal() -> None:
            """Stand in for reveal_household: lock, reveal, hold, commit."""
            async with session_factory() as session:
                await session.execute(
                    select(Program.id).where(Program.id == program_id).with_for_update()
                )
                revealed = await session.get(Enrollment, enrollment_id)
                assert revealed is not None
                revealed.revealed_at = now_naive_utc()
                await session.flush()
                locked.set()
                await release.wait()
                await session.commit()

        async def check() -> None:
            async with session_factory() as session:
                await locked.wait()
                await DisclosureGate(session).require_enrollment_open(program_id)

        try:
            revealing = asyncio.create_task(reveal())
            checking = asyncio.create_task(check())
            # #ASSUME: timing-dependency: 0.5 s is ample for an unlocked read to
            # finish on a local or CI PostgreSQL; a check still pending then is
            # blocked on the program row lock, which is what this asserts.
            # #VERIFY: without the lock the check returns at once (no error)
            # and the assertions below fail, so the test cannot pass vacuously.
            await locked.wait()
            await asyncio.sleep(0.5)
            assert not checking.done(), "the check must wait for the reveal's lock"
            release.set()
            await revealing
            with pytest.raises(HTTPException) as refused:
                await checking
            assert refused.value.status_code == 409
            assert "already revealed" in str(refused.value.detail)
        finally:
            release.set()
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(Enrollment).where(Enrollment.program_id == program_id)
                )
                await cleanup_session.execute(
                    delete(Program).where(Program.id == program_id)
                )
                await cleanup_session.execute(
                    delete(Reviewer).where(Reviewer.id == reviewer_id)
                )
                await cleanup_session.commit()
    finally:
        await engine.dispose()
