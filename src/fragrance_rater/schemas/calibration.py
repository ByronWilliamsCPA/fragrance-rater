"""Validated protocol inputs and independent unipolar response scales."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fragrance_rater.utils.gtin import is_valid_gtin

Role = Literal[
    "UNIVERSAL_BASELINE",
    "HIDDEN_REPEAT",
    "HOLDOUT",
    "ACTIVE_LEARNING",
    "RETEST",
    "OWNED_VALIDATION",
    "OTHER",
]
Stage = Literal["BLOTTER", "SKIN"]
# R7b input vocabularies. ``models.calibration`` holds the stored codes; a unit
# test pins each of these to its tuple so the two cannot drift.
ResponseStatus = Literal[
    "completed",
    "not_detected",
    "skipped",
    "unable_to_assess",
    "interrupted",
    "invalidated",
]
Recognition = Literal["new", "vaguely_familiar", "recognized_exact"]
OwnedOrWorn = Literal["yes", "no", "unknown"]
SeasonFit = Literal[
    "spring", "summer", "fall", "winter", "year_round", "none", "cannot_judge"
]
SettingFit = Literal[
    "work_school",
    "home",
    "social_outing",
    "formal_event",
    "outdoor_activity",
    "other",
    "none",
    "cannot_judge",
]
# A client clock may run a little ahead of the server's; beyond this a stamp is
# a mistake or a lie, and evidence must not be stamped in the future.
CLOCK_SKEW = timedelta(minutes=5)


def to_naive_utc(value: datetime) -> datetime:
    """Return ``value`` as naive UTC, the schema's one timestamp convention.

    Args:
        value (datetime): A naive (taken as UTC) or timezone-aware datetime.

    Returns:
        datetime: The same instant, naive, in UTC.

    Raises:
        ValueError: If the instant is in the future beyond ``CLOCK_SKEW``.
    """
    utc = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    if utc > datetime.now(UTC).replace(tzinfo=None) + CLOCK_SKEW:
        message = "Timestamps cannot be in the future"
        raise ValueError(message)
    return utc


class StrictInput(BaseModel):
    """Reject unrecognized fields rather than silently losing responses."""

    model_config = ConfigDict(extra="forbid")


class ProgramInput(StrictInput):
    """Versioned program definition."""

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)


class MembershipInput(StrictInput):
    """Require exact catalog ID and documented identity verification."""

    fragrance_id: str
    role: Role
    repeat_of_id: str | None = None
    group_name: str = Field(default="Baseline", min_length=1, max_length=200)
    selection: dict[str, str | float | None] = Field(default_factory=dict)
    identity_evidence: str = Field(min_length=1, max_length=2000)
    # #ASSUME: data-integrity: gtin is optional (a decant, a vintage
    # sample, or some indie houses carry no scannable manufacturer
    # barcode) but when given must be a real, check-digit-valid GTIN -
    # the strongest identity signal this project has, since it is
    # assigned per exact SKU and does not depend on any scraped source
    # being unambiguous. CalibrationService.add_member additionally
    # cross-checks it against the fragrance's own scraped source
    # evidence, when one exists, before accepting it.
    # #VERIFY: covered by schema tests (valid/invalid check digit) and a
    # service-level test for the cross-check.
    gtin: str | None = Field(default=None, min_length=8, max_length=14)

    @field_validator("gtin")
    @classmethod
    def _validate_gtin(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_gtin(value):
            msg = "gtin must be a valid GTIN-8/12/13/14 (GS1 check digit)"
            raise ValueError(msg)
        return value


class EnrollmentInput(StrictInput):
    """Recorder identity is independent of whose palate is measured."""

    reviewer_id: str
    recorder_usernames: list[str] = Field(min_length=1, max_length=20)
    session_size: int = Field(default=3, ge=1, le=20)
    # "standard" yields readable labels (E01-S1-2) that are easy to write on
    # vials; "random" keeps the independent 8-hex-character codes.
    label_scheme: Literal["standard", "random"] = "standard"


class SkinPlanInput(StrictInput):
    """Explicit reason, including low confidence or low-rated controls."""

    reason: str = Field(min_length=1, max_length=2000)


class ResponseInput(StrictInput):
    """A submitted timepoint; null means unanswered, zero is a response."""

    stage: Stage
    elapsed_minutes: int = Field(default=0, ge=0, le=100000)
    detected: bool | None = None
    intensity: int | None = Field(default=None, ge=0, le=5)
    liking: int | None = Field(default=None, ge=0, le=10)
    confidence: int | None = Field(default=None, ge=0, le=5)
    sweetness: int | None = Field(default=None, ge=0, le=5)
    freshness: int | None = Field(default=None, ge=0, le=5)
    density: int | None = Field(default=None, ge=0, le=5)
    familiarity: int | None = Field(default=None, ge=0, le=5)
    dryness: int | None = Field(default=None, ge=0, le=5)
    clean_soapy: int | None = Field(default=None, ge=0, le=5)
    earthy_rooty: int | None = Field(default=None, ge=0, le=5)
    bodily_animalic: int | None = Field(default=None, ge=0, le=5)
    discomfort: int | None = Field(default=None, ge=0, le=5)
    opening_liking: int | None = Field(default=None, ge=0, le=10)
    drydown_liking: int | None = Field(default=None, ge=0, le=10)
    would_wear: int | None = Field(default=None, ge=0, le=10)
    would_buy: int | None = Field(default=None, ge=0, le=10)
    artistic_appreciation: int | None = Field(default=None, ge=0, le=10)
    projection: int | None = Field(default=None, ge=0, le=5)
    longevity_minutes: int | None = Field(default=None, ge=0, le=100000)
    perceived_notes: list[str] | None = Field(default=None, max_length=50)
    likes: str | None = Field(default=None, max_length=2000)
    dislikes: str | None = Field(default=None, max_length=2000)
    reminds_me_of: str | None = Field(default=None, max_length=2000)
    comments: str | None = Field(default=None, max_length=4000)
    # R7b capture fields (R7a schema). Null still means "not recorded".
    observed_at: datetime | None = None
    response_status: ResponseStatus | None = None
    recognition: Recognition | None = None
    owned_or_worn: OwnedOrWorn | None = None
    scrubbed_off: bool | None = None
    time_to_scrub_minutes: int | None = Field(default=None, ge=0, le=100000)
    last_detected_elapsed_min: int | None = Field(default=None, ge=0, le=100000)
    first_not_detected_elapsed_min: int | None = Field(default=None, ge=0, le=100000)
    # Blind season and setting suitability (ML Decisions Q9), multi-select, asked
    # at skin stage only. Each ticked option becomes one ``FitChoice`` row.
    season_fit: list[SeasonFit] | None = Field(default=None, max_length=7)
    setting_fit: list[SettingFit] | None = Field(default=None, max_length=8)
    # R8 PR 2 (D-22, Q18): the client's key for this one submission, the same
    # on every retry of it and fresh for the next. A repeat with the same key
    # returns the original row; the same key with different answers is a 409.
    # Optional so older clients keep working; the released form always sends it.
    idempotency_key: str | None = Field(
        default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the evidence timestamp as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)

    @model_validator(mode="after")
    def validate_detection(self) -> "ResponseInput":
        """Reject neutral liking or missing intensity for non-detection."""
        if self.detected is False and (self.intensity != 0 or self.liking is not None):
            message = "Non-detection requires intensity 0 and liking null"
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def validate_capture_fields(self) -> "ResponseInput":
        """Mirror the R7a database CHECKs so a bad request is a 422, not a 500."""
        if self.response_status == "not_detected" and self.detected is not False:
            message = "response_status not_detected requires detected false"
            raise ValueError(message)
        if self.scrubbed_off is not None and self.stage != "SKIN":
            message = "scrubbed_off applies to skin wear only"
            raise ValueError(message)
        if self.time_to_scrub_minutes is not None and self.scrubbed_off is not True:
            message = "time_to_scrub_minutes requires scrubbed_off true"
            raise ValueError(message)
        last, first = (
            self.last_detected_elapsed_min,
            self.first_not_detected_elapsed_min,
        )
        if last is not None and first is not None and first <= last:
            message = (
                "first_not_detected_elapsed_min must exceed last_detected_elapsed_min"
            )
            raise ValueError(message)
        for name, choices in (
            ("season_fit", self.season_fit),
            ("setting_fit", self.setting_fit),
        ):
            if not choices:
                continue
            if self.stage != "SKIN":
                message = f"{name} is asked at skin stage only"
                raise ValueError(message)
            if len(set(choices)) != len(choices):
                message = f"{name} lists an option twice"
                raise ValueError(message)
            if {"none", "cannot_judge"} & set(choices) and len(choices) > 1:
                message = f"{name}: none and cannot_judge stand alone"
                raise ValueError(message)
        return self


def validate_timezone(name: str) -> str:
    """Return ``name`` if it is a real IANA zone, else raise ``ValueError``.

    Args:
        name (str): A zone name such as ``America/Denver``.

    Returns:
        str: The same name.

    Raises:
        ValueError: If the name is not in the IANA database.
    """
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as error:
        message = f"{name!r} is not an IANA timezone name"
        raise ValueError(message) from error
    return name


class SessionStartInput(StrictInput):
    """When and where a session actually began.

    ``started_at`` is the client clock at submit (naive UTC after validation);
    the server's receipt time stands in when it is omitted. The zone is the
    evaluator's local one, so time of day and the local calendar date can be
    derived without guessing.
    """

    evaluator_timezone: str = Field(min_length=1, max_length=64)
    started_at: datetime | None = None

    @field_validator("evaluator_timezone")
    @classmethod
    def timezone_is_iana(cls, value: str) -> str:
        """Refuse a name the IANA database does not know."""
        return validate_timezone(value)

    @field_validator("started_at")
    @classmethod
    def started_at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the start as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)


class SessionEndInput(StrictInput):
    """When a session actually ended; the server's receipt time if omitted."""

    ended_at: datetime | None = None

    @field_validator("ended_at")
    @classmethod
    def ended_at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the end as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)


