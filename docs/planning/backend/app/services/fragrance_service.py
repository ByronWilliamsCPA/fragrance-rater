"""
Service layer for fragrance operations.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.models import (
    Fragrance, Note, Reviewer, Evaluation, ReviewerPreference,
    fragrance_notes, DataSource, NotePosition, FragranceFamily, FragranceSubfamily
)
from app.schemas import (
    FragranceCreate, FragranceUpdate, FragranceSearchParams,
    EvaluationCreate, ReviewerCreate
)


class NoteService:
    """Service for note operations."""

    @staticmethod
    def get_or_create(db: Session, name: str, **kwargs) -> Note:
        """Get existing note or create new one."""
        normalized = name.lower().strip()
        note = db.query(Note).filter(Note.normalized_name == normalized).first()

        if not note:
            note = Note(
                name=name.strip(),
                normalized_name=normalized,
                **kwargs
            )
            db.add(note)
            db.flush()

        return note

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Note]:
        """Get note by name (case-insensitive)."""
        return db.query(Note).filter(
            Note.normalized_name == name.lower().strip()
        ).first()

    @staticmethod
    def search(db: Session, query: str, limit: int = 20) -> List[Note]:
        """Search notes by name."""
        return db.query(Note).filter(
            Note.normalized_name.contains(query.lower())
        ).order_by(Note.occurrence_count.desc()).limit(limit).all()

    @staticmethod
    def get_all(db: Session, limit: int = 500) -> List[Note]:
        """Get all notes ordered by usage."""
        return db.query(Note).order_by(Note.occurrence_count.desc()).limit(limit).all()


class FragranceService:
    """Service for fragrance operations."""

    @staticmethod
    def get_by_id(db: Session, fragrance_id: int) -> Optional[Fragrance]:
        """Get fragrance by ID."""
        return db.query(Fragrance).filter(Fragrance.id == fragrance_id).first()

    @staticmethod
    def get_by_name_brand(db: Session, name: str, brand: str) -> Optional[Fragrance]:
        """Get fragrance by name and brand."""
        return db.query(Fragrance).filter(
            func.lower(Fragrance.name) == name.lower().strip(),
            func.lower(Fragrance.brand) == brand.lower().strip()
        ).first()

    @staticmethod
    def create(db: Session, data: FragranceCreate) -> Fragrance:
        """Create a new fragrance."""
        # Create fragrance without notes first
        fragrance = Fragrance(
            name=data.name,
            brand=data.brand,
            concentration=data.concentration,
            gender_target=data.gender_target,
            launch_year=data.launch_year,
            country=data.country,
            primary_family=data.primary_family,
            subfamily=data.subfamily,
            longevity=data.longevity,
            sillage=data.sillage,
            rating=data.rating,
            image_url=data.image_url,
            fragrantica_url=data.fragrantica_url,
            accords=data.accords or {},
            data_source=data.data_source,
            data_source_updated_at=datetime.utcnow(),
        )
        db.add(fragrance)
        db.flush()

        # Add notes with positions
        FragranceService._add_notes(db, fragrance.id, data.top_notes, NotePosition.TOP)
        FragranceService._add_notes(db, fragrance.id, data.heart_notes, NotePosition.HEART)
        FragranceService._add_notes(db, fragrance.id, data.base_notes, NotePosition.BASE)

        return fragrance

    @staticmethod
    def _add_notes(db: Session, fragrance_id: int, note_names: List[str], position: NotePosition):
        """Add notes to a fragrance with position."""
        if not note_names:
            return

        for idx, name in enumerate(note_names):
            note = NoteService.get_or_create(db, name)
            note.occurrence_count += 1

            # Insert into association table
            db.execute(
                fragrance_notes.insert().values(
                    fragrance_id=fragrance_id,
                    note_id=note.id,
                    position=position,
                    prominence=idx
                )
            )

    @staticmethod
    def update(db: Session, fragrance_id: int, data: FragranceUpdate) -> Optional[Fragrance]:
        """Update a fragrance."""
        fragrance = FragranceService.get_by_id(db, fragrance_id)
        if not fragrance:
            return None

        # Update simple fields
        update_data = data.model_dump(exclude_unset=True, exclude={'top_notes', 'heart_notes', 'base_notes'})
        for field, value in update_data.items():
            setattr(fragrance, field, value)

        fragrance.updated_at = datetime.utcnow()

        # Update notes if provided
        if data.top_notes is not None or data.heart_notes is not None or data.base_notes is not None:
            # Clear existing notes
            db.execute(fragrance_notes.delete().where(fragrance_notes.c.fragrance_id == fragrance_id))

            # Re-add notes
            if data.top_notes:
                FragranceService._add_notes(db, fragrance_id, data.top_notes, NotePosition.TOP)
            if data.heart_notes:
                FragranceService._add_notes(db, fragrance_id, data.heart_notes, NotePosition.HEART)
            if data.base_notes:
                FragranceService._add_notes(db, fragrance_id, data.base_notes, NotePosition.BASE)

        return fragrance

    @staticmethod
    def search(db: Session, params: FragranceSearchParams) -> List[Fragrance]:
        """Search fragrances with filters."""
        query = db.query(Fragrance)

        if params.query:
            search_term = f"%{params.query.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Fragrance.name).like(search_term),
                    func.lower(Fragrance.brand).like(search_term)
                )
            )

        if params.brand:
            query = query.filter(func.lower(Fragrance.brand) == params.brand.lower())

        if params.family:
            query = query.filter(Fragrance.primary_family == params.family)

        if params.subfamily:
            query = query.filter(Fragrance.subfamily == params.subfamily)

        if params.gender:
            query = query.filter(Fragrance.gender_target == params.gender)

        if params.min_rating:
            query = query.filter(Fragrance.rating >= params.min_rating)

        if params.notes:
            # Filter by required notes (fragrance must have all specified notes)
            for note_name in params.notes:
                note = NoteService.get_by_name(db, note_name)
                if note:
                    query = query.filter(Fragrance.notes.contains(note))

        return query.order_by(Fragrance.rating.desc().nullslast()).offset(params.offset).limit(params.limit).all()

    @staticmethod
    def get_notes_by_position(db: Session, fragrance_id: int) -> Dict[str, List[Note]]:
        """Get notes organized by pyramid position."""
        result = {"top": [], "heart": [], "base": [], "general": []}

        rows = db.execute(
            fragrance_notes.select().where(fragrance_notes.c.fragrance_id == fragrance_id).order_by(fragrance_notes.c.prominence)
        ).fetchall()

        note_ids = [row.note_id for row in rows]
        if not note_ids:
            return result

        notes = {n.id: n for n in db.query(Note).filter(Note.id.in_(note_ids)).all()}

        for row in rows:
            note = notes.get(row.note_id)
            if note:
                position_key = row.position.value if row.position else "general"
                result[position_key].append(note)

        return result


class ReviewerService:
    """Service for reviewer operations."""

    @staticmethod
    def get_by_id(db: Session, reviewer_id: int) -> Optional[Reviewer]:
        return db.query(Reviewer).filter(Reviewer.id == reviewer_id).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Reviewer]:
        return db.query(Reviewer).filter(func.lower(Reviewer.name) == name.lower()).first()

    @staticmethod
    def get_all(db: Session) -> List[Reviewer]:
        return db.query(Reviewer).order_by(Reviewer.name).all()

    @staticmethod
    def create(db: Session, data: ReviewerCreate) -> Reviewer:
        reviewer = Reviewer(**data.model_dump())
        db.add(reviewer)
        db.flush()
        return reviewer

    @staticmethod
    def get_or_create(db: Session, name: str) -> Reviewer:
        reviewer = ReviewerService.get_by_name(db, name)
        if not reviewer:
            reviewer = Reviewer(name=name)
            db.add(reviewer)
            db.flush()
        return reviewer


class EvaluationService:
    """Service for evaluation operations."""

    @staticmethod
    def get_by_id(db: Session, evaluation_id: int) -> Optional[Evaluation]:
        return db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()

    @staticmethod
    def create(db: Session, data: EvaluationCreate) -> Evaluation:
        evaluation = Evaluation(
            fragrance_id=data.fragrance_id,
            reviewer_id=data.reviewer_id,
            rating=data.rating,
            notes=data.notes,
            longevity_rating=data.longevity_rating,
            sillage_rating=data.sillage_rating,
            season_preference=data.season_preference,
            occasion_tags=data.occasion_tags,
            evaluated_at=data.evaluated_at or datetime.utcnow(),
        )
        db.add(evaluation)
        db.flush()
        return evaluation

    @staticmethod
    def get_by_reviewer(db: Session, reviewer_id: int, limit: int = 100) -> List[Evaluation]:
        return db.query(Evaluation).filter(
            Evaluation.reviewer_id == reviewer_id
        ).order_by(Evaluation.evaluated_at.desc()).limit(limit).all()

    @staticmethod
    def get_by_fragrance(db: Session, fragrance_id: int) -> List[Evaluation]:
        return db.query(Evaluation).filter(
            Evaluation.fragrance_id == fragrance_id
        ).order_by(Evaluation.evaluated_at.desc()).all()

    @staticmethod
    def get_recent(db: Session, limit: int = 20) -> List[Evaluation]:
        return db.query(Evaluation).order_by(
            Evaluation.evaluated_at.desc()
        ).limit(limit).all()
