---
title: "fr-core Vocabulary v0 Authoring Plan"
schema_type: planning
component: Strategy
source: "docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md"
status: draft
owner: core-maintainer
purpose: "Author the project-owned fr-core olfactory vocabulary v0 as a validated, versioned data file, without building any D1 schema or services."
tags:
  - taxonomy
  - validation
  - specifications
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

## Goal

Produce `data/vocabulary/fr-core-v0.yaml`: the project-owned family and descriptor terms plus
a teaching display tree. A committed validator enforces the spec's publish checks against it.

## Architecture

This plan covers the "author now" half of the approved sequencing only. It adds a data file, a
standalone validator script (same pattern as `scripts/validate_calibration_manifest.py`), and
unit tests. It adds **no** SQLAlchemy models, Alembic migrations, services, or API routes;
those are D1 work, gated on the F1 proceed decision (PROJECT-PLAN section 13). The file shape
mirrors the future `vocabulary`, `vocabulary_term`, and `vocabulary_display_node` tables, so a
D1 seeder can load it directly.

## Tech Stack

Python 3.12, `ruamel.yaml` (already in the `dev` extra of `[project.optional-dependencies]`),
argparse, pytest.

## Scope guardrails

- Vocabulary `status` stays `draft`. Only the product owner flips it to `published`, after
  reading it. No task in this plan changes it.
- The vocabulary is authored independently. Do not open, fetch, or paste ScenTree's descriptor
  list or any ScenTree record while authoring. Generic perfumery words (Citrus, Floral, Woody)
  will overlap with every classification system. That is expected, and it is not copying.
- The Fragella note names used in Task 4 are local, gitignored data (`retain_for_qc_only`).
  The coverage probe output stays in `tmp_cleanup/vocab-review/` and is never committed.

## File structure

| Path | Responsibility |
| --- | --- |
| `scripts/validate_vocabulary.py` | Load a vocabulary YAML file, return a list of error strings, print a content hash |
| `tests/unit/test_validate_vocabulary.py` | Unit tests for every validator rule |
| `data/vocabulary/fr-core-v0.yaml` | The vocabulary content (draft) |
| `data/vocabulary/README.md` | What the file is, how to validate it, who may publish it |
| `docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md` | Correction: Edwards strings live in DB values, not `vocabulary.py` |
| `docs/planning/adr/adr-010-preference-learning-and-scenario-data-model.md` | Same correction in the 2026-09-24 pointer amendment |
| `tmp_cleanup/vocab-review/coverage-probe-v0.csv` | Local-only coverage probe (not committed; `tmp_cleanup/` is gitignored) |

### File format (the contract every task uses)

```yaml
vocabulary:
  code: fr-core            # slug
  version: "0.1.0"         # semver string
  owner: project           # project | external
  status: draft            # draft | published | retired
  license_id: project-owned
  provenance: "Authored independently for fragrance-rater, 2026-09-24."
terms:
  - code: woody            # slug, unique across terms
    kind: family           # family | descriptor
    label: Woody           # unique, case-insensitive
    definition: "Smells of wood: dry, resinous, or creamy timber."
    active: true
  - code: dry-woods
    kind: descriptor
    label: Dry woods
    usual_family_hint: woody   # descriptors only; must name a family code
    definition: "Dry, pencil-shaving or cedar-like wood."
    active: true
display_tree:              # nested list; UI/teaching only, never read by scoring
  - heading: Woods         # a node has exactly one of: heading, term
    children:
      - term: woody
        children:
          - term: dry-woods
```

---

### Task 1: Correct the Edwards-strings location in spec and ADR-010

**Files:**

- Modify: `docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md` (the `vocabulary`
  entity paragraph)
- Modify: `docs/planning/adr/adr-010-preference-learning-and-scenario-data-model.md`
  (the `## 2026-09-24 amendment (pointer to ADR-015)` section)

- [ ] **Step 1: Find both claims**

Run: `grep -n "vocabulary.py" docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md docs/planning/adr/adr-010-preference-learning-and-scenario-data-model.md docs/planning/adr/adr-015-project-owned-faceted-olfactory-vocabulary.md`
Expected: one or more hits that say Edwards strings in `vocabulary.py` migrate.
Abort if: no hits (someone already fixed it; skip to Task 2).

- [ ] **Step 2: Replace each claim**

