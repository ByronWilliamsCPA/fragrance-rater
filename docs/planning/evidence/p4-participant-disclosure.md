---
title: "P4 Participant Disclosure Matrix"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record participant-visible fields and concealment controls for the P4 gate."
tags:
  - planning
  - security
  - frontend
---

This matrix applies before the F1 family pilot. Verification uses synthetic records. The
`manager` value on the access endpoint is an application capability; “role” below means an
experimental membership role such as holdout or hidden repeat.

**Home.** Participants see evaluator and program names, aggregate progress, blind codes, and a safe
next action. The UI does not render membership or fragrance IDs, experimental roles, repeat links,
selection evidence, or mappings. Frontend home and participant-view API tests retain evidence.

**Enrollment list.** Participants see the reviewer and program references needed to open accessible
work. The server filters assignments to managers or assigned recorders and returns no membership
records. Calibration authorization tests retain evidence.

**Enrollment detail before reveal.** Participants see blind codes, session position, lock state,
skin-plan state, observations, and a disclosure-safe reveal blocker. The `participant_view` allowlist
omits fragrance identity, membership roles, repeat links, selection reasons, and mappings.
Calibration disclosure tests retain evidence.

**Enrollment detail after reveal.** Participants see exact fragrance identity only when eligible.
A holdout identity stays concealed until its own blotter stage is locked. Role, repeat, and selection
fields remain absent. Calibration reveal and holdout tests retain evidence.

**Unified history.** Participants see ordinary encounters and accessible controlled observations.
Controlled identity appears only when allowed by the participant view. Program mappings, membership
roles, repeat links, and selection reasons remain absent. History authorization tests retain evidence.

**Recommendation run.** Participants see ranked candidate identity, scoring, immutable impressions,
and feedback revisions. The service excludes holdouts and returns no calibration role, repeat,
mapping, or selection metadata. Recommendation measurement API tests retain evidence.

**Participant UI.** Participants see names, blind codes, progress, workflow status, and readable
outcome choices. UUIDs remain request values and are not printed. Manager setup remains
capability-gated. Frontend accessibility and workflow tests retain evidence.

FastAPI authorization remains authoritative for every request. Frontend capability checks only
control presentation and cannot grant data access.

## Participant-reachable error paths (R4)

Architecture review B-01 and B-02 found two answers that named or betrayed a holdout: a 409 body that
said "holdout", and a 404 from the catalog-ID explanation route that singled out exactly the caller's
holdouts among listable catalog fragrances. R4 fixed both. This table now has one row per error that a
manager or assigned recorder can trigger on a participant surface. A message describes the caller's
own request or protocol progress; none names a membership role, repeat link, selection reason, or
mapping. "Neutral" means the same answer covers a non-holdout cause.

| Route | Status and body | Why it discloses nothing |
| :--- | :--- | :--- |
| Any reviewer-keyed read or write by an unassigned caller | 403 "Recorder is not assigned to this evaluator" | Same for every reviewer the caller may not read (ADR-008 read policy) |
| Enrollment, presentation, or impression id that does not exist | 404 "... not found" | Existence only, of the caller's own reference |
| `POST /calibration/presentations/{id}/observations` after its identity is disclosed | 409 "Blind collection ended at reveal" | True exactly when `post_reveal_entry` is true and the identity is already shown |
| `POST /calibration/presentations/{id}/post-reveal` before its identity is disclosed | 409 "Identity has not been revealed" | True exactly when `post_reveal_entry` is false and no identity is shown |
| Blind observation on an unplanned skin stage, or on a locked stage | 409 "Skin test must be planned" / "Stage is locked; original responses are retained" | The caller's own plan and lock state, both already in the payload |
| `POST .../lock/{stage}` | 409 "Invalid stage", "Submit a detection response before locking", or "Blind collection ended at reveal" | The caller's own submission state |
| `POST /calibration/presentations/{id}/skin-plan` after finalizing | 409 "Skin plan is finalized" | Enrollment state already in the payload |
| `POST /calibration/enrollments/{id}/reveal` too early | 409 "Finalize the planned skin tests before reveal", "All blind blotter responses must be locked", or "All planned blind skin tests must be locked" | Progress only. The blotter message said "baseline and repeat" until R4, which announced hidden repeats |
| `POST /recommendation-measurement/impressions/{id}/responses` for a since-assigned holdout | 409 "feedback cannot be recorded for this recommendation" | Neutral (B-01): the server log records the reason (`feedback_refused`, `assigned_holdout`) |
| Same route with a linked outcome that does not qualify | 409 naming the linking rule ("live, on-me encounter", "revealed and match this reviewer and version", "sampling_state SAMPLED") | Describes the caller's submitted link; one message covers every non-qualifying observation |
| `GET /recommendation-measurement/impressions/{id}/explanation` for a deleted or since-assigned holdout fragrance | 404 "recommendation impression not found" | Neutral (B-02): byte-identical to a missing impression |
| `GET /recommendation-measurement/impressions/{id}/linkable-outcomes` for a since-assigned holdout | 200 `[]` | Neutral: identical to an impression with no qualifying encounter yet |
| `GET /recommendations/{reviewer_id}/{fragrance_id}/explain` | 404 (route removed in R4) | The catalog-ID oracle no longer exists; explanations need a persisted impression |

Two related controls apply to every row:

- **Caching.** Every response under `/api/v1` is `Cache-Control: private, no-store` with
  `Vary: X-Authentik-Username`, except the public catalog (B-26).
- **Client decisions.** The client takes `post_reveal_entry` from the server to choose the blind or
  post-reveal form. The follow-up form lists linkable outcomes from a narrow endpoint instead of the
  reviewer's full history, which carries ratings, notes, and revealed identities (F-15).

Evidence: `tests/unit/test_api/test_authorization_matrix.py`
(`test_holdout_answers_are_role_neutral` and the read-policy matrix);
`tests/unit/test_services/test_recommendation_measurement_service.py`
(`test_append_response_rejects_holdout_version` and `test_linkable_outcomes_match_what_feedback_accepts`);
`tests/unit/test_api/test_recommendations.py` (`test_catalog_id_explain_route_is_gone` and
`test_explain_fragrance_not_found`); `tests/unit/test_security.py` (`TestNoStoreDefault`);
`frontend/src/test/revealAndLog.test.tsx` (the `post_reveal_entry` routing tests).
