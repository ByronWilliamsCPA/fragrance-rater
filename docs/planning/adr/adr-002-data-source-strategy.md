# ADR-002: Data Source Strategy - Tiered Acquisition

> **Status**: Accepted baseline; source-provenance portions amended by ADR-006
>
> **Date**: 2025-12-28

## TL;DR

Use a local-first tiered data strategy: verified local catalog → manual entry/source link →
authorized source snapshot or refresh. Kaggle and Parfumo are current implemented source paths;
any additional provider must pass provenance and reuse-rights review.

## 2026 amendment

The tiered, local-first principle remains accepted. Fragella was not adopted as the operational
enrichment dependency; the implemented integration captures Parfumo source evidence. Future
sources must satisfy ADR-006 provenance, exact-version, and reuse-rights requirements. The
current priority is local catalog → manual verified entry/source link → authorized source
snapshot or refresh. A source is never allowed to overwrite evaluator evidence or assigned
version identity.

## 2026-09-13 amendment: Fragella as a capped reference lookup, not a source

Fragella's rejection above was as a *primary* source (its 20 requests/month free tier is far too
small for routine enrichment). This amendment authorizes a narrower, still-declined-as-a-source
use: `fragella_client.py` and the `import-data fragella-lookup`/`fragella-usage` CLI commands are
an operator-invoked, quota-capped reference lookup for the same class of gap the V3.1
baseline/holdout resolution hit by hand (see
docs/planning/evidence/baseline-v3.1-parfumo-source-resolution.md) - a same-name ambiguity
Parfumo's own search left open, or a concentration/year Parfumo does not publish.

This does not become a "Fragella-derived corpus" or a stored data source, and does not require
its own reuse-rights review the way one would: nothing `FragellaClient` returns is written into
the `Fragrance` catalog or a `SourceSnapshot`. A `fragella_lookups` row does retain the attempt
(query, status, and result payload) as a lookup-log record so a manager can see which fragrances
still have not been checked without spending another request to find out, but that row is never
adopted into `Fragrance` or `SourceSnapshot` and never written into a membership's identity
evidence - the same role a manual Fragrantica/Basenotes lookup already plays per this ADR's
original mitigation ("UI provides copy-paste from Fragrantica"). Adopting Fragella data as a
stored, provenance-bearing source remains gated behind the reuse-rights review this ADR and
ADR-006 require, unchanged.

The integration itself is built from Fragella's published API documentation, not a live
authenticated response (no API key was available while building it) - see
`fragella_client.py`'s module docstring for the explicit caveat and the smoke-test this ADR
expects before it is relied on for a real gap-filling decision.

## Context

### Problem

The application needs fragrance metadata (notes, accords, family classification) to build preference profiles. External data sources have limitations:

- **Fragella API**: High-quality structured data but only 20 requests/month free tier
- **Fragrantica**: Extensive data but requires web scraping (ToS concerns, fragile)
- **Kaggle datasets**: Free bulk data but may be stale or incomplete

### Constraints

- **Technical**: Must work when APIs unavailable; structured note/accord data required
- **Business**: Minimal cost; 20 API calls/month is insufficient for 50+ evaluations

### Significance

Data acquisition directly impacts core functionality. If users can't get fragrance metadata, preference profiling becomes impossible.

## Decision

**We will use a tiered data strategy (bulk seed → manual → API) because it ensures offline functionality while preserving scarce API calls for genuine gaps.**

### Rationale

- Bulk Kaggle import provides baseline data for common fragrances
- Manual entry ensures app never blocks on missing data
- API enrichment adds value without being a hard dependency

## Options Considered

### Option 1: Tiered Acquisition (Kaggle + Manual + API) ✓

**Pros**:

- ✅ Works completely offline after initial seed
- ✅ Preserves API calls for truly new/rare fragrances
- ✅ Manual fallback ensures app never blocks
- ✅ Each record tracks its data source for future updates

**Cons**:

- ❌ Requires UI for manual note entry
- ❌ Kaggle data may need cleanup/normalization

