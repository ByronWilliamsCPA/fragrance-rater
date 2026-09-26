# ADR-013: External Ontology and Standards Crosswalk

> **Status**: Accepted; amends ADR-004, ADR-010; amended by ADR-017 (2026-09-24)
>
> **Date**: 2026-09-15

## 2026-09-24 amendment (pointer to ADR-017)

ADR-017 makes the project's olfactory vocabulary project-owned (`fr-core`) rather than
externally authored. Decision item 1 above named Cinquieme Sens the candidate primary source
for core vocabulary meaning; that role moves to crosswalk target only. Cinquieme Sens's
outreach and reuse-rights review (Decision item 1, Follow-up) are unchanged and still gate any
ingestion; only its intended role changes, from "defines what our concepts mean" to "one more
external system mapped onto vocabulary the project already owns and can draft, approve, and
revise on its own schedule." Decision item 7's `provider_term_mapping` generalization is
further extended by ADR-017 item 10, target generalized to `note_id` XOR `term_id`. See
ADR-017 for the full model.

## Context

### Where this came from

A parallel research thread (a separate session, not this repository's own planning history) assembled a broader authority stack for grounding this project's fragrance vocabulary, rather than treating any single external API's field names as the project's ontology. It grouped ten-plus external sources into two roles: ontology/methodology authorities (Cinquieme Sens, Michael Edwards, IFRA, SSP, ASTM E18, IAO, EPC, ISIPCA, Grasse-area training, Osmotheque, Nez) and operational application-data sources (Fragella, Wikidata). The product owner explicitly flagged this material as not authoritative on its own, and separately flagged that the current schema still reflects an outdated, Parfumo-centric acquisition model. This ADR is the reconciliation: what of that research is genuinely new work for this project, what already has a planned home here, and what has no verifiable trace here at all.

### What this project already has for exactly this problem

ADR-006 already establishes the policy this crosswalk needs: source evidence, aliases, taxonomy mappings, and evaluator perception are four separate layers that must never be collapsed into each other, and it explicitly rejects forcing every source into one global family taxonomy. ADR-010 (partially implemented) already proposes, but has not built, `ClassificationSystem`/`FragranceClassification`, a versioned, pluggable multi-taxonomy model whose own stated purpose is letting `primary_family`/`subfamily` become one materialized system's values "rather than the only possible taxonomy." ADR-004's 2026-09-15 amendment already proposes, but has not built, `provider_term_mapping`, a table mapping this project's internal note/accord concepts to a single external provider's canonical vocabulary, so far scoped only to Fragella.

None of the three new entities the parallel research proposed, `OntologyTerm`, `OntologyMapping`, `FeatureSet`, exist anywhere in this repository's code or docs, confirmed by a full-repo search. Two of them substantially overlap machinery already planned here.

### What is genuinely new

Cinquieme Sens and IFRA have zero mentions anywhere in this repository prior to this ADR. Naming their intended roles is new scope, not a gap-fill of existing plans. Michael Edwards Wheel is already implemented, but exactly as this project's own gap analysis already flagged it: hardcoded, unversioned strings directly on `Fragrance.primary_family`/`Fragrance.subfamily`, not yet one row in a pluggable system. Wikidata and Fragella are unchanged; ADR-002, ADR-004, and ADR-012 already govern their roles as operational data sources, not vocabulary authorities, and nothing here revisits that.

### The unverified item

The parallel research also described "35 diagnostic dimensions" (short codes such as CIT, FRU, AQU, GRE) as this project's existing experimental feature set, to be generalized into a versioned `FeatureSet`. A full-repo search, code and documentation, found no trace of these codes, this dimension count, or a `FeatureSet` concept anywhere. This appears to originate from a document outside this repository (`fragrance_diagnostic_report.md`, referenced but not present here). This ADR does not design around unverified content; see Decision item 4.

## Decision

**We will assign each external authority a specific, bounded role against machinery this project already has or has already planned, rather than adopting a new three-table ontology model, and we will leave the unverified diagnostic-dimension material out of scope until it can be located and confirmed.**

1. **Cinquieme Sens** is the candidate primary source for core olfactory vocabulary, the meaning of this project's own family, facet, accord, material, and descriptor concepts. No content is imported, reproduced, or stored under this role until it clears ADR-006's reuse-rights review; this ADR authorizes the role, not ingestion.
2. **Michael Edwards Wheel** becomes the first concrete row in ADR-010's `ClassificationSystem`/`FragranceClassification` once that model is built, migrating `Fragrance.primary_family`/`subfamily`'s current hardcoded strings into a versioned system entry instead of a bespoke crosswalk table. This directly closes the gap this project's own data-model gap analysis already flagged.
3. **IFRA** is a reference vocabulary for raw-material and ingredient terminology, used as a mapping target for the `Note` model's alias and taxonomy layer (ADR-006's D1 milestone), attribution required, not copied wholesale. Also gated behind reuse-rights review before any term is stored.
4. **SSP's 9-point hedonic scale and ASTM E18** are methodology authorities for the evaluation protocol (the `Evaluation`/`Observation` models), not vocabulary sources. They stay outside the ontology-mapping mechanism entirely, so "how much a wearer liked it" never gets confused with "what an authority says it smells like," the same separation ADR-007 already enforces between affinity score and confidence, and ADR-011 enforces between worn-by evidence and direct evidence.
5. **IAO, EPC, ISIPCA, Grasse-area training, Osmotheque, and Nez** are educational, reference, and validation sources only. No schema implication. Out of scope for this ADR's data model; may inform future UI help content or terminology validation, not stored data.
6. **Fragella and Wikidata** are unchanged. They remain operational data sources under ADR-002, ADR-004, and ADR-012, not ontology authorities; neither is asked to define what this project's own concepts mean.
7. **The concept-level crosswalk mechanism is ADR-004's `provider_term_mapping`, generalized rather than duplicated.** Its existing shape (`provider`, `entity_type`, `internal_concept_id`, `provider_canonical_name`, `provider_occurrence`, `provider_description`, `source_value_hash`, `verified_at`) already fits a Cinquieme Sens or IFRA row as well as a Fragella row; `provider` and `entity_type` already disambiguate multiple authorities describing the same internal concept, and `source_value_hash` (ADR-004) plays the same drift-detection role for a Cinquieme Sens or IFRA term as it does for Fragella: it lets a re-verification pass notice the authority redefined a term since `verified_at`. No new mapping table is created for this purpose.
8. **The "35 diagnostic dimensions" / `FeatureSet` material is explicitly out of scope for this ADR.** It is not designed around, scaffolded, or given a placeholder table, because there is nothing in this repository to verify it against. If it is later confirmed as real prior work, it should populate ADR-010's already-deferred `FeatureDefinition`/`FeatureValue` pair, which is the correct existing shape for named, versioned sensory facts, rather than a new bespoke entity. See Follow-up.

