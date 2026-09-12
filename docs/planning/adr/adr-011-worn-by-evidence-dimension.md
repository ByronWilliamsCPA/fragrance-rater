# ADR-011: Worn-By Evidence Dimension

> **Status**: Accepted
>
> **Date**: 2026-09-12

## Context

Every `Evaluation` records `reviewer_id` (whose palate the rating reflects) and, separately,
`recorded_by` (who was logged in when it was typed in). Both describe the rating's *authorship*.
Neither describes its *subject*: whether the rating is about how the fragrance smells on the
reviewer themselves, or about how it smells on someone else.

For couples in the family program, one partner's opinion of how a fragrance smells on the other
is itself useful evidence -- it is the input to "what does my partner like me to wear?" -- but it
is not the same kind of observation as an ordinary self-worn encounter, and ADR-007's affinity
adapter has no concept of it. Recording it as a same-shape `Evaluation` row without a subject
field would silently teach the reviewer's own affinity profile from an experience that was never
theirs to have.

## Decision

Add an optional `worn_by_reviewer_id` column to `Evaluation`:

- NULL (the default, and every pre-existing row) means the rating is "on me": `reviewer_id` rated
  the fragrance as worn by themselves. This is unchanged existing behavior.
- A non-NULL value means `reviewer_id` is recording an "on others" opinion -- their own liking of
  the fragrance specifically as worn by the reviewer named in `worn_by_reviewer_id` (e.g. a
  partner's reaction). It must reference a different, existing `Reviewer`; equal to `reviewer_id`
  is rejected as a redundant, ambiguous spelling of the NULL/self case.

The subject is always an existing `Reviewer` profile (the family's existing reviewer records),
not a free-text label: partners in this program are already modeled as reviewers.

`worn_by_reviewer_id` rows are captured and returned through the ordinary CRUD surface
(`/evaluations`) like any other encounter, but are excluded from every current scoring pathway:

- `RecommendationService`'s affinity/profile query (`_get_user_profile`'s note/accord/family
  aggregation) reads only rows where `worn_by_reviewer_id IS NULL`.
- `RecommendationService`'s "exclude already-rated candidates" query reads only rows where
  `worn_by_reviewer_id IS NULL`: smelling a fragrance on a partner does not mean the reviewer has
  rated it for themselves, and must not suppress it as a future candidate.
- `PreferenceHistoryService`'s ordinary training-manifest query (feeding ADR-007's affinity-v1
  adapter) reads only rows where `worn_by_reviewer_id IS NULL`.

General reviewer-activity bookkeeping (evaluation counts in `ReviewerService`) is unaffected: the
reviewer did author the row, so it still counts as their recorded activity.

This ADR intentionally scopes only the "specific partner, on a specific wearer" case from the
two dimensions considered (see Related). A reviewer's general opinion of a scent on people in
general, independent of any specific wearer, is out of scope here and would need its own decision
if pursued.

## Consequences

- The family product can capture partner-preference evidence now without reopening ADR-004/007's
  scoring semantics.
- Folding worn-by evidence into scoring (e.g. a joint or partner-weighted affinity view) requires
  its own versioned adapter and prospective comparison, per ADR-007's consequences, and a
  separate ADR when it is pursued.
- A hard delete of a reviewer who is only ever a rating's subject is blocked (`ondelete=RESTRICT`
  on `worn_by_reviewer_id`) rather than silently deleting someone else's rating; soft-delete
  (`Reviewer.deleted_at`) remains the normal way to retire a reviewer profile and is unaffected.
- History and profile UI/API surfaces that render `Evaluation` rows must label a non-NULL
  `worn_by_reviewer_id` distinctly from an ordinary self-worn encounter, so a partner's reaction is
  never mistaken for the reviewer's own experience of the fragrance.

## Validation

- Schema tests cover the redundant self-reference rejection at creation and the PATCH-time
  equivalent (which cannot be checked at the Pydantic layer alone, since `EvaluationUpdate` has no
  `reviewer_id` field).
- API tests cover creating, listing, and updating an "on others" evaluation, and a 404 for a
  nonexistent `worn_by_reviewer_id`.
- Recommendation-service and preference-history tests cover that an "on others" row is excluded
  from a reviewer's own affinity profile, candidate exclusion, and training manifest, while still
  appearing in that reviewer's plain evaluation history and count.

## Related

- [ADR-004](adr-004-recommendation-algorithm.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
