---
title: "Olfactory Vocabulary: Faceted Terms, Source-Attributed Assertions, and Four-Layer Intake"
schema_type: common
status: draft
owner: core-maintainer
purpose: >-
  Design a project-owned faceted olfactory vocabulary (primary family plus ranked
  descriptors), modeled on ScenTree's classification shape but not its content, with a
  four-layer pipeline that lets niche houses, Fragella, and evaluators all report in their
  own words while classification stays ours.
tags:
  - taxonomy
  - design
  - architecture
  - specifications
---

Date: 2026-09-24
Milestone: the ADR-012 `SourceSnapshot` amendment columns ride **R8** (pre-F1, already planned);
`declared_label` and layers 2 to 4 are **D1** (`Depends on: F1`,
[PROJECT-PLAN.md section 13](../../planning/PROJECT-PLAN.md)).
Governing ADRs: ADR-004, ADR-006, ADR-010, ADR-012, ADR-013; proposes ADR-017.

## Problem

Fragella does not cover the niche houses this project targets, so the project needs its own
structure to take in information from those houses and from evaluators. Today the taxonomy is
thin: Michael Edwards families are hardcoded strings on `Fragrance.primary_family`/`subfamily`,
`Note.category`/`subcategory` are free text, accords are free text, and
`Observation.perceived_notes` is a free-text JSON array. ADR-010's `ClassificationSystem` and
ADR-004's `provider_term_mapping` are proposed but unbuilt. No raw label from any source is
mapped to any vocabulary.

## Premise notes