### Alternatives considered

**Adopt `OntologyTerm`, `OntologyMapping`, and `FeatureSet` as proposed, verbatim.** Rejected: `OntologyMapping` duplicates ADR-010's already-planned `ClassificationSystem` for whole-fragrance classification and ADR-004's already-planned `provider_term_mapping` for concept-level crosswalk. Building both the new tables and the already-planned ones would leave three to five overlapping "map X to Y" tables with no clear ownership boundary between them.

**Document the research as prose only, no schema decision.** Rejected: the concrete, already-flagged gap (Michael Edwards Wheel hardcoded and unversioned) needs a real landing spot, and leaving Cinquieme Sens and IFRA's roles undocumented risks a future session re-researching or duplicating this same work.

**Adopt the diagnostic-dimension `FeatureSet` now, in a modified, generic form (no hardcoded codes).** Considered, since the product owner asked this be weighed explicitly. Rejected for this ADR: there is no verified content to scaffold against, and an empty generic table with no confirmed consumer violates the same principle ADR-010 already applies to its own deferred items, "until the milestone or concrete consumer that needs each one actually exists." Revisit once the source material is located and its actual shape is known; guessing at column definitions now risks building the wrong shape twice.

## Consequences

### Positive

- Closes the gap-analysis-flagged "Michael Edwards Wheel is a single, unversioned, hardcoded taxonomy" issue using machinery this project already committed to building (ADR-010), instead of new machinery.
- Gives Cinquieme Sens and IFRA documented, bounded roles instead of leaving them as loose research notes disconnected from the codebase and at risk of being re-derived differently by a future session.
- Avoids a third and fourth near-duplicate mapping table by generalizing `provider_term_mapping` instead of building `OntologyMapping` alongside it.
- Keeps evaluation methodology (SSP, ASTM E18) cleanly separated from vocabulary and taxonomy, preserving the same "do not blend evidence types" discipline already established for score semantics (ADR-007) and worn-by evidence (ADR-011).

