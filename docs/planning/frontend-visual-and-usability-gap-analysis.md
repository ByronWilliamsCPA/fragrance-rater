# Frontend Visual and Usability Gap Analysis

> **Status**: Draft for product-owner review
> **Version**: 1.0
> **Updated**: 2026-09-21
> **Companion**: [User Roles and Workflows Gap Analysis](user-roles-and-workflows-gap-analysis.md)
> **Purpose**: Evaluate the current frontend from the perspective of an evaluator learning their
> fragrance preferences, including visual appeal and desktop/phone usability. This document is
> planning input and does not change `PROJECT-PLAN.md` status or scope.

## 1. Executive assessment

The frontend is coherent, restrained, accessible, and more thoughtfully engineered than a typical
prototype. It has strong contrast, visible focus, 44-pixel targets, real routes, useful empty/error
states, light/dark themes, and responsive grids. The "sensory evaluation record" concept also fits
the blind-calibration workflow well.

The same visual language is applied too uniformly, however. Encounter logging, recommendations,
the home workspace, and manager operations all resemble one long paper form. For a user who wants
to learn about perfume, the experience feels clinical and administrative rather than personal,
sensory, and rewarding. Hierarchy is carried almost entirely by black rules and spacing; the site
has little imagery, visual storytelling, fragrance identity, progress celebration, or distinction
between exploration and data entry.

On desktop, the main problems are underused space, long flat pages, and weak task prioritization.
On a phone, the main problems are navigation wrapping, excessive vertical length, scale controls
that wrap, loss of context during long calibration entry, and primary actions located far from the
information they affect.

The recommended direction is not a decorative redesign. It is a two-register product system:

1. **Discovery and personal record**: warm, editorial, sensory, and image-aware.
2. **Blind measurement**: precise, quiet, identity-safe, and optimized for rapid structured input.

## 2. Review method

This analysis used:

- live headless-browser captures at 1440 x 1000 and 390 x 844;
- the workspace, ordinary encounter, and populated calibration workflows;
- the frontend route/component structure;
- design tokens, layout rules, responsive breakpoints, and component CSS;
- existing accessibility tests and the prior user-role/workflow analysis.

The live captures used representative mocked household data. They were diagnostic artifacts and
were not added to the repository.

## 3. What should be preserved

### 3.1 Accessibility fundamentals

- The 44-pixel target token is appropriate for phone use.
- Keyboard focus uses a strong two-tone indicator.
- Contrast is tokenized and automatically tested in both themes.
- Native labels, fieldsets, legends, radio groups, and buttons are used appropriately.
- Page titles, skip navigation, focus transfer after routing, progress labels, and semantic tables
  provide a credible accessible foundation.
- Reduced reliance on color for state is correct.

### 3.2 Blind-integrity visual distinction

The sealed blue/monospace treatment for blind codes should remain reserved for concealed identity.
Perfume imagery, branded bottle shapes, note illustrations, family colors, or other recognizable
cues must never appear on a pre-reveal sample surface.

### 3.3 Honest visual language

Affinity scores should continue to be labeled as affinity rather than probability. Published
notes, evaluator perception, and model interpretation should remain visually and verbally
distinct.

### 3.4 Functional foundations

- Real, bookmarkable routes
- Light and dark themes
- Responsive single-column fallback
- Clear disabled states
- Confirmation for locking and reveal
- Append-only observation/history presentation
- Printable blind labels

## 4. Visual direction

### FV-01: Give the product a recognizable fragrance identity

- **Priority**: P1
- **Current state**: The masthead and nearly every content surface are monochrome form elements.
  The result is credible but generic and institutional.
- **Recommendation**:
  - Retain warm paper and charcoal as the base.
  - Add one restrained brand accent distinct from sealed blue, such as muted plum, cedar, or
    oxidized brass. Use it for discovery links, selected open-content states, and small graphic
    details, not for blind data or semantic alerts.
  - Develop a simple wordmark or abstract scent-trail mark that works without identifying any
    fragrance.
  - Use a small family of line illustrations or abstract note/family textures on welcome,
    preference-library, catalog, and recommendation surfaces.