ApplicationMethod = Literal["spray", "dab", "roll"]
SampleSourceType = Literal[
    "manufacturer_sample",
    "official_discovery_set",
    "retailer_sample",
    "decant",
    "owned_bottle",
    "unknown",
]
SampleContainer = Literal["spray_atomizer", "dab_vial", "rollerball", "retail_bottle"]


class ExposureInput(StrictInput):
    """The moment a sample was first smelled (blotter) or applied (skin).

    ``at`` is the client clock at submit. The first exposure of a stage is
    recorded once; the sample facts a recorder knows about the physical sample
    ride along because that is when they are known.
    """

    stage: Stage
    at: datetime | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    application_method: ApplicationMethod | None = None
    application_dose_sprays: int | None = Field(default=None, gt=0, le=100)
    sample_source_type: SampleSourceType | None = None
    sample_container: SampleContainer | None = None
    sample_volume_ml: float | None = Field(default=None, gt=0, le=10000)
    sample_acquired_on: date | None = None
    sample_decanted_on: date | None = None
    sample_opened_on: date | None = None
    sample_batch_code: str | None = Field(default=None, max_length=100)
    physical_sample_confirmed: bool | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_is_iana(cls, value: str | None) -> str | None:
        """Refuse a name the IANA database does not know."""
        return None if value is None else validate_timezone(value)

    @field_validator("at")
    @classmethod
    def at_is_naive_utc(cls, value: datetime | None) -> datetime | None:
        """Store the instant as naive UTC, never in the future."""
        return None if value is None else to_naive_utc(value)

    @model_validator(mode="after")
    def application_details_are_skin_only(self) -> "ExposureInput":
        """Method, dose, and a separate zone describe a skin application only.

        A blotter's local time reads through the session's own zone.
        """
        if self.stage == "BLOTTER" and (
            self.application_method is not None
            or self.application_dose_sprays is not None
            or self.timezone is not None
        ):
            message = "application_method, dose, and timezone are skin-only"
            raise ValueError(message)
        return self


class CheckpointInput(StrictInput):
    """External model outputs retain their actual units and algorithm."""

    algorithm_version: str = Field(min_length=1, max_length=200)
    predictions: list[dict[str, str | float | None]] = Field(default_factory=list)
