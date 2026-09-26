"""Tests for scripts/validate_vocabulary.py."""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
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


class _ValidatorModule(Protocol):
    """Static shape of scripts/validate_vocabulary.py for the dynamic import above."""

    validate_vocabulary: Callable[[object], list[str]]
    content_hash: Callable[[object], str]
    main: Callable[[], int]


validator = cast("_ValidatorModule", load_script("validate_vocabulary"))

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

VALID_YAML_TEXT = """\
vocabulary:
  code: fr-core
  version: "0.1.0"
  owner: project
  status: draft
  license_id: project-owned
  provenance: "Authored independently."
terms:
  - code: woody
    kind: family
    label: Woody
    definition: "Smells of wood."
    active: true
  - code: dry-woods
    kind: descriptor
    label: Dry woods
    usual_family_hint: woody
    definition: "Dry, cedar-like wood."
    active: true
display_tree:
  - heading: Woods
    children:
      - term: woody
        children:
          - term: dry-woods
"""


def doc() -> dict[str, object]:
    """Return a fresh deep copy of the valid document."""
    return copy.deepcopy(VALID)


def terms(document: dict[str, object]) -> list[dict[str, object]]:
    """Return the mutable terms list of a document."""
    return cast("list[dict[str, object]]", document["terms"])


def tree(document: dict[str, object]) -> list[dict[str, object]]:
    """Return the mutable display tree of a document."""
    return cast("list[dict[str, object]]", document["display_tree"])


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


def test_missing_top_level_key_still_reports_other_errors() -> None:
    document = doc()
    del document["terms"]
    header = cast("dict[str, object]", document["vocabulary"])
    header["status"] = "final"
    errors = validator.validate_vocabulary(document)
    assert "missing top-level key: terms" in errors
    assert any(
        error.startswith("vocabulary.status must be one of") for error in errors
    ), errors


def test_unknown_top_level_key() -> None:
    document = doc()
    document["extra"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "unknown top-level key: extra" in errors


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


def test_non_mapping_header() -> None:
    document = doc()
    document["vocabulary"] = "nope"
    assert validator.validate_vocabulary(document) == ["vocabulary must be a mapping"]


def test_unknown_header_key() -> None:
    document = doc()
    header = cast("dict[str, object]", document["vocabulary"])
    header["extra"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "vocabulary: unknown key: extra" in errors


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("code", "vocabulary.code has leading or trailing whitespace"),
        ("version", "vocabulary.version has leading or trailing whitespace"),
        ("license_id", "vocabulary.license_id has leading or trailing whitespace"),
        ("provenance", "vocabulary.provenance has leading or trailing whitespace"),
    ],
)
def test_header_whitespace(field: str, message: str) -> None:
    document = doc()
    header = cast("dict[str, object]", document["vocabulary"])
    header[field] = f" {header[field]} "
    errors = validator.validate_vocabulary(document)
    assert message in errors


def test_empty_terms_list() -> None:
    document = doc()
    document["terms"] = []
    errors = validator.validate_vocabulary(document)
    assert "terms must be a non-empty list" in errors