- **Acceptance criteria**:
  1. Blind screens remain identifiable in grayscale and never use open-content imagery.
  2. Error, warning, success, sealed, and brand colors have nonoverlapping meanings.
  3. Both themes pass existing contrast tests.

### FV-02: Use typography to distinguish exploration from data entry

- **Priority**: P2
- **Current state**: The humanist UI font is used for nearly everything. Headings are modest and
  the compressed scale makes a desktop dashboard feel visually quiet.
- **Recommendation**:
  - Preserve the current UI face for forms, scales, blind codes, and operations.
  - Introduce an editorial display face for open-content page titles, perfume names, collection,
    and preference insights. A locally hosted font would require license/REUSE handling; an
    existing system-serif stack is a low-risk first iteration.
  - Increase open-content title size and use a clearer body/metadata contrast.
  - Avoid uppercase caption text at phone sizes except for very short semantic labels.
- **Acceptance criteria**: A user can distinguish page title, task, supporting explanation, and
  metadata without relying only on horizontal rules.

### FV-03: Use imagery where it teaches, never where it leaks

- **Priority**: P2, after catalog/detail work
- **Current state**: No consumer-facing fragrance imagery exists.
- **Recommendation**:
  - Catalog and post-reveal pages may show sourced bottle photography or neutral product imagery.
  - Recommendation cards can use imagery after candidate identity is legitimately visible.
  - Note, accord, and family exploration can use licensed illustration, texture, or abstract
    diagrams instead of pretending published notes are ingredients.
  - Pre-reveal calibration uses only neutral codes and nonidentifying system graphics.
- **Acceptance criteria**: Every image has provenance, alt-text policy, responsive sizing, and a
  documented disclosure classification.

### FV-04: Introduce selective surface grouping

- **Priority**: P1
- **Current state**: The CSS deliberately avoids cards. This creates discipline, but long pages
  become a sequence of nearly identical ruled sections.
- **Recommendation**:
  - Keep the ruled-sheet pattern for dense observations and evidence logs.
  - Use quiet raised surfaces for dashboard tasks, recommendation summaries, collection items, and
    preference insights.
  - Avoid cards inside cards; one visual container should correspond to one user decision or one
    durable object.
- **Acceptance criteria**: Repeated records can be scanned as objects, while dense forms still read
  as one coherent form.

## 5. Information architecture and shared usability

### FU-01: Make Home a task-oriented personal dashboard

- **Priority**: P0
- **Current state**: Workspace presents three equal buttons, calibration progress, and explanatory
  prose. Large portions of the desktop viewport are unused.
- **Recommendation**:
  - Rename Workspace to Home unless "workspace" has a necessary domain meaning.
  - Lead with one "Continue where you left off" action.
  - Follow with compact summaries for recent encounter, collection count, calibration progress,
    and preference-library maturity.
  - Demote administrative actions into a manager area rather than placing them beside personal
    tasks.
  - Replace the long reassurance text with a short contextual note near calibration or first use.

### FU-02: Separate primary navigation by user purpose

- **Priority**: P0
- **Current state**: Six text links share one wrapping row: Welcome, Workspace, Calibration,
  Recommendations, Log an encounter, and Program setup. Welcome remains a permanent destination
  after onboarding, and Program setup sits beside evaluator tasks.
- **Recommendation**:
  - Evaluator navigation: Home, Journal, Collection, Discover/Recommendations, Profile.
  - Calibration appears as an active assignment/task and as a secondary destination while assigned.
  - Manager tools live under a Manager destination or account menu.
  - Welcome becomes onboarding and About remains secondary.
- **Acceptance criteria**: The primary nav contains no more than five evaluator destinations and
  does not expose manager information architecture to nonmanagers.

### FU-03: Replace search-then-select with a catalog combobox

