"""Unit tests for the rate-limit exception-handler adapter.

``rate_limit_exceeded_handler`` narrows Starlette's generic
``(Request, Exception) -> Response`` handler signature to the single
``RateLimitExceeded`` type it is actually registered for in ``main.py``.
The defensive ``TypeError`` branch documents itself as "should never happen
given the registration in main.py"; that claim was previously untested.
The happy path (a real ``RateLimitExceeded``) is already exercised
end-to-end by ``tests/integration/test_ratings_api.py``, which triggers a
genuine 429 through the fully wired-up app.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fragrance_rater.middleware.rate_limit import rate_limit_exceeded_handler


def test_rate_limit_exceeded_handler_raises_typeerror_for_wrong_exception_type() -> (
    None
):
    """The defensive branch fires for any exception other than RateLimitExceeded.

    This is the direct regression test for the "should never happen given the
    registration in main.py" branch: Starlette only ever calls this handler
    for RateLimitExceeded in practice, but the isinstance guard exists
    precisely to make a future registration mistake (registering this
    handler against the wrong exception type) fail loudly instead of
    silently misbehaving.
    """
    request = MagicMock()
    wrong_exception = ValueError("not a rate limit error")

    with pytest.raises(TypeError, match="unexpected exception type"):
        rate_limit_exceeded_handler(request, wrong_exception)
