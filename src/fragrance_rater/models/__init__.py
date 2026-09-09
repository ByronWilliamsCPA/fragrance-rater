"""Database models for Fragrance Rater.

This module exports all SQLAlchemy models for the application together with
their declarative ``Base``; importing it registers every table on
``Base.metadata`` (used by Alembic and the test fixtures).
"""

from fragrance_rater.core.database import Base
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)
from fragrance_rater.models.reviewer import Reviewer

__all__ = [
    "Base",
    "Evaluation",
    "Fragrance",
    "FragranceAccord",
    "FragranceNote",
    "Note",
    "Reviewer",
]