- **Priority**: P1
- **Current state**: Users type a query, press Search, and then move to a separate fragrance-version
  select. The search results are invisible until the select is opened.
- **Recommendation**:
  - Use an accessible async combobox with name, house, concentration, version, and optional year.
  - Show recent fragrances before typing.
  - Preserve the selected exact version as a visible summary with a Change action.
  - Provide a clear "not found" route to request or add catalog data according to role.

### FU-04: Make save state and next action unmistakable

- **Priority**: P0
- **Current state**: Notices confirm completion, but long forms do not show draft/dirty state. In
  calibration, Save observation and Lock responses are separate adjacent actions near the bottom.
- **Recommendation**:
  - Show Unsaved, Saving, Saved, and Locked states near the active sample heading.
  - Warn before navigation when a populated form is unsaved.
  - After save, offer Save and continue to next required timepoint/sample.
  - Keep Lock visually and spatially separate from Save; explain whether another observation is
    required before enabling it.
  - Consider local draft recovery for long calibration forms without treating drafts as submitted
    evidence.

### FU-05: Reduce text and expose help progressively

- **Priority**: P1
- **Current state**: Methodological care is valuable, but instructions, scale hints, anchors, and
  explanatory paragraphs make task pages long and visually dense.
- **Recommendation**:
  - Keep the one sentence needed to answer correctly visible.
  - Move methodology into expandable "Why we ask this" help.
  - Show protocol-level instructions once per session rather than above every sample.
  - Preserve all content for assistive technology and print where required.

## 6. Desktop improvements

### FD-01: Use the available width intentionally

- **Priority**: P1
- **Finding**: The 60rem sheet is readable, but a 1440px display leaves large empty margins while
  manager and calibration pages become extremely tall.
- **Recommendation**:
  - Keep prose at approximately 60-70 characters.
  - Allow task dashboards and master-detail workspaces to expand to roughly 72-80rem.
  - Do not stretch individual form fields across the full width; use structured columns and
    bounded field measures.

### FD-02: Make calibration a stable master-detail workspace

- **Priority**: P0
- **Finding**: The sidebar is useful but scrolls away while the observation form continues for
  several screens.
- **Recommendation**:
  - Keep sessions/sample progress in a sticky left rail.
  - Keep active code, stage, save status, and primary action in a sticky workspace header.
  - Collapse completed sessions by default.
  - Add Previous/Next incomplete sample navigation.
  - Show required versus optional fields before the user starts.

### FD-03: Break manager operations into focused modes

- **Priority**: P1
- **Finding**: Program definition, enrollment, operations, labels, metrics, and incident logging
  share one very long page. Their sequence is meaningful during setup but inefficient during daily
  operations.
- **Recommendation**:
  - Use a manager subnavigation or stepper: Definition, Enrollments, Samples/labels, Progress,
    Metrics, Operations.
  - Preserve a setup checklist for a new program.
  - Once active, default to progress rather than the create-draft form.
  - Put rare incident entry and raw evidence download behind secondary actions.

### FD-04: Turn history and recommendations into scannable records

- **Priority**: P1
- **Finding**: Encounter history is an undifferentiated vertical list. Recommendation cards have
  little visual structure beyond a top rule.
- **Recommendation**:
  - Journal history: compact date, rating, perfume identity, context, and correction menu; add
    sorting/filtering when history grows.
  - Recommendations: perfume identity, affinity, two or three evidence reasons, collection/sample
    state, and one clear feedback action.
  - Use detail drawers or routes for verbose explanation and revision history.

## 7. Phone improvements

### FM-01: Replace the wrapping header navigation

- **Priority**: P0
- **Finding**: At 390px, account details consume a separate block and six navigation links wrap to
  three rows. The task begins far below the top of the screen.
- **Recommendation**:
  - Use a compact one-line masthead.
  - Move account, role, theme, About, and manager tools into an accessible menu.
  - Use a bottom navigation bar for three to five frequent evaluator destinations, respecting safe
    areas and the on-screen keyboard.
  - Do not put destructive or blind-reveal actions in persistent bottom navigation.

