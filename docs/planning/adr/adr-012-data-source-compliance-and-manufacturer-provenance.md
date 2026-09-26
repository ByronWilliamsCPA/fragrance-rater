# ADR-012: Data Source Compliance - Parfumo Deprecation and Manufacturer Provenance

> **Status**: Accepted; amends ADR-002; SourceSnapshot provenance specified by the 2026-09-15
> amendment is partially implemented: the schema columns have landed and the Parfumo write path
> now fails closed, but the amendment's listed follow-ups remain open; vendor-licensed data added
> as a source tier by the 2026-09-21 amendment below
>
> **Date**: 2026-09-15

## 2026-09-15 amendment: SourceSnapshot per-field provenance

Decision item 4 above says source evidence must record enough to answer what may be done
with a fact, not just where it came from, and names `SourceSnapshot` as the mechanism to
extend. This amendment specifies that extension, closing the gap a direct read of the
current schema surfaced: `Fragrance.data_source` (`models/fragrance.py`) is a bare
`String(20)` with exactly three values used anywhere in the codebase today, `manual`,
`kaggle`, `parfumo`, none of which can represent this ADR's own new source tiers
(manufacturer-provided, open-licensed, bounded lookup). It is also one column per
fragrance row, not per fact, so there is no way to say concentration and release year are
manufacturer-confirmed while brand attribution still traces to Wikidata for the same row.
Separately, `Fragrance.parfumo_url` is a Parfumo-named column living directly on the core
entity even though the generic `SourceSnapshot` table already exists for this purpose;
`recommendation_measurement_service.py` already reads it into a key it calls `source_url`,
treating it as generic in practice while the column name has not caught up.

**`SourceSnapshot` (`models/calibration.py`) gains three fields and one relaxed
constraint:**

- `source_type: Mapped[str]`, CHECK-constrained (matching the existing
  `PilotOperationalEvent.event_type` and `FragellaLookup.status` precedent for
  enum-shaped string columns) to this ADR's own source hierarchy: `project_owned`,
  `manufacturer_provided`, `open_licensed`, `bounded_lookup`, `excluded_legacy`. The last
  value is for historical Parfumo-sourced snapshots being re-verified per Decision item 5;
  no new snapshot may be written with it.
- `permission_state: Mapped[str]`, CHECK-constrained, answering what may be done with the
  fact rather than just where it came from: `retain_and_train` (project-owned,
  manufacturer-provided, and open-licensed/CC0 facts, all supplied voluntarily or owned
  outright), `retain_for_qc_only` (Fragella's bounded-lookup terms, mirroring the existing
  rule from ADR-002's 2026-09-12 amendment that retained Fragella payloads are for quality
  control, never a substitute for re-querying), `excluded_no_new_writes` (legacy Parfumo
  rows). This three-way split answers retention/reuse-class at the coarseness Decision item
  4 needs for this amendment: whether a fact may be trained on, must stay QC-only, or is
  excluded outright. It does not encode export terms, attribution or share-alike
  obligations, or the underlying license evidence for a given fact; that finer-grained
  tracking is deferred to D1's provenance work per ADR-006, not solved by this column alone.
  The "never a substitute for re-querying" rule governs per-fragrance QC lookups only: a
  retained `/match` or `/similar` response for a specific fragrance must never stand in for
  asking Fragella again about that fragrance. It does not extend to ADR-004's
  `provider_term_mapping` (generalized by ADR-013 to other vocabulary authorities): a
  `provider_canonical_name` row there is a stable translation between this project's own
  internal concept and a provider's vocabulary for that concept, not a fact about any
  specific fragrance, and Cinquieme Sens/IFRA rows in the identical table shape carry no
  re-querying restriction at all. Resolving a concept once and reusing that mapping
  indefinitely permanently caches a crosswalk entry; it does not retain a fragrance-level
  lookup in place of a current one.
- `fields: Mapped[list[str]]` (JSON), required, no default. Names which `Fragrance`
  column(s) this specific snapshot evidences, for example `["concentration",
  "launch_year"]`. This is the mechanism that makes per-fact, rather than per-fragrance,
  provenance possible: two `SourceSnapshot` rows for the same fragrance can now disagree
  on which source is authoritative for which field, and both stay true at once.
