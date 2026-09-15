# ADR-012: Data Source Compliance - Parfumo Deprecation and Manufacturer Provenance

> **Status**: Accepted; amends ADR-002
>
> **Date**: 2026-09-15

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
stronger than any third-party directory, and requires no reuse-rights review at all since it is
supplied directly and voluntarily by the rights holder.

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

- Remove or flag-gate `ParfumoScraper` and its CLI commands.
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
