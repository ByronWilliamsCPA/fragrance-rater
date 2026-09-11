"""Request and response contracts for recommendation outcome measurement."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunCreate(BaseModel):
    """Parameters that produce a new persisted recommendation run."""

    reviewer_id: str
    limit: int = Field(default=10, ge=1, le=50)
    exclude_rated: bool = True
    candidate_strategy: Literal["catalog-affinity"] = "catalog-affinity"


class ResponseCreate(BaseModel):
    """Complete latest feedback state; submission appends a revision."""

    model_config = ConfigDict(extra="forbid")

    interested: bool | None = None
    sampling_state: Literal["PLANNED", "ACQUIRED", "SAMPLED", "UNAVAILABLE"] | None = (
        None
    )
    unavailable_reason: str | None = Field(default=None, max_length=2000)
    outcome_evaluation_id: str | None = None
    outcome_observation_id: str | None = None
    would_wear: bool | None = None
    would_buy: bool | None = None

    @model_validator(mode="after")
    def validate_links(self) -> ResponseCreate:
        """Keep outcome and unavailability semantics unambiguous."""
        if self.outcome_evaluation_id and self.outcome_observation_id:
            message = "link either an ordinary or controlled outcome, not both"
            raise ValueError(message)
        if self.unavailable_reason and self.sampling_state != "UNAVAILABLE":
            message = "unavailable_reason requires sampling_state UNAVAILABLE"
            raise ValueError(message)
        if (
            self.outcome_evaluation_id or self.outcome_observation_id
        ) and self.sampling_state != "SAMPLED":
            message = "linked outcomes require sampling_state SAMPLED"
            raise ValueError(message)
        return self


class ResponseView(ResponseCreate):
    """Stored append-only feedback revision."""

    id: str
    impression_id: str
    revision: int
    created_at: datetime
    recorded_by: str | None


class ImpressionView(BaseModel):
    """Candidate and immutable ranking information shown to an evaluator."""

    id: str
    fragrance_id: str
    fragrance_name: str
    fragrance_brand: str
    rank: int
    score_type: str
    score_value: float
    match_percent: int
    shown_at: datetime
    responses: list[ResponseView] = Field(default_factory=list)


class RunView(BaseModel):
    """A recommendation run and its already-persisted impressions."""

    id: str
    reviewer_id: str
    algorithm_version: str
    candidate_strategy: str
    created_at: datetime
    impressions: list[ImpressionView]


class MetricsView(BaseModel):
    """Explicit counts and denominators for recommendation outcomes."""

    reviewer_id: str
    window_start: datetime
    window_end: datetime
    reviewer_population: list[str]
    exclusion_policy: list[str]
    excluded_impressions: int
    algorithm_versions: list[str]
    candidate_strategies: list[str]
    run_filters: list[dict[str, object]]
    source_snapshots: list[dict[str, object]]
    eligible_impressions: int
    explicit_interest_responses: int
    positive_interest_responses: int
    response_coverage: float | None
    interest_rate: float | None
    sampled_recommendations: int
    sampling_conversion: float | None
    linked_outcomes: int
    mean_ordinary_rating: float | None
    would_wear_positive: int
    would_wear_responses: int
    would_buy_positive: int
    would_buy_responses: int
    unique_brands: int
    unavailable_candidates: int
    llm_call_count: int
    llm_cache_hits: int
    llm_failures: int
    mean_llm_latency_ms: float | None
    llm_calls_with_known_estimated_cost: int
    known_estimated_cost_usd: float | None
    llm_calls_with_known_provider_cost: int
    known_provider_cost_usd: float | None
    connectivity_failures: int
    manual_recoveries: int


class OperationalEventCreate(BaseModel):
    """Pilot connectivity or manual-recovery observation."""

    reviewer_id: str
    event_type: Literal["CONNECTIVITY_FAILURE", "MANUAL_RECOVERY"]
    details: str | None = Field(default=None, max_length=2000)