Replace wording of the form "`vocabulary.py`'s hardcoded strings migrate to it" with:
"the Edwards family strings currently stored as values in `Fragrance.primary_family` and
`Fragrance.subfamily` migrate to it (`core/vocabulary.py` holds no Edwards constants; verified
2026-09-24)". Apply this in every file Step 1 found.

- [ ] **Step 3: Verify**

Run: `grep -rn "vocabulary.py" docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md docs/planning/adr/`
Expected: every remaining hit includes "holds no Edwards constants".

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md docs/planning/adr/adr-010-preference-learning-and-scenario-data-model.md docs/planning/adr/adr-015-project-owned-faceted-olfactory-vocabulary.md
git commit -S -m "docs(taxonomy): correct where Edwards family strings live"
```

(Stage `adr-015` only if Step 1 found a hit there.)

---

### Task 2: Validator, header and term rules (TDD)

`depends-on: none`

**Files:**

- Create: `scripts/validate_vocabulary.py`
- Create: `tests/unit/test_validate_vocabulary.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for scripts/validate_vocabulary.py."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_validate_vocabulary.py -v`
Expected: collection ERROR, `FileNotFoundError` or spec loader failure for
`scripts/validate_vocabulary.py`.

- [ ] **Step 3: Write the minimal implementation (header and term rules)**

```python
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
    errors: list[str] = []
    if not SLUG.match(_text(header.get("code"))):
        errors.append("vocabulary.code must be a lowercase slug")
    if not SEMVER.match(_text(header.get("version"))):
        errors.append("vocabulary.version must be semver (e.g. 0.1.0)")
    if header.get("owner") not in OWNERS:
        errors.append(f"vocabulary.owner must be one of {OWNERS}")
    if header.get("status") not in STATUSES:
        errors.append(f"vocabulary.status must be one of {STATUSES}")
    for field in ("license_id", "provenance"):
        if not _text(header.get(field)):
            errors.append(f"vocabulary.{field} is required")
    return errors


def _validate_terms(raw_terms: object) -> tuple[list[str], dict[str, dict[str, object]]]:
    if not isinstance(raw_terms, list) or not raw_terms:
        return ["terms must be a non-empty list"], {}
    errors: list[str] = []
    by_code: dict[str, dict[str, object]] = {}
    labels: set[str] = set()
    for index, term in enumerate(raw_terms):
        if not isinstance(term, dict):
            errors.append(f"terms[{index}] must be a mapping")
            continue
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


def validate_vocabulary(document: object) -> list[str]:
    """Return every rule violation in a vocabulary document."""
    if not isinstance(document, dict):
        return ["document must be a mapping"]
    errors = [f"missing top-level key: {key}" for key in TOP_LEVEL if key not in document]
    if errors:
        return errors
    errors.extend(_validate_header(document["vocabulary"]))
    term_errors, _by_code = _validate_terms(document["terms"])
    errors.extend(term_errors)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_validate_vocabulary.py -v`
Expected: all tests PASS. (The valid fixture's display tree is not checked yet; Task 3 adds
that.)

- [ ] **Step 5: Lint**

Run: `uv run ruff check scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py && uv run ruff format --check scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py`
Expected: no findings. Fix real findings; do not add `noqa`.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py
git commit -S -m "feat(taxonomy): add vocabulary validator header and term rules"
```

---

### Task 3: Validator, display tree rules (TDD)

`depends-on: Task2 [output]`

**Files:**

- Modify: `scripts/validate_vocabulary.py`
- Modify: `tests/unit/test_validate_vocabulary.py` (append; reuse `doc()`, `terms()`,
  `validator`)

- [ ] **Step 1: Append failing tests**

```python
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
    assert "display_tree[0].children[0].children[0]: term dry-woods is inactive" in errors


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/test_validate_vocabulary.py -v`
Expected: the new tree tests FAIL (no tree checks yet); `test_content_hash_is_stable...` and
`test_descriptor_may_appear_under_several_nodes` may already pass.

- [ ] **Step 3: Implement tree checks**

Add to `scripts/validate_vocabulary.py`, above `validate_vocabulary`:

```python
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
        if depth > MAX_TREE_DEPTH:
            errors.append(f"{where}: display_tree is deeper than {MAX_TREE_DEPTH} levels")
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
```

And in `validate_vocabulary`, replace the last three lines with:

```python
    term_errors, by_code = _validate_terms(document["terms"])
    errors.extend(term_errors)
    errors.extend(_validate_tree(document["display_tree"], by_code))
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_validate_vocabulary.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