### Trade-offs

- Cinquieme Sens and IFRA content is still gated behind ADR-006's reuse-rights review before any of it is actually usable; this ADR authorizes the role, not the data, so no immediate vocabulary improvement follows from it alone.
- Generalizing `provider_term_mapping` to multi-provider is a scope change to something ADR-004 already proposed but has not built; the cost is low since no code exists yet, but it is a cross-ADR dependency worth tracking.
- The diagnostic-dimension question stays genuinely open. If that material turns out to be real, sourced, and urgent, this ADR's deferral will look like under-scoping in hindsight; that risk is accepted deliberately given there is nothing in this repository to verify it against today.

### Follow-up (implementation, not part of this decision)

- Locate and verify `fragrance_diagnostic_report.md` and `Fragrance_Rater_Concept.docx` (or their current equivalents) before any diagnostic-dimension or `FeatureSet` schema work begins.
- Build ADR-010's `ClassificationSystem`/`FragranceClassification`, with Michael Edwards Wheel as its first migrated system.
- Generalize ADR-004's `provider_term_mapping` to accept `provider` values beyond `fragella` (for example `cinquieme_sens`, `ifra`) once those sources clear reuse-rights review.
- Run ADR-006's reuse-rights review specifically for Cinquieme Sens and IFRA; neither has been reviewed, mirroring the process ADR-002 already used for Fragrantica and Parfumo.

## Validation

- Before any Cinquieme Sens or IFRA term appears in `Fragrance`-facing data, its specific reuse-rights review should exist in the same place ADR-006 already requires for every other source.
- A future repo-wide search for the diagnostic-dimension codes or `FeatureSet` finding real, sourced content should trigger revisiting this ADR's deferral explicitly, not a silent schema addition elsewhere.
- Michael Edwards Wheel should trace to a `ClassificationSystem` row, not a hardcoded string, before this project admits participants beyond the current household, consistent with ADR-012's own participant-scaling gate.

## Related

- [ADR-004](adr-004-recommendation-algorithm.md): `provider_term_mapping`, generalized here from Fragella-only to multi-provider
- [ADR-006](adr-006-version-identity-and-source-provenance.md): source provenance, alias, and taxonomy layering this ADR relies on; governs reuse-rights review for every new source named here
- [ADR-010](adr-010-preference-learning-and-scenario-data-model.md): `ClassificationSystem`/`FragranceClassification` and `FeatureDefinition`/`FeatureValue`, both used as landing spots here instead of new entities
- [ADR-012](adr-012-data-source-compliance-and-manufacturer-provenance.md): Wikidata and Fragella source-tier classification, unchanged by this ADR
- [ADR-017](adr-017-project-owned-faceted-olfactory-vocabulary.md): amends this ADR's Decision
  item 1, Cinquieme Sens moves from candidate primary vocabulary authority to crosswalk target
- `docs/planning/evidence/data-model-gap-analysis.md`: source of the "Michael Edwards Wheel is hardcoded and unversioned" finding this ADR addresses
