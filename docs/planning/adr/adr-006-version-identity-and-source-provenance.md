# ADR-006: Version Identity, Source Provenance, and Vocabulary

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

Names alone do not identify fragrance versions. Concentrations, release versions, and flankers
can differ materially. Source datasets also disagree on notes and taxonomies, contain aliases,
and may have incomplete or restricted provenance.

Controlled assignments and prospective model inputs must remain reproducible even after a source
changes.

## Decision

`Fragrance` remains the canonical version entity through D5. Brand, exact display name,
concentration, and version key distinguish versions. Unknown concentration remains unknown.
Identity fields become immutable after assignment to a controlled program.

Source evidence is append-only and records source identifier, URL/revision, retrieval time,
content hash, parsed payload, verification state, and applicable license or permission evidence.
A refresh adds evidence without rewriting observations or assigned identity.

Raw source labels, normalized aliases, taxonomy mappings, evaluator perceptions, and model
interpretations are separate layers. Alias and taxonomy mappings are versioned. Mapping may
deduplicate equivalent labels for a declared computation but never deletes the raw labels.

No external code or corpus is imported until its intended use and reuse rights are documented.

## Consequences

- Same-name concentrations coexist.
- Historical records imported with defaulted concentrations are not retroactively certified.
- Statistical artifacts can be regenerated from pinned inputs.
- Mapping changes require an explicit version and reprocessing/backfill plan.
- Multiple source taxonomies may coexist rather than being forced into one global family.

## Validation

- Tests cover concentration variants, unknown concentration, alias collisions, ambiguous terms,
  duplicate mapped notes, source refresh, and immutable assigned identity.
- D1 produces a rights record and snapshot hash for each adopted asset.
- Backfills support dry-run counts, collision review, idempotency, and recovery.

## Related

- [ADR-002](adr-002-data-source-strategy.md)
- [ADR-005](adr-005-controlled-calibration.md)
- [Scent Chords Analysis](../../research/scent-chords-analysis.md)