### FM-02: Make calibration progressive rather than one 5,900px form

- **Priority**: P0
- **Finding**: The representative phone calibration page was approximately 5,886px tall. The user
  loses the sample code, elapsed-time context, and progress long before reaching Save and Lock.
- **Recommendation**:
  - Step 1: choose/confirm sample and stage.
  - Step 2: detection and core required ratings.
  - Step 3: optional perceptual dimensions.
  - Step 4: notes and review.
  - Keep the blind code, session progress, save state, and Back/Next controls sticky.
  - Allow users to skip optional groups explicitly without answering each field.
  - Show saved observations in a collapsed summary after submission.

### FM-03: Prevent numerical rating scales from wrapping

- **Priority**: P0
- **Finding**: The 0-10 segmented liking scale cannot fit eleven 44px targets plus "Not answered"
  in a phone viewport, so it wraps. Once wrapped, the scale no longer reads as one ordered
  continuum and its endpoint anchors do not describe the visual rows cleanly.
- **Recommendation**:
  - For 0-5, retain a single-row segmented control if it fits.
  - For 0-10, evaluate an accessible range control with a large thumb, always-visible numeric
    value, endpoint labels, and decrement/increment buttons.
  - Keep a separate Clear/Not answered action rather than placing it as a twelfth segment.
  - If a segmented 0-10 control is retained, use an explicitly horizontally scrollable one-row
    control with visible overflow affordance and test it with touch and screen readers.
- **Acceptance criteria**: Values remain ordered on one axis at 320px; every target remains at least
  44px; keyboard and screen-reader users can select and clear a value.

### FM-04: Collapse the session/sample navigator

- **Priority**: P1
- **Finding**: All sessions and all samples appear before the form, consuming most of the first
  viewport as the baseline grows.
- **Recommendation**:
  - Show the current session and next incomplete sample first.
  - Put other sessions in an accordion or dedicated progress drawer.
  - Use text plus icon/status, never color alone, for Open, Saved, and Locked.

### FM-05: Optimize encounter entry for one-handed use

- **Priority**: P1
- **Finding**: The phone form reflows correctly but still requires search, search button, evaluator
  select, version select, numeric rating input, date, worn-by, notes, and save.
- **Recommendation**:
  - Default and visually confirm the signed-in evaluator.
  - Use the catalog combobox instead of search plus select.
  - Replace the numeric rating box with five large rating choices carrying both number and verbal
    anchor.
  - Default the date/time to now and hide editing behind Change.
  - Keep worn-by collapsed under "This was on someone else" for the less common case.
  - Make Save a full-width or sticky bottom action when the keyboard is closed.

### FM-06: Design for interruption and recovery

- **Priority**: P1
- **Finding**: Phone evaluation is likely to happen around physical samples, timers, and movement.
  A refresh, accidental navigation, or screen sleep can discard the long form.
- **Recommendation**:
  - Recover local unsaved values per presentation and stage.
  - Show when a draft was restored.
  - Never sync or train on a draft until explicit submission.
  - Test screen rotation, keyboard appearance, background/resume, and slow-network retries.

## 8. Page-level target experience

### Home

- Personal greeting and active evaluator context
- One prominent resume/next action
- Calibration completion ring or linear progress with session count
- Recent journal entry
- Collection summary
- Preference-library maturity
- Recommendation/sample follow-up reminder

### Journal

- Fast add control at the top
- Accessible perfume autocomplete
- Five-choice overall rating
- Optional details progressively disclosed
- Filterable timeline grouped by month or fragrance

### Collection

- Visual grid/list switch
- Exact version and ownership format
- Wishlist/sample/decant/bottle/formerly-owned filters
- Quick state changes without forcing a review

### Calibration

- Neutral identity-safe visual register
- Clear current code and session progress
- One manageable rating step at a time on phone
- Sticky sample context and save state
- Fast next-incomplete-sample navigation