- `source_url: Mapped[str | None]`, relaxed from its current non-nullable `String(1000)`.
  A manufacturer confirmation arriving as a letter reply, an email, or a phone call has no
  URL to cite, and the column's current NOT NULL constraint cannot represent that.
- New `source_reference: Mapped[str | None]` (`String(500)`), for exactly that case, for
  example `"Email reply from Brand X contact, 2026-09-20"`. A CHECK constraint requires at
  least one of `source_url` or `source_reference` to be non-null; a snapshot with neither
  is not evidence of anything.

**`Fragrance.data_source`'s value space widens** to add `manufacturer`, `wikidata`, and
`fragella` alongside the existing `manual`, `kaggle`, and `parfumo` (the last retained only
on historical rows; `ParfumoScraper`'s retirement per Decision item 1 means no new writes
use it). Its role changes from sole provenance record to a lightweight display/summary
label; the authoritative per-field record lives in `SourceSnapshot.fields` going forward.

**`Fragrance.parfumo_url` is deprecated**, no new writes once `ParfumoScraper` is retired.
New source URLs and references adopted as fact evidence, manufacturer confirmations and
Wikidata entity links, go into `SourceSnapshot.source_url` / `source_reference` instead of
a source-specific column on the core entity. Fragella lookup citations stay where they
already are, the existing `fragella_lookups` QC log from ADR-002's 2026-09-12 amendment,
never `SourceSnapshot`: a bounded lookup is retained for quality control, not adopted as
source evidence for a fact, which is exactly the distinction `retain_for_qc_only` versus
`retain_and_train` draws above. Dropping the `parfumo_url` column itself is a migration,
tracked as follow-up alongside `ParfumoScraper`'s removal, not part of this decision.

**Alternatives considered for this amendment.** Adding the new source tiers as more
`data_source` string values and stopping there, no `SourceSnapshot` changes: rejected,
does not solve the actual problem, a single column per fragrance still cannot express
partial confirmation (concentration confirmed, attribution not), which is the normal case
once manufacturer replies start arriving piecemeal. Giving `Fragrance` one column per
confirmable fact (`concentration_source`, `launch_year_source`, and so on) instead of a
`fields` array on `SourceSnapshot`: rejected, duplicates the append-only evidence ledger
ADR-006 already established, and would need a new column every time a new confirmable
fact is added; `SourceSnapshot.fields` keeps the ledger single and extensible.

**Consequences of this amendment.** Positive: closes the Decision item 4 gap with
concrete, implementable column definitions
instead of leaving it as unspecified policy; the outreach letters' manufacturer replies
now have a real landing spot that can express partial confirmation; `parfumo_url`'s
Parfumo-specific naming stops leaking into the core entity.

Trade-offs: existing `SourceSnapshot` rows (written only by `parfumo_scraper.py` today)
need a backfill migration assigning `source_type="excluded_legacy"`,
`permission_state="excluded_no_new_writes"`, and `fields=["concentration", "launch_year",
"brand"]` (or a narrower list, whatever each row actually evidences) before the new NOT
NULL `fields` column can be added without breaking existing rows.

Follow-up (implementation, not part of this decision):

- Write the Alembic migration: add `source_type`, `permission_state`, `fields`,
  `source_reference` to `calibration_source_snapshots`; relax `source_url` to nullable;
  backfill existing rows per the trade-off above; add the CHECK constraints.
- Update `recommendation_measurement_service.py`'s read of `Fragrance.parfumo_url` (line
  ~109) to read the newest relevant `SourceSnapshot` instead, once the column is dropped.
- Widen `Fragrance.data_source`'s CHECK constraint (if any exists at the DB level; today
  it is unconstrained at the column level) to the new value set.

## 2026-09-21 amendment: vendor-licensed data as a source tier

