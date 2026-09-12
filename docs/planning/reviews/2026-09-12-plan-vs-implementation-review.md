---
title: "Project Plan vs. Implementation Review - 2026-09-12"
schema_type: common
status: published
owner: core-maintainer
purpose: "Independent comparison of the authoritative project plan's claimed status against
  the code, tests, migrations, and gate evidence actually present in the repository."
tags:
  - planning
  - review
---

**Reviewer:** Claude Code (automated review, requested by the core maintainer)
**Date:** 2026-09-12
**Baseline reviewed:** `origin/main` @ `1c9bc2af9b3bf948c0ddda5b863fc8faae71e056`
(`feat: complete P5 manager operations UI (#74)`), plus the unmerged branch
`origin/feat/p6-pilot-readiness` @ `9c8d455`.
**Scope:** [PROJECT-PLAN.md](../PROJECT-PLAN.md), [roadmap.md](../roadmap.md), all files under
`docs/planning/gates/` and `docs/planning/evidence/`, the ADR set, and the corresponding backend
(`src/fragrance_rater/`) and frontend (`frontend/src/`) implementation, tests, and migrations.

This review does not re-run the test suite or CI; it reconciles what the planning documents
*claim* against what the code, migrations, and retained evidence files *show*. Local
verification (`pytest --cov`, `ruff`, `basedpyright`, frontend `build`/`test`) was intentionally
skipped at the requester's direction; the test/coverage counts below are cited as
**self-reported** by the gate documents, not independently re-executed.

## 1. Executive summary

The plan is unusually well self-documented, and its status claims for P0–P4 hold up against an
independent code read: commit hashes and PR numbers cited in the gate files check out in `git
log`, and every gate is explicit about what it does *not* yet cover. The one material gap found
is that **P5 has already merged to `main` (PR #74, 2026-09-12) but `PROJECT-PLAN.md`,
`roadmap.md`, and `gates/p5.md` still say "review pending"** as of the commit this review was
requested against - a one-day documentation lag, not a fabricated claim. An unmerged branch
(`feat/p6-pilot-readiness`) already contains the fix for this plus the start of P6 evidence
scaffolding; it just hasn't landed yet (see §4.1).

Beyond that lag, three implementation gaps are worth the core maintainer's attention even though
none of them contradict a plan claim outright:

1. Two coexisting auth mechanisms - the Authentik-header identity (ADR-008) and an older static
   `X-API-Key` middleware - gate different routers, so some mutating/LLM-billed endpoints are not
   behind the trust boundary ADR-008 describes as authoritative (§4.2).
2. "End-to-end" and "automated accessibility baseline" in the P3/P4/P5 gate language describe
   Vitest + Testing Library component tests with a fully mocked `axios` client and a hand-rolled
   accessibility check, not a real-browser e2e framework or an accessibility engine (§4.3).
3. P1's ten work packages remain fully open (baseline manifest, backup/restore, concurrency,
   trust-boundary and disclosure evidence, target-environment verification, Parfumo fixtures,
   operations runbook) - this matches the plan's own "external evidence pending" framing exactly,
   so it is not a discrepancy, but it is the largest concentration of remaining work standing
   between the project and P6/F1 (§4.4).

Everything else reviewed - the calibration domain model, the Alembic migration chain, the
production Compose port lockdown, the LLM cost/telemetry pipeline, and the P0–P4 gate evidence -
matches what the plan and gates claim.

## 2. Milestone-by-milestone findings