### Preference library

- Open-content editorial treatment
- Strongest likes, dislikes, families, and accords
- Evidence count and maturity
- Links to the encounters that support each pattern
- Clear separation of reported perception, catalog data, and model interpretation

### Recommendations

- Richer perfume summaries linked to catalog detail
- Affinity score qualification visible but not dominant
- Concise "why" evidence
- Collection/sample state integrated into the primary card
- One clear feedback/follow-up action with details on demand

### Manager

- Separate operational navigation
- Program setup checklist
- Progress-first active-program view
- Dense tables where comparison matters
- Confirmation and audit context for reveal, role/grant, import, and destructive actions

## 9. Proposed remediation sequence

### Phase 1: Navigation and high-friction mobile fixes

1. Define evaluator navigation and separate manager navigation.
2. Compact the phone masthead and replace wrapping navigation.
3. Stop 0-10 scales from wrapping.
4. Add sticky calibration context/actions and unsaved-state protection.
5. Default ordinary entry to the authenticated evaluator once identity remediation exists.

### Phase 2: Task-oriented page restructuring

1. Redesign Home around resume/next action.
2. Convert calibration to progressive phone steps and sticky desktop master-detail.
3. Split manager operations into focused modes.
4. Replace catalog search-plus-select with a combobox.
5. Improve encounter history and recommendation scanning.

### Phase 3: Visual identity and learning surfaces

1. Establish the open-content brand accent and editorial type treatment.
2. Build catalog/detail, collection, and preference-library pages.
3. Add licensed/provenanced imagery after disclosure rules are encoded.
4. Add restrained transitions and completion feedback.

## 10. Validation plan

Every frontend remediation should be evaluated at minimum at:

- 320 x 568 phone;
- 390 x 844 phone;
- phone landscape with on-screen keyboard considerations;
- 768px tablet portrait;
- 1280px desktop;
- 1440px desktop;
- 200% browser zoom and text-only zoom;
- light, dark, high-contrast/forced-colors where supported;
- keyboard-only and representative screen-reader use.

Task-based tests should measure:

- time and errors for saving an ordinary encounter;
- time, scroll distance, and missed required fields for one calibration observation;
- wrong-evaluator selection rate for recorders;
- ability to resume the next incomplete sample;
- successful interpretation of affinity versus predicted liking;
- successful identification of saved versus locked state;
- navigation reachability with one hand on a phone.

## 11. Success measures

- Median ordinary encounter entry remains under 30 seconds.
- The active sample code and save state remain visible throughout phone calibration entry.
- No ordinal scale wraps into multiple rows at 320px.
- A phone user reaches any frequent evaluator destination in one tap from primary navigation.
- A returning user can identify their next task within five seconds.
- A user can explain what the preference library learned and which evidence supports it.
- Blind identity and experimental role remain undisclosed before reveal.
- Existing automated contrast, accessibility, routing, and disclosure tests continue to pass.

## 12. Primary implementation evidence

- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/ScaleField.tsx`
- `frontend/src/styles/tokens.css`
- `frontend/src/styles/base.css`
- `frontend/src/styles/layout.css`
- `frontend/src/styles/components.css`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/pages/RatingsPage.tsx`
- `frontend/src/pages/CalibrationPage.tsx`
- `frontend/src/pages/RecommendationsPage.tsx`
- `frontend/src/pages/ProgramSetupPage.tsx`
- `frontend/src/test/accessibility.test.tsx`
- `frontend/e2e/accessibility.spec.ts`
- `frontend/e2e/welcome-and-workspace.spec.ts`
- `frontend/e2e/blind-calibration.spec.ts`

## 13. Change-control note

This analysis recommends presentation and interaction changes but does not authorize changes to
the calibration protocol, rating semantics, disclosure policy, or training eligibility. Any change
to those contracts belongs in the relevant ADR and authoritative project plan before UI work begins.
