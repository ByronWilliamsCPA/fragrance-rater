"""Tests for scripts/validate_vocabulary.py."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str) -> ModuleType:
    """Load a repository script as a module."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_script("validate_vocabulary")

VALID: dict[str, object] = {
    "vocabulary": {
        "code": "fr-core",
        "version": "0.1.0",
        "owner": "project",
        "status": "draft",
        "license_id": "project-owned",
        "provenance": "Authored independently.",
    },
    "terms": [
        {
            "code": "woody",
            "kind": "family",
            "label": "Woody",
            "definition": "Smells of wood.",
            "active": True,
        },
        {
            "code": "dry-woods",
            "kind": "descriptor",
            "label": "Dry woods",
            "usual_family_hint": "woody",
            "definition": "Dry, cedar-like wood.",
            "active": True,
        },
    ],
    "display_tree": [
        {
            "heading": "Woods",
            "children": [
                {"term": "woody", "children": [{"term": "dry-woods"}]},
            ],
        }
    ],
}


def doc() -> dict[str, object]:
    """Return a fresh deep copy of the valid document."""
    return copy.deepcopy(VALID)


def terms(document: dict[str, object]) -> list[dict[str, object]]:
    """Return the mutable terms list of a document."""
    return cast("list[dict[str, object]]", document["terms"])


def test_valid_document_has_no_errors() -> None:
    assert validator.validate_vocabulary(doc()) == []


def test_non_mapping_document_is_rejected() -> None:
    assert validator.validate_vocabulary(["not", "a", "mapping"]) == [
        "document must be a mapping"
    ]


@pytest.mark.parametrize("key", ["vocabulary", "terms", "display_tree"])
def test_missing_top_level_key(key: str) -> None:
    document = doc()
    del document[key]
    assert f"missing top-level key: {key}" in validator.validate_vocabulary(document)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "final", "vocabulary.status must be one of"),
        ("owner", "someone", "vocabulary.owner must be one of"),
        ("version", "v1", "vocabulary.version must be semver"),
        ("code", "FR Core", "vocabulary.code must be a lowercase slug"),
        ("license_id", "", "vocabulary.license_id is required"),
        ("provenance", "", "vocabulary.provenance is required"),
    ],
)
def test_header_rules(field: str, value: str, message: str) -> None:
    document = doc()
    header = document["vocabulary"]
    assert isinstance(header, dict)
    header[field] = value
    errors = validator.validate_vocabulary(document)
    assert any(error.startswith(message) for error in errors), errors


def test_duplicate_term_code() -> None:
    document = doc()
    terms(document)[1]["code"] = "woody"
    assert "duplicate term code: woody" in validator.validate_vocabulary(document)


def test_duplicate_label_is_case_insensitive() -> None:
    document = doc()
    terms(document)[1]["label"] = "WOODY"
    assert "duplicate term label: woody" in validator.validate_vocabulary(document)


def test_invalid_kind() -> None:
    document = doc()
    terms(document)[1]["kind"] = "accord"
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: kind must be family or descriptor" in errors


def test_missing_definition() -> None:
    document = doc()
    terms(document)[1]["definition"] = "  "
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: definition is required" in errors


def test_family_may_not_carry_hint() -> None:
    document = doc()
    terms(document)[0]["usual_family_hint"] = "woody"
    errors = validator.validate_vocabulary(document)
    assert "term woody: families may not have usual_family_hint" in errors


def test_hint_must_name_a_family() -> None:
    document = doc()
    terms(document)[1]["usual_family_hint"] = "dry-woods"
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: usual_family_hint dry-woods is not a family" in errors


def test_active_must_be_boolean() -> None:
    document = doc()
    terms(document)[1]["active"] = "yes"
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: active must be true or false" in errors


def tree(document: dict[str, object]) -> list[dict[str, object]]:
    """Return the mutable display tree of a document."""
    return cast("list[dict[str, object]]", document["display_tree"])


def test_node_needs_exactly_one_of_heading_or_term() -> None:
    document = doc()
    tree(document)[0]["term"] = "woody"
    errors = validator.validate_vocabulary(document)
    assert "display_tree[0]: node needs exactly one of heading or term" in errors


def test_node_term_must_exist() -> None:
    document = doc()
    tree(document).append({"term": "smoky"})
    errors = validator.validate_vocabulary(document)
    assert "display_tree[1]: unknown term smoky" in errors


def test_heading_needs_children() -> None:
    document = doc()
    tree(document).append({"heading": "Empty"})
    errors = validator.validate_vocabulary(document)
    assert "display_tree[1]: heading Empty has no children" in errors


def test_active_term_missing_from_tree() -> None:
    document = doc()
    terms(document).append(
        {
            "code": "smoky",
            "kind": "descriptor",
            "label": "Smoky",
            "usual_family_hint": "woody",
            "definition": "Smoke.",
            "active": True,
        }
    )
    errors = validator.validate_vocabulary(document)
    assert "active term smoky is missing from display_tree" in errors


def test_inactive_term_may_not_appear_in_tree() -> None:
    document = doc()
    terms(document)[1]["active"] = False
    errors = validator.validate_vocabulary(document)
    assert (
        "display_tree[0].children[0].children[0]: term dry-woods is inactive" in errors
    )


def test_descriptor_may_appear_under_several_nodes() -> None:
    document = doc()
    tree(document).append({"heading": "Also", "children": [{"term": "dry-woods"}]})
    assert validator.validate_vocabulary(document) == []


def test_depth_limit() -> None:
    document = doc()
    deep: dict[str, object] = {"term": "dry-woods"}
    for index in range(4):
        deep = {"heading": f"Level {index}", "children": [deep]}
    tree(document).append(deep)
    errors = validator.validate_vocabulary(document)
    assert any("deeper than 4 levels" in error for error in errors), errors


def test_content_hash_is_stable_and_order_insensitive_for_keys() -> None:
    first = doc()
    second = doc()
    header = second["vocabulary"]
    assert isinstance(header, dict)
    second["vocabulary"] = dict(reversed(list(header.items())))
    assert validator.content_hash(first) == validator.content_hash(second)
    assert len(validator.content_hash(first)) == 64
