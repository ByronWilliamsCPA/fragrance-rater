#!/usr/bin/env python3
"""Reject a production Compose render that exposes an authentication bypass."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def validate_topology(config: object) -> list[str]:
    """Return security violations from a rendered Compose document."""
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
        if service.get("network_mode") == "host":
            errors.append(f"service {name} uses host networking")
        if service.get("volumes") and name in {"app", "frontend"}:
            errors.append(f"service {name} retains a development source mount")

    app = services.get("app", {})
    app_environment = app.get("environment", {})
    if app_environment.get("AUTHENTIK_REQUIRED") != "true":
        errors.append("app must set AUTHENTIK_REQUIRED=true")
    if not str(app_environment.get("DATABASE_URL", "")).startswith(
        "postgresql+asyncpg://"
    ):
        errors.append("app DATABASE_URL must use the postgresql+asyncpg scheme")
    frontend = services.get("frontend", {})
    if frontend.get("environment", {}).get("VITE_API_URL") != "/api":
        errors.append("frontend must use the authenticated same-origin /api path")
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
    if "authentik@file" not in middleware_tokens:
        errors.append("Traefik router must declare the Authentik middleware")
    declared_networks = config.get("networks", {})
    edge = declared_networks.get("authenticated-edge", {})
    if not isinstance(edge, dict) or not edge.get("external"):
        errors.append("authenticated-edge must be a dedicated external network")
    return errors


def main() -> int:
    """Validate the JSON output of ``docker compose config --format json``."""
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} RENDERED_CONFIG.json", file=sys.stderr)
        return 2
    try:
        config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"config could not be read: {exc}", file=sys.stderr)
        return 2
    errors = validate_topology(config)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("production topology blocks direct host access and requires proxy identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
