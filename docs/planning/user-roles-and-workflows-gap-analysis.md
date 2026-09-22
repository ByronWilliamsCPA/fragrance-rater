# User Roles and Workflows Gap Analysis

> **Status**: Draft for product-owner review
> **Version**: 1.0
> **Updated**: 2026-09-21
> **Purpose**: Record expected user-role workflows, current implementation evidence, gaps, and
> candidate remediation work. This document is planning input, not an approved milestone or a
> replacement for `PROJECT-PLAN.md`.

Visual presentation and responsive interaction are evaluated separately in the
[Frontend Visual and Usability Gap Analysis](frontend-visual-and-usability-gap-analysis.md).

## 1. Executive summary

Fragrance Rater has a strong controlled-calibration prototype and a functional recommendation
feedback loop. Its current product model is nevertheless closer to a shared household workstation
than a role-complete application: an Authentik identity is not linked to a `Reviewer`, the
"Participant" label is inferred from the absence of manager or recorder capabilities, and
ordinary encounters do not use the reviewer-scoped authorization applied to controlled
calibration.

The principal remediation themes are:

1. Make users, reviewer profiles, roles, and delegated access first-class domain concepts.
2. Apply one reviewer-scoped authorization policy to every personal-data workflow.
3. Add the missing collection/ownership workflow.
4. Surface the computed preference library to the evaluator.
5. Turn the documented 33-fragrance baseline into a validated, reusable program template.
6. Add a consumer-facing catalog and fragrance-learning experience.
7. Complete administrator tooling for accounts, catalog data, imports, and audit review.

## 2. Product goal and personas

The product goal evaluated here is to help people learn from perfumes they try, maintain a record
of perfumes they own, complete a blind 33-fragrance evaluation that establishes a core preference
library, and use that library to identify promising future perfumes.

### 2.1 Administrator

An administrator should be able to manage users and permissions, maintain the fragrance catalog,
configure and operate the controlled-calibration program, monitor progress, correct operational
problems, review audit history, and export evidence.

### 2.2 Evaluator/end user

An evaluator should enter the application in their own context, record encounters and ownership,
complete assigned blind work, understand what the system has learned, receive recommendations,
and provide outcome feedback without handling internal IDs or selecting another person's profile.

### 2.3 Recorder acting for another evaluator

A recorder should be granted access to specific evaluators, clearly see whose record they are
editing, switch subjects deliberately, and leave an immutable authorship trail. A recorder grant
should not implicitly confer catalog or administrative powers.

## 3. Status vocabulary

| Status | Meaning |
| :--- | :--- |
| Implemented | A usable frontend workflow and supporting backend behavior exist. |
| Partial | Important pieces exist, but the user journey or policy is incomplete. |
| API only | Backend capability exists without a supported user-facing workflow. |
| Missing | No material implementation was found. |
| Intentional constraint | The current behavior follows documented household-product scope but would not satisfy a broader role model. |

## 4. Findings register

### UR-01: Authenticated identities are not linked to reviewer profiles

- **Severity**: High
- **Status**: Missing
- **Affected roles**: Evaluator, recorder, administrator
- **Evidence**:
  - `Reviewer` stores an ID, name, timestamps, and evaluation relationships but no Authentik UID,
    username, account link, or ownership relationship (`models/reviewer.py`).
  - `/calibration/access` returns only the forwarded username and whether that username appears in
    the configured manager list (`api/calibration.py`).
  - Frontend capabilities are derived from `access.manager` and whether any enrollment is visible;
    the role label is then inferred as Manager, Recorder, or Participant (`frontend/src/api/types.ts`).
- **Impact**: The application cannot reliably implement "my profile," default to the signed-in
  evaluator, distinguish an evaluator from an unassigned authenticated person, or enforce personal
  data ownership consistently.
- **Recommendation**: Add a first-class account/profile association using the stable Authentik UID,
  with username retained as display/audit metadata rather than the durable key.
- **Draft acceptance criteria**:
  1. Each active evaluator account resolves to exactly one active reviewer profile unless an
     administrator explicitly creates a service/recorder-only account.
  2. Renaming an Authentik username does not orphan reviewer ownership.
  3. The API exposes a `me` representation containing account, reviewer, roles, and grants without
     disclosing other users.
  4. Existing reviewer history can be linked through an explicit, audited migration procedure.