Decision item 3's source hierarchy names manufacturer-provided confirmation and open-licensed
data (Wikidata) but has no tier for a fragrance-database vendor's structured field data acquired
under a direct license. Research into candidate vendors (Fragrances of the World, WikiParfum,
Fragrantica and Parfumo under a direct commercial agreement distinct from the scraping this ADR
already excludes, PERFUMIST, and several conditional aggregators still pending upstream-provenance
diligence) surfaced a real path to closing the 0/33 gap `baseline-v3.1-catalog-coverage.md`
documents for the 33-fragrance baseline (the 43-fragrance vendor-request figure below adds the 10
validation holdouts), but one the existing hierarchy has no place for. This amendment adds that
tier and records the request-shape decision that governs how it is pursued, without yet
implementing it:
no vendor has agreed to a license as of this writing, so there is nothing to backfill and no
justification for a schema change today, the same spec-now-implement-later pattern the
2026-09-15 amendment above used for `SourceSnapshot` itself.

**Record scope and rights scope are requested separately, and at different breadths.** The
concrete, near-term ask made of any vendor is a named list of the 43 baseline and holdout
fragrances, not the vendor's full catalog: a vendor is far more likely to agree to license 43
named products than to become a production data dependency for an entire recommendation
platform. The rights requested for that narrow list are not narrowed to match, however: every
outreach asks for the full breadth this project will eventually need (local storage, ML
training, embeddings, recommendation-model use, and a defined path from personal/research use to
commercial use), and separately asks whether the arrangement can later be amended or extended in
scope rather than renegotiated from nothing. The reason to keep these two axes separate: closing
today's gate with rights narrower than the project will eventually need would just relocate the
renegotiation to later, with a vendor who has already seen the project ask for less.

**Upstream provenance diligence applies to a vendor license exactly as it applied to Parfumo.**
A downstream license cannot create upstream rights the vendor never possessed; the governing
question for any candidate is not whether it advertises commercial use, but whether it can
demonstrate it had the rights to acquire the underlying data before it can grant this project the
rights above. This is the same diligence standard Decision item 3's excluded-sources list already
applies to FragDB (whose own documentation names Fragrantica as an upstream source) and to
unverified Kaggle/GitHub/Hugging Face datasets; a vendor's own license terms, read alone, are not
sufficient clearance.

**Where this tier sits in the hierarchy is fact-dependent, not a single fixed rank.** For
identity facts a brand can and does confirm directly (concentration, release year, brand/line
attribution), manufacturer-provided confirmation remains preferred; a vendor's third-party
characterization of another company's product is not stronger evidence than the product owner's
own statement. For olfactory and sensory fields (notes, accords, fragrance family) that
manufacturer outreach less reliably supplies, a cleared vendor database is the preferred source,
ranking above open-licensed Wikidata for those fields specifically, since Wikidata's fragrance
coverage is identity-oriented and does not generally carry olfactory detail.

**A cleared vendor license maps to `retain_and_train`.** The rights language above (local
storage, ML training, embeddings, recommendation use, no resale or redistribution of the
underlying dataset) matches the `retain_and_train` permission state already defined for
project-owned, manufacturer-provided, and open-licensed facts: no resale or redistribution right
is needed for that state, since it governs retention and internal use, not third-party
redistribution.

**Alternatives considered.** Negotiating full-catalog rights from the first conversation with
each vendor: rejected for the near-term objective, more likely to stall a vendor relationship
that a narrower, answerable request would not, and unnecessary since the immediate need is 43
named fragrances, not catalog-wide coverage. Treating a vendor's "commercial use permitted"
marketing language as sufficient clearance on its own: rejected, for the same reason Parfumo was
excluded and FragDB was left conditional, downstream license terms do not establish upstream
rights.

**Consequences.** Positive: gives the outreach effort already underway (the owner's private
outreach records, not committed to this repository, covering Tier 1 and Tier 2 vendor letters) a
named source tier and permission state to land evidence in once a vendor responds, instead of
forcing a licensed vendor fact into `manufacturer_provided` or `open_licensed` where it does not
belong. Trade-offs: adds a source tier with no data behind it yet; if no vendor responds, this
amendment records a decision with no immediate effect on coverage, and the project falls back to
the manufacturer-outreach and Wikidata paths the 2026-09-15 amendment already established.

