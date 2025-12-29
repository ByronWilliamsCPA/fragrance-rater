"""
LLM-powered fragrance recommendation service.

Combines:
- Preference profile analysis from evaluations
- Note/accord affinity scoring
- LLM for natural language insights and recommendations
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import defaultdict
import json

from app.models import (
    Fragrance, Note, Reviewer, Evaluation, ReviewerPreference,
    fragrance_notes, NotePosition
)
from app.services.fragrance_service import FragranceService, NoteService
from app.services.openrouter_client import openrouter


class PreferenceAnalyzer:
    """
    Analyzes a reviewer's evaluations to build a preference profile.
    """

    def __init__(self, db: Session):
        self.db = db

    def compute_profile(self, reviewer_id: int) -> Dict[str, Any]:
        """
        Compute preference profile from all evaluations.

        Returns dict with:
        - family_scores: {family: avg_rating}
        - note_affinities: {note_name: affinity_score}
        - accord_affinities: {accord: affinity_score}
        - preferred_notes: [top liked notes]
        - disliked_notes: [notes that correlate with low ratings]
        - summary_stats: {count, avg_rating, etc.}
        """
        evaluations = self.db.query(Evaluation).filter(
            Evaluation.reviewer_id == reviewer_id
        ).all()

        if not evaluations:
            return {
                "family_scores": {},
                "note_affinities": {},
                "accord_affinities": {},
                "preferred_notes": [],
                "disliked_notes": [],
                "summary_stats": {"count": 0}
            }

        # Collect data
        note_ratings = defaultdict(list)  # note_name -> [ratings]
        accord_ratings = defaultdict(list)
        family_ratings = defaultdict(list)

        for eval in evaluations:
            fragrance = eval.fragrance
            if not fragrance:
                continue

            # Normalize rating to -1 to 1 scale (3 = neutral)
            normalized = (eval.rating - 3) / 2

            # Family
            if fragrance.primary_family:
                family_ratings[fragrance.primary_family.value].append(eval.rating)

            # Notes
            notes_by_pos = FragranceService.get_notes_by_position(self.db, fragrance.id)
            all_notes = (
                notes_by_pos.get('top', []) +
                notes_by_pos.get('heart', []) +
                notes_by_pos.get('base', []) +
                notes_by_pos.get('general', [])
            )

            for note in all_notes:
                note_ratings[note.name.lower()].append(normalized)

            # Accords
            if fragrance.accords:
                for accord, intensity in fragrance.accords.items():
                    # Weight by accord intensity
                    weighted_rating = normalized * float(intensity)
                    accord_ratings[accord.lower()].append(weighted_rating)

        # Compute averages
        def avg(lst):
            return sum(lst) / len(lst) if lst else 0

        note_affinities = {
            note: avg(ratings)
            for note, ratings in note_ratings.items()
            if len(ratings) >= 1  # Need at least 1 data point
        }

        accord_affinities = {
            accord: avg(ratings)
            for accord, ratings in accord_ratings.items()
        }

        family_scores = {
            family: avg(ratings)
            for family, ratings in family_ratings.items()
        }

        # Sort notes by affinity
        sorted_notes = sorted(note_affinities.items(), key=lambda x: x[1], reverse=True)
        preferred_notes = [n for n, score in sorted_notes if score > 0.2][:10]
        disliked_notes = [n for n, score in sorted_notes if score < -0.2][:10]

        return {
            "family_scores": family_scores,
            "note_affinities": note_affinities,
            "accord_affinities": accord_affinities,
            "preferred_notes": preferred_notes,
            "disliked_notes": disliked_notes,
            "summary_stats": {
                "count": len(evaluations),
                "avg_rating": avg([e.rating for e in evaluations]),
                "unique_fragrances": len(set(e.fragrance_id for e in evaluations)),
            }
        }

    def score_fragrance(
        self,
        profile: Dict[str, Any],
        fragrance: Fragrance
    ) -> Tuple[float, List[str], List[str]]:
        """
        Score how well a fragrance matches a preference profile.

        Returns:
            (score 0-1, reasons list, warnings list)
        """
        score = 0.5  # Start neutral
        reasons = []
        warnings = []

        weights = {
            'family': 0.15,
            'notes': 0.50,
            'accords': 0.35,
        }

        # Family match
        if fragrance.primary_family:
            family_key = fragrance.primary_family.value
            if family_key in profile.get('family_scores', {}):
                family_score = profile['family_scores'][family_key]
                # Normalize from 1-5 to 0-1
                normalized = (family_score - 1) / 4
                score += weights['family'] * (normalized - 0.5)

                if family_score >= 4:
                    reasons.append(f"You tend to like {family_key} fragrances")
                elif family_score <= 2:
                    warnings.append(f"You haven't loved {family_key} fragrances")

        # Note matching
        notes_by_pos = FragranceService.get_notes_by_position(self.db, fragrance.id)
        all_notes = (
            notes_by_pos.get('top', []) +
            notes_by_pos.get('heart', []) +
            notes_by_pos.get('base', [])
        )

        note_affinities = profile.get('note_affinities', {})
        note_scores = []

        for note in all_notes:
            note_lower = note.name.lower()
            if note_lower in note_affinities:
                affinity = note_affinities[note_lower]
                note_scores.append(affinity)

                if affinity > 0.5:
                    reasons.append(f"Contains {note.name} which you love")
                elif affinity < -0.5:
                    warnings.append(f"Contains {note.name} which you dislike")

        if note_scores:
            avg_note_score = sum(note_scores) / len(note_scores)
            # Check for strong negatives (veto effect)
            if min(note_scores) < -0.6:
                score *= 0.5  # Heavy penalty
                warnings.append("Contains notes you've rated poorly")
            else:
                # Normalize from -1,1 to 0,1
                normalized = (avg_note_score + 1) / 2
                score += weights['notes'] * (normalized - 0.5)

        # Accord matching
        if fragrance.accords:
            accord_affinities = profile.get('accord_affinities', {})
            accord_scores = []

            for accord, intensity in fragrance.accords.items():
                accord_lower = accord.lower()
                if accord_lower in accord_affinities:
                    affinity = accord_affinities[accord_lower]
                    accord_scores.append(affinity * float(intensity))

            if accord_scores:
                avg_accord = sum(accord_scores) / len(accord_scores)
                normalized = (avg_accord + 1) / 2
                score += weights['accords'] * (normalized - 0.5)

        # Clamp to 0-1
        score = max(0.0, min(1.0, score))

        return score, reasons[:3], warnings[:3]


class RecommendationService:
    """
    Generates fragrance recommendations using preference analysis + LLM.
    """

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = PreferenceAnalyzer(db)

    def get_recommendations(
        self,
        reviewer_id: int,
        limit: int = 10,
        exclude_evaluated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get top fragrance recommendations for a reviewer.

        Returns list of:
        {
            "fragrance": FragranceResponse,
            "match_score": float,
            "reasons": [str],
            "warnings": [str]
        }
        """
        profile = self.analyzer.compute_profile(reviewer_id)

        if profile['summary_stats']['count'] < 3:
            return []  # Not enough data

        # Get fragrances to score
        query = self.db.query(Fragrance)

        if exclude_evaluated:
            evaluated_ids = [
                e.fragrance_id for e in
                self.db.query(Evaluation.fragrance_id)
                .filter(Evaluation.reviewer_id == reviewer_id)
                .all()
            ]
            if evaluated_ids:
                query = query.filter(~Fragrance.id.in_(evaluated_ids))

        # Limit to fragrances with decent data
        fragrances = query.filter(
            Fragrance.accords.isnot(None)
        ).limit(500).all()

        # Score each fragrance
        scored = []
        for fragrance in fragrances:
            score, reasons, warnings = self.analyzer.score_fragrance(profile, fragrance)
            scored.append({
                "fragrance": fragrance,
                "match_score": score,
                "reasons": reasons,
                "warnings": warnings,
            })

        # Sort by score and return top
        scored.sort(key=lambda x: x['match_score'], reverse=True)
        return scored[:limit]

    def generate_profile_summary(self, reviewer_id: int) -> str:
        """
        Use LLM to generate a natural language summary of preferences.
        """
        reviewer = self.db.query(Reviewer).get(reviewer_id)
        if not reviewer:
            return "Reviewer not found."

        profile = self.analyzer.compute_profile(reviewer_id)

        if profile['summary_stats']['count'] < 2:
            return f"{reviewer.name} hasn't evaluated enough fragrances yet to build a profile."

        # Get recent evaluations for context
        recent_evals = self.db.query(Evaluation).filter(
            Evaluation.reviewer_id == reviewer_id
        ).order_by(Evaluation.evaluated_at.desc()).limit(10).all()

        eval_summaries = []
        for e in recent_evals:
            if e.fragrance:
                eval_summaries.append({
                    "fragrance": f"{e.fragrance.name} by {e.fragrance.brand}",
                    "rating": e.rating,
                    "notes": e.notes or "",
                })

        # Build prompt
        prompt = f"""Analyze this person's fragrance preferences and write a concise profile summary.

Person: {reviewer.name}

Evaluation Statistics:
- Total fragrances evaluated: {profile['summary_stats']['count']}
- Average rating: {profile['summary_stats']['avg_rating']:.1f}/5

Family Preferences (1-5 scale):
{json.dumps(profile['family_scores'], indent=2)}

Notes They Tend to Like:
{', '.join(profile['preferred_notes'][:8]) or 'Not enough data'}

Notes They Tend to Dislike:
{', '.join(profile['disliked_notes'][:5]) or 'None identified'}

Recent Evaluations:
{json.dumps(eval_summaries[:5], indent=2)}

Write a 2-3 sentence natural profile summary describing what kinds of fragrances this person enjoys,
any specific notes or accords they gravitate toward or avoid, and any patterns you notice.
Be specific and practical - this will help when shopping for fragrances for them.
"""

        if not openrouter.is_configured:
            # Fallback to basic template
            return self._generate_basic_summary(reviewer.name, profile)

        try:
            response = openrouter.chat(
                messages=[{"role": "user", "content": prompt}],
                model=openrouter.FAST_MODEL,  # Use faster model for summaries
                max_tokens=300,
                temperature=0.7,
            )
            return response.strip()
        except Exception as e:
            return self._generate_basic_summary(reviewer.name, profile)

    def _generate_basic_summary(self, name: str, profile: Dict) -> str:
        """Fallback summary without LLM."""
        parts = [f"{name} has evaluated {profile['summary_stats']['count']} fragrances"]

        if profile['preferred_notes']:
            parts.append(f"They tend to enjoy notes like {', '.join(profile['preferred_notes'][:3])}")

        if profile['disliked_notes']:
            parts.append(f"They seem to avoid {', '.join(profile['disliked_notes'][:2])}")

        # Find favorite family
        if profile['family_scores']:
            fav_family = max(profile['family_scores'].items(), key=lambda x: x[1])
            if fav_family[1] >= 3.5:
                parts.append(f"They gravitate toward {fav_family[0]} fragrances")

        return ". ".join(parts) + "."

    def explain_recommendation(
        self,
        reviewer_id: int,
        fragrance_id: int,
    ) -> str:
        """
        Use LLM to explain why a fragrance might work for someone.
        """
        reviewer = self.db.query(Reviewer).get(reviewer_id)
        fragrance = self.db.query(Fragrance).get(fragrance_id)

        if not reviewer or not fragrance:
            return "Could not generate explanation."

        profile = self.analyzer.compute_profile(reviewer_id)
        score, reasons, warnings = self.analyzer.score_fragrance(profile, fragrance)

        # Get fragrance notes
        notes_by_pos = FragranceService.get_notes_by_position(self.db, fragrance_id)

        prompt = f"""Explain why this fragrance might (or might not) work for this person.

Person: {reviewer.name}
Their preferences:
- Likes: {', '.join(profile['preferred_notes'][:5]) or 'Unknown'}
- Dislikes: {', '.join(profile['disliked_notes'][:3]) or 'None identified'}
- Favorite families: {', '.join(k for k, v in profile.get('family_scores', {}).items() if v >= 3.5) or 'Unknown'}

Fragrance: {fragrance.name} by {fragrance.brand}
Family: {fragrance.primary_family.value if fragrance.primary_family else 'Unknown'}
Top notes: {', '.join(n.name for n in notes_by_pos.get('top', []))}
Heart notes: {', '.join(n.name for n in notes_by_pos.get('heart', []))}
Base notes: {', '.join(n.name for n in notes_by_pos.get('base', []))}
Main accords: {', '.join(fragrance.accords.keys()) if fragrance.accords else 'Unknown'}

Match score: {score:.0%}
Key reasons: {', '.join(reasons) if reasons else 'General match'}
Concerns: {', '.join(warnings) if warnings else 'None'}

Write a brief (2-3 sentences) explanation of why this fragrance would or wouldn't suit them,
referencing specific notes and their known preferences. Be practical and conversational.
"""

        if not openrouter.is_configured:
            # Fallback
            explanation = f"Match score: {score:.0%}."
            if reasons:
                explanation += f" {reasons[0]}."
            if warnings:
                explanation += f" However, {warnings[0].lower()}."
            return explanation

        try:
            response = openrouter.chat(
                messages=[{"role": "user", "content": prompt}],
                model=openrouter.FAST_MODEL,
                max_tokens=200,
                temperature=0.7,
            )
            return response.strip()
        except Exception:
            return f"Match score: {score:.0%}. " + (reasons[0] if reasons else "")

    def suggest_new_fragrances(
        self,
        reviewer_id: int,
        context: str = "",
    ) -> List[Dict[str, str]]:
        """
        Use LLM to suggest fragrances that might not be in our database.

        Args:
            reviewer_id: Who to recommend for
            context: Optional context like "for summer" or "date night"

        Returns:
            List of {name, brand, reason} suggestions
        """
        if not openrouter.is_configured:
            return []

        reviewer = self.db.query(Reviewer).get(reviewer_id)
        if not reviewer:
            return []

        profile = self.analyzer.compute_profile(reviewer_id)

        if profile['summary_stats']['count'] < 3:
            return []

        prompt = f"""Based on this person's fragrance preferences, suggest 5 specific fragrances they might enjoy.

Person: {reviewer.name}

Their Profile:
- Favorite fragrance families: {', '.join(k for k, v in profile.get('family_scores', {}).items() if v >= 3.5) or 'No clear preference'}
- Notes they love: {', '.join(profile['preferred_notes'][:6]) or 'Unknown'}
- Notes they dislike: {', '.join(profile['disliked_notes'][:4]) or 'None identified'}
- Average rating given: {profile['summary_stats']['avg_rating']:.1f}/5

{f'Context: {context}' if context else ''}

Suggest 5 specific, real fragrances (name + brand) that would match their preferences.
Include a mix of popular and lesser-known options at different price points.

Respond in JSON format:
[
  {{"name": "Fragrance Name", "brand": "Brand Name", "reason": "Brief reason why"}},
  ...
]
"""

        try:
            result = openrouter.chat_json(
                messages=[{"role": "user", "content": prompt}],
                model=openrouter.DEFAULT_MODEL,
                max_tokens=600,
            )
            return result if isinstance(result, list) else []
        except Exception:
            return []
