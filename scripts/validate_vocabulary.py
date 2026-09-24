#!/usr/bin/env python3
"""Validate a project-owned olfactory vocabulary file.

Checks the header, the term list, and the UI-only display tree against the
publish rules in docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
STATUSES = ("draft", "published", "retired")
OWNERS = ("project", "external")
KINDS = ("family", "descriptor")
TOP_LEVEL = ("vocabulary", "terms", "display_tree")
MAX_TREE_DEPTH = 4


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate_header(header: object) -> list[str]:
    if not isinstance(header, dict):
        return ["vocabulary must be a mapping"]
    header = cast("dict[str, object]", header)
    errors: list[str] = []
    if not SLUG.match(_text(header.get("code"))):
        errors.append("vocabulary.code must be a lowercase slug")
    if not SEMVER.match(_text(header.get("version"))):
        errors.append("vocabulary.version must be semver (e.g. 0.1.0)")
    if header.get("owner") not in OWNERS:
        errors.append(f"vocabulary.owner must be one of {OWNERS}")
    if header.get("status") not in STATUSES:
        errors.append(f"vocabulary.status must be one of {STATUSES}")
    errors.extend(
        f"vocabulary.{field} is required"
        for field in ("license_id", "provenance")
        if not _text(header.get(field))
    )
    return errors


def _validate_terms(
    raw_terms: object,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    if not isinstance(raw_terms, list) or not raw_terms:
        return ["terms must be a non-empty list"], {}
    errors: list[str] = []
    by_code: dict[str, dict[str, object]] = {}
    labels: set[str] = set()
    for index, term in enumerate(raw_terms):
        if not isinstance(term, dict):
            errors.append(f"terms[{index}] must be a mapping")
            continue
        term = cast("dict[str, object]", term)
        code = _text(term.get("code"))
        if not SLUG.match(code):
            errors.append(f"terms[{index}]: code must be a lowercase slug")
            continue
        if code in by_code:
            errors.append(f"duplicate term code: {code}")
            continue
        by_code[code] = term
        label = _text(term.get("label")).casefold()
        if not label:
            errors.append(f"term {code}: label is required")
        elif label in labels:
            errors.append(f"duplicate term label: {label}")
        labels.add(label)
        if term.get("kind") not in KINDS:
            errors.append(f"term {code}: kind must be family or descriptor")
        if not _text(term.get("definition")):
            errors.append(f"term {code}: definition is required")
        if not isinstance(term.get("active"), bool):
            errors.append(f"term {code}: active must be true or false")
    for code, term in by_code.items():
        hint = term.get("usual_family_hint")
        if hint is None:
            continue
        if term.get("kind") == "family":
            errors.append(f"term {code}: families may not have usual_family_hint")
        elif by_code.get(str(hint), {}).get("kind") != "family":
            errors.append(f"term {code}: usual_family_hint {hint} is not a family")
    return errors, by_code


def _walk_tree(
    nodes: object,
    by_code: dict[str, dict[str, object]],
    path: str,
    depth: int,
    seen: set[str],
    errors: list[str],
) -> None:
    if not isinstance(nodes, list):
        errors.append(f"{path}: must be a list")
        return
    for index, node in enumerate(nodes):
        where = f"{path}[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{where}: node must be a mapping")
            continue
        node = cast("dict[str, object]", node)
        if depth > MAX_TREE_DEPTH:
            errors.append(
                f"{where}: display_tree is deeper than {MAX_TREE_DEPTH} levels"
            )
            continue
        has_heading = bool(_text(node.get("heading")))
        term_code = _text(node.get("term"))
        if has_heading == bool(term_code):
            errors.append(f"{where}: node needs exactly one of heading or term")
        elif term_code:
            term = by_code.get(term_code)
            if term is None:
                errors.append(f"{where}: unknown term {term_code}")
            elif term.get("active") is not True:
                errors.append(f"{where}: term {term_code} is inactive")
            else:
                seen.add(term_code)
        children = node.get("children")
        if children is None:
            if has_heading and not term_code:
                errors.append(f"{where}: heading {node.get('heading')} has no children")
            continue
        _walk_tree(children, by_code, f"{where}.children", depth + 1, seen, errors)


def _validate_tree(tree: object, by_code: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    _walk_tree(tree, by_code, "display_tree", 1, seen, errors)
    for code, term in by_code.items():
        if term.get("active") is True and code not in seen:
            errors.append(f"active term {code} is missing from display_tree")
    return errors


def validate_vocabulary(document: object) -> list[str]:
    """Return every rule violation in a vocabulary document."""
    if not isinstance(document, dict):
        return ["document must be a mapping"]
    errors = [
        f"missing top-level key: {key}" for key in TOP_LEVEL if key not in document
    ]
    if errors:
        return errors
    errors.extend(_validate_header(document["vocabulary"]))
    term_errors, by_code = _validate_terms(document["terms"])
    errors.extend(term_errors)
    errors.extend(_validate_tree(document["display_tree"], by_code))
    return errors


def content_hash(document: object) -> str:
    """Return a SHA-256 of the canonical JSON form of the document."""
    canonical = json.dumps(document, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    """Validate a vocabulary file and print its content hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        document = YAML(typ="safe").load(args.path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    errors = validate_vocabulary(document)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"OK {args.path} sha256={content_hash(document)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