Run: `uv run ruff check scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py && uv run ruff format --check scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py`
Expected: no findings.

```bash
git add scripts/validate_vocabulary.py tests/unit/test_validate_vocabulary.py
git commit -S -m "feat(taxonomy): validate vocabulary display tree"
```

---

### Task 4: Author fr-core v0 (draft)

`depends-on: Task3 [output]` (needs the validator)

**Files:**

- Create: `data/vocabulary/fr-core-v0.yaml`

- [ ] **Step 1: Draft the header**

Use the exact header from "File format" above, with `version: "0.1.0"`, `status: draft`, and
`provenance: "Authored independently for fragrance-rater on 2026-09-24 from general perfumery
vocabulary. Not derived from ScenTree's descriptor list or any licensed compilation."`

- [ ] **Step 2: Author families**

Write 12 to 18 `kind: family` terms. Each describes the dominant olfactory character of a
material, note, or fragrance. The set must cover citrus, floral, fruity, green, herbal or
aromatic, spicy, woody, resinous or balsamic, amber, gourmand or edible, musky, animalic,
leathery, smoky, earthy or mossy, aquatic or ozonic, and aldehydic or powdery characters.
Merge or split these as judgment dictates; the list is coverage guidance, not a mandated
term list. Write every `definition` in plain words, one sentence, 20 words or fewer,
understandable to a family evaluator with no perfumery training.

- [ ] **Step 3: Author descriptors**

Write 50 to 90 `kind: descriptor` terms: finer qualities a subject can carry at ranks 1 to 5
(for example: sheer musk, powdery, soapy clean, salty, rubbery, milky, pencil shavings). Each has `usual_family_hint` naming one family code, and a one-sentence plain
definition. Descriptors must not simply repeat a family label (no descriptor `woody` beside a
family `woody`).

- [ ] **Step 4: Author the display tree**

Group families under 4 to 6 teaching headings (for example Fresh, Floral, Warm, Woody,
Unusual). Put each family's descriptors under it, following `usual_family_hint`. List a
descriptor under a second family where teaching benefits, and record why in the term's
definition only if it changes meaning. Keep depth at most 4 (heading, family, descriptor).

- [ ] **Step 5: Validate**

Run: `uv run python scripts/validate_vocabulary.py data/vocabulary/fr-core-v0.yaml`
Expected: `OK data/vocabulary/fr-core-v0.yaml sha256=<64 hex>` and exit code 0.
Abort if: errors are printed. Fix the content, not the validator.

- [ ] **Step 6: Independence check**

Run: `grep -inE "^\s+label: (Butyric Buttery|Burnt Leather|Balsamic Ambery|Solvents|Sulfuric|Undergrowth)$" data/vocabulary/fr-core-v0.yaml`
Expected: no output. These are ScenTree's distinctive published family names (the brief lists
all 17, verified against descriptors_list.html on 2026-09-24). Generic words like Citrus or
Woody are fine. Abort if: a match appears; rename it.

Then run: `grep -inE "^\s+label: (Cool spices|Terpenic|Dry woods|Camphoric|Citric|Zesty|Grassy|Ambery woods|Orris root|Buttery|Light flowers|White flowers)$" data/vocabulary/fr-core-v0.yaml`
These are the only ScenTree descriptors the brief shows. Any match is reported to the product
owner in the task summary, not aborted: some are ordinary perfumery words. The full ScenTree
descriptor list was never fetched, so descriptor overlap beyond these twelve cannot be checked
mechanically; the owner's review is the control.

- [ ] **Step 7: Commit**

```bash
git add data/vocabulary/fr-core-v0.yaml
git commit -S -m "feat(taxonomy): author fr-core vocabulary v0 draft"
```

---

### Task 5: Local coverage probe against existing note names

`depends-on: Task4 [output]`

This is vocabulary QA, not layer-3 assertions. Nothing from this task goes into git or any
database.

**Files:**

- Create (local only): `tmp_cleanup/vocab-review/coverage-probe-v0.csv`
- Read (local only): the main checkout's
  `tmp_cleanup/fragella-non-panel-collection/unique_notes.json` (285 entries, fields `name`,
  `count`, `source_ids`)

