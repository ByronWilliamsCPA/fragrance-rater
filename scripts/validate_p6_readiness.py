#!/usr/bin/env python3
"""Validate the machine-readable P6 closure record."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

GATES = {f"P6.{index}" for index in range(1, 7)}
ARTIFACTS = {
    "device_matrix",
    "operations_drill",
    "p1_gate",
    "quality_report",
    "redacted_export_manifest",
    "signed_decision",
    "synthetic_rehearsal",
}
COMMIT = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def non_empty_text(value: object) -> bool:
    """Return whether a value is non-empty text."""
    return isinstance(value, str) and bool(value.strip())


def completed_text(value: object) -> bool:
    """Return whether text is non-empty and no longer a template placeholder."""
    if not non_empty_text(value):
        return False
    normalized = str(value).strip().lower()
    return "pending" not in normalized and "replace-with" not in normalized


def validate_release(release: object) -> list[str]:
    """Validate immutable candidate identity and remote CI state."""
    if not isinstance(release, dict):
        return ["release must be an object"]
    errors: list[str] = []
    if not COMMIT.fullmatch(str(release.get("commit", ""))):
        errors.append("release.commit must be a 40-character lowercase Git commit")
    errors.extend(
        f"release.{field} must be an immutable SHA-256 digest"
        for field in ("app_image_digest", "frontend_image_digest")
        if not DIGEST.fullmatch(str(release.get(field, "")))
    )
    if not completed_text(release.get("deployment_reference")):
        errors.append(
            "release.deployment_reference must be a completed private reference"
        )
    if release.get("remote_ci_passed") is not True:
        errors.append("release.remote_ci_passed must be true")
    return errors


def validate_limitations(limitations: object) -> list[str]:
    """Reject malformed or unresolved release-blocking limitations."""
    if not isinstance(limitations, list):
        return ["known_limitations must be an array"]
    errors: list[str] = []
    for index, limitation in enumerate(limitations):
        prefix = f"known_limitations[{index}]"
        if not isinstance(limitation, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(
            f"{prefix}.{field} must be completed text"
            for field in ("id", "summary", "disposition")
            if not completed_text(limitation.get(field))
        )
        if not isinstance(limitation.get("blocking"), bool):
            errors.append(f"{prefix}.blocking must be a boolean")
        elif limitation["blocking"]:
            errors.append(f"{prefix} remains release blocking")
    return errors


def validate_decision(decision: object) -> list[str]:
    """Require an attributable UTC go decision."""
    if not isinstance(decision, dict):
        return ["decision must be an object"]
    errors: list[str] = []
    if decision.get("value") != "go":
        errors.append("decision.value must be go to close P6")
    if not completed_text(decision.get("decided_by")):
        errors.append("decision.decided_by must identify the decision maker")
    decided_at = decision.get("decided_at")
    if not non_empty_text(decided_at):
        errors.append("decision.decided_at must be a UTC timestamp")
    else:
        timestamp = str(decided_at)
        if timestamp.endswith("Z"):
            timestamp = f"{timestamp[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            errors.append("decision.decided_at must be an ISO 8601 UTC timestamp")
        else:
            offset = parsed.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                errors.append("decision.decided_at must be in UTC")
    return errors


def validate_readiness(document: object) -> list[str]:
    """Return every contract violation in a P6 closure record."""
    if not isinstance(document, dict):
        return ["root must be an object"]
    errors = validate_release(document.get("release"))

    gates = document.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
    else:
        missing = GATES - gates.keys()
        extra = gates.keys() - GATES
        errors.extend(f"gates.{gate} is required" for gate in sorted(missing))
        errors.extend(f"gates.{gate} is not recognized" for gate in sorted(extra))
        errors.extend(
            f"gates.{gate} must be pass"
            for gate in sorted(GATES)
            if gates.get(gate) != "pass"
        )

    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
    else:
        for name in sorted(ARTIFACTS):
            if not completed_text(artifacts.get(name)):
                errors.append(
                    f"artifacts.{name} must be a completed private evidence reference"
                )

    errors.extend(validate_limitations(document.get("known_limitations")))
    errors.extend(validate_decision(document.get("decision")))
    return errors


def main() -> int:
    """Validate a JSON record and return a shell-friendly exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        document: Any = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"readiness record could not be read: {exc}", file=sys.stderr)
        return 2
    errors = validate_readiness(document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid P6 go record for commit {document['release']['commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