### Option 2: API-First (Fragella Primary)

**Pros**:

- ✅ Cleanest, most structured data
- ✅ No manual entry burden

**Cons**:

- ❌ 20 req/month insufficient for MVP usage
- ❌ App unusable when API quota exhausted
- ❌ Monthly cost for higher tiers ($29+/month)

### Option 3: Scraping-First (Fragrantica)

**Pros**:

- ✅ Largest dataset (60K+ fragrances)
- ✅ Free

**Cons**:

- ❌ ToS violation risk
- ❌ Fragile to HTML changes
- ❌ Requires maintenance when site updates

## Consequences

### Positive

- ✅ **Resilience**: App works fully offline after seed
- ✅ **Cost control**: Zero ongoing API costs for typical use
- ✅ **Data quality tracking**: Each record knows its source

### Trade-offs

- ⚠️ **Manual entry overhead**: Users must enter notes for rare fragrances
  - Mitigation: UI provides copy-paste from Fragrantica
- ⚠️ **Data staleness**: Kaggle data may be outdated
  - Mitigation: API can enrich/update existing records

### Technical Debt

- Build Kaggle CSV importer with data normalization
- Add data source tracking to fragrance model

## Implementation

### Data Source Priority

```python
class DataSource(Enum):
    MANUAL = "manual"        # User-entered
    KAGGLE = "kaggle"        # Bulk import
    FRAGELLA = "fragella"    # API enrichment
    FRAGRANTICA = "fragrantica"  # Future scraper
```

### Fragrance Lookup Flow

```text
User searches "Chanel Chance"
        │
        ▼
┌─────────────────────┐
│ 1. Search local DB  │
└─────────────────────┘
        │
        ├── Found → Return result
        │
        ▼ Not found
┌─────────────────────┐
│ 2. Show manual form │
│    (with Fragrantica│
│     link to copy)   │
└─────────────────────┘
        │
        ▼ After save
┌─────────────────────┐
│ 3. Background:      │
│    Queue for API    │
│    enrichment       │
└─────────────────────┘
```

### Components Affected

1. **ImportService**: Kaggle CSV parser with normalization
2. **FragranceService**: Multi-source lookup with priority
3. **EnrichmentWorker**: Background API calls for manual entries
4. **Fragrance model**: `data_source` and `external_id` fields

### Background Task Implementation

The "Queue for background API enrichment" will use **FastAPI's built-in `BackgroundTasks`** to avoid adding external dependencies (Celery/Redis) in the MVP.

**Trade-off**: Tasks are lost on server restart, which is acceptable for non-critical enrichment. Can upgrade to Celery if durability becomes a requirement in Phase 2+.

```python
from fastapi import BackgroundTasks

@router.post("/fragrances")
async def create_fragrance(
    fragrance: FragranceCreate,
    background_tasks: BackgroundTasks,
):
    db_fragrance = await save_fragrance(fragrance)

    # Queue enrichment without blocking response
    background_tasks.add_task(
        enrich_from_fragella,
        fragrance_id=db_fragrance.id
    )

    return db_fragrance
```

### Testing Strategy

- Unit: Mock API responses, test fallback chain
- Integration: Import sample Kaggle CSV, verify normalization

## Validation

### Success Criteria

- [ ] Kaggle import creates 1000+ fragrances with notes/accords
- [ ] Manual entry form captures top/heart/base notes
- [ ] API enrichment updates manual entries without duplicates
- [ ] App remains functional with Fragella API disabled

### Review Schedule

- Initial: After Kaggle import complete
- Ongoing: Monthly check on API quota usage

## Related

- [ADR-001](./adr-001-initial-architecture.md): Overall architecture
- [ADR-003](./adr-003-llm-integration.md): LLM uses this data for recommendations
- [ADR-006](./adr-006-version-identity-and-source-provenance.md): Current identity,
  provenance, rights, alias, and taxonomy policy
- [Tech Spec Data Domains](../tech-spec.md#data-domains): Current entity boundaries