def test_non_list_terms() -> None:
    document = doc()
    document["terms"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "terms must be a non-empty list" in errors


def test_non_mapping_term() -> None:
    document = doc()
    terms(document).append(cast("dict[str, object]", "nope"))
    errors = validator.validate_vocabulary(document)
    assert "terms[2] must be a mapping" in errors


def test_invalid_term_code_slug() -> None:
    document = doc()
    terms(document)[1]["code"] = "Dry Woods"
    errors = validator.validate_vocabulary(document)
    assert "terms[1]: code must be a lowercase slug" in errors


def test_invalid_term_code_still_validates_other_fields() -> None:
    document = doc()
    terms(document)[1]["code"] = "Dry Woods"
    terms(document)[1]["label"] = ""
    errors = validator.validate_vocabulary(document)
    assert "terms[1]: code must be a lowercase slug" in errors
    assert "terms[1]: label is required" in errors


@pytest.mark.parametrize("code", ["a--b", "a-", "1abc", "-a"])
def test_slug_rejects_malformed_codes(code: str) -> None:
    document = doc()
    terms(document)[1]["code"] = code
    errors = validator.validate_vocabulary(document)
    assert "terms[1]: code must be a lowercase slug" in errors


def test_unknown_term_key() -> None:
    document = doc()
    terms(document)[1]["extra"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "terms[1]: unknown key: extra" in errors


def test_term_code_whitespace() -> None:
    document = doc()
    terms(document)[1]["code"] = " dry-woods "
    errors = validator.validate_vocabulary(document)
    assert "terms[1]: code has leading or trailing whitespace" in errors


def test_term_label_whitespace() -> None:
    document = doc()
    terms(document)[1]["label"] = " Dry woods "
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: label has leading or trailing whitespace" in errors


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


def test_definition_whitespace() -> None:
    document = doc()
    terms(document)[1]["definition"] = " Dry, cedar-like wood. "
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: definition has leading or trailing whitespace" in errors


def test_definition_word_count_at_limit_is_fine() -> None:
    document = doc()
    terms(document)[1]["definition"] = " ".join(["word"] * 20) + "."
    assert validator.validate_vocabulary(document) == []


def test_definition_word_count_over_limit_is_an_error() -> None:
    document = doc()
    terms(document)[1]["definition"] = " ".join(["word"] * 21) + "."
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: definition has more than 20 words" in errors


def test_missing_label() -> None:
    document = doc()
    terms(document)[1]["label"] = ""
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: label is required" in errors


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


def test_hint_must_point_to_an_active_family() -> None:
    document = doc()
    terms(document)[0]["active"] = False
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: usual_family_hint woody is not an active family" in errors


def test_usual_family_hint_whitespace() -> None:
    document = doc()
    terms(document)[1]["usual_family_hint"] = " woody "
    errors = validator.validate_vocabulary(document)
    assert (
        "term dry-woods: usual_family_hint has leading or trailing whitespace" in errors
    )


def test_active_must_be_boolean() -> None:
    document = doc()
    terms(document)[1]["active"] = "yes"
    errors = validator.validate_vocabulary(document)
    assert "term dry-woods: active must be true or false" in errors


@pytest.mark.parametrize(
    "node",
    [
        {"heading": "Woods", "term": "woody", "children": [{"term": "dry-woods"}]},
        {"children": [{"term": "dry-woods"}]},
    ],
    ids=["both-heading-and-term", "children-only"],
)
def test_node_needs_exactly_one_of_heading_or_term(node: dict[str, object]) -> None:
    document = doc()
    tree(document)[0] = node
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


def test_heading_with_empty_children_list_is_an_error() -> None:
    document = doc()
    tree(document).append({"heading": "Empty", "children": []})
    errors = validator.validate_vocabulary(document)
    assert "display_tree[1]: heading Empty has no children" in errors


def test_non_heading_node_with_empty_children_list_is_fine() -> None:
    document = doc()
    tree(document).append({"term": "woody", "children": []})
    assert validator.validate_vocabulary(document) == []


def test_unknown_node_key() -> None:
    document = doc()
    tree(document)[0]["extra"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "display_tree[0]: unknown key: extra" in errors


def test_node_heading_whitespace() -> None:
    document = doc()
    tree(document)[0]["heading"] = " Woods "
    errors = validator.validate_vocabulary(document)
    assert "display_tree[0]: heading has leading or trailing whitespace" in errors


def test_node_term_whitespace() -> None:
    document = doc()
    root = tree(document)[0]
    children = cast("list[dict[str, object]]", root["children"])
    children[0]["term"] = " woody "
    errors = validator.validate_vocabulary(document)
    assert (
        "display_tree[0].children[0]: term has leading or trailing whitespace" in errors
    )


def test_non_mapping_node() -> None:
    document = doc()
    tree(document).append(cast("dict[str, object]", "nope"))
    errors = validator.validate_vocabulary(document)
    assert "display_tree[1]: node must be a mapping" in errors


def test_non_list_children() -> None:
    document = doc()
    tree(document)[0]["children"] = "nope"
    errors = validator.validate_vocabulary(document)
    assert "display_tree[0].children: must be a list" in errors


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


def test_depth_four_tree_has_no_depth_error() -> None:
    document = doc()
    tree(document).append(
        {
            "heading": "Outer",
            "children": [
                {
                    "heading": "Inner",
                    "children": [
                        {"term": "woody", "children": [{"term": "dry-woods"}]}
                    ],
                }
            ],
        }
    )
    errors = validator.validate_vocabulary(document)
    assert not any("deeper than" in error for error in errors), errors


def test_content_hash_is_stable_and_order_insensitive_for_keys() -> None:
    first = doc()
    second = doc()
    header = cast("dict[str, object]", second["vocabulary"])
    second["vocabulary"] = dict(reversed(list(header.items())))
    assert validator.content_hash(first) == validator.content_hash(second)
    assert len(validator.content_hash(first)) == 64


def test_content_hash_changes_when_definition_changes() -> None:
    first = doc()
    second = doc()
    terms(second)[0]["definition"] = "Different definition entirely."
    assert validator.content_hash(first) != validator.content_hash(second)


def test_content_hash_unchanged_when_only_status_changes() -> None:
    first = doc()
    second = doc()
    header = cast("dict[str, object]", second["vocabulary"])
    header["status"] = "published"
    assert validator.content_hash(first) == validator.content_hash(second)


def test_content_hash_does_not_mutate_input() -> None:
    document = doc()
    validator.content_hash(document)
    header = cast("dict[str, object]", document["vocabulary"])
    assert header["status"] == "draft"


def test_cli_exit_0_prints_ok_and_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vocab_path = tmp_path / "fr-core-v0.yaml"
    vocab_path.write_text(VALID_YAML_TEXT, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith(f"OK {vocab_path}")
    assert re.search(r"sha256=[0-9a-f]{64}\s*$", captured.out)


def test_cli_exit_1_on_rule_violation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vocab_path = tmp_path / "bad.yaml"
    vocab_path.write_text(
        VALID_YAML_TEXT.replace("status: draft", "status: final"), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "vocabulary.status must be one of" in captured.err


def test_cli_exit_2_on_missing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing.yaml"
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(missing)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cannot read" in captured.err


def test_cli_exit_2_on_non_utf8_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_path = tmp_path / "bad-encoding.yaml"
    bad_path.write_bytes(b"\xff\xfe")
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(bad_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cannot read" in captured.err


def test_cli_unknown_key_with_non_string_value_exits_1_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown key's value type does not change the outcome.

    The extra ``reviewed_on`` key is a YAML date here, not a string; the
    test only exercises that this type does not change the reported error
    or crash while iterating the document, not any date-specific behavior
    (the validator never reads the value of an unknown key at all).
    """
    vocab_path = tmp_path / "date-key.yaml"
    vocab_path.write_text(
        VALID_YAML_TEXT + "reviewed_on: 2026-09-24\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown top-level key: reviewed_on" in captured.err
    assert "Traceback" not in captured.err


def test_cli_exit_2_on_duplicate_mapping_key(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vocab_path = tmp_path / "dup-key.yaml"
    vocab_path.write_text(
        VALID_YAML_TEXT + "vocabulary:\n  code: fr-core-again\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cannot read" in captured.err
    assert "Traceback" not in captured.err


def test_cli_exit_2_on_malformed_yaml(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vocab_path = tmp_path / "malformed.yaml"
    vocab_path.write_text("vocabulary: [unclosed\n  code: fr-core\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cannot read" in captured.err
    assert "Traceback" not in captured.err


def _deeply_nested_display_tree_yaml(depth: int) -> str:
    """Build a valid header/terms document with a display_tree nested text.

    Unlike the dict-literal depth tests above, this builds the nesting as
    raw YAML text, so it exercises ruamel's parser itself rather than the
    validator's own recursive tree walk.
    """
    lines = [
        "vocabulary:",
        "  code: fr-core",
        '  version: "0.1.0"',
        "  owner: project",
        "  status: draft",
        "  license_id: project-owned",
        '  provenance: "Authored independently."',
        "terms:",
        "  - code: woody",
        "    kind: family",
        "    label: Woody",
        '    definition: "Smells of wood."',
        "    active: true",
        "display_tree:",
    ]
    indent = "  "
    for level in range(depth):
        lines.append(f'{indent}- heading: "L{level}"')
        lines.append(f"{indent}  children:")
        indent += "    "
    lines.append(f"{indent}- term: woody")
    return "\n".join(lines) + "\n"


def test_cli_exit_2_on_deeply_nested_yaml_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ~500-level nested display_tree overflows ruamel's own parser.

    200 levels is still well inside the recursion limit and produces the
    ordinary "deeper than 4 levels" rule violation (exit 1); this is about
    the parser itself, not the validator's tree walk, so it must be built
    as YAML text rather than a Python dict literal.
    """
    vocab_path = tmp_path / "too-deep.yaml"
    vocab_path.write_text(_deeply_nested_display_tree_yaml(500), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cannot read" in captured.err
    assert "Traceback" not in captured.err


def test_cli_accepts_multiple_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good_path = tmp_path / "good.yaml"
    good_path.write_text(VALID_YAML_TEXT, encoding="utf-8")
    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text(
        VALID_YAML_TEXT.replace("status: draft", "status: final"), encoding="utf-8"
    )
    monkeypatch.setattr(
        sys, "argv", ["validate_vocabulary.py", str(good_path), str(bad_path)]
    )
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out.startswith(f"OK {good_path}")
    assert "vocabulary.status must be one of" in captured.err


def test_committed_fr_core_v0_yaml_validates(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs the publish-gate rules in CI (via pytest), not only by hand."""
    vocab_path = ROOT / "data" / "vocabulary" / "fr-core-v0.yaml"
    monkeypatch.setattr(sys, "argv", ["validate_vocabulary.py", str(vocab_path)])
    exit_code = validator.main()
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert captured.out.startswith(f"OK {vocab_path}")