### UR-02: Roles are inferred capabilities rather than durable authorization assignments

- **Severity**: High
- **Status**: Partial
- **Affected roles**: All
- **Evidence**:
  - Manager authority is a username membership check against
    `settings.calibration_admin_usernames`.
  - Recorder authority exists as `Enrollment.recorder_usernames` and is limited to calibration and
    measured-recommendation paths.
  - `RoleLabel = 'Manager' | 'Recorder' | 'Participant'` is presentation logic rather than a domain
    role model.
- **Impact**: Role administration cannot be audited or managed in the app; a username change can
  break grants; "Participant" does not prove that the identity owns the selected reviewer; and
  authorization policy varies by router.
- **Recommendation**: Define durable account roles and evaluator grants. Keep capabilities as the
  computed output of authorization policy, not the source of truth.
- **Draft acceptance criteria**:
  1. Supported roles and their permissions are documented in one matrix.
  2. Role and grant changes are administrator-only and audited.
  3. UI visibility and API enforcement derive from the same server-returned capabilities.
  4. Removing a grant immediately removes both read and mutation access.

### UR-03: Ordinary encounter access is broader than controlled-calibration access

- **Severity**: High
- **Status**: Partial
- **Affected roles**: Evaluator, recorder
- **Evidence**:
  - The ordinary encounter form receives every reviewer and permits the operator to select any of
    them (`frontend/src/pages/RatingsPage.tsx`).
  - Create/update/delete routes record the forwarded identity but do not authorize that identity
    for the target reviewer (`api/evaluations.py`).
  - List and single-evaluation reads do not take the identity dependency at all.
  - By contrast, calibration enrollments and recommendation-measurement runs authorize managers or
    usernames explicitly granted to the reviewer (`api/calibration.py`,
    `api/recommendation_measurement.py`).
- **Impact**: Any identity admitted through the deployment boundary can act on or read any
  reviewer's ordinary history. This conflicts with a robust evaluator/recorder role distinction,
  even if it is acceptable for the current trusted-household deployment.
- **Recommendation**: Centralize reviewer authorization and apply it to ordinary evaluations,
  unified history, preference profiles, predictions, recommendation endpoints, and exports.
- **Draft acceptance criteria**:
  1. Evaluators can access their own ordinary history.
  2. Recorders can access only reviewers covered by an active grant.
  3. Administrators can access all reviewers for supported administrative purposes.
  4. Cross-reviewer reads and writes return 403 without revealing whether a hidden record exists.
  5. Authorization tests cover list, detail, create, correction, deletion, and soft-deleted records.

### UR-04: Acting on behalf of another evaluator lacks a complete context workflow

- **Severity**: Medium
- **Status**: Partial
- **Affected roles**: Recorder
- **Existing strengths**:
  - `recorded_by` is stored separately from `reviewer_id`.
  - Calibration enrollment grants explicitly list authorized recorder usernames.
  - Calibration and recommendation screens identify the selected evaluator.
- **Gaps**:
  - Ordinary entry has no equivalent delegated grant.
  - There is no persistent "Recording for ..." context indicator.
  - Selecting the wrong evaluator requires no confirmation and is easy on a shared device.
  - The history UI does not display who recorded each encounter.
- **Recommendation**: Introduce an explicit acting context backed by server-authorized grants.
- **Draft acceptance criteria**:
  1. A recorder chooses only among granted evaluator profiles.
  2. The active evaluator remains visible throughout capture and correction.
  3. Switching evaluators clears unsaved form state or requests confirmation.
  4. Saved history distinguishes evaluator, recorder, and optional worn-by subject.

### UW-01: Welcome and workspace provide orientation but not complete onboarding

- **Severity**: Medium
- **Status**: Partial
- **Affected roles**: Evaluator, recorder
- **Existing strengths**: Welcome copy, methodology, calibration protocol, role label, workspace
  actions, assignment progress, and next-action guidance exist.
- **Gaps**: No account/profile association, consent or privacy explanation, first-encounter tour,
  calibration-readiness check, or recovery path when a user's account has no expected reviewer or
  assignment.
- **Recommendation**: Add role-aware onboarding with administrator-resolvable account states.
- **Draft acceptance criteria**:
  1. A new evaluator can reach their first useful task without choosing an internal reviewer ID.
  2. Missing profile, missing grant, and missing assignment states explain who can resolve them.
  3. Onboarding completion is resumable and does not block ordinary encounter capture unnecessarily.

