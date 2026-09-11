"""Tests for evaluation API endpoints.

Covers Major finding 9: creating an evaluation against a nonexistent
fragrance_id or reviewer_id must return a clean 404, not silently succeed
(SQLite, FKs off by default in tests) or 500 (Postgres, FK violation).
"""

import sqlite3

import pytest

from fragrance_rater.core.config import settings

API_PREFIX = "/api/v1"


async def _create_reviewer(test_app, name: str) -> str:
    """Create a reviewer via the API and return its id."""
    response = await test_app.post(f"{API_PREFIX}/reviewers", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


async def _create_fragrance(test_app, name: str, brand: str = "Brand") -> str:
    """Create a fragrance via the API and return its id."""
    response = await test_app.post(
        f"{API_PREFIX}/fragrances",
        json={
            "name": name,
            "brand": brand,
            "concentration": "EDP",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_evaluation(
    test_app, reviewer_id: str, fragrance_id: str, rating: int = 4, **extra
) -> dict:
    """Create an evaluation via the API and return its response body."""
    payload = {
        "fragrance_id": fragrance_id,
        "reviewer_id": reviewer_id,
        "rating": rating,
        **extra,
    }
    response = await test_app.post(f"{API_PREFIX}/evaluations", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
class TestCreateEvaluationAPI:
    """Tests for POST /evaluations."""

    async def test_create_evaluation_success(self, test_app):
        """A valid fragrance_id and reviewer_id should create the evaluation."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Eval Create Tester"},
        )
        assert reviewer_resp.status_code == 201
        reviewer_id = reviewer_resp.json()["id"]

        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Eval Create Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        assert fragrance_resp.status_code == 201
        fragrance_id = fragrance_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["fragrance_id"] == fragrance_id
        assert data["reviewer_id"] == reviewer_id

    async def test_create_evaluation_nonexistent_fragrance_returns_404(self, test_app):
        """A nonexistent fragrance_id must 404, not 500 or silently insert."""
        reviewer_resp = await test_app.post(
            f"{API_PREFIX}/reviewers",
            json={"name": "Eval FK Tester Fragrance"},
        )
        reviewer_id = reviewer_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": "nonexistent-fragrance",
                "reviewer_id": reviewer_id,
                "rating": 4,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "FRAGRANCE_NOT_FOUND"

    async def test_create_evaluation_nonexistent_reviewer_returns_404(self, test_app):
        """A nonexistent reviewer_id must 404, not 500 or silently insert."""
        fragrance_resp = await test_app.post(
            f"{API_PREFIX}/fragrances",
            json={
                "name": "Eval FK Tester Reviewer Fragrance",
                "brand": "Brand",
                "concentration": "EDP",
                "gender_target": "Unisex",
                "primary_family": "woody",
                "subfamily": "aromatic",
            },
        )
        fragrance_id = fragrance_resp.json()["id"]

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": "nonexistent-reviewer",
                "rating": 4,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "REVIEWER_NOT_FOUND"

    async def test_create_evaluation_both_fk_missing_reports_fragrance_first(
        self, test_app
    ):
        """When both FKs are invalid, the fragrance check runs first and is
        reported; this pins down the documented check order.
        """
        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": "nonexistent-fragrance",
                "reviewer_id": "nonexistent-reviewer",
                "rating": 3,
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "FRAGRANCE_NOT_FOUND"

    async def test_repeated_encounters_retain_history(self, test_app):
        """New submissions preserve dated ratings; correction edits one encounter."""
        reviewer_id = await _create_reviewer(test_app, "Encounter Tester")
        fragrance_id = await _create_fragrance(test_app, "Encounter Fragrance")
        payload = {"fragrance_id": fragrance_id, "reviewer_id": reviewer_id}
        first = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={**payload, "rating": 4, "evaluated_at": "2026-09-10T12:00:00-07:00"},
        )
        second = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={**payload, "rating": 2, "evaluated_at": "2026-09-11T10:00:00Z"},
        )
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] != second.json()["id"]
        assert first.json()["evaluated_at"] == "2026-09-10T19:00:00"
        history = await test_app.get(
            f"{API_PREFIX}/evaluations", params={"reviewer_id": reviewer_id}
        )
        assert [row["rating"] for row in history.json()] == [2, 4]
        correction = await test_app.patch(
            f"{API_PREFIX}/evaluations/{second.json()['id']}", json={"rating": 3}
        )
        assert correction.status_code == 200
        original = await test_app.get(f"{API_PREFIX}/evaluations/{first.json()['id']}")
        assert original.json()["rating"] == 4
        deleted = await test_app.delete(
            f"{API_PREFIX}/evaluations/{second.json()['id']}"
        )
        assert deleted.status_code == 204
        history = await test_app.get(
            f"{API_PREFIX}/evaluations", params={"reviewer_id": reviewer_id}
        )
        assert [row["id"] for row in history.json()] == [first.json()["id"]]


@pytest.mark.asyncio
class TestListEvaluationsAPI:
    """Tests for GET /evaluations.

    Important finding: this route previously had zero coverage.
    """

    async def test_list_evaluations_no_filter_returns_empty(self, test_app):
        """The route documents this as a safety default, not an accident:
        omitting both reviewer_id and fragrance_id returns [], never a
        full unscoped dump.
        """
        reviewer_id = await _create_reviewer(test_app, "List No Filter Reviewer")
        fragrance_id = await _create_fragrance(test_app, "List No Filter Fragrance")
        await _create_evaluation(test_app, reviewer_id, fragrance_id)

        response = await test_app.get(f"{API_PREFIX}/evaluations")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_evaluations_by_reviewer_id(self, test_app):
        """Filtering by reviewer_id returns only that reviewer's evaluations."""
        reviewer_id = await _create_reviewer(test_app, "List By Reviewer")
        other_reviewer_id = await _create_reviewer(test_app, "List By Reviewer Other")
        fragrance_id = await _create_fragrance(test_app, "List By Reviewer Fragrance")
        other_fragrance_id = await _create_fragrance(
            test_app, "List By Reviewer Fragrance Other"
        )
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)
        await _create_evaluation(test_app, other_reviewer_id, other_fragrance_id)

        response = await test_app.get(
            f"{API_PREFIX}/evaluations?reviewer_id={reviewer_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == evaluation["id"]

    async def test_list_evaluations_by_fragrance_id(self, test_app):
        """Filtering by fragrance_id returns only that fragrance's evaluations."""
        reviewer_id = await _create_reviewer(test_app, "List By Fragrance Reviewer")
        other_reviewer_id = await _create_reviewer(
            test_app, "List By Fragrance Reviewer Other"
        )
        fragrance_id = await _create_fragrance(test_app, "List By Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)
        other_evaluation = await _create_evaluation(
            test_app, other_reviewer_id, fragrance_id
        )

        response = await test_app.get(
            f"{API_PREFIX}/evaluations?fragrance_id={fragrance_id}"
        )
        assert response.status_code == 200
        data = response.json()
        ids = {e["id"] for e in data}
        assert ids == {evaluation["id"], other_evaluation["id"]}


@pytest.mark.asyncio
class TestGetEvaluationAPI:
    """Tests for GET /evaluations/{evaluation_id}.

    Important finding: this route previously had zero coverage.
    """

    async def test_get_evaluation_by_id(self, test_app):
        """The happy path returns the evaluation's full response shape."""
        reviewer_id = await _create_reviewer(test_app, "Get Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Get Eval Fragrance")
        evaluation = await _create_evaluation(
            test_app, reviewer_id, fragrance_id, rating=3, notes="solid"
        )

        response = await test_app.get(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == evaluation["id"]
        assert data["rating"] == 3
        assert data["notes"] == "solid"

    async def test_get_evaluation_not_found(self, test_app):
        """A nonexistent id 404s with the documented error code."""
        response = await test_app.get(f"{API_PREFIX}/evaluations/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "EVALUATION_NOT_FOUND"

    async def test_get_evaluation_soft_deleted_returns_404(self, test_app):
        """A soft-deleted evaluation is indistinguishable from nonexistent."""
        reviewer_id = await _create_reviewer(test_app, "Get Deleted Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Get Deleted Eval Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        delete_resp = await test_app.delete(
            f"{API_PREFIX}/evaluations/{evaluation['id']}"
        )
        assert delete_resp.status_code == 204

        response = await test_app.get(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "EVALUATION_NOT_FOUND"


@pytest.mark.asyncio
class TestUpdateEvaluationAPI:
    """Tests for PATCH /evaluations/{evaluation_id}.

    Important finding: this route previously had zero coverage. Also
    exercises the omitted-vs-explicit-null PATCH boundary fixed in
    schemas/evaluation.py by a different agent in this same session (see
    tests/unit/test_schemas/test_evaluation.py for the schema-level
    coverage of that fix; these are the API-level equivalents).
    """

    async def test_update_evaluation_partial(self, test_app):
        """A partial PATCH updates only the supplied field."""
        reviewer_id = await _create_reviewer(test_app, "Patch Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Patch Eval Fragrance")
        evaluation = await _create_evaluation(
            test_app, reviewer_id, fragrance_id, rating=3, notes="ok"
        )

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert data["notes"] == "ok"

    async def test_update_evaluation_omitted_field_left_unchanged(self, test_app):
        """Omitting a field from the PATCH body leaves its current value."""
        reviewer_id = await _create_reviewer(test_app, "Patch Omit Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Patch Omit Fragrance")
        evaluation = await _create_evaluation(
            test_app,
            reviewer_id,
            fragrance_id,
            rating=4,
            longevity_rating=3,
            sillage_rating=2,
        )

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert data["longevity_rating"] == 3
        assert data["sillage_rating"] == 2

    async def test_update_evaluation_explicit_null_rating_rejected(self, test_app):
        """An explicit null for the non-nullable rating field is a clean
        422 (the other agent's schemas/evaluation.py fix), not a raw
        IntegrityError, and the row must be left untouched.
        """
        reviewer_id = await _create_reviewer(test_app, "Patch Null Rating Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Patch Null Rating Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": None},
        )
        assert response.status_code == 422

        unchanged = await test_app.get(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert unchanged.json()["rating"] == evaluation["rating"]

    async def test_update_evaluation_explicit_null_clears_nullable_notes(
        self, test_app
    ):
        """An explicit null for the nullable notes field clears it."""
        reviewer_id = await _create_reviewer(test_app, "Patch Null Notes Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Patch Null Notes Fragrance")
        evaluation = await _create_evaluation(
            test_app, reviewer_id, fragrance_id, notes="to be cleared"
        )

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"notes": None},
        )
        assert response.status_code == 200
        assert response.json()["notes"] is None

    async def test_update_evaluation_not_found(self, test_app):
        """A PATCH against a nonexistent id 404s."""
        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/nonexistent-id",
            json={"rating": 5},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "EVALUATION_NOT_FOUND"

    async def test_update_evaluation_rating_out_of_range_returns_422(self, test_app):
        """An out-of-range rating (outside 1-5) is a 422."""
        reviewer_id = await _create_reviewer(test_app, "Patch Range Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Patch Range Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": 6},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestDeleteEvaluationAPI:
    """Tests for DELETE /evaluations/{evaluation_id}.

    Important finding: this route previously had zero coverage.
    """

    async def test_delete_evaluation_removes_from_subsequent_gets(self, test_app):
        """A soft-deleted evaluation 404s on a subsequent GET."""
        reviewer_id = await _create_reviewer(test_app, "Delete Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Delete Eval Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        response = await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert response.status_code == 204

        get_response = await test_app.get(
            f"{API_PREFIX}/evaluations/{evaluation['id']}"
        )
        assert get_response.status_code == 404

    async def test_delete_evaluation_sets_deleted_at_column(self, test_app, tmp_path):
        """The row's deleted_at column is actually populated, not just
        hidden from subsequent GETs; this pins the "soft" in soft-delete
        by reading the underlying SQLite file directly (`test_app` and
        this test share the same function-scoped `tmp_path`, so `test.db`
        is the same file `test_app`'s override_get_db writes to).
        """
        reviewer_id = await _create_reviewer(test_app, "Deleted At Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Deleted At Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        response = await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert response.status_code == 204

        conn = sqlite3.connect(tmp_path / "test.db")
        try:
            row = conn.execute(
                "SELECT deleted_at FROM evaluations WHERE id = ?",
                (evaluation["id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] is not None

    async def test_delete_evaluation_not_found(self, test_app):
        """A DELETE against a nonexistent id 404s."""
        response = await test_app.delete(f"{API_PREFIX}/evaluations/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "EVALUATION_NOT_FOUND"

    async def test_delete_evaluation_already_deleted_returns_404(self, test_app):
        """A second DELETE against an already soft-deleted id 404s (delete()
        excludes already-deleted rows via the same get_by_id filter used
        for reads).
        """
        reviewer_id = await _create_reviewer(test_app, "Double Delete Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Double Delete Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        first = await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert first.status_code == 204

        second = await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert second.status_code == 404
        assert second.json()["detail"]["error"] == "EVALUATION_NOT_FOUND"


@pytest.mark.asyncio
class TestEvaluationAuthentikRequired:
    """Important finding: of the ~9 mutating routes gated by
    ``Depends(get_current_identity)``, only ``create_reviewer`` (see
    ``TestReviewerAuthentikRequired`` in test_reviewers.py) had a test
    actually confirming the dependency is enforced. This class adds that
    coverage for all three evaluations mutating routes.
    """

    async def test_create_evaluation_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        reviewer_id = await _create_reviewer(test_app, "Auth Create Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Auth Create Eval Fragrance")
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 4,
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_create_evaluation_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        reviewer_id = await _create_reviewer(test_app, "Auth Create Eval OK Reviewer")
        fragrance_id = await _create_fragrance(
            test_app, "Auth Create Eval OK Fragrance"
        )
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/evaluations",
            json={
                "fragrance_id": fragrance_id,
                "reviewer_id": reviewer_id,
                "rating": 4,
            },
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 201
        assert response.json()["recorded_by"] == "byron"

    async def test_update_evaluation_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        reviewer_id = await _create_reviewer(test_app, "Auth Patch Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Auth Patch Eval Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": 5},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_update_evaluation_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        reviewer_id = await _create_reviewer(test_app, "Auth Patch Eval OK Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Auth Patch Eval OK Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.patch(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            json={"rating": 5},
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 200
        assert response.json()["rating"] == 5

    async def test_delete_evaluation_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        reviewer_id = await _create_reviewer(test_app, "Auth Delete Eval Reviewer")
        fragrance_id = await _create_fragrance(test_app, "Auth Delete Eval Fragrance")
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.delete(f"{API_PREFIX}/evaluations/{evaluation['id']}")
        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_delete_evaluation_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the mutation through."""
        reviewer_id = await _create_reviewer(test_app, "Auth Delete Eval OK Reviewer")
        fragrance_id = await _create_fragrance(
            test_app, "Auth Delete Eval OK Fragrance"
        )
        evaluation = await _create_evaluation(test_app, reviewer_id, fragrance_id)

        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.delete(
            f"{API_PREFIX}/evaluations/{evaluation['id']}",
            headers={"X-Authentik-Username": "byron"},
        )
        assert response.status_code == 204
