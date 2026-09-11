#!/usr/bin/env python3
"""Validate the identity and evidence contract for a calibration manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REQUIRED_TEXT = (
    "membership_key",
    "fragrance_id",
    "brand",
    "name",
    "concentration",
    "version_key",
    "source_url",
    "verification_evidence",
)
ROLES = {
    "ACTIVE_LEARNING",
    "HIDDEN_REPEAT",
    "HOLDOUT",
    "OTHER",
    "OWNED_VALIDATION",
    "RETEST",
    "UNIVERSAL_BASELINE",
}


def validate_manifest(document: object) -> list[str]:
    """Return all contract violations in a calibration manifest."""
    if not isinstance(document, dict):
        return ["root must be an object"]
    errors: list[str] = []
    if not document.get("program_name"):
        errors.append("program_name is required")
    if not document.get("program_version"):
        errors.append("program_version is required")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        return [*errors, "entries must be a non-empty array"]

    seen_ids: set[str] = set()
    seen_memberships: set[str] = set()
    membership_entries: dict[str, dict[str, Any]] = {
        str(item.get("membership_key")): item
        for item in entries
        if isinstance(item, dict) and item.get("membership_key")
    }
    for index, raw in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        entry: dict[str, Any] = raw
        for field in REQUIRED_TEXT:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be non-empty text")
        fragrance_id = entry.get("fragrance_id")
        membership_key = entry.get("membership_key")
        role = entry.get("role")
        if isinstance(fragrance_id, str):
            if fragrance_id in seen_ids and role != "HIDDEN_REPEAT":
                errors.append(f"{prefix}.fragrance_id is duplicated")
            seen_ids.add(fragrance_id)
        if isinstance(membership_key, str):
            if membership_key in seen_memberships:
                errors.append(f"{prefix}.membership_key is duplicated")
            seen_memberships.add(membership_key)
        if str(entry.get("concentration", "")).strip().lower() == "unknown":
            errors.append(f"{prefix}.concentration cannot be unknown")
        source_url = entry.get("source_url")
        if isinstance(source_url, str):
            parsed = urlparse(source_url)
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{prefix}.source_url must be an absolute HTTPS URL")
        if entry.get("physical_sample_confirmed") is not True:
            errors.append(f"{prefix}.physical_sample_confirmed must be true")
        if role not in ROLES:
            errors.append(f"{prefix}.role must be one of {sorted(ROLES)}")
        repeat_of = entry.get("repeat_of_membership_key")
        if role == "HIDDEN_REPEAT":
            original = membership_entries.get(str(repeat_of))
            if original is None or repeat_of == membership_key:
                errors.append(
                    f"{prefix}.repeat_of_membership_key must reference another entry"
                )
            elif original.get("fragrance_id") != fragrance_id or original.get(
                "version_key"
            ) != entry.get("version_key"):
                errors.append(f"{prefix} repeat must use the original exact version")
        elif repeat_of is not None:
            errors.append(
                f"{prefix}.repeat_of_membership_key is allowed only for HIDDEN_REPEAT"
            )
    return errors


def main() -> int:
    """Validate a JSON file and return a shell-friendly exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"manifest could not be read: {exc}", file=sys.stderr)
        return 2
    errors = validate_manifest(document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid calibration manifest: {len(document['entries'])} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
