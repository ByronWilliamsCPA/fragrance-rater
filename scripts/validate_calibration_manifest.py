#!/usr/bin/env python3
"""Validate the identity and evidence contract for a calibration manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from fragrance_rater.utils.gtin import is_valid_gtin

SOURCE_REFERENCE_PARTS = 3
MIN_LABEL_CHECKERS = 2
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")
# Names accepted by --expect-shape, mapped to the program role they count.
SHAPE_ROLES = {
    "baseline": "UNIVERSAL_BASELINE",
    "hidden_repeat": "HIDDEN_REPEAT",
    "holdout": "HOLDOUT",
}
REQUIRED_TEXT = (
    "membership_key",
    "fragrance_id",
    "brand",
    "name",
    "concentration",
    "version_key",
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


def _validate_verification(document: dict[str, object]) -> list[str]:
    """Check who verified the manifest and when (the template ships both as null)."""
    errors: list[str] = []
    verified_by = document.get("verified_by")
    if not isinstance(verified_by, str) or not verified_by.strip():
        errors.append("verified_by must be the non-empty name of the verifier")
    verified_at = document.get("verified_at")
    if not isinstance(verified_at, str) or not UTC_TIMESTAMP.fullmatch(verified_at):
        errors.append("verified_at must be a UTC timestamp like 2026-11-08T14:30:00Z")
    else:
        try:
            datetime.fromisoformat(verified_at)
        except ValueError:
            errors.append("verified_at is not a real date and time")
    return errors


def _validate_label_check(
    prefix: str, entry: dict[str, object], *, required: bool
) -> list[str]:
    """Check the two-person decant label check recorded in label_checked_by."""
    # #ASSUME: data-integrity: the owner's 2026-11-01 decant standard needs a
    # two-person label check, but a non-decant entry (a bottle with packaging)
    # has no such check, so label_checked_by is validated when present and
    # only demanded when the caller opts in with required=True.
    # #VERIFY: tests/unit/test_release_readiness.py::TestLabelCheck
    if "label_checked_by" not in entry:
        if required:
            return [f"{prefix}.label_checked_by is required (two people)"]
        return []
    raw = entry["label_checked_by"]
    names = cast("list[object]", raw) if isinstance(raw, list) else []
    texts = [name.strip() for name in names if isinstance(name, str)]
    if not names or len(texts) != len(names) or not all(texts):
        return [f"{prefix}.label_checked_by must be a list of non-empty names"]
    distinct = {text.casefold() for text in texts}
    if len(distinct) < MIN_LABEL_CHECKERS:
        return [
            f"{prefix}.label_checked_by needs {MIN_LABEL_CHECKERS} different people"
        ]
    return []


def validate_manifest(
    document: object, *, require_label_check: bool = False
) -> list[str]:
    """Return all contract violations in a calibration manifest."""
    if not isinstance(document, dict):
        return ["root must be an object"]
    errors: list[str] = []
    if not document.get("program_name"):
        errors.append("program_name is required")
    if not document.get("program_version"):
        errors.append("program_version is required")
    errors.extend(_validate_verification(document))
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
        # #ASSUME: data-integrity: ADR-012's SourceSnapshot amendment allows a
        # manufacturer confirmation with no URL (an email or phone reply) to
        # stand as evidence via source_reference instead of source_url, with
        # a CHECK constraint requiring at least one of the two. Mirroring
        # that here, instead of keeping source_url unconditionally required,
        # is what lets a direct reply be recorded as P1.1 evidence without
        # inventing a public URL for a private reply. A key that is present
        # but the wrong type (an int, a list, a dict, an explicit JSON
        # null) is a distinct authoring mistake from omitting the key
        # entirely, so it must fail validation rather than being silently
        # treated the same as "absent" - `entry.get(...)` alone can't tell
        # those two cases apart, hence the explicit `"source_url" in entry`
        # membership check below.
        # #VERIFY: covered by
        # tests/unit/test_release_readiness.py::TestSourceEvidence
        # (url-only, reference-only, both, neither, wrong-type and
        # blank-string source_url/source_reference, and a malformed
        # source_url that would otherwise crash urlparse and lose every
        # error accumulated so far).
        source_url = entry.get("source_url")
        source_reference = entry.get("source_reference")
        has_url = False
        if "source_url" in entry:
            if isinstance(source_url, str) and source_url.strip():
                has_url = True
            else:
                errors.append(f"{prefix}.source_url must be a non-empty string")
        has_reference = False
        if "source_reference" in entry:
            if isinstance(source_reference, str) and source_reference.strip():
                has_reference = True
            else:
                errors.append(f"{prefix}.source_reference must be a non-empty string")
        if not has_url and not has_reference:
            errors.append(
                f"{prefix} must have a non-empty source_url or source_reference"
            )
        if has_reference:
            # A reference is "who | ISO date | evidence or scope", the minimal
            # record for a physical or decant verification (issue #130).
            parts = [part.strip() for part in str(source_reference).split("|")]
            if len(parts) != SOURCE_REFERENCE_PARTS or not all(parts):
                errors.append(
                    f"{prefix}.source_reference must be 'who | YYYY-MM-DD | "
                    "evidence or scope'"
                )
            else:
                # fromisoformat also accepts 20260920 and 2026-W38-7 on
                # Python 3.12, so the round trip pins the YYYY-MM-DD form.
                try:
                    canonical = date.fromisoformat(parts[1]).isoformat()
                except ValueError:
                    canonical = None
                if canonical != parts[1]:
                    errors.append(f"{prefix}.source_reference date must be YYYY-MM-DD")
        if has_url:
            try:
                parsed = urlparse(source_url)
            except ValueError:
                errors.append(f"{prefix}.source_url must be an absolute HTTPS URL")
            else:
                if parsed.scheme != "https" or not parsed.netloc:
                    errors.append(f"{prefix}.source_url must be an absolute HTTPS URL")
        if entry.get("physical_sample_confirmed") is not True:
            errors.append(f"{prefix}.physical_sample_confirmed must be true")
        errors.extend(
            _validate_label_check(prefix, entry, required=require_label_check)
        )
        # #ASSUME: data-integrity: gtin is optional (some physical samples
        # - decants, vintage, some indie houses - carry no scannable
        # manufacturer barcode) but when present must be a real,
        # check-digit-valid GTIN, not free text; a value that fails the
        # GS1 checksum is far more likely a transcription error than a
        # genuine identity signal, so it is rejected rather than stored.
        # Require the manifest to author it as a JSON string, matching
        # MembershipInput's live-path contract: a JSON number has no
        # leading-zero literal, so an author who wrote e.g. 36000291452
        # instead of "036000291452" would have already silently lost a
        # digit before this script ever runs. Coercing via str(gtin)
        # here would accept that mistake and reject it (if at all) with
        # a misleading "invalid GTIN" rather than naming the real cause.
        # #VERIFY: covered by tests for a valid GTIN, an invalid check
        # digit, a JSON-number gtin, and an absent field.
        gtin = entry.get("gtin")
        if gtin is not None:
            if not isinstance(gtin, str):
                errors.append(
                    f"{prefix}.gtin must be a JSON string, not a number "
                    "(a bare number loses any leading zero)"
                )
            elif not is_valid_gtin(gtin):
                errors.append(
                    f"{prefix}.gtin must be a valid GTIN-8/12/13/14 or omitted"
                )
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


def parse_shape(text: str) -> dict[str, int]:
    """Parse ``baseline=33,hidden_repeat=6,holdout=10`` into role counts."""
    shape: dict[str, int] = {}
    for part in text.split(","):
        name, separator, count = part.strip().partition("=")
        if not separator or name not in SHAPE_ROLES or not count.strip().isdigit():
            names = ", ".join(sorted(SHAPE_ROLES))
            msg = f"{part.strip()!r} is not NAME=COUNT with NAME one of {names}"
            raise argparse.ArgumentTypeError(msg)
        if name in shape:
            msg = f"{name} is given more than once"
            raise argparse.ArgumentTypeError(msg)
        shape[name] = int(count)
    return shape


def validate_shape(document: object, expected: dict[str, int]) -> list[str]:
    """Compare the number of memberships per role with the declared program shape."""
    if not isinstance(document, dict):
        return []  # validate_manifest already reports an unusable document
    entries = cast("dict[str, object]", document).get("entries")
    if not isinstance(entries, list):
        return []
    counts: dict[str, int] = {}
    for entry in cast("list[object]", entries):
        if isinstance(entry, dict):
            role = str(cast("dict[str, object]", entry).get("role"))
            counts[role] = counts.get(role, 0) + 1
    return [
        f"expected {want} {name} membership(s) ({SHAPE_ROLES[name]}), found "
        f"{counts.get(SHAPE_ROLES[name], 0)}"
        for name, want in expected.items()
        if counts.get(SHAPE_ROLES[name], 0) != want
    ]


class _Args(argparse.Namespace):
    """Typed view of the parsed command line."""

    manifest: Path = Path()
    expect_shape: dict[str, int] | None = None
    require_label_check: bool = False


def main(argv: list[str] | None = None) -> int:
    """Validate a JSON file and return a shell-friendly exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--expect-shape",
        type=parse_shape,
        metavar="baseline=N,hidden_repeat=N,holdout=N",
        help="also require exactly this many memberships per role",
    )
    parser.add_argument(
        "--require-label-check",
        action="store_true",
        help="require label_checked_by (two different people) on every entry",
    )
    args = parser.parse_args(argv, namespace=_Args())
    try:
        document = cast("object", json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"manifest could not be read: {exc}", file=sys.stderr)
        return 2
    errors = validate_manifest(document, require_label_check=args.require_label_check)
    if args.expect_shape:
        errors.extend(validate_shape(document, args.expect_shape))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    entries = cast("dict[str, list[object]]", document)["entries"]
    print(f"valid calibration manifest: {len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