- [ ] **Step 1: Confirm the output path is ignored**

Run: `git -C /home/byron/dev/fragrance-rater check-ignore -v tmp_cleanup/vocab-review/coverage-probe-v0.csv`
Expected: a `.gitignore` rule matching `tmp_cleanup/`.
Abort if: no rule matches.

- [ ] **Step 2: Classify every note name**

For each of the 285 note names, assign the single best `fr-core` family code, or `NONE` if no
family fits. Write `/home/byron/dev/fragrance-rater/tmp_cleanup/vocab-review/coverage-probe-v0.csv`
with columns `note_name,count,family_code,fit` where `fit` is `good`, `weak`, or `none`.

- [ ] **Step 3: Summarize gaps**

Report the counts of `good`, `weak` and `none` (weighted and unweighted by `count`), and list
every `none` or `weak` note. A gap is a vocabulary finding only when several notes share it.

- [ ] **Step 4: Revise the vocabulary if a real gap exists**

If three or more `none`/`weak` notes share a missing character, add or adjust terms in
`data/vocabulary/fr-core-v0.yaml`, rerun the validator (Task 4 Step 5), and commit:

```bash
git add data/vocabulary/fr-core-v0.yaml
git commit -S -m "feat(taxonomy): close fr-core v0 coverage gaps from note probe"
```

If no shared gap exists, record that in the task report and make no commit.

---

### Task 6: README for the vocabulary directory

`depends-on: Task4 [completion]`

**Files:**

- Create: `data/vocabulary/README.md`

- [ ] **Step 1: Write the README**

```markdown
# Project-owned vocabularies

`fr-core-v0.yaml` is fragrance-rater's own olfactory vocabulary: primary families plus
descriptors that a note, material, or fragrance can carry at ranks 1 to 5, and a display tree
for browsing and teaching. Design and rules:
[olfactory vocabulary spec](../../docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md)
and ADR-015.

## Rules

- The display tree is for UI and teaching only. Scoring, features, and ML never read it.
- Families and descriptors are independent lists. `usual_family_hint` is informational.
- `status` changes from `draft` to `published` only by the product owner, after review.
- A new version is a new file (`fr-core-v1.yaml`). Published files are never edited in place.

## Validate

    uv run python scripts/validate_vocabulary.py data/vocabulary/fr-core-v0.yaml

Exit 0 prints the file's SHA-256 content hash, which the D1 `vocabulary.content_hash` column
will record. Exit 1 lists rule violations. Exit 2 means the file could not be read.
```

- [ ] **Step 2: Lint and commit**

Run: `pre-commit run --files data/vocabulary/README.md data/vocabulary/fr-core-v0.yaml`
Expected: all hooks pass (markdownlint, em-dash, yamllint).

```bash
git add data/vocabulary/README.md
git commit -S -m "docs(taxonomy): document the vocabulary directory"
```

---

### Task 7: Final verification

`depends-on: Task5 [completion], Task6 [completion]`

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all pass, with no new failures compared to `origin/main`.

- [ ] **Step 2: Pre-commit on every changed file**

Run: `pre-commit run --files $(git diff --name-only origin/main...HEAD)`
Expected: all hooks pass.

- [ ] **Step 3: Scope check**

Run: `git diff --name-only origin/main...HEAD | grep -E "^(src/|alembic/|migrations/)"`
Expected: no output. This plan adds no application code or migrations.
Abort if: any path matches; D1 work leaked in.

- [ ] **Step 4: Status check**

Run: `grep -n "status:" data/vocabulary/fr-core-v0.yaml | head -1`
Expected: `status: draft`.

## Spec coverage

| Spec clause | Task |
| --- | --- |
| Project-owned `fr-core` vocabulary, versioned, `draft/published/retired` | 2, 4 |
| `vocabulary_term` fields: code, label, kind, usual_family_hint, active | 2, 4 |
| Publish check: every active term in the tree | 3 |
| Publish check: nodes reference terms of the same version | 3 (single-file scope) |
| Publish check: acyclic, depth at most 4 | 3 (YAML anchors can build a cycle; the depth limit rejects it) |
| Publish check: import boundary on display tree | D1 (no display-tree module exists yet) |
| `content_hash` | 2, 3 |
| Author vocabulary content now | 4, 5 |
| Everything in layers 1 to 4 that needs schema or services | D1, not this plan |