### UW-02: Ordinary encounter journaling is functional

- **Severity**: None; preserve behavior
- **Status**: Implemented
- **Affected roles**: Evaluator, recorder
- **Evidence**: Catalog search, exact-version selection, 1-5 rating, optional encounter time,
  observations, on-me/on-others context, retained repeated encounters, history, and corrections are
  implemented in `frontend/src/pages/RatingsPage.tsx` and `api/evaluations.py`.
- **Recommendations**:
  - Preserve append/history semantics while adding authorization.
  - Default the evaluator from the authenticated context.
  - Consider adding structured longevity, projection, venue/context, and quick tags only after the
    sub-30-second entry target is usability-tested.
- **Draft acceptance criteria**:
  1. A typical encounter can still be saved in under 30 seconds.
  2. Repeated encounters remain distinct and chronologically visible.
  3. Corrections retain an auditable revision trail or an explicit correction event.

### UW-03: Personal collection and ownership tracking are absent

- **Severity**: High
- **Status**: Missing
- **Affected roles**: Evaluator, recorder
- **Evidence**:
  - No ownership, collection, wardrobe, shelf, or wishlist entity exists in the application model.
  - Recommendation responses track only recommendation-scoped sampling state and would-buy/wear.
  - The existing data-model gap analysis identifies categorical ownership/familiarity and general
    behavioral events as incomplete.
- **Recommendation**: Add a collection item or ownership-event model distinct from reviews and
  recommendation impressions.
- **Candidate data**:
  - reviewer and exact fragrance version;
  - state: sample, decant, travel spray, bottle, formerly owned, wishlist;
  - quantity/size and optional remaining amount;
  - acquired, opened, finished, gifted, or disposed dates;
  - source, batch code, purchase format, and private notes;
  - append-only state history for acquisition and disposition events.
- **Draft acceptance criteria**:
  1. Evaluators can add an exact fragrance version to their collection without reviewing it.
  2. Ownership can change over time without erasing history.
  3. "Already owned" and "formerly owned" are available to recommendation filtering and
     explanations but are not treated as liking labels.
  4. Recorder access follows the same reviewer grant policy as encounters.

### UW-04: The product lacks a consumer-facing fragrance-learning journey

- **Severity**: Medium
- **Status**: Partial
- **Affected roles**: Evaluator
- **Existing strengths**: The API can search by name/brand and filter by family/gender, and a detail
  response includes version metadata, note pyramid, and accords.
- **Gaps**:
  - No catalog route or fragrance detail page exists in the frontend.
  - Encounter and manager forms reduce search results to selection options.
  - No comparison, related-fragrance view, glossary, evidence-layer labeling, or direct path from a
    recommendation to catalog details exists.
  - Perfumer attribution is available in revealed calibration output but intentionally omitted from
    general fragrance API responses.
- **Recommendation**: Add browse, detail, and compare workflows that clearly separate published
  catalog facts, evaluator perceptions, and model interpretation.
- **Draft acceptance criteria**:
  1. A user can browse/search without starting an encounter form.
  2. A detail page identifies the exact concentration/version and provenance.
  3. Published notes are not presented as ingredients or as what the evaluator necessarily smelled.
  4. Recommendations link to the same canonical version detail.

### UC-01: Controlled blind calibration is the strongest implemented workflow

- **Severity**: None; preserve behavior
- **Status**: Implemented
- **Affected roles**: Evaluator, recorder, administrator
- **Existing strengths**:
  - frozen programs and exact-version memberships;
  - per-evaluator randomized sessions and blind codes;
  - concealed identities, hidden repeats, and holdouts;
  - structured blotter and optional skin observations;
  - multiple append-only timepoints;
  - stage locks, skin-plan finalization, reveal blockers, delayed reveal, and post-reveal entries;
  - workspace progress, session grouping, assignment deep links, and manager monitoring;
  - mapping and printable label support.
- **Evidence**: `frontend/src/pages/CalibrationPage.tsx`,
  `frontend/src/pages/WorkspacePage.tsx`, `frontend/src/pages/ProgramSetupPage.tsx`, and
  `api/calibration.py`.
- **Recommendation**: Treat these disclosure, append-only, and locking behaviors as invariants in
  future role remediation.

### UC-02: The documented 33-fragrance baseline is not a validated product template

