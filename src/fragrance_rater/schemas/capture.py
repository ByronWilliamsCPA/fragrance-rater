"""Validated inputs for rankings and quality flags (R7b).

Rank positions follow standard competition ranking: ties share the lower
position and the next position skips (1, 1, 3), which is what the instrument
offers. A pairwise judgment is a ranking with two entries, never a separate
record (ADR-005 2026-09-19 amendment; ML Decisions Q8).
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from fragrance_rater.schemas.calibration import Stage, StrictInput, to_naive_utc

RankStatus = Literal[
    "completed", "skipped", "unable_to_assess", "interrupted", "invalidated"
]
FlagTarget = Literal["session", "presentation", "observation"]
FlagAction = Literal["raised", "resolved", "invalidated"]
# ``automatic_validation`` is reserved for rules the server runs itself; a
# caller cannot claim it.
FlagSource = Literal["evaluator", "recorder", "manager"]
FlagSeverity = Literal["info", "minor", "major"]
FlagDisposition = Literal["review", "include", "exclude"]
FlagCode = Literal[
    "out_of_order_presentation",
    "outside_planned_window",
    "timestamp_inconsistent",
    "daily_load_exceeded",
    "minimum_spacing_violated",
    "clean_air_break_missed",
    "interrupted",
    "sample_substitution",
    "sample_spill",
    "mislabel_suspected",
    "competing_odor",
    "recorder_assistance",
    "instrument_fault",
    "evaluator_reported_problem",
    "other",
]


class RankEntryInput(StrictInput):
    """One detected sample's place in the ranking."""

    presentation_id: str = Field(min_length=1, max_length=36)
    rank_position: int = Field(ge=1, le=1000)


class RankingInput(StrictInput):
    """An end-of-session ranking of the detected samples.

    Only samples the evaluator detected are ranked; the server lists the
    undetected ones itself, so a client cannot rank or hide them.
    """

    stage: Stage
    criterion: Literal["liking"] = "liking"
    response_status: RankStatus
    ranked_at: datetime | None = None
    entries: list[RankEntryInput] = Field(default_factory=list, max_length=100)

    @field_validator("ranked_at")
    @classmethod
    def ranked_at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the instant as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)

    @model_validator(mode="after")
    def validate_entries(self) -> "RankingInput":
        """A completed ranking carries ordered entries; any other status carries none."""
        if self.response_status != "completed":
            if self.entries:
                message = f"A {self.response_status} ranking carries no entries"
                raise ValueError(message)
            return self
        if len(self.entries) < 2:
            message = "A completed ranking needs at least two detected samples"
            raise ValueError(message)
        ids = [entry.presentation_id for entry in self.entries]
        if len(set(ids)) != len(ids):
            message = "A sample appears twice in the ranking"
            raise ValueError(message)
        positions = sorted(entry.rank_position for entry in self.entries)
        for index, position in enumerate(positions):
            expected = 1 + sum(1 for other in positions if other < position)
            if position != expected:
                message = (
                    "Positions must follow competition ranking (for example 1, 1, 3), "
                    f"but {position} cannot follow {positions[:index]}"
                )
                raise ValueError(message)
        return self


class QualityFlagInput(StrictInput):
    """Raise a flag, or close one with a later ``resolved`` or ``invalidated`` row.

    A flag is never edited. ``raised`` names its target and code; a closing row
    names only the flag it closes and inherits the target and code from it.
    """

    action: FlagAction
    source: FlagSource
    disposition: FlagDisposition
    target_type: FlagTarget | None = None
    target_id: str | None = Field(default=None, min_length=1, max_length=36)
    code: FlagCode | None = None
    severity: FlagSeverity | None = None
    supersedes_id: str | None = Field(default=None, min_length=1, max_length=36)
    explanation: str | None = Field(default=None, max_length=4000)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the instant as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)

    @model_validator(mode="after")
    def validate_shape(self) -> "QualityFlagInput":
        """Raising names a target and code; closing names the flag it closes."""
        if self.action == "raised":
            missing = [
                name
                for name in ("target_type", "target_id", "code", "severity")
                if getattr(self, name) is None
            ]
            if missing:
                message = f"Raising a flag requires {', '.join(missing)}"
                raise ValueError(message)
            if self.supersedes_id is not None:
                message = "A raised flag has nothing to supersede"
                raise ValueError(message)
            return self
        if self.supersedes_id is None:
            message = f"A {self.action} flag must name the flag it closes"
            raise ValueError(message)
        if self.target_type or self.target_id or self.code:
            message = "A closing flag inherits its target and code"
            raise ValueError(message)
        return self