Follow-up (implementation, not part of this decision):

- Add `vendor_licensed` to `SourceSnapshot.source_type`'s CHECK constraint and to Decision item
  3's source hierarchy text once, and only once, all three of the following hold: a signed
  agreement, completed upstream-provenance diligence per the standard above, and an explicit
  grant covering the rights this amendment lists (local storage, ML training, embeddings,
  recommendation-model use, and commercial use where applicable). Only a grant that covers
  training rights maps to `retain_and_train`; a narrower grant maps to a narrower
  `permission_state`.
- Record per-vendor diligence findings, license terms, and correspondence in the local outreach
  packet, not in this ADR; this ADR records the durable request-shape and hierarchy decision
  only.

## Context

### The gap

ADR-002's 2026 amendment named Parfumo as "the implemented integration" for fragrance metadata
(notes, accords, concentration, release year, brand attribution). That amendment gave Fragrantica
an explicit ToS review and rejected it on that basis (Option 3 in ADR-002: "ToS violation risk").
Parfumo received no equivalent review before becoming the implemented source. That asymmetry is a
governance gap, not a considered decision: nothing in this project's planning history establishes
that Parfumo's terms permit the scraping `ParfumoScraper` performs.

This gap was tolerable at four evaluators drawing on a single 43-fragrance baseline. It stops being
tolerable once the project scales to additional participants, since usage volume and durability of
the underlying data are exactly what turn an unreviewed source into a real compliance liability
rather than a theoretical one.

### What is actually at risk

An inventory of every Parfumo-derived reference in this repository (2026-09-15) found no populated
database. No `.db`/`.sqlite` file exists anywhere in the working tree, tracked or untracked. What
exists is:

- The scraper pipeline itself: `ParfumoScraper` (`src/fragrance_rater/services/parfumo_scraper.py`)
  and the `import-data parfumo-url` / `import-data parfumo-search` CLI commands that invoke it.
- Schema shaped to hold its output: `Fragrance.parfumo_url`, `Fragrance.data_source`, and
  `SourceSnapshot.payload`, none of which are Parfumo-specific in structure, only in current use.
- Concrete captured facts, but only in planning documentation, not application data:
  `docs/planning/evidence/baseline-v3.1-parfumo-source-resolution.md` resolves all 43 baseline and
  holdout fragrances against specific Parfumo source URLs with brand, concentration, and release
  year confirmed against the live pages.
- One real scraped fact echoed into test fixtures: Chanel N5 Parfum's GTIN barcode, reused across
  five test files as example data, not as a stored application record.

This materially narrows the remediation problem: there is no production corpus to purge, only a
pipeline to stop using and a documentation trail to re-verify against compliant sources as
replacements become available.

### What compliant alternatives look like

Two independent research passes this session, this project's own source research and a parallel
review the product owner supplied, converged on the same classification for every source this
project has touched or considered:

| Source | Classification | Basis |
| --- | --- | --- |
| Wikidata | Open, CC0 | Suitable for factual enrichment (brand identity, release dates, perfumer identity) with per-record verification; not a sensory-data source |
| Fragella | Bounded lookup only | Terms permit application-time lookups, not caching or a locally replicated catalog; already governed correctly by ADR-002's 2026-09-12 amendment |
| Manufacturer-provided (direct correspondence) | Permissioned, strongest attribution | The brand's own statement about its own product; no scraping or third-party characterization involved |
| Parfumo | Excluded | No documented license for automated extraction; the gap this ADR closes |
| Fragrantica | Excluded | Terms explicitly prohibit scraping, crawling, and commercial/ML use without a written license (already reflected in ADR-002 Option 3) |
| Basenotes | Excluded | Terms characterize content as personal/non-commercial and prohibit extraction tools without written consent |
| FragDB | Not approved | Its own documentation identifies Fragrantica as the source of major portions of its dataset; a permissive customer license cannot cure an unresolved upstream rights problem |
| Kaggle / GitHub / Hugging Face datasets | Case by case | A dataset's own license (MIT, CC BY, etc.) covers the uploader's contribution, not necessarily data the uploader lacked rights to sublicense; each dataset needs its own provenance check before use. This project's `kaggle_importer.py` is a generic CSV importer with no dataset pinned to it; nothing currently imported through it was found to carry this risk, but any CSV fed into it in the future must clear this check first |