- **Severity**: High
- **Status**: Partial
- **Affected roles**: Administrator, evaluator
- **Evidence**:
  - Planning material defines 33 unique baseline fragrances, six hidden repeats, ten holdouts, and
    three samples per session.
  - Program creation explicitly avoids a hard-coded baseline size.
  - Activation requires only a nonempty membership list.
  - The manager UI adds versions one at a time and accepts session sizes from 1 through 20.
- **Impact**: An administrator can activate and enroll a program that does not establish the
  promised core preference library. Manual entry of the canonical program is also error-prone.
- **Recommendation**: Keep the engine generic, but add a versioned canonical-baseline template or
  manifest importer with explicit validation.
- **Draft acceptance criteria**:
  1. A canonical template validates 33 unique baseline identities, six valid repeat links, ten
     disjoint holdouts, and the approved session plan.
  2. Activation reports every structural error in one actionable response.
  3. The UI previews counts and roles before freezing the program.
  4. Generic/noncanonical research programs remain possible but are labeled distinctly and cannot
     claim completion of the core baseline.

### UC-03: Progress and resumption are implemented, but scheduling support is absent

- **Severity**: Medium
- **Status**: Partial
- **Affected roles**: Evaluator, recorder, administrator
- **Existing strengths**: Assignment deep links, locked/open sample state, completed counts, reveal
  blockers, and next-action guidance support resumption.
- **Gaps**: No reminders, calendar/session schedule, daily-load guidance, overdue indicators, or
  notification preferences were found.
- **Recommendation**: First add an in-app session plan and due/ready state; add external
  notifications only if real pilot use demonstrates a need.

### UP-01: Preference evidence is computed but not presented as a core library

- **Severity**: High
- **Status**: API only
- **Affected roles**: Evaluator, recorder
- **Existing strengths**:
  - Ordinary and locked controlled evidence feed a shared training manifest.
  - Holdouts and hidden repeats are excluded from training as required.
  - Controlled observations influence ordinary recommendations only after reveal.
  - A profile-summary API can return liked/disliked notes, preferred accords, families, and an
    optional narrative summary.
- **Gaps**:
  - No preference-profile route or page exists in the React application.
  - Users cannot see evidence counts, contributing encounters, uncertainty, or changes over time.
  - The phrase "core preference library" has no explicit completion or version state in the UI.
- **Recommendation**: Add an evidence-backed preference-library page rather than only an LLM
  narrative.
- **Draft acceptance criteria**:
  1. The page shows contributing evidence count and distinguishes ordinary from controlled data.
  2. Liked and disliked families, accords, and notes link back to supporting encounters.
  3. Holdouts, repeats, on-others ratings, and ineligible catalog rows are visibly excluded from
     contribution counts.
  4. Model-derived interpretations are labeled separately from reported perceptions and published
     metadata.
  5. The page works without the optional LLM service.

### UP-02: Recommendations are not gated on core-baseline completion

- **Severity**: Medium
- **Status**: Partial
- **Affected roles**: Evaluator
- **Evidence**: The recommendation service requires three eligible evaluations, not completion of
  the 33-fragrance baseline. The recommendation UI does not identify the maturity of the underlying
  preference evidence.
- **Recommendation**: Decide explicitly whether early recommendations are a feature. If retained,
  label them as preliminary and display evidence maturity; reserve "core preference library
  complete" for a validated baseline.
- **Draft acceptance criteria**:
  1. Recommendation sets expose the profile/evidence version used.
  2. Preliminary and baseline-complete recommendation states are visibly distinct.
  3. A completed baseline is not required for ordinary exploratory recommendations unless the
     product owner chooses that policy explicitly.

### UP-03: Recommendation delivery and feedback are functional

- **Severity**: None; preserve behavior
- **Status**: Implemented
- **Affected roles**: Evaluator, recorder, administrator
- **Existing strengths**:
  - persisted recommendation runs and impressions;
  - ranked affinity scores with honest non-probability disclosure;
  - deterministic fallback when optional explanation service is unavailable;
  - interest/pass responses;
  - planned, acquired, sampled, and unavailable states;
  - linked later outcomes and would-wear/would-buy feedback;
  - append-only response revisions and manager metrics.
- **Recommendation**: Preserve impression and revision semantics while integrating account
  ownership, collection state, catalog detail, and preference-library maturity.