- **Structure, not content.** ScenTree (815 raw-material records, 17 families, 92 descriptors,
  verified 2026-09-24 at <https://www.scentree.co/en/discover_scentree.html>) contributes its
  *shape*: one primary family plus descriptors ordered by olfactory importance. A data model is
  not copyrightable. ScenTree's term list and material-to-descriptor assignments are the part
  under a rights question: its About page claims CC BY-NC 4.0, its Legal page
  (<https://www.scentree.co/en/legal.html>) prohibits any reproduction or adaptation without
  prior written authorization, and neither page says which elements each statement covers.
- **ScenTree classifies raw materials, not notes or perfumes.** It has no accord concept.
  Applying its structure to notes and finished fragrances is this project's extension, not a
  ScenTree claim.
- **Sequencing.** D1 is blocked until an F1 "proceed to D1" decision. This spec and the
  vocabulary content are desk work that cannot affect F1; schema and services are not built
  before D1. Evaluator-facing vocabulary must not alter the F1 calibration protocol.

## Decisions

| Decision | Choice |
| --- | --- |
| Canonical vocabulary | Project-owned terms; ScenTree, Edwards, SFP, Cinquieme Sens map onto it via crosswalk |
| Family/descriptor relation | Faceted storage is the source of truth, plus a separate UI/teaching display tree |
| Expert-baseline assertions | LLM drafts, product owner approves; nothing enters the baseline unapproved |
| ScenTree use before permission | Reference-only: consulted manually during review, cited by URL, nothing stored |
| Review surface | Spreadsheet round-trip with fingerprinted sets |
| House intake instrument | Separate follow-up spec built on this model |

## Architecture: four layers

```text
LAYER 1  RAW DECLARATION   what a source said, stored as given
  SourceSnapshot   exists; ADR-012 amendment columns applied under R8
  Observation      exists; evaluator data, separate from source evidence
  declared_label   NEW (D1; not R8, unlike the SourceSnapshot columns above)
LAYER 2  NORMALIZATION     raw text -> canonical concept
  Note                     exists; category/subcategory deprecated in favor of layer 3
  provider_term_mapping    NEW (ADR-004/013 spec, never built; R6 ships NoteAlias first,
                            already planned pre-F1, migrated into this table in D1)
LAYER 3  CLASSIFICATION    canonical concept -> our vocabulary
  vocabulary, vocabulary_term, vocabulary_display_node, assertion_source, term_assertion
LAYER 4  PROFILE           fragrance -> family + ranked descriptors
  derived in feature space fs-v2; asserted via term_assertion(fragrance_id)
```

Houses are never asked to answer in our vocabulary. Their words land in layer 1 verbatim; the
mapping in layers 2 and 3 is ours and is reviewed. This keeps "marketing note is not formula
disclosure" auditable and satisfies ADR-006's separate-layers rule.

### Entities

**`declared_label`** (layer 1): `id`, `snapshot_id` XOR `observation_id` (CHECK exactly one),
`label_kind` (`note | accord | family | descriptor`), `raw_text` (verbatim, never normalized),
`position` (`top | heart | base | unspecified`), `source_order` (nullable int), `created_at`.
Fragella results are **not** a carrier: ADR-012 keeps them in `fragella_lookups`, never in
`SourceSnapshot`. Fragella is read only for alias discovery (drafting `provider_term_mapping`
rows); no fragrance profile is ever built from Fragella data.

**`provider_term_mapping`** (layer 2): `provider_key` (`fragella`, `house:<brand_id>`,
`evaluator`, `edwards`, ...), `raw_term`, target `note_id` XOR `term_id`, `status`
(`draft | approved | rejected`), `reviewer`, `reviewed_at`, `source_value_hash` (ADR-004; a hash
of the provider's canonical value as read at `verified_at`, so re-verification can detect a
silent upstream rename). Many-to-one only after approval (tech-spec D1 contract). Ambiguous
labels stay unresolved until reviewed. Milestone R6 ships `NoteAlias`, already planned and
pre-F1, for the same note-normalization problem; D1 migrates `NoteAlias` rows into this table
rather than keeping both.

**`vocabulary`** (layer 3): realizes ADR-010's `ClassificationSystem`. `code`, `version`,
`owner` (`project | external`), `status` (`draft | published | retired`), `license_id`,
`provenance`, `content_hash`. `content_hash` excludes `status`: a draft file and the same content
later flipped to `published`, with no other change, hash identically. The project vocabulary is
`fr-core`.
Edwards becomes an external, family-only vocabulary; the Edwards family strings currently
stored as values in `Fragrance.primary_family` and `Fragrance.subfamily` migrate to it
(`core/vocabulary.py` holds no Edwards constants; verified 2026-09-24).

**`vocabulary_term`**: `vocabulary_id`, `code`, `label`, `kind` (`family | descriptor`),
`usual_family_hint` (nullable, descriptors only, informational), `definition` (text,
required), `active`.

**`vocabulary_display_node`**: `vocabulary_id`, `parent_id`, `term_id` (nullable for pure
headings), `heading` (text, nullable; exactly one of `heading` or `term_id` is set),
`sort_order`. UI and teaching only. This shape lets the versioned YAML file (which carries
`heading` and `term` per node the same way) seed these tables directly.

**`assertion_source`**: lookup following the `TrainingEligibility` stable-code pattern
(`models/fragrance.py`). Rows: `expert_baseline`, `evaluator`, `manufacturer`, and future
`crosswalk:<system>`. Carries `license_id`, `commercial_use` (bool), `training_allowed`
(bool), `attribution_text`.

**`term_assertion`**: `note_id` XOR `fragrance_id` XOR `observation_id` (CHECK exactly one;
`material_id` added in the later material-layer sub-project), `vocabulary_id`, `term_id`,
`rank`, `source_id`, `status` (`draft | approved | rejected | superseded`), `set_id` (groups
one subject's family plus descriptors), `declared_label_id` (nullable evidence link, required
for `manufacturer`), `evidence_note`, `drafted_by`, `reviewer`, `reviewed_at`.

## Rank semantics

- Rank 0 is the primary family; only `kind=family` terms. Ranks 1 to 5 are descriptors; only
  `kind=descriptor` terms. Enforced in the service (cross-table rule) and pinned by tests.
- Rank is ordinal olfactory prominence, not intensity. Any numeric weighting is defined and
  versioned in `fs-v2`, never stored.
- Partial unique indexes where `status='approved'`: (subject, source, vocabulary, rank) and
  (subject, source, vocabulary, term).
- Every assertion pins one vocabulary version.

## Lifecycle and review

```text
draft --approve--> approved --revise--> superseded   (new approved set replaces it)
  '--reject--> rejected
```

- Approved rows are immutable; revision writes a new set and supersedes the old one.
- Approval is per set (family plus ordered descriptors together), not per row.

| Source | Created by | Initial status |
| --- | --- | --- |
| `expert_baseline` | LLM drafting script (OpenRouter, ADR-003) | `draft` |
| `manufacturer` | Mapping a house's `declared_label` rows to our terms | `draft` (approve fidelity to their words) |
| `evaluator` | Evaluator form, sub-project 3, post-F1 protocol version | `approved` at capture; never counted as baseline |
| `crosswalk:<system>` | Not stored while ScenTree is reference-only | none |

**Drafting** sends only note names and the `fr-core` vocabulary to the LLM, never evaluator
data, and never fetches or passes ScenTree pages (automated fetching would be crawling). The
reviewer consults ScenTree manually and records `consulted: <URL>` in `evidence_note`.

**Spreadsheet round-trip.** Export rows carry assertion id, subject id, and a set fingerprint
(hash of the draft set at export). Editable: term, rank, per-set `decision`
(`approve | reject | edit`). Import validates term codes against the pinned vocabulary,
family-only-at-rank-0, contiguous ranks from 1, no duplicate terms, and fingerprint match.
Each set applies atomically; a stale fingerprint refuses that set; a set already applied
reports `already applied` (import is idempotent). Review files live in
`tmp_cleanup/vocab-review/` (gitignored). The validator is a reusable module so the house
intake spec can reuse it.

## Permissions, licensing, purge

Permission is resolved through each assertion's evidence chain:

```text
manufacturer    -> declared_label -> SourceSnapshot.permission_state
evaluator       -> Observation    -> TrainingEligibility (exists)
expert_baseline -> project-owned, no upstream chain
```

The feature builder includes an assertion only if every link permits training; a commercial
build additionally requires `assertion_source.commercial_use=true`. If ScenTree grants
permission, `crosswalk:scentree` is one `assertion_source` row (`CC-BY-NC-4.0`,
`commercial_use=false`), excluded from commercial builds by the same filter.

**Purge by source** is an explicit service operation, not a DB cascade (FKs stay `RESTRICT`):
dry run by default with per-layer counts, `--execute` plus a reason to apply, one transaction,
idempotent, audited. First uses: Fragella subscription lapse, house permission withdrawal,
ScenTree refusal or revocation.

## Display tree consistency

A vocabulary version cannot move to `published` unless: every active term appears in the tree
at least once (a descriptor may appear under several families); all nodes reference terms of
the same version; the tree is acyclic with depth at most 4, where the top-level list is level 1
and each `children` list adds one level (a heading, family, descriptor chain is 3 levels deep,
leaving one level of headroom). An import-boundary test fails if any scoring, feature, or ML
module imports the display tree.

## ADR changes

- **New ADR-017**: project-owned faceted olfactory vocabulary and source-attributed assertions.
- **ADR-013 pointer amendment**: Cinquieme Sens moves from primary vocabulary authority to a
  crosswalk target; the canonical vocabulary is project-owned.
- **ADR-010 pointer amendment**: `ClassificationSystem` is realized as `vocabulary`; Edwards
  becomes an external family-only vocabulary.
- **ADR-004 note**: `provider_term_mapping` target generalized to `note_id` XOR `term_id`.

This follows D1's standing default for "one global family taxonomy": preserve source-specific
classifications and explicit mapping versions. No source's own classification is overwritten.

## Error handling

| Failure | Response |
| --- | --- |
| XOR carrier or subject violation, wrong kind at rank, duplicate term | `ValidationError(field=...)`; DB CHECK or partial index backs the service check |
| Mutating an approved row | `BusinessLogicError`; only supersede |
| OpenRouter unavailable | `ExternalServiceError`; drafting transactional per subject; batch report lists skips |
| Unparseable LLM output | Subject rejected and logged; `#ASSUME: external-resources` with `#VERIFY: pydantic validation before write` |
| Import set failure | That set only; others proceed; report lists each |
| Purge | `#CRITICAL: data-integrity`; dry run default; `--execute` plus reason |

## Testing

- **Layer 1**: flush fails with both or neither carrier; `raw_text` round-trips exactly
  (`vanille`, `Acqua di Giò`).
- **Layer 2 (D1 required fixtures)**: `oak moss`/`oakmoss`, `vanille`/`vanilla` resolve only
  via approved mappings; `amber` stays unresolved until reviewed; unknown terms queue; mapped
  duplicates dedupe within a fragrance for statistics while every source label survives;
  sparse or minimalist fragrances.
- **Layer 3**: family-only-at-rank-0; both partial unique indexes; supersede preserves the
  prior set; vocabulary version pinning; each publish check; the display-tree import boundary.
- **Import**: stale fingerprint refused; unknown term code; rank gap; duplicate term; mixed
  file applies valid sets only; re-import of an applied file is a no-op.
- **Permissions**: training filter drops `retain_for_qc_only` and ineligible-observation
  chains; commercial filter drops `commercial_use=false`; Fragella never yields a profile.
- **Purge**: dry-run counts equal executed deletions; second run deletes zero.
- **Feature space**: `fs-v2` derived profile is deterministic for fixed inputs.

## Sub-projects and order

| # | Sub-project | Depends on | When |
| --- | --- | --- | --- |
| 1 | Vocabulary and assertion model (this spec) | none | Spec and `fr-core` content now; build in D1 |
| 2 | Note vocabulary: map existing notes onto `fr-core` | 1 | D1 |
| 3 | Evaluator descriptors in the rating flow | 1 | New calibration protocol version after F1 |
| 4 | Fragrance profile, `fs-v2` | 1, and 2 or 3 | D1 or later |
| 5 | Material layer (notes to candidate materials, flagged inferred) | 1, ScenTree rights | Later D milestone |
| next | House intake instrument | this spec | Next spec; raw capture (`declared_label`) rides D1 |

## Out of scope

- Storing any ScenTree term, assignment, or narrative before written permission.
- Changing the F1 calibration protocol or evaluator form.
- A web review UI (the service layer supports one later).
- Treating house-declared notes as formula disclosure.

## Follow-up actions

- Send a permission request to `contact@scentree.co` (draft kept local in
  `tmp_cleanup/letters/`; not sent without product-owner review). Ask specifically: whether
  the CC BY-NC 4.0 grant covers the family/descriptor list and per-ingredient classifications;
  whether storing targeted assignments for owned materials in a private database is permitted;
  whether ML training on them is permitted; and terms for commercial use.
- Author `fr-core` v0 terms and display tree as a versioned project-owned file.
