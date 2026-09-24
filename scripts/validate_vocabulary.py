#!/usr/bin/env python3
"""Validate a project-owned olfactory vocabulary file.

Checks the header, the term list, and the UI-only display tree against the
publish rules in docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md.
"""

from __future__ import annotations

import argparse
import copy
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
TOP_LEVEL_KEYS = frozenset(TOP_LEVEL)
HEADER_KEYS = frozenset(
    {"code", "version", "owner", "status", "license_id", "provenance"}
)
TERM_KEYS = frozenset(
    {"code", "kind", "label", "usual_family_hint", "definition", "active"}
)
NODE_KEYS = frozenset({"heading", "term", "children"})
MAX_TREE_DEPTH = 4


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _whitespace_error(raw: object, location: str, field: str) -> str | None:
    if isinstance(raw, str) and raw != raw.strip():
        return f"{location}: {field} has leading or trailing whitespace"
    return None


def _is_empty_list(value: object) -> bool:
    """Return whether ``value`` is a list with no items.

    Kept as its own function (rather than inlined) so basedpyright does not
    carry an aliased isinstance narrowing of the caller's variable across the
    call boundary.
    """
    return isinstance(value, list) and not value


def _validate_header(header: object) -> list[str]:
    if not isinstance(header, dict):
        return ["vocabulary must be a mapping"]
    header = cast("dict[str, object]", header)
    errors: list[str] = [
        f"vocabulary: unknown key: {key}" for key in header if key not in HEADER_KEYS
    ]
    raw_code = header.get("code")
    if isinstance(raw_code, str) and raw_code != raw_code.strip():
        errors.append("vocabulary.code has leading or trailing whitespace")
    if not SLUG.match(_text(raw_code)):
        errors.append("vocabulary.code must be a lowercase slug")
    raw_version = header.get("version")
    if isinstance(raw_version, str) and raw_version != raw_version.strip():
        errors.append("vocabulary.version has leading or trailing whitespace")
    if not SEMVER.match(_text(raw_version)):
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
    raw_terms = cast("list[object]", raw_terms)
    errors: list[str] = []
    by_code: dict[str, dict[str, object]] = {}
    labels: set[str] = set()
    for index, term in enumerate(raw_terms):
        if not isinstance(term, dict):
            errors.append(f"terms[{index}] must be a mapping")
            continue
        term = cast("dict[str, object]", term)
        errors.extend(
            f"terms[{index}]: unknown key: {key}"
            for key in term
            if key not in TERM_KEYS
        )
        raw_code = term.get("code")
        if isinstance(raw_code, str) and raw_code != raw_code.strip():
            errors.append(f"terms[{index}]: code has leading or trailing whitespace")
        code = _text(raw_code)
        if not SLUG.match(code):
            errors.append(f"terms[{index}]: code must be a lowercase slug")
            continue
        if code in by_code:
            errors.append(f"duplicate term code: {code}")
            continue
        by_code[code] = term
        raw_label = term.get("label")
        if isinstance(raw_label, str) and raw_label != raw_label.strip():
            errors.append(f"term {code}: label has leading or trailing whitespace")
        label = _text(raw_label).casefold()
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
            continue
        target = by_code.get(str(hint))
        if target is None or target.get("kind") != "family":
            errors.append(f"term {code}: usual_family_hint {hint} is not a family")
        elif target.get("active") is not True:
            errors.append(
                f"term {code}: usual_family_hint {hint} is not an active family"
            )
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
    nodes = cast("list[object]", nodes)
    for index, node in enumerate(nodes):
        where = f"{path}[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{where}: node must be a mapping")
            continue
        node = cast("dict[str, object]", node)
        errors.extend(
            f"{where}: unknown key: {key}" for key in node if key not in NODE_KEYS
        )
        if depth > MAX_TREE_DEPTH:
            errors.append(
                f"{where}: display_tree is deeper than {MAX_TREE_DEPTH} levels"
            )
            continue
        raw_heading = node.get("heading")
        raw_term = node.get("term")
        heading_whitespace = _whitespace_error(raw_heading, where, "heading")
        if heading_whitespace:
            errors.append(heading_whitespace)
        term_whitespace = _whitespace_error(raw_term, where, "term")
        if term_whitespace:
            errors.append(term_whitespace)
        has_heading = bool(_text(raw_heading))
        term_code = _text(raw_term)
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
        is_heading_only = has_heading and not term_code
        children = node.get("children")
        if children is None or _is_empty_list(children):
            if is_heading_only:
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
    document = cast("dict[str, object]", document)
    errors = [
        f"missing top-level key: {key}" for key in TOP_LEVEL if key not in document
    ]
    if errors:
        return errors
    errors.extend(
        f"unknown top-level key: {key}" for key in document if key not in TOP_LEVEL_KEYS
    )
    errors.extend(_validate_header(document["vocabulary"]))
    term_errors, by_code = _validate_terms(document["terms"])
    errors.extend(term_errors)
    errors.extend(_validate_tree(document["display_tree"], by_code))
    return errors


def content_hash(document: object) -> str:
    """Return a SHA-256 of the canonical JSON form of the document.

    The hash excludes ``vocabulary.status`` so a draft file and the same
    content later flipped to ``published``, with no other change, hash
    identically. The input is deep-copied before ``status`` is dropped; the
    caller's document is never mutated.
    """
    hashed = copy.deepcopy(document)
    if isinstance(hashed, dict):
        hashed = cast("dict[str, object]", hashed)
        vocabulary = hashed.get("vocabulary")
        if isinstance(vocabulary, dict):
            vocabulary = cast("dict[str, object]", vocabulary)
            vocabulary.pop("status", None)
    canonical = json.dumps(hashed, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    """Validate a vocabulary file and print its content hash."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    path = cast("Path", args.path)
    try:
        document = cast(
            "object", YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    errors = validate_vocabulary(document)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    try:
        digest = content_hash(document)
    except (TypeError, ValueError) as exc:
        print(f"cannot compute content hash: {exc}", file=sys.stderr)
        return 1
    print(f"OK {path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