| Milestone | Plan/roadmap status | Independent finding | Verdict |
| :--- | :--- | :--- | :--- |
| P0 | Complete | Gate cites merge `7f0884f`/PR #70, confirmed in `git log`; evidence table is concrete (named tools, test counts) and explicitly scopes out what P0 does *not* cover | Matches |
| P1 | Repository controls implemented; external evidence pending through P6 | All 10 work packages (P1.1–P1.10) are still open on disk (see §4.4); this is exactly what the plan states, not a gap in the plan itself | Matches (large open scope) |
| P2 | Complete | Gate cites the same merge, 622 tests / 87.71% coverage (self-reported), and explicitly excludes real baseline values as an F1 concern | Matches |
| P3 | Complete | Gate cites merge `3b563b6`/PR #72, confirmed in `git log`; routed shell, shared components, and 360px/keyboard/focus handling are present in `frontend/src` | Matches, with the e2e/accessibility caveat in §4.3 |
| P4 | Complete | Gate cites merge `4a2f9c2`/PR #73, confirmed in `git log`; participant flows (calibration, ratings, recommendations) and no-UUID/no-manager-leakage behavior are present and covered by tests | Matches, with the e2e caveat in §4.3 |
| P5 | **Plan/roadmap/gate say "Implementation complete; review pending"** | **PR #74 already merged to `main` as `1c9bc2a` on 2026-09-12** - one day after the plan's cited audit date. The merge, manager/operations UI, and disclosure evidence (`p5-manager-disclosure.md`) are all present and match the acceptance criteria | **Documentation lag** - see §4.1 |
| P6 | Planned | Matches on `main`; **but** an unmerged branch `feat/p6-pilot-readiness` already contains P6 evidence-template scaffolding, pilot guides, and a `validate_p6_readiness.py` script, and updates the plan/gate status to reflect the P5 merge | Matches on `main`; in-flight work exists off-branch |
| F1 | Planned; blocked on P6 | No pilot activity of any kind found in the repository; matches | Matches |
| D1–D5 | Planned | No implementation attempted; matches | Matches |

## 3. Cross-cutting checks

- **ADR index:** ADR-005 through ADR-009 are listed and individually headered as `Accepted`,
  dated 2026-09-11, with no drift between the index and the ADR files themselves. ADR-004 is
  correctly marked "partially superseded by ADR-007."
- **Alembic migration chain:** ten revisions form one single, unbranched chain from `001_initial_schema`
  through `c731b42e9a01_controlled_calibration` to `f5c2d3e4a5b6_openrouter_usage_accounting`
  - no orphaned heads, consistent with the plan's "fresh-schema verified" claim.
- **Production Compose:** `docker-compose.prod.yml` sets `ports: !reset []` on `app`, `frontend`,
  and `db`, removing the dev Compose's direct port mappings, and `scripts/validate_production_topology.py`
  exists to check this programmatically. The plan's own audit-finding disposition table (§22)
  flags "Production Compose could expose backend port 8000" as a past finding; the repository-level
  fix is in place. What remains is P1.6's *deployed*-topology proof, which the plan already scopes
  as external evidence.
- **Baseline manifest:** `data/calibration/baseline-manifest.template.json` is a blank template
  (`entries: []`); no populated 43-fragrance manifest exists anywhere in the repository. This
  matches the ledger's "Not available" line exactly.
- **LLM integration:** `services/llm_service.py` has a bounded in-process cache, deterministic
  fallback paths, and full prompt/completion/cost telemetry persisted via the
  `f5c2d3e4a5b6_openrouter_usage_accounting` migration - matches the plan's claims for the
  OpenRouter explanation feature.

## 4. Findings requiring attention

### 4.1 P5 merge is not reflected in the plan on `main` (documentation lag)

`docs/planning/gates/p5.md` (as of `1c9bc2a`) still reads "Implementation complete; review
pending" and closes with "P5 becomes complete after independent review, remote CI, and merge
evidence are recorded" - but that review, CI run, and merge already happened as PR #74, merged
to `main` the same day. `PROJECT-PLAN.md`'s current-state ledger is still pinned to the P0–P2
merge (`7f0884f`, 2026-09-11) and its P5 row still reads "P4 complete; P5 review pending."
`roadmap.md`'s "Immediate queue" item 1 ("Review and merge the P5 manager … workflows") is
likewise now stale.

