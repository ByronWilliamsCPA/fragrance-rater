---
title: "Baseline V3.1 Catalog Coverage Test"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Measure documented catalog readiness for the 33 fragrances in the initial blind-evaluation baseline without treating restricted reference material as reusable catalog data."
tags:
  - planning
  - calibration
  - evidence
---

**Checked:** 2026-09-21. **Denominator:** the 33 unique baseline fragrances, #01–#33, in the [authoritative V3.1 inventory](baseline-v3.1-universal-and-holdout.md). The six hidden repeats add presentations, not catalog entries. The ten validation holdouts are outside this first coverage test.

This is a **documented-evidence audit**, not a live count of any deployed database or a claim that the missing information does not exist. The repository contains an empty `data/calibration/baseline-manifest.template.json`, and the [P1.1 gate](../gates/p1.md#p11-evidence-2026-09-12) records no catalog-resolved or physically confirmed entries. Inventory arrival and brand replies may have changed since those records were written; neither is evidenced in this repository as of this check.

| Coverage measure | Documented count | Interpretation |
| :--- | ---: | :--- |
| Named, concentration-specified design identities | 33/33 | Product-owner baseline specification; sufficient to define the test set, not sufficient to load a verified catalog version. |
| Project-owned diagnostic role labels | 33/33 | Useful study-design labels, but not a complete perfume catalog or independent confirmation of notes and accords; keep them from blind evaluators. |
| Historical third-party identity references | 33/33 | Each has a Parfumo URL in the [source-resolution record](baseline-v3.1-parfumo-source-resolution.md). These are research leads, not an approved ingestion or reuse path under [ADR-012](../adr/adr-012-data-source-compliance-and-manufacturer-provenance.md). |
| Canonical `FragranceVersion` IDs with verification evidence in a P1.1 manifest | 0/33 | The committed manifest template has no entries; the P1.1 evidence explicitly records this gap. This does not prove an external deployment has no records. |
| Independently sourced notes/accords with documented rights for retention and intended ML use | 0/33 | No per-fragrance manufacturer permission, approved open-data provenance, or data license is recorded for those fields in the repository. The project-owned diagnostic roles are counted separately; the earlier web-search research does not establish reuse rights. |
| Physical samples marked confirmed in a P1.1 manifest | 0/33 | P1.1 records two already-owned products (#16 and #33), but neither has a completed physical-sample confirmation in a manifest. Ownership and confirmation are separate measures. |
| Baseline entries ready for the full P1.1 assignment gate | 0/33 | Every entry still needs the required catalog ID, verification evidence, source reference, and physical confirmation. |

**Result:** The initial 33 solve the *selection* problem: the project knows which perfumes it wants users to evaluate. They do not yet solve the *reusable catalog* problem. The current documented coverage for **independently sourced, rights-cleared notes and accords is 0/33**, meaning **no qualifying evidence is recorded**, not that all 33 are impossible to source. The project-owned diagnostic roles are a separate, narrower asset. Parfumo's historical 33/33 reference coverage must not be reported as licensed catalog coverage. Fragella lookups likewise cannot be counted as retained catalog data under [ADR-002](../adr/adr-002-data-source-strategy.md#2026-09-12-amendment-fragella-as-a-capped-reference-lookup-not-a-source).

## Next measurement pass

Track each of the 33 baseline numbers through a private, access-controlled evidence ledger. For each exact product and concentration, record:

1. Manufacturer confirmation of identity and version, with a named contact or document.
2. Separate permission for retention, display, intended ML use, and export of each supplied field or image. A public product page alone does not document these rights.
3. Reviewed open-source matches, with the source item ID, field-level provenance, license version, and any attribution or share-alike obligations. Test Wikidata for identity facts and Open Beauty Facts for barcode/product facts; do not assume either covers perfume notes or accords.
4. Physical sample status, label/packaging match, and the completed P1.1 manifest reference.

**Implementation gate:** `scripts/validate_calibration_manifest.py` currently requires an absolute HTTPS `source_url` for every entry. A manufacturer confirmation received only by email or phone cannot satisfy that field as written, although ADR-012 explicitly allows a non-URL `source_reference` in `SourceSnapshot`. Reconcile the manifest contract with the accepted provenance model before using direct replies as P1.1 evidence; do not invent a public URL for a private reply.

Publish only aggregate counts while the blind evaluation is active. Keep note pyramids, accord labels, and per-product diagnostic descriptions out of evaluator-accessible material. Recompute three separate coverage rates after the ledger is populated: exact-version identity, rights-cleared descriptive features, and physically confirmed baseline samples. An entry qualifies for the second rate only for fields whose rights cover the intended retention and ML use.
