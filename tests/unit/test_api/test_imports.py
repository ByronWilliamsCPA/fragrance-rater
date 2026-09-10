"""Tests for the Kaggle CSV import API endpoint.

Important finding: of the ~9 mutating routes gated by
``Depends(get_current_identity)``, only ``create_reviewer`` (see
``TestReviewerAuthentikRequired`` in test_reviewers.py) had a test actually
confirming the dependency is enforced. This adds that coverage for
``import_kaggle_csv``, the one gated mutating route living outside
fragrances/evaluations/reviewers.
"""

import io

import pytest

from fragrance_rater.core.config import settings

API_PREFIX = "/api/v1"

# A minimal, syntactically valid CSV; the auth dependency is checked before
# the route body ever parses this, so its content only needs to satisfy the
# route's own ".csv" filename check for the request to reach that point.
_MINIMAL_CSV = b"name,brand,concentration,gender,family\n"


@pytest.mark.asyncio
class TestImportKaggleCsvAuthentikRequired:
    """Critical finding 2 / Important finding: import_kaggle_csv fails
    closed when Authentik is required, same as the other mutating routes.
    """

    async def test_import_rejected_without_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A missing X-Authentik-Username must 401 when authentik_required
        is True.
        """
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/import/kaggle",
            files={"file": ("fragrances.csv", io.BytesIO(_MINIMAL_CSV), "text/csv")},
            params={"dry_run": True},
        )

        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "AUTHENTIK_IDENTITY_REQUIRED"

    async def test_import_succeeds_with_identity_header(
        self, test_app, monkeypatch: pytest.MonkeyPatch
    ):
        """A valid X-Authentik-Username header allows the request through to
        the route's normal logic. dry_run=True so nothing is written.
        """
        monkeypatch.setattr(settings, "authentik_required", True)

        response = await test_app.post(
            f"{API_PREFIX}/import/kaggle",
            files={"file": ("fragrances.csv", io.BytesIO(_MINIMAL_CSV), "text/csv")},
            params={"dry_run": True},
            headers={"X-Authentik-Username": "byron"},
        )

        assert response.status_code == 200
