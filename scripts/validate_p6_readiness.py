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
PRIVATE_REFERENCE = re.compile(r"private:[A-Za-z0-9](?:[A-Za-z0-9._/-]*[A-Za-z0-9])?")
# RFC 3339 UTC only: an explicit Z/z or +00:00 designator. "-00:00" means
# "offset unknown" per RFC 3339 4.3, not attributable UTC, so it is
# deliberately excluded here rather than accepted as a zero offset.
_TIMESTAMP = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"[Tt ]"
    r"(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d+)?)"
    r"(?P<offset>Z|z|\+00:00)"
)
# Obvious non-completions an operator might type instead of real data. None
# of these contain "pending" or a "replace-with" prefix, so they pass the
# placeholder check below unless rejected explicitly.
_JUNK_TOKENS = frozenset(
    {"tbd", "tba", "n/a", "na", "todo", "fixme", "x", "-", "--", "?", "??"}
)


def non_empty_text(value: object) -> bool:
    """Return whether a value is non-empty text."""
    return isinstance(value, str) and bool(value.strip())


def completed_text(value: object) -> bool:
    """Return whether text is non-empty and no longer a template placeholder.

    Template placeholders in this repo are always either the exact literal
    "pending" or a value starting with "replace-with"; a substring search
    would also reject legitimate prose that happens to contain "pending"
    (e.g. "no longer depending on the LLM provider"), so this matches
    exactly or by prefix instead.
    """
    if not non_empty_text(value):
        return False
    normalized = str(value).strip().lower()
    if normalized == "pending" or normalized.startswith("replace-with"):
        return False
    return normalized not in _JUNK_TOKENS


def private_reference(value: object) -> bool:
    """Return whether a value is an opaque reference inside the private store."""
    if not completed_text(value):
        return False
    reference = str(value).strip()
    if not PRIVATE_REFERENCE.fullmatch(reference):
        return False
    path = reference.removeprefix("private:")
    return all(segment not in {"", ".", ".."} for segment in path.split("/"))


def _parse_utc_timestamp(value: str) -> datetime | None:
    """Parse a UTC timestamp using a version-independent grammar.

    `datetime.fromisoformat()` accepts progressively more variants across
    Python 3.10-3.13 (3.11 relaxed it considerably), so the same record can
    pass on one CI runner and fail on another if this delegated to it
    directly. Instead, `_TIMESTAMP` alone defines what is accepted, and the
    matched value is normalized (fractional seconds padded to exactly six
    digits) before the one canonical form is parsed, so acceptance no
    longer depends on which interpreter runs the validator.
    """
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        return None
    time_part = match["time"]
    if "." in time_part:
        whole, fraction = time_part.split(".", 1)
        time_part = f"{whole}.{fraction[:6].ljust(6, '0')}"
    canonical = f"{match['date']}T{time_part}+00:00"
    try:
        return datetime.fromisoformat(canonical)
    except ValueError:
        return None


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
    if not private_reference(release.get("deployment_reference")):
        errors.append(
            "release.deployment_reference must use the private:<opaque-reference> format"
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
            for field in (
                "id",
                "summary",
                "affected_role",
                "workflow",
                "likelihood",
                "impact",
                "workaround",
                "owner",
                "disposition",
            )
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
    elif _parse_utc_timestamp(str(decided_at).strip()) is None:
        errors.append(
            "decision.decided_at must be an ISO 8601 UTC timestamp (Z or +00:00 only)"
        )
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
            if str(gates.get(gate, "")).strip().lower() != "pass"
        )

    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
    else:
        for name in sorted(ARTIFACTS):
            if not private_reference(artifacts.get(name)):
                errors.append(
                    f"artifacts.{name} must use the private:<opaque-reference> format"
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
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
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