### The outreach opportunity

Separately, and not originally framed as a data-source decision, this project is running a sample
outreach campaign to brand contacts requesting free sample vials for the controlled baseline
(tracked locally, outside this repository, per its own local-only handling). That campaign already
reaches every brand behind a baseline or holdout fragrance. It is a natural, already-planned channel
to also ask each brand to confirm the exact facts this project has otherwise needed from third-party
sources: concentration, release year, brand/line attribution, and perfumer where relevant. A brand's
own confirmation of its own product is the strongest-attribution source available for that fact,
stronger than any third-party directory. Because it is supplied directly and voluntarily by the
rights holder, it needs none of the third-party ToS/licensing review this ADR required for
Parfumo, but it is not automatically unrestricted evidence either: the reply itself becomes a
`SourceSnapshot` row (per ADR-006) and must record who replied and any scope the brand stated. A
reply from a named brand representative defaults to `retain_and_train`; an unattributed
contact-form reply, or one that states a narrower scope such as confirmation only with no
ML/export use, should not.

## Decision

**We will deprecate Parfumo as a production ingestion source, and establish manufacturer-provided
confirmation, solicited through the existing outreach campaign, as the preferred replacement for the
canonical identity facts Parfumo was supplying.**

1. **Retire Parfumo ingestion.** `ParfumoScraper` and the `import-data parfumo-url` /
   `import-data parfumo-search` CLI commands are deprecated; no new writes through this path.
   Removing the code itself is implementation work tracked separately from this decision.
2. **Manufacturer-provided data becomes a first-class source type**, ranked above open data for any
   fact a brand confirms directly. The outreach campaign's letters should ask every contacted brand
   to confirm concentration, release year, and brand/line attribution for the fragrance(s) requested,
   not only the subset where prior source-resolution work already found a specific gap. A reply that
   confirms these facts becomes that fragrance's canonical source for them, superseding any earlier
   Parfumo-derived value.
3. **The ongoing source hierarchy**, consistent with ADR-002 and ADR-006, is: project-owned
   evaluation and baseline data, then manufacturer-provided confirmation, then open-licensed data
   (Wikidata), then bounded capped enrichment (Fragella, unchanged), then excluded sources (Parfumo,
   Fragrantica, Basenotes scraping; FragDB and unverified Kaggle/GitHub/Hugging Face datasets until
   their specific upstream provenance is demonstrated).
4. **Source evidence must record enough to answer, not just where a fact came from, but what may be
   done with it**: source type, retrieval date, and whether the assertion may be retained
   indefinitely, used in the project's own ML work, or exported. This extends `SourceSnapshot`
   rather than replacing it; ADR-006 already requires append-only source evidence with license or
   permission state, this makes the permission state explicit instead of implicit in the source
   name.
5. **Re-verify, do not delete.** The facts in
   `docs/planning/evidence/baseline-v3.1-parfumo-source-resolution.md` that currently rely solely on
   Parfumo should be re-confirmed against manufacturer replies or Wikidata as they arrive, updating
   that document's provenance per entry. The existing Parfumo URLs stay in the document as a
   cross-check trail; they are not themselves the compliance problem, the automated extraction that
   populated application data from them was.

### Alternatives considered

