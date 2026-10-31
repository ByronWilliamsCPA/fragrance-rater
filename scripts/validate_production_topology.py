#!/usr/bin/env python3
"""Reject a production Compose render that exposes an authentication bypass."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_AUTHENTIK_MIDDLEWARE = "authentik@file"

# A value an operator copied from an example file or left as a stand-in is not a
# secret. This is deliberately conservative: it only rejects the shapes that
# ``.env.example`` and typical documentation use.
_PLACEHOLDER = re.compile(
    r"(change[-_ ]?me|your[-_ ]|placeholder|example|xxxx|todo|\$\{|<.*>|replace[-_ ]?me)",
    re.IGNORECASE,
)
_TRUTHY = {"1", "true", "yes", "on"}
_REQUIRED_SECRETS = ("FRAGRANCE_RATER_API_KEY", "OPENROUTER_API_KEY")


def validate_topology(
    config: object,
    edge_subnet: str | None = None,
    authentik_middleware: str = DEFAULT_AUTHENTIK_MIDDLEWARE,
) -> list[str]:
    """Return security violations from a rendered Compose document.

    ``edge_subnet`` is the live subnet of ``FRAGRANCE_TRAEFIK_NETWORK`` as
    ``docker network inspect`` reports it; when given, the configured
    ``FRAGRANCE_TRAEFIK_CIDR`` must equal it. ``authentik_middleware`` is the
    forward-auth middleware name the deployment configured
    (``AUTHENTIK_MIDDLEWARE``); the Traefik router must carry exactly that one.
    """
    if not isinstance(config, dict) or not isinstance(config.get("services"), dict):
        return ["rendered Compose config must contain services"]
    services: dict[str, Any] = config["services"]
    errors: list[str] = []
    for name in ("app", "frontend", "db"):
        service = services.get(name)
        if not isinstance(service, dict):
            errors.append(f"service {name} is missing")
            continue
        if service.get("ports"):
            errors.append(f"service {name} publishes a host port")
        network_mode = service.get("network_mode")
        if name in {"app", "db"} and network_mode:
            errors.append(f"service {name} must not set network_mode={network_mode}")
        elif network_mode == "host":
            errors.append(f"service {name} uses host networking")
        if service.get("volumes") and name in {"app", "frontend"}:
            errors.append(f"service {name} retains a development source mount")

    app = services.get("app", {})
    app_environment = app.get("environment", {})
    if app_environment.get("AUTHENTIK_REQUIRED") != "true":
        errors.append("app must set AUTHENTIK_REQUIRED=true")
    if app_environment.get("ENVIRONMENT") != "production":
        errors.append("app must set ENVIRONMENT=production")
    trusted_hosts = [
        host.strip()
        for host in str(app_environment.get("TRUSTED_HOSTS", "")).split(",")
        if host.strip()
    ]
    if not trusted_hosts or "*" in trusted_hosts:
        errors.append("app must set TRUSTED_HOSTS to explicit host names")
    forwarded_allow_ips = str(app_environment.get("FORWARDED_ALLOW_IPS", ""))
    if not forwarded_allow_ips.strip() or "*" in forwarded_allow_ips:
        errors.append("app must set FORWARDED_ALLOW_IPS to the proxy subnets")
    if not str(app_environment.get("DATABASE_URL", "")).startswith(
        "postgresql+asyncpg://"
    ):
        errors.append("app DATABASE_URL must use the postgresql+asyncpg scheme")
    errors.extend(_app_runtime_errors(app, app_environment))
    frontend = services.get("frontend", {})
    frontend_environment = frontend.get("environment", {})
    if frontend_environment.get("VITE_API_URL") != "/api":
        errors.append("frontend must use the authenticated same-origin /api path")
    edge_cidr = frontend_environment.get("FRAGRANCE_TRAEFIK_CIDR")
    cidr_errors = _edge_cidr_errors(edge_cidr)
    errors.extend(cidr_errors)
    if edge_subnet is not None and not cidr_errors:
        errors.extend(_edge_subnet_mismatch(str(edge_cidr), edge_subnet))
    networks = frontend.get("networks", {})
    if not {"fragrance_rater-network", "authenticated-edge"}.issubset(networks):
        errors.append("frontend must join application and authenticated-edge networks")
    for name in ("app", "db"):
        private_networks = services.get(name, {}).get("networks", {})
        if "authenticated-edge" in private_networks:
            errors.append(
                f"service {name} must not join the authenticated-edge network"
            )
    labels = frontend.get("labels", {})
    if labels.get("traefik.enable") != "true":
        errors.append("frontend must enable Traefik routing")
    middleware_chain = labels.get(
        "traefik.http.routers.fragrance-rater.middlewares", ""
    )
    middleware_tokens = {
        token.strip() for token in str(middleware_chain).split(",") if token.strip()
    }
    if authentik_middleware not in middleware_tokens:
        errors.append(
            f"Traefik router must declare the Authentik middleware "
            f"{authentik_middleware!r}"
        )
    declared_networks = config.get("networks", {})
    edge = declared_networks.get("authenticated-edge", {})
    if not isinstance(edge, dict) or not edge.get("external"):
        errors.append("authenticated-edge must be a dedicated external network")
    return errors


def _app_runtime_errors(app: dict[str, Any], environment: dict[str, Any]) -> list[str]:
    """Check what the app container needs to be safe and usable in production.

    Covers the single replica (the rate limiter is process-local), the manager
    allow-list, the CORS allow-list, the two billed-endpoint secrets (S-04), and
    ``TEST_MODE`` (S-27). Each is a setting that fails open or silently
    degrades when an operator leaves it unset.
    """
    errors: list[str] = []
    deploy = app.get("deploy")
    replicas = deploy.get("replicas", 1) if isinstance(deploy, dict) else 1
    if str(replicas).strip() != "1":
        errors.append(
            "app must run a single replica: its rate limiter is process-local, "
            "so more replicas multiply the effective limit"
        )
    errors.extend(_admin_errors(environment.get("CALIBRATION_ADMIN_USERNAMES")))
    errors.extend(_cors_errors(environment.get("CORS_ALLOWED_ORIGINS")))
    for name in _REQUIRED_SECRETS:
        value = str(environment.get(name) or "").strip()
        if not value:
            errors.append(f"app must set {name}")
        elif _PLACEHOLDER.search(value):
            errors.append(f"app {name} is a placeholder, not a secret")
    if str(environment.get("TEST_MODE", "")).strip().lower() in _TRUTHY:
        errors.append("app must not set TEST_MODE in production")
    return errors


def _split_list(value: object) -> list[str] | None:
    """Parse a JSON array or comma list the way the settings model does."""
    if value is None:
        return None
    text = str(value).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list):
            return None
        return [str(item).strip() for item in parsed]
    return [item.strip() for item in text.split(",") if item.strip()]


def _admin_errors(value: object) -> list[str]:
    """The manager allow-list must name specific, verified users."""
    names = _split_list(value)
    if names is None:
        return ["CALIBRATION_ADMIN_USERNAMES must be a JSON array or comma list"]
    if not names or any(not name for name in names):
        return ["CALIBRATION_ADMIN_USERNAMES must name at least one manager"]
    if "*" in names:
        return ["CALIBRATION_ADMIN_USERNAMES must not contain a wildcard"]
    return []


def _cors_errors(value: object) -> list[str]:
    """CORS may be unset (production defaults to none) but never wide open."""
    if value is None or not str(value).strip():
        return []
    origins = _split_list(value)
    if origins is None:
        return ["CORS_ALLOWED_ORIGINS must be a JSON array or comma list"]
    errors: list[str] = []
    if "*" in origins:
        errors.append("CORS_ALLOWED_ORIGINS must not contain a wildcard")
    errors.extend(
        f"CORS_ALLOWED_ORIGINS entry {origin!r} must be an https origin"
        for origin in origins
        if origin != "*" and not origin.startswith("https://")
    )
    return errors


def _edge_cidr_errors(value: object) -> list[str]:
    """Check the subnet nginx trusts for identity headers (S-01).

    A missing value, a single host, or a range wide enough to cover other
    networks (anything broader than a /16, or 0.0.0.0/0) would let peers
    other than Traefik forward forged ``X-Authentik-*`` headers.
    """
    if not value:
        return ["frontend must set FRAGRANCE_TRAEFIK_CIDR to the edge network subnet"]
    try:
        network = ipaddress.ip_network(str(value), strict=False)
    except ValueError:
        return [f"FRAGRANCE_TRAEFIK_CIDR {value!r} is not a valid CIDR"]
    minimum_prefix = 16 if network.version == 4 else 48
    if network.prefixlen < minimum_prefix:
        message = (
            f"FRAGRANCE_TRAEFIK_CIDR {value!r} is broader than "
            f"/{minimum_prefix}; trust only the dedicated edge network"
        )
        return [message]
    return []


def _edge_subnet_mismatch(cidr: str, edge_subnet: str) -> list[str]:
    """Compare the trusted CIDR with the edge network as Docker reports it.

    A wider value trusts peers off the edge network; a narrower or different
    one can exclude Traefik, which clears every legitimate identity header.
    """
    try:
        live = ipaddress.ip_network(edge_subnet.strip(), strict=False)
    except ValueError:
        return [f"edge network subnet {edge_subnet!r} is not a valid CIDR"]
    if ipaddress.ip_network(cidr, strict=False) != live:
        message = (
            f"FRAGRANCE_TRAEFIK_CIDR {cidr!r} does not match the edge network "
            f"subnet {str(live)!r}"
        )
        return [message]
    return []


def main() -> int:
    """Validate a ``docker compose config --format json`` render.

    ``EDGE_SUBNET`` is the live subnet of ``FRAGRANCE_TRAEFIK_NETWORK``, so a
    stale or mistyped ``FRAGRANCE_TRAEFIK_CIDR`` fails here rather than in
    production. ``--authentik-middleware`` is the middleware name the
    deployment uses; it defaults to ``$AUTHENTIK_MIDDLEWARE``, then to
    ``authentik@file``.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("rendered_config", type=Path, metavar="RENDERED_CONFIG.json")
    parser.add_argument("edge_subnet", metavar="EDGE_SUBNET")
    parser.add_argument(
        "--authentik-middleware",
        default=os.environ.get("AUTHENTIK_MIDDLEWARE") or DEFAULT_AUTHENTIK_MIDDLEWARE,
    )
    try:
        args = parser.parse_args()
    except SystemExit as exit_request:
        # argparse exits 2 on a usage error and 0 for --help; report it as the
        # return value so callers (and tests) see the same contract as before.
        return int(exit_request.code or 0)
    try:
        config = json.loads(args.rendered_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"config could not be read: {exc}", file=sys.stderr)
        return 2
    errors = validate_topology(
        config,
        edge_subnet=args.edge_subnet,
        authentik_middleware=args.authentik_middleware,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("production topology blocks direct host access and requires proxy identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