### UA-01: Calibration administration is strong; general administration is incomplete

- **Severity**: High
- **Status**: Partial
- **Affected roles**: Administrator
- **Existing strengths**: Program definition, catalog-version membership, version evidence,
  activation, enrollment, recorder assignment, mappings, labels, progress, reveal, metrics, and
  operational-event handling exist in the manager UI.
- **Gaps**:
  - No UI for account/reviewer linking, roles, grants, suspension, or deletion.
  - No UI for general catalog create/update/archive or import.
  - Fragrance, reviewer, and import mutation APIs require an authenticated identity but not the
    calibration manager role.
  - No administrator-facing audit-event browser exists.
- **Recommendation**: Define an app-wide administrator capability and place administrative
  mutations behind it before adding corresponding screens.
- **Draft acceptance criteria**:
  1. Nonadministrators cannot create/archive reviewers, mutate catalog data, or run imports.
  2. Administrators can manage account/profile links and delegated recorder grants.
  3. Destructive or irreversible actions require confirmation and explain downstream impact.
  4. Audit records can be filtered by actor, evaluator, action, and time window.

### UX-01: Accessibility and failure handling have a credible foundation

- **Severity**: Low
- **Status**: Implemented/partial
- **Existing strengths**: Routed URLs, distinct document titles, keyboard-native controls,
  accessible progress labels, feedback banners, loading/empty/error states, and confirmation for
  reveal and lock actions exist. The frontend component suite passed 178 tests during this audit.
- **Gaps**:
  - Several frontend tests emit React `act(...)` warnings.
  - The app has no true offline capture queue; operations provide a paper/manual fallback and event
    logging instead.
  - Backend-focused pytest commands stalled without producing output during this audit and were
    stopped, so this document makes no current full-backend validation claim.
- **Recommendation**: Keep accessibility and recovery requirements in each remediation story;
  separately diagnose the backend test startup/stall before using those tests as gate evidence.

### UD-01: Evaluator data controls are incomplete

- **Severity**: Medium
- **Status**: Missing/partial
- **Affected roles**: Evaluator, administrator
- **Existing strengths**: Manager metrics can be downloaded as JSON, and soft deletion exists for
  several domain records.
- **Gaps**: No evaluator-facing export, account deletion, reviewer data archive, privacy summary,
  or correction history export exists.
- **Recommendation**: Define household-appropriate data access, export, retention, and deletion
  policies before implementing public or multi-household accounts.

## 5. Role-capability target matrix

The following is a candidate product contract to review, not an approved authorization design.

| Capability | Evaluator | Delegated recorder | Administrator |
| :--- | :---: | :---: | :---: |
| View evaluator profile | Own | Granted profiles | All |
| Record/correct ordinary encounter | Own | Granted profiles | Supported exception only |
| Manage personal collection | Own | Granted profiles | Supported exception only |
| Complete calibration observation | Own assignment | Granted assignments | Operational exception only |
| Reveal own completed enrollment | Policy decision | If granted | Yes |
| View preference library | Own | Granted profiles | All |
| Generate/respond to recommendations | Own | Granted profiles | Supported exception only |
| Create reviewer/account link | No | No | Yes |
| Assign recorder grant | No | No | Yes |
| Mutate catalog/import data | No | No | Yes |
| Create/activate calibration program | No | No | Yes |
| View blind mapping before reveal | No | No | Yes |
| View operational metrics/audit | Own summary only | Granted summary only | All |

## 6. Proposed remediation sequence

### Foundation A: Identity and authorization

Addresses UR-01 through UR-04 and is a prerequisite for most role-aware UI work.

1. Decide the account, reviewer, role, and grant data model.
2. Write an authorization matrix and threat model for the Authentik/Traefik boundary.
3. Add account-to-reviewer migration and administrator linking workflow.
4. Centralize reviewer authorization dependencies/services.
5. Protect ordinary evaluation, legacy recommendation/profile, prediction, catalog mutation, reviewer
   mutation, import, and export routes.
6. Replace client-inferred roles with server-returned capabilities.

### Foundation B: Personal workspace

Addresses UW-01, UW-02, UW-03, and UD-01.

1. Default all evaluator workflows to the signed-in reviewer.
2. Add deliberate acting-for context for recorders.
3. Add collection/ownership data and UI.
4. Add evaluator export and documented retention/deletion behavior.

