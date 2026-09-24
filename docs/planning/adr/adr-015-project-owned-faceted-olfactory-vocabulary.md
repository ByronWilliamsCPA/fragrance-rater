# ADR-015: Project-Owned Faceted Olfactory Vocabulary

> **Status**: Proposed; amends ADR-004, ADR-010, ADR-013
>
> **Date**: 2026-09-24

**Numbering note**: the design that produced this record (see the spec linked under Related)
called out its target number as ADR-014, but `main` already carries two records under that
number (`adr-014-frontend-e2e-and-accessibility-strategy.md`, merged in PR #103, and
`adr-014-training-eligibility-and-unclassified-family.md`, merged in PR #105); `docs/planning/adr/README.md`
already flags the clash and states ADR-015 is free. ADR-016 (2026-09-19) already took the same
approach to avoid a third collision. This record takes 015 for the same reason.

## Context

Fragella (ADR-012) does not cover the niche houses this project targets, so the project needs
its own structure to take in information from those houses and from evaluators. Today the
taxonomy is thin: Michael Edwards families are hardcoded strings on
`Fragrance.primary_family`/`subfamily`, `Note.category`/`subcategory` are free text, accords are
free text, and `Observation.perceived_notes` is a free-text JSON array. ADR-010's
`ClassificationSystem` and ADR-004's `provider_term_mapping` are proposed but unbuilt. No raw
label from any source is mapped to any vocabulary.

Two structural constraints shape the decision below. First, a data model is not copyrightable,
but a term list and material-to-descriptor assignments can be: ScenTree (815 raw-material
records, 17 families, 92 descriptors, verified 2026-09-24 at
<https://www.scentree.co/en/discover_scentree.html>) contributes its shape, one primary family
plus descriptors ordered by olfactory importance, not its content. ScenTree's About page claims
a CC BY-NC 4.0 license; its Legal page (<https://www.scentree.co/en/legal.html>) prohibits any
reproduction or adaptation without prior written authorization; neither page states which
elements each statement covers. Until that conflict is resolved by a written reply, nothing from
ScenTree is stored. Second, ScenTree classifies raw materials, not notes or finished fragrances;
applying its structure to notes and perfumes is this project's own extension, not a ScenTree
claim.

Sequencing follows the project plan's existing gates: D1 is blocked until an F1 "proceed to D1"
decision. Vocabulary content and this ADR are desk work that cannot affect F1; the schema and
services below are not built before D1, and nothing in this ADR alters the F1 calibration
protocol.

## Decision

1. **Canonical vocabulary is project-owned.** The project vocabulary is `fr-core`. External
   authorities (ScenTree, Michael Edwards, SFP, Cinquieme Sens) map onto `fr-core` through a
   crosswalk; none of them is adopted as the canonical vocabulary itself.
2. **Four-layer intake model**, so that no source is ever asked to answer in the project's own
   terms:
   - **Layer 1, raw declaration**: what a source said, stored as given. `declared_label`
     (new): `id`, `snapshot_id` XOR `observation_id` (exactly one), `label_kind`
     (`note | accord | family | descriptor`), `raw_text` (verbatim, never normalized),
     `position` (`top | heart | base | unspecified`), `source_order`, `created_at`. Fragella
     results are never a carrier here; ADR-012 keeps them in `fragella_lookups`. Fragella is
     read only for alias discovery when drafting `provider_term_mapping` rows; no fragrance
     profile is ever built from Fragella data.
   - **Layer 2, normalization**: raw text to canonical concept, via `provider_term_mapping`
     (ADR-004/ADR-013, generalized here per item 7 below).
   - **Layer 3, classification**: canonical concept to `fr-core`, via `vocabulary`,
     `vocabulary_term`, `vocabulary_display_node`, `assertion_source`, `term_assertion` (all
     new; see items 3 to 6).
   - **Layer 4, profile**: fragrance to family plus ranked descriptors, derived in feature
     space `fs-v2`, asserted via `term_assertion(fragrance_id)`.
3. **Faceted storage is the source of truth; a separate display tree is UI and teaching only.**
   `vocabulary` realizes ADR-010's `ClassificationSystem` (`code`, `version`, `owner`
   (`project | external`), `status` (`draft | published | retired`), `content_hash`, which
   excludes `status` so a draft and the same content later published, with no other change,
   hash identically). `vocabulary_term` carries `kind` (`family | descriptor`), a required text
   `definition`, and an informational, nullable `usual_family_hint` for descriptors.
   `vocabulary_display_node` (`vocabulary_id`, `parent_id`, `term_id` nullable for pure
   headings, `heading` text nullable, exactly one of `heading` or `term_id` set, `sort_order`)
   renders a tree for humans without constraining storage: a strict single tree cannot represent
   a material or note whose descriptors legitimately span more than one family. A vocabulary
   version cannot move to `published` unless every active term appears in the tree at least
   once, every node references terms of the same version, and the tree is acyclic with depth at
   most 4. An
   import-boundary test fails if any scoring, feature, or ML module imports the display tree.
4. **Rank semantics.** Rank 0 is the primary family; only `kind=family` terms may hold it.
   Ranks 1 to 5 are descriptors; only `kind=descriptor` terms may hold them. This is enforced in
   the service, backed by a cross-table check, and pinned by tests. Rank is ordinal olfactory
   prominence, not intensity; any numeric weighting is defined and versioned in `fs-v2`, never
   stored. Partial unique indexes, scoped to `status='approved'`, cover (subject, source,
   vocabulary, rank) and (subject, source, vocabulary, term). Every assertion pins one
   vocabulary version.
5. **Draft, approve, supersede lifecycle, with LLM drafting and product-owner approval.**
   `draft -> approved -> superseded` (a later approved set replaces the prior one) or
   `draft -> rejected`. Approved rows are immutable; revision writes a new set. Approval is per
   set (family plus its ordered descriptors together), not per row. `expert_baseline` rows are
   drafted by an LLM script over OpenRouter (ADR-003), sent only note names and the `fr-core`
   vocabulary, never evaluator data, and never fetching or passing ScenTree pages (automated
   fetching would be crawling); a human reviewer may consult ScenTree manually and record
   `consulted: <URL>` in `evidence_note`. `manufacturer` rows are drafted by mapping a house's
   `declared_label` rows to `fr-core` terms and start `draft`, approved for fidelity to the
   house's own words. `evaluator` rows are `approved` at capture, under a post-F1 calibration
   protocol version, and never counted as expert baseline. `crosswalk:<system>` rows are not
   stored while ScenTree remains reference-only.
6. **Spreadsheet round-trip is the review surface.** Export rows carry the assertion id, the
   subject id, and a fingerprint (a hash of the draft set at export). Editable columns: term,
   rank, and a per-set `decision` (`approve | reject | edit`). Import validates term codes
   against the pinned vocabulary version, family-only-at-rank-0, contiguous ranks from 1, no
   duplicate terms, and fingerprint match; each set applies atomically, a stale fingerprint
   refuses that set, and an already-applied set reports `already applied` (import is
   idempotent). Review files live in `tmp_cleanup/vocab-review/` (gitignored). The validator is
   a reusable module so a later house-intake instrument can reuse it.
7. **`assertion_source` carries license metadata, and the training filter walks the evidence
   chain.** `assertion_source` (`expert_baseline`, `evaluator`, `manufacturer`, and future
   `crosswalk:<system>`) carries `license_id`, `commercial_use` (bool), `training_allowed`
   (bool), `attribution_text`. Permission is resolved per assertion by walking its evidence
   chain: `manufacturer -> declared_label -> SourceSnapshot.permission_state`;
   `evaluator -> Observation -> TrainingEligibility` (exists); `expert_baseline`, project-owned,
   no upstream chain. The feature builder includes an assertion only if every link in its chain
   permits training; a commercial build additionally requires
   `assertion_source.commercial_use=true`. If ScenTree grants permission, `crosswalk:scentree`
   becomes one `assertion_source` row (`CC-BY-NC-4.0`, `commercial_use=false`), excluded from
   commercial builds by the same filter.
8. **Purge by source is an explicit, audited service operation, not a database cascade.**
   Foreign keys stay `RESTRICT`. Dry run by default, with per-layer counts; `--execute` plus a
   reason applies the purge; one transaction; idempotent (a second run deletes zero rows).
   First uses: Fragella subscription lapse, house permission withdrawal, ScenTree refusal or
   revocation.
9. **ScenTree stays reference-only pending written permission.** No ScenTree term, assignment,
   or narrative is stored before a written reply resolves the CC BY-NC 4.0 versus Legal-page
   conflict described in Context. A permission request will ask specifically whether the CC
   BY-NC 4.0 grant covers the family/descriptor list and per-ingredient classifications, whether
   storing targeted assignments for owned materials in a private database is permitted, whether
   ML training on them is permitted, and the terms for commercial use.
10. **`provider_term_mapping`'s target is generalized to `note_id` XOR `term_id`.** This lets
    the same table serve layer 2 normalization (mapping to a `Note`) and layer 3 classification
    aliasing (mapping to a `vocabulary_term`) without a second near-duplicate table.
11. **Sequencing.** Layer 1 (`declared_label` plus the ADR-012 `SourceSnapshot` amendment
    columns) rides milestone R8, already planned and pre-F1. Layers 2 through 4 are milestone
    D1, gated on F1's "proceed to D1" decision. Content work, drafting `fr-core` v0 terms and
    the display tree, may proceed now as a versioned project-owned file; schema and services
    are not built before D1.

### Alternatives considered

**Adopt ScenTree's 17 families and 92 descriptors as the project's canonical vocabulary.**
Rejected: its About page's CC BY-NC 4.0 claim and its Legal page's prohibition on reproduction
or adaptation without prior written authorization conflict, and neither page states which
elements each covers; adopting its content as canonical before that is resolved would store
exactly the material under a rights question. Its noncommercial-only claim, even if the
conflict resolved in the project's favor, would also foreclose any future commercial build.

**Adopt Cinquieme Sens as the primary vocabulary authority, per ADR-013's original framing.**
Rejected as canonical for now: ADR-013 named Cinquieme Sens the *candidate* primary source for
vocabulary meaning, gated behind reuse-rights review and outreach that has not yet cleared
(see the project's data-licensing outreach tracking). It remains a crosswalk target once
cleared, not the vocabulary itself, since the project needs a vocabulary it can draft, approve,
and revise on its own schedule independent of any external authority's response time.

**A strict single classification tree, no faceted storage.** Rejected: a material or note can
legitimately carry descriptors that belong to more than one family (a note can smell both
"woody" and "smoky" without one family owning both), and a strict tree forces a single parent,
losing that information. Faceted storage keeps the assertions as the source of truth; the tree
is rebuilt as a display and teaching aid on top of them.

**Per-subject assertion tables** (a separate table for note-level, fragrance-level, and
observation-level assertions). Rejected: each would need its own copy of the
draft/approve/supersede lifecycle, its own rank-semantics checks, and its own partial unique
indexes, tripling the surface area for what is otherwise identical logic. A single
`term_assertion` table with an XOR-constrained subject carrier keeps the lifecycle in one place.

**JSON profile columns directly on `Fragrance`.** Rejected: an opaque JSON blob is unqueryable
for the partial-unique-index and rank-semantics guarantees this ADR requires, and it collapses
layers 3 and 4 into the entity row, which violates ADR-006's rule that source evidence, aliases,
taxonomy mappings, and evaluator perception stay in separate layers.

## Consequences

### Positive

- Gives niche-house and evaluator vocabulary a real intake path without waiting on any external
  authority's rights clearance, and without forcing a house's own words into the project's
  taxonomy at the point of capture.
- Closes the ADR-010 `ClassificationSystem` and ADR-004 `provider_term_mapping` gaps with one
  coherent four-layer model instead of two separately-built, overlapping mechanisms.
- Keeps ScenTree's useful shape (one primary family, ranked descriptors) available for design
  purposes now, while keeping its content entirely out of storage until permission is resolved.
- The evidence-chain training filter and per-source purge give the project a concrete answer to
  "can this be trained on" and "can this be removed" per source, rather than a blanket policy.

### Trade-offs

- Two new tables (`declared_label`, `provider_term_mapping`) plus five more, the layer-3 set
  (`vocabulary`, `vocabulary_term`, `vocabulary_display_node`, `assertion_source`,
  `term_assertion`), seven in total, is a larger schema surface than a single classification
  table would have been; the alternatives above were rejected because each is worse on some
  other axis, not because this one is free.
- Nothing in layers 2 through 4 is usable until D1, which itself does not start before F1
  reaches its "proceed to D1" decision; the practical benefit of this ADR is deferred by that
  same gate.
- The spreadsheet round-trip review adds a manual step (export, edit, import) to every
  vocabulary change; a web review UI is explicitly out of scope for this ADR, so that manual
  step is the interim cost of shipping the service layer first.

## Validation

- Layer 1: a `declared_label` insert fails with both or neither carrier populated; `raw_text`
  round-trips exactly for representative inputs (for example `vanille`, `Acqua di Giò`).
- Layer 2 (D1 required fixtures): `oak moss`/`oakmoss` and `vanille`/`vanilla` resolve only via
  approved mappings; an ambiguous label such as `amber` stays unresolved until reviewed; unknown
  terms queue for review; mapped duplicates dedupe within a fragrance for statistics while every
  source label survives unchanged.
- Layer 3: family-only-at-rank-0 is enforced; both partial unique indexes hold; supersede
  preserves the prior set rather than deleting it; vocabulary version pinning holds across a
  publish; the display-tree import-boundary test fails on any scoring/feature/ML import.
- Import: a stale fingerprint is refused; an unknown term code, a rank gap, or a duplicate term
  each fails that set only; a mixed file applies its valid sets and reports the rest; re-import
  of an already-applied file is a no-op.
- Permissions: the training filter drops `retain_for_qc_only` and any evidence chain with an
  ineligible observation; the commercial filter drops any `assertion_source.commercial_use=false`
  row; no fragrance profile is ever built from Fragella data.
- Purge: a dry run's counts equal the row counts an `--execute` run actually deletes; a second
  `--execute` run against the same source deletes zero rows.
- Before any ScenTree term, assignment, or narrative is stored, a written reply resolving the
  CC BY-NC 4.0 versus Legal-page conflict should exist in the same place ADR-006 already
  requires reuse-rights review to be recorded.

## Related

- [ADR-003](adr-003-llm-integration.md): OpenRouter LLM integration this ADR's expert-baseline
  drafting step uses
- [ADR-004](adr-004-recommendation-algorithm.md): `provider_term_mapping`, whose target this ADR
  generalizes to `note_id` XOR `term_id`
- [ADR-006](adr-006-version-identity-and-source-provenance.md): the separate-layers rule and
  reuse-rights review this ADR's four-layer model and ScenTree posture both satisfy
- [ADR-010](adr-010-preference-learning-and-scenario-data-model.md): `ClassificationSystem`,
  realized here as `vocabulary`
- [ADR-012](adr-012-data-source-compliance-and-manufacturer-provenance.md): `SourceSnapshot`
  and `permission_state`, the layer-1 evidence chain a `manufacturer` assertion walks
- [ADR-013](adr-013-external-ontology-and-standards-crosswalk.md): Cinquieme Sens's crosswalk
  role, amended by this ADR from candidate primary vocabulary authority to crosswalk target
- [ADR-016](adr-016-per-dimension-preference-capture.md): precedent for renumbering around the
  ADR-014 collision this record's Numbering note describes
- `docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md`: the approved design this
  ADR records
