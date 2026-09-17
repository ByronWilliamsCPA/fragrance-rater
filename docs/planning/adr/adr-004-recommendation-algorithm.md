# ADR-004: V1 Recommendation Scoring Algorithm

> **Status**: Partially superseded by ADR-007; candidate discovery extended by the 2026-09-15
> amendment (Fragella-sourced candidates, bounded by ADR-012)
>
> **Date**: 2025-12-28

## TL;DR

Use a simple weighted scoring algorithm based on cumulative note/accord affinities derived from user ratings, with a "veto" mechanism for strongly disliked notes.

## 2026-09-15 amendment: Fragella-sourced candidate discovery

Candidates today come only from `get_fragrances()` (Step 3, below): the local catalog. Once a
household has rated most of what is locally catalogued, the system runs out of new things to
suggest. ADR-012 deprecates Parfumo as the source that used to grow that catalog and establishes
Fragella as a bounded, non-storage lookup rather than a replacement bulk source. This amendment
defines how Fragella participates in candidate generation under that constraint.

When fresh discovery is wanted, call Fragella's `GET /fragrances/match` (preferred) or
`GET /fragrances/similar` (name-seeded fallback, when no accord/note query makes sense) at
recommendation time. Score every fragrance either call returns through the existing
`calculate_match_score` function unchanged, the same weighted affinity and veto logic this ADR
already defines for local candidates. Never rank by Fragella's own signal: `/match` returns no
score at all, and `/similar`'s `SimilarityScore` is partly machine-imputed (Fragella's own
documentation states accords and notes are ML-predicted at an estimated 80% confidence when
community data is sparse). Merge the scored Fragella candidates with scored local candidates and
return the combined top N, 3 by default for this discovery path, using the existing `limit`
parameter on `get_recommendations`.

