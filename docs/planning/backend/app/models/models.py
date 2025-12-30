"""
Database models for the Fragrance Tracker application.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey,
    Enum, Boolean, Table, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# --- Enums ---

class DataSource(str, PyEnum):
    """Tracks where fragrance data originated"""
    KAGGLE = "kaggle"
    FRAGELLA = "fragella"
    FRAGRANTICA = "fragrantica"
    MANUAL = "manual"


class Concentration(str, PyEnum):
    """Perfume concentration types"""
    PARFUM = "parfum"
    EDP = "edp"          # Eau de Parfum
    EDT = "edt"          # Eau de Toilette
    EDC = "edc"          # Eau de Cologne
    BODY_MIST = "body_mist"
    OTHER = "other"


class GenderTarget(str, PyEnum):
    """Intended gender for fragrance"""
    FEMININE = "feminine"
    MASCULINE = "masculine"
    UNISEX = "unisex"


class NotePosition(str, PyEnum):
    """Position in the olfactory pyramid"""
    TOP = "top"
    HEART = "heart"
    BASE = "base"
    GENERAL = "general"  # When pyramid position unknown


class FragranceFamily(str, PyEnum):
    """Michael Edwards primary families"""
    FRESH = "fresh"
    FLORAL = "floral"
    AMBER = "amber"      # Formerly "Oriental"
    WOODY = "woody"


class FragranceSubfamily(str, PyEnum):
    """Michael Edwards 14 subfamilies"""
    # Fresh family
    AROMATIC = "aromatic"
    CITRUS = "citrus"
    WATER = "water"
    GREEN = "green"
    FRUITY = "fruity"
    # Floral family
    FLORAL = "floral"
    SOFT_FLORAL = "soft_floral"
    FLORAL_AMBER = "floral_amber"
    # Amber family
    SOFT_AMBER = "soft_amber"
    AMBER = "amber"
    WOODY_AMBER = "woody_amber"
    # Woody family
    WOODS = "woods"
    MOSSY_WOODS = "mossy_woods"
    DRY_WOODS = "dry_woods"


# --- Association Tables ---

# Many-to-many: Fragrance <-> Note with position
fragrance_notes = Table(
    'fragrance_notes',
    Base.metadata,
    Column('fragrance_id', Integer, ForeignKey('fragrances.id', ondelete='CASCADE'), primary_key=True),
    Column('note_id', Integer, ForeignKey('notes.id', ondelete='CASCADE'), primary_key=True),
    Column('position', Enum(NotePosition), default=NotePosition.GENERAL),
    Column('prominence', Integer, default=0),  # Order/prominence within position (0 = most prominent)
)


# --- Core Models ---

class Note(Base):
    """Individual fragrance notes (ingredients)"""
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    normalized_name = Column(String(100), index=True)  # Lowercase, standardized

    # Classification
    category = Column(String(50))  # citrus, floral, woody, etc.
    subcategory = Column(String(50))

    # Metadata
    description = Column(Text)
    occurrence_count = Column(Integer, default=0)  # How many fragrances use this note
    image_url = Column(String(500))

    # Relationships
    fragrances = relationship(
        "Fragrance",
        secondary=fragrance_notes,
        back_populates="notes"
    )

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Note(name='{self.name}')>"


class Fragrance(Base):
    """Core fragrance/perfume entity"""
    __tablename__ = 'fragrances'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity
    name = Column(String(255), nullable=False, index=True)
    brand = Column(String(255), nullable=False, index=True)

    # External references
    fragrantica_url = Column(String(500))
    fragella_id = Column(String(100))
    external_id = Column(String(100))  # Generic external ID

    # Classification
    concentration = Column(Enum(Concentration))
    gender_target = Column(Enum(GenderTarget))
    launch_year = Column(Integer)
    country = Column(String(100))

    # Michael Edwards classification
    primary_family = Column(Enum(FragranceFamily))
    subfamily = Column(Enum(FragranceSubfamily))

    # Performance metrics (from community data)
    longevity = Column(String(50))  # "Weak", "Moderate", "Long Lasting", etc.
    sillage = Column(String(50))    # "Soft", "Moderate", "Heavy", etc.
    longevity_score = Column(Float)  # Numeric if available
    sillage_score = Column(Float)

    # Pricing
    price = Column(Float)
    price_currency = Column(String(3), default="USD")

    # Community ratings
    rating = Column(Float)
    rating_count = Column(Integer, default=0)

    # Media
    image_url = Column(String(500))
    purchase_url = Column(String(500))

    # Accords stored as JSON: {"woody": 0.85, "citrus": 0.72, ...}
    accords = Column(JSON, default=dict)

    # Season and occasion rankings stored as JSON
    season_ranking = Column(JSON)   # {"spring": 2.3, "summer": 1.2, ...}
    occasion_ranking = Column(JSON)  # {"professional": 2.6, "casual": 1.1, ...}

    # Data source tracking
    data_source = Column(Enum(DataSource), default=DataSource.MANUAL)
    data_source_updated_at = Column(DateTime)

    # Relationships
    notes = relationship(
        "Note",
        secondary=fragrance_notes,
        back_populates="fragrances"
    )
    evaluations = relationship("Evaluation", back_populates="fragrance", cascade="all, delete-orphan")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('name', 'brand', name='uq_fragrance_name_brand'),
        Index('ix_fragrance_search', 'name', 'brand'),
    )

    def __repr__(self):
        return f"<Fragrance(name='{self.name}', brand='{self.brand}')>"


class Reviewer(Base):
    """Family members who evaluate fragrances"""
    __tablename__ = 'reviewers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

    # Optional profile info
    notes_text = Column(Text)  # General notes about this person's preferences

    # Relationships
    evaluations = relationship("Evaluation", back_populates="reviewer", cascade="all, delete-orphan")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Reviewer(name='{self.name}')>"


class Evaluation(Base):
    """A reviewer's evaluation of a fragrance"""
    __tablename__ = 'evaluations'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core relationships
    fragrance_id = Column(Integer, ForeignKey('fragrances.id', ondelete='CASCADE'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('reviewers.id', ondelete='CASCADE'), nullable=False)

    # Rating (1-5 scale)
    rating = Column(Integer, nullable=False)

    # Free-form notes
    notes = Column(Text)

    # Optional structured feedback
    longevity_rating = Column(Integer)  # 1-5
    sillage_rating = Column(Integer)    # 1-5

    # Context
    season_preference = Column(JSON)  # ["spring", "summer"]
    occasion_tags = Column(JSON)      # ["date night", "work", "casual"]

    # When was this fragrance actually tested
    evaluated_at = Column(DateTime, default=func.now())

    # Relationships
    fragrance = relationship("Fragrance", back_populates="evaluations")
    reviewer = relationship("Reviewer", back_populates="evaluations")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Allow multiple evaluations of same fragrance by same person (over time)
        Index('ix_evaluation_fragrance_reviewer', 'fragrance_id', 'reviewer_id'),
    )

    def __repr__(self):
        return f"<Evaluation(fragrance_id={self.fragrance_id}, reviewer_id={self.reviewer_id}, rating={self.rating})>"


class ReviewerPreference(Base):
    """Computed preference profile for a reviewer (updated periodically)"""
    __tablename__ = 'reviewer_preferences'

    id = Column(Integer, primary_key=True, autoincrement=True)
    reviewer_id = Column(Integer, ForeignKey('reviewers.id', ondelete='CASCADE'), unique=True, nullable=False)

    # Aggregated preferences
    family_scores = Column(JSON)      # {"fresh": 0.82, "woody": 0.51, ...}
    subfamily_scores = Column(JSON)
    note_affinities = Column(JSON)    # {"bergamot": 0.9, "lemon": -0.8, ...}
    accord_affinities = Column(JSON)

    # Identified patterns
    preferred_notes = Column(JSON)    # [note_ids]
    disliked_notes = Column(JSON)     # [note_ids]
    preferred_families = Column(JSON)

    # Confidence metrics
    evaluation_count = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.0)

    computed_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<ReviewerPreference(reviewer_id={self.reviewer_id})>"
