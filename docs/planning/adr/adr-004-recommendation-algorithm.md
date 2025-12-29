# ADR-004: V1 Recommendation Scoring Algorithm

> **Status**: Accepted
> **Date**: 2025-12-28

## TL;DR

Use a simple weighted scoring algorithm based on cumulative note/accord affinities derived from user ratings, with a "veto" mechanism for strongly disliked notes.

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
- ✅ Leverages similar users' ratings

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
- ⚠️ **No cross-user learning**: Doesn't leverage patterns from other family members
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
- [Tech Spec API](../tech-spec.md#api-specification): Recommendation endpoints
- [Concept Doc](../../../concept.md): Original algorithm concept