**Query construction for `/fragrances/match`**: pass only the user's top 2-3 highest-affinity
accords and top 3-5 highest-affinity notes from `UserProfile`, not the full profile. The endpoint
applies conjunctive (AND) matching; a full profile would almost always return zero results. Map
the internal `top`/`heart`/`base` note-position vocabulary to Fragella's `top`/`middle`/`base`
parameter names. The accord weight scale is not fully documented (the API's own examples show
values in an 80-100 range with no stated bound) and must be verified against a live call before
being relied on, the same live-verification discipline `fragella_client.py`'s docstring already
applies to its search endpoint (it caught `Year` returning as a string and `Notes` returning as
objects, not bare strings, versus the vendor documentation). The accord parameter format is
`name:minPercent`, comma-separated; multi-word accord names (`fresh spicy`, `white floral`) keep
their internal space and Fragella's own lowercase casing rather than being converted to
`snake_case`, `camelCase`, or title case. A secondary research pass reports `/match` (per
Fragella's own creator, not independently confirmed here) uses exact canonical note names rather
than the fuzzy text matching `/fragrances`'s ordinary search tolerates; treat this as a working
assumption pending live confirmation, not a settled fact, but it means a resolved canonical value
(see Vocabulary alignment, below), never a raw user-typed or internal-taxonomy string, is what
should ever reach `/match`.

Fragella's playground (`https://api.fragella.com/playground.html`) was checked directly
(screen captures, 2026-09-15) and ruled out as a free way to do this verification. Every
backend-endpoint panel, `/fragrances/match` and `/fragrances/similar` included, is labeled
"Using a test API Key. Results are hardcoded," and the `/fragrances/match` panel ships
pre-filled with the exact accord/note example from Fragella's own documentation. The playground's
own banner claims its controls "execute standard backend REST API requests using your Secret API
Key," contradicting the per-field label; this was resolved empirically, not just by trusting one
claim over the other: the project owner edited the form's accord/note/fragrance-name values
directly and confirmed the returned output does not change, so the panel is confirmed hardcoded,
not merely labeled as such. The playground remains useful for confirming parameter
names and generated curl shape, nothing more. The weight-scale and unrecognized-value questions
below still require either spending one of the real 20 monthly requests through
`fragella_client.py`, or asking Fragella support directly, which costs nothing against the quota
and is worth trying first given how scarce that quota is.

**Vocabulary alignment**: `/notes` and `/accords` are search endpoints (a query term, `limit`
defaulting to 10 and capped at 20), not a listing; there is no call that returns Fragella's full
controlled vocabulary, and both endpoints draw on the same 20 requests/month account-wide cap as
`/match` and `/similar`. Bulk-syncing a full local vocabulary table by iterating those endpoints
would still cost most or all of that monthly budget before a single recommendation call runs, the
same problem ADR-012 already identified for the catalog itself, one level down, and stays
rejected for that reason.

What query construction does instead: resolve each *distinct* internal note or accord (ADR-006's
and ADR-010's taxonomy) to its Fragella canonical name once, the first time that concept is ever
needed in a query, via a single `/notes?search=` or `/accords?search=` call, then cache the result
permanently rather than re-querying it. This is a provider-vocabulary mapping (`provider`,
`entity_type`, `internal_concept_id`, `provider_canonical_name`, `provider_occurrence`,
`provider_description`, `verified_at`), not a local copy of Fragella's catalog: its size is
bounded by how many distinct concepts this project's own taxonomy actually uses, not by
Fragella's vocabulary size, and each row is resolved once, ever, not refreshed on a schedule. This
still respects the quota (an incremental, one-time-per-concept cost spread across however many
months it takes, not a bulk sync attempted in one) while directly fixing the mismatch problem
instead of just tolerating it, which the earlier "send internal names and accept some won't match"
approach did. A `/notes` search for a broad concept can return multiple distinct Fragella records
rather than one, `Bergamot`, `Sicilian Bergamot`, `Calabrian Bergamot`, and `White Bergamot` are
observed as separate entries with separate occurrence counts, not synonyms, so a resolution must
pick one deliberately; default to the higher-occurrence, more generic entry unless a fragrance's
known composition calls for a specific variant. Every retained `/match`/`/similar` response (see
Storage, below) also carries its own `Notes`/`Accords` fields on each returned fragrance, a second,
free source of confirmed canonical names as a byproduct of calls already being made, independent
of the deliberate resolution calls above.

What happens when a supplied accord or note is not recognized is undocumented and must be
verified live rather than assumed, and actually splits into two distinct cases with different
likely defaults, not one. Fragella's general error-handling section distinguishes `400 Bad
Request` ("a required parameter... fails validation"), `404 Not Found` ("no fragrances were
found"), and `429` (quota exceeded), among standard statuses. Malformed syntax that cannot be
parsed at all, `woody:notanumber` for the accord weight, is the stronger candidate for a `400`,
since the parameter itself fails validation before any lookup happens. A syntactically valid but
unrecognized value, `general=ZZZNotARealNote`, is the stronger candidate for a `404` or an empty
result set, since the criteria are well-formed but match nothing; neither hypothesis is confirmed.
This determines whether `/fragrances/match` needs a strip-and-retry fallback for a rejected term
(if 400) or can rely on the AND-match's own sparsity handling (if 404/empty).

Resolve both cases in the same live-verification pass already planned for the accord-weight-scale
question, rather than as separate work: a control call with a known-good canonical value, one with
a syntactically valid but nonexistent note, one with a syntactically valid but nonexistent accord,
and one with malformed accord syntax, four calls total, each isolating one variable. This spends a
meaningful fraction of the monthly quota (4 of 20) in one sitting, so it should happen
deliberately when `/fragrances/match` is actually being implemented, not before, matching this
ADR's existing position that no additional Fragella work is needed during the current
baseline-data phase. Capture each result the way `fragella_client.py`'s existing `#ASSUME`/
`#VERIFY` marker and `LIVE_VERIFIED_SEARCH_RESPONSE` fixture already do for the search endpoint.
Do not call `/usage` reflexively before every Fragella request to check remaining budget either;
whether `/usage` itself counts against the monthly quota is unconfirmed, so check it deliberately,
not automatically.

**Qualitative accords are not the same as the numeric threshold `/match` accepts**: a returned
fragrance's `Main Accords`/`Main Accords Percentage` fields expose qualitative strength buckets
(`Dominant`, `Prominent`, `Moderate`, `Subtle`), while `/fragrances/match`'s `accords` parameter
takes a numeric minimum percentage (`woody:50`). The relationship between the two is undocumented;
do not derive a numeric threshold from a qualitative bucket, or vice versa, without an explicit
vendor mapping. The qualitative buckets describe a *returned* fragrance's own composition; the
numeric threshold constrains what gets *matched* in the first place. Treat them as two independent
signals.

**Terminology**: per ADR-007, the value shown to the user remains the "affinity score," never
"confidence," "probability," or "predicted liking," for Fragella-sourced candidates exactly as for
local ones. Fragella's own ranking or `SimilarityScore` is not exposed to the user; it may be
logged internally for debugging or later comparison only.

**Storage**: Fragella-sourced candidates are never written to `Fragrance` or any other durable
catalog table, and a retained call log is never read back as a substitute for calling Fragella
again, that is the specific thing Fragella's terms restrict, not retention itself. What is
retained (the request and raw response for each `/match` or `/similar` call, extending
`RecommendationRun.source_snapshot`) is kept as a quality-control record: evaluating how well a
given call's returned candidates matched what the model expected, and refining future query
construction (which accords/notes to select, how many, in what order) as calls accumulate. This
mirrors the existing `fragella_lookups` pattern from ADR-002's 2026-09-12 amendment, where a
lookup's query, status, and payload are retained as an audit record without that record ever being
adopted into `Fragrance` or `SourceSnapshot` as data, or used to answer a later lookup in place of
a fresh request. Every new recommendation event calls Fragella live regardless of what a prior log
contains. If a user samples and rates a Fragella-discovered fragrance, it then needs its own
canonical identity record, created the same way any other new fragrance would be (manual entry, or
a manufacturer-confirmed record per ADR-012), not by copying Fragella's fields, retained or
otherwise, wholesale.

**Provenance labeling**: a Fragella-sourced candidate has not been through the same catalog
curation as a locally-sourced one, and its underlying accords/notes may themselves be
ML-imputed by Fragella. Following the pattern ADR-011 already established for worn-by evidence
(distinct evidence types get an explicit label, never silently blended), API and UI surfaces must
label Fragella-sourced recommendations distinctly from local-catalog ones.

Consequences of this amendment:

- Positive: extends the candidate pool past the fixed local catalog without violating Fragella's
  storage restriction, addressing the practical version of this ADR's original "cold start" concern,
  what happens once a household has rated most of what is locally available, not just early on.
- Trade-off: Fragella-sourced candidates carry lower-fidelity note/accord data than curated local
  entries, so their affinity-score inputs are weaker signal; the provenance label above exists so
  this is visible, not blended away.
- Follow-up (implementation, not part of this decision): `fragella_client.py` needs `/fragrances/match`
  and `/fragrances/similar` wrappers; neither exists today, only `/fragrances` search and `/usage`.
  `calculate_match_score` needs to accept a transient, non-persisted fragrance-shaped object, not
  only an ORM `Fragrance` row, since Fragella-sourced candidates are scored without ever being
  written to the database. `RecommendationRun.source_snapshot` currently holds only a
  `parfumo_url`/`data_source` summary per candidate; holding the full request/response needed for
  the QC use above is a schema extension, not something the column already supports.
- Follow-up (implementation, not part of this decision): the live verification pass for
  `/fragrances/match` should run the four isolated calls described above (control, unrecognized
  note, unrecognized accord, malformed syntax) in one sitting. Record each result as a fixture
  plus an `#ASSUME`/`#VERIFY` marker in the new wrapper, the same precedent `fragella_client.py`
  already sets for the search endpoint.
- Follow-up (implementation, not part of this decision): the vocabulary-alignment design above
  needs a `provider_term_mapping` table (`provider`, `entity_type`, `internal_concept_id`,
  `provider_canonical_name`, `provider_occurrence`, `provider_description`, `source_value_hash`,
  `verified_at`) that doesn't exist yet; this sits alongside `SourceSnapshot` conceptually
  (ADR-006's provenance model) but is a distinct table, since it maps this project's ontology to
  an external provider's vocabulary rather than recording where a fact came from.
  `source_value_hash` is a hash of the provider's canonical name, occurrence, and description as
  read at `verified_at`, so a later re-verification pass can detect that the provider silently
  redefined or renamed a term without needing a fully versioned row per provider value the way
  ADR-006 tracks source facts; `verified_at` alone only answers when a mapping was last checked,
  not whether the provider has since changed underneath it.

## Context

### Problem

The recommendation system needs to predict which unrated fragrances a user will enjoy based on their past evaluations. The algorithm must:

- Generate a numeric match score (0-100%) for any fragrance
- Handle nuanced preferences (e.g., "likes citrus, dislikes lemon specifically")
- Be explainable to users and debuggable by developers
- Run efficiently for database queries

### Constraints

- **Technical**: Must work with PostgreSQL queries for sorting/filtering; no ML libraries in MVP
- **Business**: Simple enough to implement in Phase 1; accuracy target 80%

### Significance

This is the core value proposition. A bad algorithm undermines the entire application purpose.

## Decision

**We will use a weighted affinity scoring algorithm with cumulative note/accord preferences and a veto mechanism for strong dislikes, because it's simple, explainable, and handles nuanced preferences like "likes citrus except lemon".**

### Rationale

- Cumulative scoring naturally identifies patterns across multiple evaluations
- Veto mechanism prevents recommendations with dealbreaker notes
- Weights can be tuned based on user feedback without changing architecture

## Options Considered

### Option 1: Weighted Affinity Scoring with Veto ✓

**Pros**:

- ✅ Simple to implement and explain
- ✅ Handles specific note dislikes (the "lemon problem")
- ✅ Deterministic and reproducible
- ✅ Can be computed in SQL for efficient queries

**Cons**:

- ❌ Doesn't capture complex interactions between notes
- ❌ Cold start problem with few evaluations

### Option 2: Collaborative Filtering

**Pros**:

- ✅ Discovers latent preferences
- ✅ Uses similar users' ratings

**Cons**:

- ❌ Requires substantial user base (we have 4 users)
- ❌ More complex to implement
- ❌ Less explainable

### Option 3: Content-Based ML (embeddings)

**Pros**:

- ✅ Captures semantic similarity
- ✅ Handles novel fragrances well

**Cons**:

- ❌ Requires ML infrastructure
- ❌ Overkill for MVP with 4 users
- ❌ Less explainable

## Algorithm Specification

### Step 1: Build User Preference Profile

```python
def build_preference_profile(user_id: UUID) -> UserProfile:
    """
    Aggregate note/accord affinities from all user evaluations.

    Rating weights:
        5 stars = +2.0
        4 stars = +1.0
        3 stars =  0.0 (neutral)
        2 stars = -1.0
        1 star  = -2.0
    """
    evaluations = get_evaluations(user_id)

    note_affinities: dict[UUID, float] = defaultdict(float)
    accord_affinities: dict[str, float] = defaultdict(float)
    family_affinities: dict[str, float] = defaultdict(float)

    for eval in evaluations:
        weight = (eval.rating - 3)  # Maps 1-5 to -2 to +2
        fragrance = eval.fragrance

        # Accumulate note affinities
        for note in fragrance.all_notes:
            note_affinities[note.id] += weight

        # Accumulate accord affinities (weighted by accord intensity)
        for accord, intensity in fragrance.accords.items():
            accord_affinities[accord] += weight * intensity

        # Accumulate family affinities
        family_affinities[fragrance.primary_family] += weight
        family_affinities[fragrance.subfamily] += weight * 0.5

    return UserProfile(
        note_affinities=note_affinities,
        accord_affinities=accord_affinities,
        family_affinities=family_affinities,
        evaluation_count=len(evaluations),
    )
```

### Step 2: Calculate Match Score

```python
def calculate_match_score(profile: UserProfile, fragrance: Fragrance) -> MatchResult:
    """
    Score a fragrance against user preferences.
    Returns 0.0-1.0 normalized score.

    Component weights:
        - Notes: 40% (most predictive)
        - Accords: 30%
        - Family: 20%
        - Subfamily: 10%
    """
    WEIGHTS = {
        'notes': 0.40,
        'accords': 0.30,
        'family': 0.20,
        'subfamily': 0.10,
    }

    # Check for veto (strong dislike of any note)
    VETO_THRESHOLD = -3.0  # Cumulative score indicating strong dislike
    for note in fragrance.all_notes:
        if profile.note_affinities.get(note.id, 0) < VETO_THRESHOLD:
            return MatchResult(
                score=0.1,  # Very low but not zero
                vetoed=True,
                veto_note=note.name,
            )

    # Calculate component scores
    note_scores = [
        profile.note_affinities.get(n.id, 0)
        for n in fragrance.all_notes
    ]
    note_score = sum(note_scores) / max(len(note_scores), 1)

    accord_scores = [
        profile.accord_affinities.get(accord, 0) * intensity
        for accord, intensity in fragrance.accords.items()
    ]
    accord_score = sum(accord_scores) / max(len(accord_scores), 1)

    family_score = profile.family_affinities.get(fragrance.primary_family, 0)
    subfamily_score = profile.family_affinities.get(fragrance.subfamily, 0)

    # Weighted sum (raw score can be negative)
    raw_score = (
        WEIGHTS['notes'] * note_score +
        WEIGHTS['accords'] * accord_score +
        WEIGHTS['family'] * family_score +
        WEIGHTS['subfamily'] * subfamily_score
    )

    # Normalize to 0-1 range using sigmoid-like function
    # This maps roughly: -4 → 0.1, 0 → 0.5, +4 → 0.9
    normalized = 1 / (1 + math.exp(-raw_score))

    return MatchResult(
        score=normalized,
        vetoed=False,
        components={
            'notes': note_score,
            'accords': accord_score,
            'family': family_score,
        }
    )
```

### Step 3: Generate Recommendations

```python
def get_recommendations(
    user_id: UUID,
    limit: int = 10,
    exclude_rated: bool = True,
) -> list[Recommendation]:
    """
    Return top-N fragrances for a user, sorted by match score.
    """
    profile = build_preference_profile(user_id)

    if profile.evaluation_count < 3:
        raise InsufficientDataError("Need at least 3 evaluations")

    # Get candidate fragrances
    candidates = get_fragrances(exclude_user_rated=user_id if exclude_rated else None)

    # Score and sort
    scored = []
    for fragrance in candidates:
        result = calculate_match_score(profile, fragrance)
        scored.append(Recommendation(
            fragrance=fragrance,
            match_score=result.score,
            vetoed=result.vetoed,
            veto_reason=f"Contains {result.veto_note} which you dislike" if result.vetoed else None,
        ))

    # Sort by score descending, vetoed items last
    scored.sort(key=lambda r: (not r.vetoed, r.score), reverse=True)

    return scored[:limit]
```

## Consequences

### Positive

- ✅ **Explainable**: Can show users exactly which notes influenced the score
- ✅ **Nuanced**: Handles "likes citrus except lemon" via specific note tracking
- ✅ **Efficient**: Profile can be cached; scoring is O(n) per fragrance
- ✅ **Tunable**: Weights can be adjusted based on accuracy feedback

### Trade-offs

- ⚠️ **Cold start**: Needs 3+ evaluations for meaningful recommendations
  - Mitigation: Show "rate more fragrances" prompt; suggest popular ones
- ⚠️ **No cross-user learning**: Doesn't use patterns from other family members
  - Mitigation: Add collaborative filtering in Phase 3 if needed

### Technical Debt

- Profile computation should be cached with invalidation on new evaluation
- Consider SQL-based scoring for large fragrance databases (>10K)

## Implementation

### Components Affected

1. **UserProfile model**: Stores computed affinities
2. **RecommendationService**: Implements scoring algorithm
3. **Profile cache**: Invalidates on new evaluation
4. **API endpoints**: `/recommendations/{user_id}`

### Testing Strategy

- Unit: Test scoring with known inputs/outputs
- Integration: Verify recommendations change after new evaluations
- Accuracy: Track thumbs-up/down on recommendations to measure 80% target

## Validation

### Success Criteria

- [ ] Recommendations differ meaningfully between family members
- [ ] Adding a 1-star rating for a fragrance with lemon lowers all lemon-containing recommendations
- [ ] Match scores update within 1 second of new evaluation
- [ ] 80% of recommendations marked "interesting" after 10+ evaluations

### Review Schedule

- Initial: After first 50 evaluations across family
- Ongoing: Monthly accuracy review via thumbs-up/down tracking

## Related

- [ADR-003](./adr-003-llm-integration.md): LLM adds explanations to these scores
- [ADR-007](./adr-007-preference-evidence-and-score-semantics.md): Current evidence
  selection and score semantics
- [ADR-011](./adr-011-worn-by-evidence-dimension.md): Precedent for labeling a distinct
  evidence/provenance type rather than blending it silently
- [ADR-012](./adr-012-data-source-compliance-and-manufacturer-provenance.md): Fragella's storage
  boundary and bounded-lookup role that the 2026-09-15 amendment operates within
- [Tech Spec API](../tech-spec.md#api-surface): Recommendation endpoints