**Continue using Parfumo, restrict it to manual/human lookup only.** Rejected: this project already
has that pattern for Fragrantica and Basenotes (ADR-002's original mitigation, "UI provides
copy-paste from Fragrantica"). Parfumo could be added to that same manual-reference role, but manual
lookup does not solve the actual need this ADR addresses, an authoritative, ToS-clean source for
canonical identity facts going forward, which manufacturer confirmation solves more directly and
with stronger attribution than a manual copy-paste from any third-party directory would.

**Adopt FragDB as the replacement catalog.** Rejected: its own documentation identifies Fragrantica
as a major upstream source, which means a permissive-looking customer license would not necessarily
carry the rights needed. Revisit only if FragDB or Fragrantica produces documented evidence the
underlying rights were actually cleared.

**Treat Wikidata as sufficient on its own.** Rejected as the sole strategy: Wikidata's fragrance
coverage is limited and a fragrance name alone does not reliably distinguish concentration or
flanker versions, exactly the ambiguity this project's source-resolution work already ran into with
Parfumo. Wikidata remains valuable as enrichment, but manufacturer confirmation is preferred wherever
available because it resolves that same ambiguity at the source instead of requiring separate
identity matching.

## Consequences

### Positive

- Removes the largest unreviewed ToS exposure in the project before scaling to additional
  participants, when usage volume would make that exposure worse, not better.
- Manufacturer confirmation becomes the default acquisition path for exactly the canonical identity
  facts this project has repeatedly needed and repeatedly found gaps in third-party coverage for
  (see `baseline-v3.1-parfumo-source-resolution.md`), using a channel the project was already
  running for an unrelated reason (sample requests).
- Data confirmed directly by a manufacturer carries fewer downstream restrictions than any scraped
  or vendor-API source, since it is supplied voluntarily and directly rather than extracted, which
  simplifies the eventual ML training-data provenance question ADR-006 already anticipates.
- The provenance-metadata extension lets a future licensed catalog, additional indie maker, or a
  cleared FragDB relationship plug into the same model without another architecture change.

### Trade-offs

- Coverage regresses for any fragrance whose only prior identity confirmation ran through Parfumo,
  until it is either manually re-verified against a compliant source or a brand replies.
- Manufacturer response is voluntary and not guaranteed; some fragrances, particularly from brands
  routed through generic corporate contact forms rather than a direct brand contact, may never
  receive a reply. Wikidata and Fragella remain the fallback for those.
- Fragella's 20 requests/month cap is unchanged by this decision and remains insufficient for
  anything beyond the same bounded gap-filling role ADR-002's 2026-09-12 amendment already
  describes.

### Follow-up (implementation, not part of this decision)

- The Parfumo import path now refuses to write (fails closed per Decision item 1); removing
  `ParfumoScraper` and its CLI commands outright remains open.
- Add source-type and permission-state fields to `SourceSnapshot` per item 4 above.
- Re-verify each Parfumo-sourced entry in `baseline-v3.1-parfumo-source-resolution.md` as
  manufacturer replies and open-data cross-checks arrive.

## Validation

- The 2026-09-15 inventory (no populated database, no committed dataset carrying Parfumo or
  Fragrantica-rescrape risk) is the baseline this decision assumes; a repository-wide search for
  Parfumo references finding a populated table or seed file in the future would mean this
  assumption needs revisiting.
- Before the project admits participants beyond the current household, every baseline and holdout
  fragrance's concentration, release year, and brand attribution should trace to a source other than
  Parfumo in `baseline-v3.1-parfumo-source-resolution.md`, or be explicitly flagged as still pending
  manufacturer confirmation.
- Any future addition to `kaggle_importer.py`'s input, or any new bulk dataset, should be checked
  against the source table in this ADR before import, not assumed safe because the dataset's own
  license file looks permissive.

## Related

- [ADR-002](adr-002-data-source-strategy.md): tiered acquisition strategy this ADR amends
- [ADR-006](adr-006-version-identity-and-source-provenance.md): source evidence and reuse-rights
  requirements this ADR's provenance-metadata extension satisfies
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md): frozen-checkpoint baseline that
  depends on stable, correctly-attributed fragrance identity
- [ADR-004](adr-004-recommendation-algorithm.md): 2026-09-15 amendment uses Fragella's bounded
  lookup role established here for candidate discovery, not identity enrichment
- `docs/planning/evidence/baseline-v3.1-parfumo-source-resolution.md`: the document holding the
  facts this ADR requires re-verifying
- Outreach contact tracker (tracked locally, outside this repository; see project `.gitignore`)
- Data-licensing outreach packet and per-vendor provenance due diligence (tracked locally,
  outside this repository; see project `.gitignore`)
