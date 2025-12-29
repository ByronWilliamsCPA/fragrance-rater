"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models import (
    DataSource, Concentration, GenderTarget, NotePosition,
    FragranceFamily, FragranceSubfamily
)


# --- Note Schemas ---

class NoteBase(BaseModel):
    name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None


class NoteCreate(NoteBase):
    pass


class NoteResponse(NoteBase):
    id: int
    normalized_name: Optional[str] = None
    occurrence_count: int = 0
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NoteWithPosition(BaseModel):
    """Note with its position in the olfactory pyramid"""
    note: NoteResponse
    position: NotePosition


# --- Fragrance Schemas ---

class FragranceBase(BaseModel):
    name: str
    brand: str
    concentration: Optional[Concentration] = None
    gender_target: Optional[GenderTarget] = None
    launch_year: Optional[int] = None
    country: Optional[str] = None
    primary_family: Optional[FragranceFamily] = None
    subfamily: Optional[FragranceSubfamily] = None


class FragranceCreate(FragranceBase):
    """Schema for creating a new fragrance"""
    # Notes as lists of note names or IDs
    top_notes: Optional[List[str]] = Field(default_factory=list)
    heart_notes: Optional[List[str]] = Field(default_factory=list)
    base_notes: Optional[List[str]] = Field(default_factory=list)

    # Accords as dict
    accords: Optional[Dict[str, float]] = Field(default_factory=dict)

    # Performance
    longevity: Optional[str] = None
    sillage: Optional[str] = None

    # Optional
    rating: Optional[float] = None
    image_url: Optional[str] = None
    fragrantica_url: Optional[str] = None

    # Data source (for tracking)
    data_source: DataSource = DataSource.MANUAL


class FragranceUpdate(BaseModel):
    """Schema for updating a fragrance"""
    name: Optional[str] = None
    brand: Optional[str] = None
    concentration: Optional[Concentration] = None
    gender_target: Optional[GenderTarget] = None
    launch_year: Optional[int] = None
    country: Optional[str] = None
    primary_family: Optional[FragranceFamily] = None
    subfamily: Optional[FragranceSubfamily] = None
    top_notes: Optional[List[str]] = None
    heart_notes: Optional[List[str]] = None
    base_notes: Optional[List[str]] = None
    accords: Optional[Dict[str, float]] = None
    longevity: Optional[str] = None
    sillage: Optional[str] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    data_source: Optional[DataSource] = None


class FragranceResponse(FragranceBase):
    """Full fragrance response with all details"""
    id: int

    # Notes organized by position
    top_notes: List[NoteResponse] = Field(default_factory=list)
    heart_notes: List[NoteResponse] = Field(default_factory=list)
    base_notes: List[NoteResponse] = Field(default_factory=list)

    # Accords
    accords: Dict[str, Any] = Field(default_factory=dict)

    # Performance
    longevity: Optional[str] = None
    sillage: Optional[str] = None
    longevity_score: Optional[float] = None
    sillage_score: Optional[float] = None

    # Ratings
    rating: Optional[float] = None
    rating_count: int = 0

    # Media
    image_url: Optional[str] = None
    purchase_url: Optional[str] = None
    fragrantica_url: Optional[str] = None

    # Season/occasion
    season_ranking: Optional[Dict[str, float]] = None
    occasion_ranking: Optional[Dict[str, float]] = None

    # Metadata
    data_source: DataSource
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FragranceListResponse(BaseModel):
    """Simplified fragrance for list views"""
    id: int
    name: str
    brand: str
    concentration: Optional[Concentration] = None
    gender_target: Optional[GenderTarget] = None
    primary_family: Optional[FragranceFamily] = None
    rating: Optional[float] = None
    image_url: Optional[str] = None
    data_source: DataSource

    model_config = ConfigDict(from_attributes=True)


# --- Reviewer Schemas ---

class ReviewerBase(BaseModel):
    name: str
    notes_text: Optional[str] = None


class ReviewerCreate(ReviewerBase):
    pass


class ReviewerResponse(ReviewerBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Evaluation Schemas ---

class EvaluationBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    notes: Optional[str] = None
    longevity_rating: Optional[int] = Field(None, ge=1, le=5)
    sillage_rating: Optional[int] = Field(None, ge=1, le=5)
    season_preference: Optional[List[str]] = None
    occasion_tags: Optional[List[str]] = None


class EvaluationCreate(EvaluationBase):
    fragrance_id: int
    reviewer_id: int
    evaluated_at: Optional[datetime] = None


class EvaluationResponse(EvaluationBase):
    id: int
    fragrance_id: int
    reviewer_id: int
    evaluated_at: datetime
    created_at: datetime

    # Include related data
    fragrance: Optional[FragranceListResponse] = None
    reviewer: Optional[ReviewerResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- Preference Profile Schemas ---

class NoteAffinity(BaseModel):
    """A note with its affinity score for a reviewer"""
    note: NoteResponse
    affinity: float  # -1.0 to 1.0


class ReviewerPreferenceResponse(BaseModel):
    """Computed preference profile for a reviewer"""
    reviewer_id: int

    family_scores: Dict[str, float] = Field(default_factory=dict)
    subfamily_scores: Dict[str, float] = Field(default_factory=dict)

    preferred_notes: List[NoteAffinity] = Field(default_factory=list)
    disliked_notes: List[NoteAffinity] = Field(default_factory=list)

    evaluation_count: int = 0
    confidence_score: float = 0.0
    computed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Recommendation Schemas ---

class RecommendationResponse(BaseModel):
    """A fragrance recommendation for a reviewer"""
    fragrance: FragranceListResponse
    match_score: float  # 0.0 to 1.0
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)  # e.g., "Contains lemon which you dislike"


# --- Search/Filter Schemas ---

class FragranceSearchParams(BaseModel):
    """Parameters for searching fragrances"""
    query: Optional[str] = None  # Search name/brand
    brand: Optional[str] = None
    family: Optional[FragranceFamily] = None
    subfamily: Optional[FragranceSubfamily] = None
    gender: Optional[GenderTarget] = None
    notes: Optional[List[str]] = None  # Must contain these notes
    min_rating: Optional[float] = None
    limit: int = Field(default=50, le=200)
    offset: int = 0


# --- Data Import Schemas ---

class ImportResult(BaseModel):
    """Result of a data import operation"""
    source: DataSource
    total_records: int
    imported: int
    updated: int
    skipped: int
    errors: int
    error_messages: List[str] = Field(default_factory=list)
