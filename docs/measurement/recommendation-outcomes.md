---
title: "Recommendation Outcome Measurement"
schema_type: common
status: published
owner: core-maintainer
purpose: "Event, revision, outcome-link, and reporting contract for P2."
tags:
  - architecture
  - evaluation
  - observability
---

The measured recommendation path starts with `POST /api/v1/recommendation-measurement/runs`.
The transaction freezes the current preference input manifest and creates one impression for
each ranked candidate before the response returns. `GET /runs/{id}` reads that event and creates
nothing. A deliberate request for a new run represents a new exposure; refreshing or reopening
an existing run does not.

Each feedback submission appends a complete revision. Earlier revisions remain immutable. The
latest revision supplies current interest, sampling state, wear, buy, and outcome-link values.
An ordinary outcome link must identify a live encounter for the same evaluator and exact
fragrance version. A controlled outcome link must identify the same evaluator and version and is
accepted only after reveal. Raw evaluations and observations are never rewritten by linking.

Assigned holdout versions are removed from candidate generation regardless of the
`exclude_rated` option. Feedback rejects a version that becomes a holdout, and reporting removes
current holdouts conservatively. Reports use the latest response revision and expose numerator
and denominator counts alongside rates.

The current evaluator UI records interest or pass in one tap. The implemented feedback API also
accepts sampling state, outcome linking, wear, and buy in later append-only response revisions;
P4 exposes those follow-up actions in the participant UI. Managers retrieve the report from
`GET /api/v1/recommendation-measurement/reviewers/{reviewer_id}/metrics`. Optional
`window_start` and `window_end` query parameters bound the report; the response always states the
effective window and frozen run provenance. When `window_start` is omitted, the API applies a
90-day window ending at `window_end` (or the current time when both are omitted).

## Metric meanings

- Eligible impressions exclude holdouts.
- Response coverage divides explicit interest responses by eligible impressions.
- Interest rate divides positive responses by explicit responses.
- Sampling conversion divides latest `SAMPLED` states by eligible impressions.
- Ordinary post-sample liking retains its original 1–5 scale.
- Wear and buy have separate response and positive counts.
- Variety currently reports unique houses; candidate count and unavailable count accompany it.
- LLM telemetry records attempt count, latency, cache status, failure status, model, token counts,
  prompt-template version, and OpenRouter's provider-reported cost in USD. Missing provider
  accounting remains null;
  reports distinguish calls with known cost and never silently convert an unknown cost to zero.
- Connectivity failures and manual recoveries are explicit pilot events.

Every exported analysis must additionally state its time window, reviewer population, algorithm
version, candidate strategy, filters, exclusions, source snapshot, and counts. Small samples show
their counts and uncertainty. “Accuracy” is reserved for a separately declared prediction target
and decision rule.