This is not a fabricated status - it is the ordinary lag between a merge landing and the plan
being updated in a follow-up PR, and the fix is already drafted: branch
`feat/p6-pilot-readiness` (unmerged, `9c8d455`, authored by Byron Williams) updates exactly these
three files to say P5 is `Complete`, records the PR #74 completion evidence in `gates/p5.md`
(including an updated backend test count - "Thirty-two focused backend API tests," up from the
"Nine" the current `p5.md` cites), and begins P6 scaffolding (evidence templates, two pilot
guides, and `scripts/validate_p6_readiness.py`).

**Recommendation:** Merge (or otherwise land) the plan/gate/roadmap updates from
`feat/p6-pilot-readiness` - or an equivalent update - so `main`'s planning documents reflect
that P5 is done, before starting new P6 work against a ledger that still shows P5 as pending.

### 4.2 Two coexisting authentication mechanisms

ADR-008 describes the Authentik/Traefik proxy as the production trust boundary, and
`src/fragrance_rater/core/auth.py` implements that model correctly (reads
`X-Authentik-Username/Uid/Email`, fails closed under `AUTHENTIK_REQUIRED=true`). It gates
`api/calibration.py`, `evaluations.py`, `recommendation_measurement.py`, `reviewers.py`,
`imports.py`, and `fragrances.py`.

However, `src/fragrance_rater/middleware/auth.py` implements a separate, older static
`X-API-Key` ("household API key") mechanism, and it - not the Authentik identity - is what
actually gates `POST /ratings` (`api/ratings.py:114`) and the LLM-backed `GET
/{reviewer_id}/profile` / `/explain` routes in `api/recommendations.py`. So the mutating and
LLM-billed routes on those two routers sit behind a different, weaker boundary than the one
ADR-008 names as authoritative for production.

**Recommendation:** Reconcile the two mechanisms as part of P1.6/P1.7 evidence - either migrate
`ratings.py`/`recommendations.py`'s billed routes onto `core/auth.py`'s Authentik identity, or
explicitly document in ADR-008 why the household API key remains an accepted exception for these
specific routes, before P1.6's trust-boundary evidence is recorded as passing.

### 4.3 "End-to-end" and "accessibility baseline" language overstates the tooling in place

Across P3/P4/P5 gate text and acceptance criteria, "end-to-end tests" and an "automated
accessibility baseline" are cited as evidence. In the actual `frontend/` tree:

- There is no Playwright, Cypress, or other real-browser e2e framework installed or configured
  (no `playwright.config.*`, no `cypress.config.*`, no e2e directory). All tests described as
  end-to-end are Vitest + Testing Library tests that render `<App/>` in jsdom against a fully
  mocked `axios` client (`frontend/src/test/App.test.tsx`, 24 tests) - real network behavior,
  real browser navigation/reload, and real serialization are not exercised.
- There is no accessibility-testing library (no `axe-core`, `jest-axe`, `vitest-axe`, `pa11y`).
  `frontend/src/test/accessibility.test.tsx` is one hand-written test asserting labeled inputs,
  non-empty interactive text, and unique DOM ids - useful, but not a substitute for an actual
  accessibility engine, and it won't catch contrast, ARIA misuse, or most WCAG failure classes.

This does not mean P3/P4/P5's underlying UI behavior is wrong - the reviewed code genuinely
implements route-backed navigation, keyboard/focus handling, and role-gated views - but the gate
language should say "Vitest/Testing-Library integration tests" and "a custom semantic check"
rather than "end-to-end tests" and "automated accessibility baseline," so a future reader doesn't
assume browser-level or WCAG-engine coverage that isn't there.

**Recommendation:** Either add a real e2e/accessibility tool before P6's rehearsal (the P6 gate's
"accessibility, keyboard … checks pass for every pilot-critical page" criterion is the natural
place to require it), or reword the P3–P5 gate language to describe what is actually tested so
the plan's own evidence claims stay literal.

