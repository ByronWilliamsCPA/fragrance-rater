"""The production nginx config forwards identity only from Traefik (R3, S-01).

Renders ``frontend/nginx.conf`` the way the nginx image does at start (envsubst
over the template, substituting only variables that are set), runs a real
nginx in front of a header-echoing stub, and sends forged ``X-Authentik-*``
and forwarding headers from a peer inside and outside ``FRAGRANCE_TRAEFIK_CIDR``.

Skipped locally when ``nginx`` or ``envsubst`` is not installed. Under CI
(``CI`` set) the tests run regardless and fail if either is missing, so the
boundary cannot pass unexercised; GitHub's Ubuntu runners have both.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

NGINX = shutil.which("nginx")
ENVSUBST = shutil.which("envsubst")
TEMPLATE = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"

pytestmark = pytest.mark.skipif(
    (NGINX is None or ENVSUBST is None) and not os.environ.get("CI"),
    reason="nginx and envsubst are required",
)

FORGED = {
    "X-Authentik-Username": "forged-manager",
    "X-Authentik-Uid": "forged-uid",
    "X-Authentik-Email": "forged@example.invalid",
    "X-Authentik-Groups": "forged-group",
    "X-Forwarded-For": "203.0.113.66",
    "X-Forwarded-Proto": "https",
}


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({k.lower(): v for k, v in self.headers.items()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def echo_port() -> Iterator[int]:
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield int(server.server_address[1])
    server.shutdown()


def _render(cidr: str | None, tmp_path: Path, echo_port: int, port: int) -> Path:
    """Render the template as the image would and point it at the stub."""
    env = {"PATH": os.environ.get("PATH", "")}
    if cidr is not None:
        env["FRAGRANCE_TRAEFIK_CIDR"] = cidr
    defined = " ".join(f"${{{name}}}" for name in env)
    assert ENVSUBST is not None
    rendered = subprocess.run(  # noqa: S603 - fixed argv, test-only
        [ENVSUBST, defined],
        input=TEMPLATE.read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=30,
    ).stdout
    rendered = rendered.replace("listen 80;", f"listen 127.0.0.1:{port};")
    rendered = rendered.replace("http://app:8000/", f"http://127.0.0.1:{echo_port}/")
    conf_d = tmp_path / "conf.d"
    conf_d.mkdir()
    (conf_d / "default.conf").write_text(rendered, encoding="utf-8")
    (tmp_path / "logs").mkdir()
    main = tmp_path / "nginx.conf"
    main.write_text(
        f"pid {tmp_path}/nginx.pid;\n"
        f"error_log {tmp_path}/logs/error.log;\n"
        "events {}\n"
        "http {\n"
        "  access_log off;\n"
        f"  client_body_temp_path {tmp_path}/body;\n"
        f"  proxy_temp_path {tmp_path}/proxy;\n"
        f"  fastcgi_temp_path {tmp_path}/fastcgi;\n"
        f"  uwsgi_temp_path {tmp_path}/uwsgi;\n"
        f"  scgi_temp_path {tmp_path}/scgi;\n"
        f"  include {conf_d}/*.conf;\n"
        "}\n",
        encoding="utf-8",
    )
    return main


def _nginx(main: Path, *args: str) -> subprocess.CompletedProcess[str]:
    assert NGINX is not None
    return subprocess.run(  # noqa: S603 - fixed argv, test-only
        [NGINX, "-p", str(main.parent), "-c", str(main), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _forwarded_headers(cidr: str, tmp_path: Path, echo_port: int) -> dict[str, str]:
    port = _free_port()
    main = _render(cidr, tmp_path, echo_port, port)
    started = _nginx(main)
    assert started.returncode == 0, started.stderr
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/probe", headers=FORGED
        )
        for _ in range(50):
            try:
                with urllib.request.urlopen(request, timeout=2) as response:  # noqa: S310
                    return dict(json.loads(response.read()))
            except OSError:
                time.sleep(0.1)
        pytest.fail("nginx did not start serving")
    finally:
        _nginx(main, "-s", "stop")


def test_untrusted_peer_cannot_forge_identity_or_client(
    tmp_path: Path, echo_port: int
) -> None:
    """A peer outside the edge subnet reaches the API with no identity."""
    headers = _forwarded_headers("10.255.0.0/16", tmp_path, echo_port)
    assert not any(name.startswith("x-authentik-") for name in headers), headers
    assert headers["x-forwarded-for"] == "127.0.0.1"
    assert headers["x-forwarded-proto"] == "http"


def test_traefik_peer_identity_and_client_are_forwarded(
    tmp_path: Path, echo_port: int
) -> None:
    """Headers from a peer inside the edge subnet (Traefik) pass through."""
    headers = _forwarded_headers("127.0.0.0/8", tmp_path, echo_port)
    assert headers["x-authentik-username"] == "forged-manager"
    assert headers["x-authentik-uid"] == "forged-uid"
    assert headers["x-authentik-email"] == "forged@example.invalid"
    assert headers["x-authentik-groups"] == "forged-group"
    assert headers["x-forwarded-for"] == "203.0.113.66, 127.0.0.1"
    assert headers["x-forwarded-proto"] == "https"


def test_missing_cidr_refuses_to_start(tmp_path: Path, echo_port: int) -> None:
    """Without FRAGRANCE_TRAEFIK_CIDR nginx fails closed instead of trusting."""
    main = _render(None, tmp_path, echo_port, _free_port())
    result = _nginx(main, "-t")
    assert result.returncode != 0
    assert "invalid network" in result.stderr