### Product C: Core preference library

Addresses UC-02, UC-03, UP-01, and UP-02.

1. Import and validate a versioned canonical 33-fragrance template.
2. Define baseline progress and completion state independently of generic program completion.
3. Add the preference-library page with evidence provenance and exclusions.
4. Label recommendation maturity and freeze the evidence/profile version per run.

### Product D: Discovery and learning

Addresses UW-04 and extends UP-03.

1. Add catalog browse and exact-version detail routes.
2. Add evidence-layer explanations and vocabulary help.
3. Link encounters, collection entries, calibration reveals, and recommendations to canonical
   fragrance details.
4. Add comparison or related-fragrance exploration only after detail usability is established.

### Operations E: Complete administration

Addresses UA-01 and supports all foundations.

1. Add account, role, grant, and reviewer-link administration.
2. Add catalog maintenance and controlled import UI.
3. Add audit exploration and scoped operational reporting.
4. Preserve blind-mapping restrictions and require confirmation for reveal/freeze actions.

## 7. Suggested priority

| Priority | Findings | Rationale |
| :--- | :--- | :--- |
| P0 | UR-01, UR-02, UR-03, UA-01 authorization portion | Establishes trustworthy ownership and prevents inconsistent personal-data access. |
| P1 | UR-04, UW-03, UC-02, UP-01 | Delivers the stated roles, ownership goal, canonical evaluation, and visible core preference library. |
| P2 | UW-01, UW-04, UP-02, UD-01 | Completes onboarding, learning/discovery, maturity communication, and user data controls. |
| P3 | UC-03 notifications, advanced comparison, richer operational UI | Useful enhancements that should follow evidence from real pilot use. |

## 8. Decisions required before implementation planning

1. Is the application permanently a trusted single-household tool, or should the model support
   multiple households later?
2. Is every evaluator expected to have a separate Authentik account?
3. May one account own more than one reviewer profile, or should additional access always be a
   delegated recorder grant?
4. Can evaluators reveal their own completed baseline, or is reveal manager-controlled?
5. Should preliminary recommendations remain available before the 33-fragrance baseline is
   complete?
6. Which collection states and acquisition details are useful enough to justify entry burden?
7. What export, retention, and deletion guarantees should a family member receive?
8. Should catalog and user administration share the calibration-manager role or use separate
   administrator capabilities?

## 9. Verification performed for this analysis

- Reviewed the indexed codebase architecture, routes, domain models, frontend pages, planning
  documents, and focused tests on the current `main` checkout.
- Confirmed the worktree was clean before and after the audit.
- Ran `npm run test:run -- --reporter=dot`: 13 test files and 178 tests passed, with several React
  `act(...)` warnings.
- Attempted focused backend API/service pytest runs. They produced no output and did not complete;
  a bounded retry timed out after 45 seconds. Backend behavior in this document is therefore based
  on current source and existing test coverage, not a newly completed backend test run.

## 10. Primary implementation evidence

- `src/fragrance_rater/models/reviewer.py`
- `src/fragrance_rater/models/evaluation.py`
- `src/fragrance_rater/models/calibration.py`
- `src/fragrance_rater/api/calibration.py`
- `src/fragrance_rater/api/evaluations.py`
- `src/fragrance_rater/api/fragrances.py`
- `src/fragrance_rater/api/reviewers.py`
- `src/fragrance_rater/api/recommendations.py`
- `src/fragrance_rater/api/recommendation_measurement.py`
- `src/fragrance_rater/services/preference_history.py`
- `src/fragrance_rater/services/recommendation_service.py`
- `frontend/src/App.tsx`
- `frontend/src/api/types.ts`
- `frontend/src/routing/routes.ts`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/pages/RatingsPage.tsx`
- `frontend/src/pages/CalibrationPage.tsx`
- `frontend/src/pages/RecommendationsPage.tsx`
- `frontend/src/pages/ProgramSetupPage.tsx`
- `docs/planning/project-vision.md`
- `docs/planning/data-model-gap-analysis.md`
- `docs/planning/PROJECT-PLAN.md`

## 11. Change-control note

Moving any recommendation from this document into delivery scope should create or amend a named
milestone in `PROJECT-PLAN.md`, identify dependencies and validation evidence, and update the
roadmap mirror in the same change. Security-sensitive role and disclosure decisions should receive
an ADR before implementation.