### 4.4 P1 remains fully open - the largest block of remaining work

Independent code inspection confirms every P1 work package is still outstanding, matching
`gates/p1.md`'s own "Blocked on inventory / Awaiting deployment / Blocked on fixtures" language
line for line:

- **P1.1** - no populated baseline manifest exists (only the blank template).
- **P1.9** - `tests/unit/test_services/test_parfumo_scraper.py` uses hand-authored synthetic
  HTML fixtures ("Test Fragrance", "Test Brand2024"), not captured real Parfumo pages, and does
  not yet cover the requested-metrics/status/related-versions/missing-field cases the plan
  requires.
- **P1.10** - no standalone operations runbook file exists; `docs/deployment/p1-release-readiness.md`
  has an operations *checklist* (what must be verified), not the rehearsed runbook artifact
  itself, though the health-check code (`api/health.py`) that a runbook would document is real.
- **P1.2–P1.8** - backup/restore, live migration, concurrency, rollback, trust-boundary, and
  blind-disclosure evidence all require the deployed target environment and are correctly marked
  as pending rather than fabricated.

This is not a discrepancy between the plan and the code - it is accurately described as pending
in both - but it is worth restating plainly: **P1's ten items, not P6 or F1 mechanics, are the
critical path** to closing P6 and beginning F1, since P6 explicitly depends on "P1 repository
controls" plus a completed P1 evidence pass (P6.1) before it can close.

## 5. Items that matched cleanly (no action needed)

- Calibration blind-disclosure logic (`services/calibration_service.py:333-430`): holdout
  identities stay hidden until blotter lock; fragrance identity attaches only post-reveal;
  manager-only mapping endpoint is never reachable from participant routes - matches ADR-005/006/007
  and the P4/P5 disclosure evidence files.
  - `middleware/security.py`'s `Cache-Control: private, no-store` + `Vary: X-Authentik-Username`
  on calibration/recommendation-measurement GET routes matches the P5 cache-disclosure criterion;
  `core/cache.py` is unrelated generic Redis boilerplate used only by the health check, not a
  disclosure mechanism, so it should not be cited as satisfying that criterion.
- No manager-only field (role, repeat, group, mapping) appears in any participant-facing frontend
  type; tests assert raw IDs never render on participant pages.
- Frontend has no dead/duplicated page logic for layout, confirmation, status, or loading/empty/
  error states - all four feature pages share `AppShell`, `ConfirmAction`, `FeedbackBanner`, and
  `PageState`.

## 6. Recommended next actions (priority order)

1. Land the plan/gate/roadmap corrections already drafted on `feat/p6-pilot-readiness` (or a
   fresh equivalent PR) so `main`'s planning documents show P5 as `Complete` with PR #74 as its
   completion evidence, before treating P6 work as building on an accurate ledger.
2. Decide and record (ADR update or new ADR) whether the `X-API-Key` middleware on
   `ratings.py`/`recommendations.py` is an accepted, time-boxed exception to ADR-008 or should be
   migrated onto the Authentik identity - do this before P1.6/P1.7 evidence is recorded as
   passing.
3. Reword "end-to-end" and "automated accessibility baseline" in the P3–P5 gate files to describe
   the actual Vitest/Testing-Library and custom-check tooling, or add real tooling (Playwright and
   an accessibility engine) as an explicit P6 entry-gate item.
4. Continue P1's non-deployment evidence in parallel: populate/verify the baseline manifest
   (P1.1) and add authorized Parfumo fixtures (P1.9) - neither requires the target deployment and
   both currently block D1-adjacent confidence even though they are formally P1/D1 items.
5. Sequence the deployment-dependent P1 items (backup clone, live migration, concurrency,
   trust-boundary, disclosure audit, target-environment verification, operations runbook) as the
   P6.1 evidence pass the plan already calls for, since P6 cannot close without them.
