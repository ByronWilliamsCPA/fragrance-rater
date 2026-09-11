"""Persist recommendation exposure before collecting auditable feedback."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.recommendation_measurement import (
    LLMInvocation,
    PilotOperationalEvent,
    RecommendationImpression,
    RecommendationResponseRevision,
    RecommendationRun,
)
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.schemas.recommendation_measurement import (
    MetricsView,
    ResponseCreate,
    RunCreate,
)
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.services.recommendation_service import RecommendationService
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MeasurementConflictError(ValueError):
    """The requested feedback would violate measurement or blind policy."""


class RecommendationMeasurementService:
    """Create immutable runs and append-only response revisions."""

    ALGORITHM_VERSION = "affinity-v1"
    SCORE_TYPE = "uncalibrated-affinity"
    DEFAULT_METRICS_WINDOW = timedelta(days=90)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_run(
        self, data: RunCreate, *, recorded_by: str | None
    ) -> RecommendationRun:
        """Generate candidates and persist the run and impressions atomically."""
        reviewer = await self.db.scalar(
            select(Reviewer).where(
                Reviewer.id == data.reviewer_id, Reviewer.deleted_at.is_(None)
            )
        )
        if reviewer is None:
            message = "reviewer not found"
            raise LookupError(message)
        history = PreferenceHistoryService(self.db)
        manifest = await history.training_manifest(data.reviewer_id)
        input_version_keys: set[str] = set()
        for row in manifest:
            source_features = row.get("source_features")
            if isinstance(source_features, dict):
                version_key = source_features.get("version_key")
                if isinstance(version_key, str):
                    input_version_keys.add(version_key)
        candidates = await RecommendationService(self.db).get_recommendations(
            data.reviewer_id,
            limit=data.limit,
            exclude_rated=data.exclude_rated,
        )
        candidate_ids = [candidate.fragrance_id for candidate in candidates]
        candidate_versions = (
            list(
                await self.db.scalars(
                    select(Fragrance).where(Fragrance.id.in_(candidate_ids))
                )
            )
            if candidate_ids
            else []
        )
        candidate_by_id = {fragrance.id: fragrance for fragrance in candidate_versions}
        run = RecommendationRun(
            reviewer_id=data.reviewer_id,
            algorithm_version=self.ALGORITHM_VERSION,
            candidate_strategy=data.candidate_strategy,
            filters={"exclude_rated": data.exclude_rated, "limit": data.limit},
            input_manifest=manifest,
            source_snapshot={
                "input_version_keys": sorted(input_version_keys),
                "candidate_versions": [
                    {
                        "fragrance_id": candidate_by_id[candidate_id].id,
                        "name": candidate_by_id[candidate_id].name,
                        "brand": candidate_by_id[candidate_id].brand,
                        "version_key": candidate_by_id[candidate_id].version_key,
                        "data_source": candidate_by_id[candidate_id].data_source,
                        "external_id": candidate_by_id[candidate_id].external_id,
                        "source_url": candidate_by_id[candidate_id].parfumo_url,
                    }
                    for candidate_id in candidate_ids
                    if candidate_id in candidate_by_id
                ],
            },
            recorded_by=recorded_by,
        )
        self.db.add(run)
        await self.db.flush()
        self.db.add_all(
            [
                RecommendationImpression(
                    run_id=run.id,
                    fragrance_id=item.fragrance_id,
                    rank=index,
                    score_type=self.SCORE_TYPE,
                    score_value=item.match_score,
                )
                for index, item in enumerate(candidates, start=1)
            ]
        )
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def run_rows(
        self, run_id: str
    ) -> tuple[RecommendationRun, list[tuple[RecommendationImpression, Fragrance]]]:
        """Load a run and its persisted impressions without creating events."""
        run = await self.db.get(RecommendationRun, run_id)
        if run is None:
            message = "recommendation run not found"
            raise LookupError(message)
        result = await self.db.execute(
            select(RecommendationImpression, Fragrance)
            .join(Fragrance, Fragrance.id == RecommendationImpression.fragrance_id)
            .where(RecommendationImpression.run_id == run_id)
            .order_by(RecommendationImpression.rank)
        )
        return run, [(row[0], row[1]) for row in result]

    async def append_response(
        self,
        impression_id: str,
        data: ResponseCreate,
        *,
        recorded_by: str | None,
    ) -> RecommendationResponseRevision:
        """Append one complete response revision after validating outcome links."""
        impression = await self.db.scalar(
            select(RecommendationImpression)
            .where(RecommendationImpression.id == impression_id)
            .with_for_update()
        )
        if impression is None:
            message = "recommendation impression not found"
            raise LookupError(message)
        run = await self.db.get(RecommendationRun, impression.run_id)
        if run is None:
            message = "recommendation run not found"
            raise LookupError(message)
        if impression.fragrance_id in await PreferenceHistoryService(
            self.db
        ).excluded_versions(run.reviewer_id):
            message = "feedback is unavailable for a holdout version"
            raise MeasurementConflictError(message)
        await self._validate_outcome(data, run, impression)
        current = await self.db.scalar(
            select(func.max(RecommendationResponseRevision.revision)).where(
                RecommendationResponseRevision.impression_id == impression_id
            )
        )
        revision = RecommendationResponseRevision(
            impression_id=impression_id,
            revision=(current or 0) + 1,
            recorded_by=recorded_by,
            **data.model_dump(),
        )
        self.db.add(revision)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            # PostgreSQL serializes on the locked impression. SQLite ignores
            # FOR UPDATE, so its unique constraint is the concurrency guard;
            # translate that race into a stable API conflict instead of 500.
            await self.db.rollback()
            message = "response revision conflicted with a concurrent append"
            raise MeasurementConflictError(message) from exc
        await self.db.refresh(revision)
        return revision

    async def _validate_outcome(
        self,
        data: ResponseCreate,
        run: RecommendationRun,
        impression: RecommendationImpression,
    ) -> None:
        """Ensure linked raw outcomes belong to this reviewer and candidate."""
        if (
            data.outcome_evaluation_id or data.outcome_observation_id
        ) and data.sampling_state != "SAMPLED":
            message = "linked outcomes require sampling_state SAMPLED"
            raise MeasurementConflictError(message)
        if data.outcome_evaluation_id:
            evaluation = await self.db.get(Evaluation, data.outcome_evaluation_id)
            if (
                evaluation is None
                or evaluation.deleted_at is not None
                or evaluation.reviewer_id != run.reviewer_id
                or evaluation.fragrance_id != impression.fragrance_id
                or self._naive_utc(evaluation.evaluated_at) < impression.shown_at
            ):
                message = "ordinary outcome must be a live encounter for this reviewer and version"
                raise MeasurementConflictError(message)
        if data.outcome_observation_id:
            controlled = await self.db.execute(
                select(Observation, Membership, Enrollment)
                .join(Presentation, Presentation.id == Observation.presentation_id)
                .join(Membership, Membership.id == Presentation.membership_id)
                .join(
                    CalibrationSession, CalibrationSession.id == Presentation.session_id
                )
                .join(Enrollment, Enrollment.id == CalibrationSession.enrollment_id)
                .where(Observation.id == data.outcome_observation_id)
            )
            row = controlled.one_or_none()
            membership = row[1] if row else None
            enrollment = row[2] if row else None
            if (
                row is None
                or membership is None
                or enrollment is None
                or membership.fragrance_id != impression.fragrance_id
                or enrollment.reviewer_id != run.reviewer_id
                or enrollment.revealed_at is None
                or row[0].created_at < impression.shown_at
            ):
                message = "controlled outcome must be revealed and match this reviewer and version"
                raise MeasurementConflictError(message)

    async def metrics(
        self,
        reviewer_id: str,
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> MetricsView:
        """Calculate declared metrics from latest revisions with explicit denominators."""
        end = self._naive_utc(window_end) if window_end else now_naive_utc()
        start = (
            self._naive_utc(window_start)
            if window_start
            else end - self.DEFAULT_METRICS_WINDOW
        )
        if start >= end:
            message = "window_start must be before window_end"
            raise ValueError(message)
        result = await self.db.execute(
            select(RecommendationImpression, Fragrance, RecommendationRun)
            .join(
                RecommendationRun,
                RecommendationRun.id == RecommendationImpression.run_id,
            )
            .join(Fragrance, Fragrance.id == RecommendationImpression.fragrance_id)
            .where(
                RecommendationRun.reviewer_id == reviewer_id,
                RecommendationImpression.shown_at >= start,
                RecommendationImpression.shown_at <= end,
            )
        )
        all_rows: list[
            tuple[RecommendationImpression, Fragrance, RecommendationRun]
        ] = [(row[0], row[1], row[2]) for row in result]
        excluded = await PreferenceHistoryService(self.db).excluded_versions(
            reviewer_id
        )
        rows = [row for row in all_rows if row[0].fragrance_id not in excluded]
        impression_ids = [row[0].id for row in rows]
        revisions: dict[str, RecommendationResponseRevision] = {}
        if impression_ids:
            all_revisions = list(
                await self.db.scalars(
                    select(RecommendationResponseRevision)
                    .where(
                        RecommendationResponseRevision.impression_id.in_(impression_ids)
                        & (RecommendationResponseRevision.created_at <= end)
                    )
                    .order_by(
                        RecommendationResponseRevision.impression_id,
                        RecommendationResponseRevision.revision.desc(),
                    )
                )
            )
            for response in all_revisions:
                revisions.setdefault(response.impression_id, response)
        values = list(revisions.values())
        explicit = [item for item in values if item.interested is not None]
        sampled = [item for item in values if item.sampling_state == "SAMPLED"]
        linked = [
            item
            for item in values
            if item.outcome_evaluation_id or item.outcome_observation_id
        ]
        rating_ids = [
            item.outcome_evaluation_id for item in linked if item.outcome_evaluation_id
        ]
        ratings = (
            list(
                await self.db.scalars(
                    select(Evaluation.rating).where(Evaluation.id.in_(rating_ids))
                )
            )
            if rating_ids
            else []
        )
        wear = [item.would_wear for item in values if item.would_wear is not None]
        buy = [item.would_buy for item in values if item.would_buy is not None]
        llm = list(
            await self.db.scalars(
                select(LLMInvocation).where(
                    LLMInvocation.reviewer_id == reviewer_id,
                    LLMInvocation.created_at >= start,
                    LLMInvocation.created_at <= end,
                )
            )
        )
        operational_result = await self.db.execute(
            select(PilotOperationalEvent.event_type, func.count())
            .where(
                PilotOperationalEvent.reviewer_id == reviewer_id,
                PilotOperationalEvent.occurred_at >= start,
                PilotOperationalEvent.occurred_at <= end,
            )
            .group_by(PilotOperationalEvent.event_type)
        )
        operational_counts = {str(row[0]): int(row[1]) for row in operational_result}
        runs = {row[2].id: row[2] for row in rows}.values()
        eligible = len(rows)
        return MetricsView(
            reviewer_id=reviewer_id,
            window_start=start,
            window_end=end,
            reviewer_population=[reviewer_id],
            exclusion_policy=["current assigned holdout versions"],
            excluded_impressions=len(all_rows) - eligible,
            algorithm_versions=sorted({run.algorithm_version for run in runs}),
            candidate_strategies=sorted({run.candidate_strategy for run in runs}),
            run_filters=self._unique_json([run.filters for run in runs]),
            source_snapshots=self._unique_json([run.source_snapshot for run in runs]),
            eligible_impressions=eligible,
            explicit_interest_responses=len(explicit),
            positive_interest_responses=sum(
                item.interested is True for item in explicit
            ),
            response_coverage=len(explicit) / eligible if eligible else None,
            interest_rate=(
                sum(item.interested is True for item in explicit) / len(explicit)
                if explicit
                else None
            ),
            sampled_recommendations=len(sampled),
            sampling_conversion=len(sampled) / eligible if eligible else None,
            linked_outcomes=len(linked),
            mean_ordinary_rating=sum(ratings) / len(ratings) if ratings else None,
            would_wear_positive=sum(wear),
            would_wear_responses=len(wear),
            would_buy_positive=sum(buy),
            would_buy_responses=len(buy),
            unique_brands=len({fragrance.brand for _, fragrance, _run in rows}),
            unavailable_candidates=sum(
                item.sampling_state == "UNAVAILABLE" for item in values
            ),
            llm_call_count=len(llm),
            llm_cache_hits=sum(item.cache_hit for item in llm),
            llm_failures=sum(not item.succeeded for item in llm),
            mean_llm_latency_ms=(
                sum(item.latency_ms for item in llm) / len(llm) if llm else None
            ),
            llm_calls_with_known_estimated_cost=sum(
                item.estimated_cost_usd is not None for item in llm
            ),
            known_estimated_cost_usd=(
                sum(
                    item.estimated_cost_usd
                    for item in llm
                    if item.estimated_cost_usd is not None
                )
                if any(item.estimated_cost_usd is not None for item in llm)
                else None
            ),
            llm_calls_with_known_provider_cost=sum(
                item.provider_cost_usd is not None for item in llm
            ),
            known_provider_cost_usd=(
                sum(
                    item.provider_cost_usd
                    for item in llm
                    if item.provider_cost_usd is not None
                )
                if any(item.provider_cost_usd is not None for item in llm)
                else None
            ),
            connectivity_failures=operational_counts.get("CONNECTIVITY_FAILURE", 0),
            manual_recoveries=operational_counts.get("MANUAL_RECOVERY", 0),
        )

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        """Normalize an API timestamp for UTC-naive database columns."""
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _unique_json(items: list[dict[str, object]]) -> list[dict[str, object]]:
        """Return deterministic unique JSON objects for report provenance."""
        unique = {json.dumps(item, sort_keys=True): item for item in items}
        return [unique[key] for key in sorted(unique)]

    async def record_operational_event(
        self,
        reviewer_id: str,
        event_type: str,
        details: str | None,
        *,
        recorded_by: str,
    ) -> PilotOperationalEvent:
        """Persist a pilot failure or recovery event."""
        reviewer = await self.db.scalar(
            select(Reviewer.id).where(
                Reviewer.id == reviewer_id, Reviewer.deleted_at.is_(None)
            )
        )
        if reviewer is None:
            message = "reviewer not found"
            raise LookupError(message)
        item = PilotOperationalEvent(
            reviewer_id=reviewer_id,
            event_type=event_type,
            details=details,
            recorded_by=recorded_by,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item
