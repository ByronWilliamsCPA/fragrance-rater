"""A write must be committed before the client is told it succeeded.

``get_db`` commits after its ``yield``. FastAPI runs a ``yield`` dependency's
exit code after the response has been sent unless the dependency is declared
with ``scope="function"``. Without that, a client receives "201 Created" before
the commit lands: a fast follow-up request can run first and see nothing (the
real-stack e2e tier showed ``Program not found`` straight after creating the
program), and a commit that failed would already have been reported as success.

The in-process test client waits for the whole app call, so it cannot show the
difference; these tests look at the order of events instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import pytest
from fastapi import Depends, FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
_GET_DB_DEPENDENCY = re.compile(r"Depends\(\s*get_db\b[^)]*\)")

_events: list[str] = []


async def _session() -> AsyncGenerator[str, None]:
    """Stand-in for ``get_db``: it commits after the ``yield``."""
    yield "session"
    _events.append("commit")


DefaultScope = Annotated[str, Depends(_session)]
FunctionScope = Annotated[str, Depends(_session, scope="function")]

_api = FastAPI()


@_api.post("/default")
async def _default(session: DefaultScope) -> dict[str, str]:
    return {"session": session}


@_api.post("/function")
async def _function(session: FunctionScope) -> dict[str, str]:
    return {"session": session}


async def _order_of_events(path: str) -> list[str]:
    """Drive one request through a bare ASGI call and record what happens when."""
    _events.clear()
    request = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"host", b"test")],
        "server": ("test", 80),
        "client": ("127.0.0.1", 1),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            # A 422 or 500 would also "send a response" without ever running
            # the dependency, so the status is part of what is checked.
            assert message["status"] == 200
            _events.append("response_sent")

    await _api(request, receive, send)
    return list(_events)


@pytest.mark.asyncio
async def test_a_function_scoped_dependency_commits_before_the_response() -> None:
    assert await _order_of_events("/function") == ["commit", "response_sent"]


@pytest.mark.asyncio
async def test_the_default_scope_responds_before_it_commits() -> None:
    """The control: this is the behaviour the fix removes."""
    assert await _order_of_events("/default") == ["response_sent", "commit"]


def test_every_get_db_dependency_is_function_scoped() -> None:
    """A new route must not bring the response-first behaviour back."""
    uses = 0
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for match in _GET_DB_DEPENDENCY.finditer(path.read_text(encoding="utf-8")):
            uses += 1
            if 'scope="function"' not in match.group(0):
                line = path.read_text(encoding="utf-8")[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(SRC.parent)}:{line}")

    assert uses > 20, "the scan found too few get_db dependencies to prove anything"
    assert offenders == []
