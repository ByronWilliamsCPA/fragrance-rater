# ADR-003: LLM Integration - OpenRouter for Recommendations

> **Status**: Accepted
> **Date**: 2025-12-28

## TL;DR

Use OpenRouter as an LLM gateway for generating natural language recommendation explanations, with algorithmic scoring as the primary ranking mechanism.

## Context

### Problem

The recommendation system needs to:

1. Calculate match scores based on note/accord affinities (algorithmic)
2. Generate human-readable explanations for why a fragrance matches (requires LLM)
3. Summarize a user's overall preference profile in natural language

### Constraints

- **Technical**: LLM calls add latency and cost; must not block core functionality
- **Business**: Cost per recommendation should be <$0.05; system must work without LLM

### Significance

LLM integration significantly impacts user experience and operational costs. Over-reliance on LLM makes the app expensive and fragile; under-use misses the opportunity for compelling explanations.

## Decision

**We will use OpenRouter as an LLM gateway with algorithmic scoring as the primary ranking mechanism and LLM-generated explanations as an enhancement layer, because it provides flexibility to choose cost-effective models while keeping the core recommendation logic independent.**

### Rationale

- OpenRouter provides unified API to 100+ models with consistent pricing
- Algorithmic scoring works offline; LLM adds value but isn't required
- Explanations can be cached to reduce repeated API calls

## Options Considered

### Option 1: OpenRouter Gateway + Algorithmic Primary ✓

**Pros**:

- ✅ Model flexibility: Switch between GPT-4o-mini, Claude Haiku, Llama 3 based on cost/quality
- ✅ Graceful degradation: Recommendations work without LLM
- ✅ Caching: Same fragrance → same explanation (cacheable)
- ✅ Cost control: Pay-per-use, no monthly minimum

**Cons**:

- ❌ Additional API dependency
- ❌ Explanation quality varies by model

### Option 2: Direct OpenAI API

**Pros**:

- ✅ Highest quality models
- ✅ Simpler integration

**Cons**:

- ❌ Locked into OpenAI pricing
- ❌ No model flexibility
- ❌ Higher cost for GPT-4 class models

### Option 3: Local LLM (Ollama)

**Pros**:

- ✅ Zero API costs
- ✅ Full privacy
- ✅ Works offline

**Cons**:

- ❌ Significant GPU requirements
- ❌ Model quality lower than cloud options
- ❌ Additional operational complexity on Unraid

## Consequences

### Positive

- ✅ **Flexibility**: Can switch models without code changes
- ✅ **Cost control**: Use cheap models (Claude Haiku ~$0.001/call) for simple tasks
- ✅ **Resilience**: Core scoring works without LLM

### Trade-offs

- ⚠️ **Latency**: LLM calls add 1-3 seconds
  - Mitigation: Generate explanations async, show scores immediately
- ⚠️ **Cost variability**: Usage spikes increase costs
  - Mitigation: Cache explanations, rate limit generation

### Technical Debt

- Implement explanation caching (fragrance + reviewer → cached explanation)
- Add cost monitoring dashboard

## Implementation

### LLM Usage Patterns

| Use Case | Model Tier | Estimated Cost |
|----------|------------|----------------|
| Recommendation explanation | Cheap (Haiku/GPT-4o-mini) | ~$0.001/call |
| Profile summary | Cheap | ~$0.002/call |
| Fragrance comparison | Medium | ~$0.01/call |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Recommendation Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────┐     ┌────────────────────────────┐  │
│  │ 1. Calculate Match │ ──► │ Return ranked list         │  │
│  │    Scores (local)  │     │ with numeric scores        │  │
│  └────────────────────┘     └────────────────────────────┘  │
│          │                                                   │
│          ▼ (async, non-blocking)                            │
│  ┌────────────────────┐     ┌────────────────────────────┐  │
│  │ 2. Check Cache     │ ──► │ Return cached explanation  │  │
│  └────────────────────┘     └────────────────────────────┘  │
│          │ Miss                                              │
│          ▼                                                   │
│  ┌────────────────────┐     ┌────────────────────────────┐  │
│  │ 3. Call OpenRouter │ ──► │ Cache & return explanation │  │
│  └────────────────────┘     └────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Prompt Templates

```python
RECOMMENDATION_PROMPT = """
You are a fragrance expert. Explain why this fragrance might appeal to the user.

User's preference profile:
- Likes: {liked_notes}
- Dislikes: {disliked_notes}
- Preferred families: {preferred_families}

Fragrance: {fragrance_name}
- Family: {family} > {subfamily}
- Top notes: {top_notes}
- Heart notes: {heart_notes}
- Base notes: {base_notes}
- Accords: {accords}

Write 2-3 sentences explaining the match. Highlight specific notes they'll enjoy.
If there are notes they typically dislike, acknowledge this as a potential concern.
"""
```

### Components Affected

1. **LLMService**: OpenRouter client with model selection
2. **ExplanationCache**: Redis or PostgreSQL cache for generated text
3. **RecommendationService**: Combines algorithmic scores with LLM explanations
4. **Frontend**: Shows scores immediately, loads explanations async

### Testing Strategy

- Unit: Mock OpenRouter responses, test prompt generation
- Integration: End-to-end recommendation with real API (dev only)

## Validation

### Success Criteria

- [ ] Recommendations load with scores in <500ms (without LLM)
- [ ] Explanations populate within 3 seconds
- [ ] Cost per recommendation <$0.02 average
- [ ] Cached explanations reused for repeat views

### Review Schedule

- Initial: After first 100 recommendations generated
- Ongoing: Monthly cost review

## Related

- [ADR-001](adr/adr-001-initial-architecture.md): Overall architecture
- [ADR-002](adr/adr-002-data-source-strategy.md): Fragrance data for prompts
- [Tech Spec API](tech-spec.md#api-specification): Recommendation endpoints
