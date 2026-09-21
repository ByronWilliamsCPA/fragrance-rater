---
title: "Architecture and Design Review, September 2026"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record a critical review of the design and architecture so later agents can plan and implement remediation."
tags:
  - planning
  - architecture
  - analysis
  - security
  - quality
---

> **Reviewed commit**: `83257f0` on `main` (2026-09-19) | **Review type**: read-only, evidence-anchored |
> **Authority**: advisory. This document proposes work; it does not change plan status. Any accepted
> item must be scheduled through [PROJECT-PLAN.md](PROJECT-PLAN.md) change control and, where it
> alters a durable decision, an ADR.

## 1. How to use this document

This review is written for the next agents and for the core maintainer. It answers three questions:
where the implementation diverges from the governing documents, where the design itself is weak,
and what to do about it in what order.

- Section 2 is the verdict. Read it first.
- Section 3 is the measured baseline from this session, so later work can show movement.
- Section 4 holds every finding, grouped by theme. Each has an ID, a severity, a file and line
  anchor, and a recommended action. IDs are stable: `G-` governance and process, `S-` security and
  deployment, `B-` backend, `D-` data model and migrations, `F-` frontend and API contract.
- Section 5 lists what is genuinely well done, so remediation does not undo it.
- Section 6 lists decisions only the owner can make. Several workstreams block on them.
- Section 7 is the recommended workstream sequence with entry conditions, scope, and acceptance
  criteria. A future agent should be able to pick a workstream, read its cited findings, and start.
- Appendices carry the detail tables (contract drift, CI gate matrix, import map).

Severity meaning: **Critical** blocks the P6 go decision on its own; **High** should be fixed before
F1 or explicitly accepted in the P6 known-limitations table; **Medium** is real debt that will
bite during D1-D5; **Low** is hygiene.

Method: the governing documents (vision, plan, tech-spec, calibration guide, all ADRs, gate and
evidence records) were read first, then four independent deep reviews were run over the backend,
the data model and migrations, the frontend and API contract, and security, deployment, and CI.
Every finding was required to cite a file and line. The supervisor spot-checked the highest-impact
claims from each review against source before including them. All quality gates were executed
locally on Python 3.12 and Node 22; results are in Section 3.

## 2. Verdict

The project has an unusually good governance layer and a competent core domain, wrapped in a
template-generated shell that has never been pruned. The controlled-calibration domain, the
preference-history and holdout exclusion logic, the recommendation-measurement provenance, and the
planning discipline (one authoritative plan, gate records, evidence templates, honest status
terms) are all better than typical for a single-developer project. Those parts should be preserved.

The problems are concentrated in six places.

1. **Gate evidence overstates what is verified.** P3, P4, and P5 are marked Complete with
   "end-to-end" tests as retained evidence, but no browser end-to-end harness exists; the evidence is
   Vitest component tests with a fully mocked API client. No workflow in this repository runs those
   frontend tests at all. The P2 measurement service is 44 % covered and its substantive branches run
   only in a PostgreSQL test that skips by default. The 80 % coverage gate omits the entire API layer,
   which is where authorization is wired. The plan's own rule, "Complete requires the milestone exit
   gate and retained evidence", is not met for P3-P5 as written (G-01, G-02, S-09, S-11, F-10).
2. **The trust boundary is a topology promise, not a code property.** Identity is whatever the
   `X-Authentik-*` headers say. The frontend nginx re-emits client-supplied copies of those headers
   upstream, the backend trusts them unconditionally, uvicorn runs without proxy-header handling, and
   the only thing that strips forged headers is Traefik configuration in another repository. Reads of
   personal data carry no identity dependency at all. Rate limiting keys on one container IP, so the
   household shares a single bucket (S-01, S-02, S-05, S-06, F-02, B-10).
3. **Blind disclosure has two participant-reachable leaks and no audit trail.** A recorder can learn
   that a version is a holdout from a 409 body and from a 404 oracle on the explain route. The
   manager-only mapping route, the single most sensitive read in the system, writes no audit event
   (B-01, B-02, B-03, B-26).
4. **A vestigial scaffold product ships inside the real one.** The root-mounted `/ratings` LLM
   endpoint, the in-memory `/fragrances` stub, the shared API-key auth scheme, a second LLM client
   that always fails outside test mode, a 513-line unused Redis cache, an empty jobs package, and a
   1,543-line deprecated Parfumo scraper are all still in the runtime package. The FastAPI app
   describes itself as an LLM rating service. Two auth schemes and two LLM stacks coexist
   (G-03, B-21, B-22, B-23, B-24, B-30, S-03, S-04).
5. **The backend has no single owner of transactions, errors, or authorization.** Five places
   commit; services raise `HTTPException`; the 418-line exception hierarchy has no handler
   registered; authorization helpers live in a router and are imported by other routers; one router
   is a second service layer (B-04, B-07, B-08, B-09, B-11).
6. **The calibration API, the product's core, has no typed contract on either side.** Nineteen
   routes return bare dicts, OpenAPI publishes `additionalProperties: true` for them, the frontend
   hand-writes 277 lines of types nobody checks, and the generated-client script has never been run.
   Provenance fields the tech-spec calls required (algorithm version, candidate strategy, score
   type) never reach the UI (F-03, F-04, F-05, B-12, B-13).
7. **The schema is right but the schema tooling will erode it.** ORM and migrations agree on
   PostgreSQL today, verified here. But there is no naming convention, so autogenerate proposes
   dropping 37 real CHECK constraints; no test runs the chain; no CI job has PostgreSQL; the unit
   suite never enables SQLite foreign keys; and the immutability and provenance guarantees the spec
   describes (append-only observations, frozen checkpoints, source content hashes and license
   evidence) are conventions or absent, not constraints (D-01, D-03, D-05, D-06, D-07, D-08).

None of this is unrecoverable. Most of it is subtraction (delete the scaffold), consolidation (one
auth dependency, one transaction owner, one error handler), and making CI tell the truth. The
workstreams in Section 7 are sized so that each fits in one pull request and can be verified by the
repository's own gates once those gates are corrected.

## 3. Measured baseline, this session

Environment: Python 3.12.11 via uv, Node 22.22, branch head `83257f0`, `AUTHENTIK_REQUIRED=false`.

| Gate | Result |
| :--- | :--- |
| `uv run pytest` (845 tests) | 845 passed, 1 skipped (PostgreSQL test gated on `P1_DATABASE_URL`), 57 s |
| Backend coverage | 89.6 % of the measured set; `api/*`, `llm/*`, and `main.py` are omitted from measurement (`pyproject.toml`, `[tool.coverage.run] omit`) |
| `ruff check .` | clean |
| `basedpyright src/` | 0 errors, 184 warnings (mostly `reportAny` on SQLAlchemy row access) |
| `bandit -r src` | 0 medium or high, 17 low (16 `B101` assert, tracked as B-17; 1 `B311` random, already justified inline in `ml/reliability.py:179`) |
| `vulture src --min-confidence 80` | 6 hits, all false positives (`cls` in validators) |
| Frontend `eslint`, `tsc --noEmit` | clean |
| Frontend `vitest run` | 4 files, 40 tests pass; 78.9 % statements, 70.1 % branches |
| Frontend `vite build` | one 331.85 kB chunk (104.6 kB gzip), no code splitting, source maps published |
| Committed `docs/api/openapi.json` vs live `app.openapi()` | identical (45 paths, 44 schemas) |

Lowest-covered backend modules: `jobs/__init__.py` 0 % (stub), `services/recommendation_measurement_service.py` 44.4 %, `middleware/correlation.py` 74.8 %, `services/parfumo_scraper.py` 78.3 %.

Size: 15,021 lines of Python under `src/`, 17,991 lines of tests, 4,528 lines of TypeScript and CSS. Largest modules: `parfumo_scraper.py` 1,543, `cli.py` 649, `llm_service.py` 583, `calibration_service.py` 562, `api/calibration.py` 537, `recommendation_service.py` 534, `core/cache.py` 513 (unreferenced), `ProgramSetupPage.tsx` 707.

## 4. Findings

### 4.1 Governance and evidence integrity

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| G-01 | High | Gate records cite end-to-end tests that do not exist. No Playwright config, no `frontend/e2e`, no `tests/e2e`, no E2E dependency. The cited evidence is jsdom component tests with axios fully mocked. Tech-spec and P3/P4 acceptance require E2E journeys including interruption and retry. | `docs/planning/gates/p4.md:23-26`, `gates/p5.md:22`; `tech-spec.md` Testing strategy; `PROJECT-PLAN.md:230,255-256`; `frontend/src/test/App.test.tsx:9-11` | Either add the E2E harness (WS-8) and re-close P4/P5 against it, or amend the gate records to say "component tests" and add E2E to the P6 known-limitations table. Do not leave the records as written. |
| G-02 | High | P2 is Complete but its measurement service is 44 % covered. Uncovered: candidate source-snapshot construction (only reached when a run has candidates), outcome-link validation, metrics computation. The PostgreSQL test that exercises them skips without `P1_DATABASE_URL`. | `services/recommendation_measurement_service.py:92-117,236-276,331-354`; `tests/integration/test_recommendation_measurement_postgres.py:24` | Add SQLite-runnable unit tests for runs with candidates, both outcome-link branches, and metrics; make the PostgreSQL job visibly run in CI (WS-1). |
| G-03 | High | The product surface still contains the cookiecutter demo: root `/ratings` (free-text LLM scoring, API-key auth), root `/fragrances` (3 hard-coded entries), the Postman suite that asserts on them, and an app description advertising an "LLM-powered rating endpoint". Tech-spec says legacy routes "must be inventoried before removal" but no milestone owns it. | `api/ratings.py`, `api/catalog_stub.py`, `middleware/auth.py`, `main.py:81-92,162-165`, `docs/api/postman-collection.json`, `.github/workflows/postman-api-tests.yml`, README line 37 | Owner decision Q1, then WS-4. |
| G-04 | Medium | Documentation sprawl: `docs/ADRs/` (template) beside `docs/planning/adr/` (real); three roadmap-like pages; `concept.md` (642 lines, original concept, contradicts vision v2) at repo root; `CONFIG_TEMPLATES_SUMMARY.md` referencing a cookiecutter path; README of 736 lines with about 10 lines of product overview and about 150 lines of Assured OSS/GCP material the project does not use. `.markdownlintignore` exempts 20 of the most-read files. | Repo root; `.markdownlintignore`; `mkdocs.yml` nav | WS-11. |
| G-05 | Medium | `CLAUDE.md` misleads agents: its Project Structure omits `api/`, `services/`, `models/`, `schemas/`, `llm/`, `jobs/`, `alembic/`; it instructs "address ALL type checker warnings" while 184 exist; it assigns work to `mcp__zen__*` agents that `.mcp.json` does not configure. | `CLAUDE.md` Project Structure and Supervisor sections; `.mcp.json` | WS-11. Regenerate the structure section from the tree; state the real warning policy. |
| G-06 | Medium | CI is template-scale: 21 workflows including PyPI publishing and semantic release for a self-hosted app, a Python 3.10-3.14 matrix while the tech-spec fixes 3.12, FIPS, SLSA, SBOM, mutation testing. `requires-python = ">=3.10,<3.15"` contradicts the declared target. The primary gate is an external reusable workflow whose contents are not reviewable here. | `.github/workflows/*`, `pyproject.toml:13`, `ci.yml:33` | Owner decision Q9. Record what the reusable workflow runs (S-22). Consider retiring publish and compatibility workflows. |
| G-07 | Low | Template residue in the runtime package: `jobs/` documents an ARQ worker that does not exist; `cli.py` keeps `hello` and `config` demo commands; `utils/financial.py` is a docstring. | `jobs/__init__.py`, `cli.py:586-640`, `utils/financial.py` | WS-4. |
| G-08 | Low | P6 evidence pages carry `status: published` front matter and sit in public navigation while every cell reads "Pending". | `docs/planning/evidence/p6-*.md` | Mark them `draft` until filled, or keep them out of nav until P6 closes. |
| G-09 | Low | `ruff format --check .` (the command in CLAUDE.md Quick Start) fails on 12 Markdown files because ruff 0.16 formats fenced Python; the pre-commit hook pins the old scope. The documented command and the enforced hook disagree. | `.pre-commit-config.yaml:68-75` | Document the hook scope or pass `--extension` filters in CLAUDE.md. |
| G-10 | Medium | `SECURITY-FINDINGS.md` is materially stale: it asserts no auth code exists in `src/` and cites `core/sentry.py`, which is not in the tree. `docs/known-vulnerabilities.md` says no active ignores while `pyproject.toml` still ignores `PYSEC-2022-42969` with a reassessment date two months past. | `SECURITY-FINDINGS.md:121,136-142`; `pyproject.toml:747-753`; `docs/known-vulnerabilities.md:22-31` | Supersede `SECURITY-FINDINGS.md` with a short re-verification against real `src/`; remove the stale ignore (S-14). |
| G-11 | Medium | Two merge-gate definitions disagree: `scripts/setup_github_protection.py` requires check contexts no workflow emits, while workflow comments say an org ruleset with bare names is authoritative. | `scripts/setup_github_protection.py:160-186`; `ci.yml:48-54`; `pr-validation.yml:37,73,107` | Owner decision Q8; delete or correct the script. |

### 4.2 Trust boundary and authorization

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| S-01 | Critical | nginx forwards `X-Authentik-Username/Uid/Email` verbatim from the client (`$http_x_authentik_*`), and the backend trusts them unconditionally. Only Traefik's forward-auth stripping, configured in an external repository, prevents spoofing. Anything on the `authenticated-edge` or internal network can present a forged manager identity. | `frontend/nginx.conf:56-67`; `core/auth.py:73-96`; `docker-compose.prod.yml:70-74`; ADR-008 | WS-2: reset the three headers in nginx unless the peer is Traefik; record the exact Traefik middleware in `docs/deployment/`; add a P1.6 test that forges the header from a sibling container. Longer term, verify a signed identity (Authentik JWT) in `core/auth.py` so trust does not depend on out-of-repo config. |
| S-02 | High | uvicorn runs without `--proxy-headers`, so `request.client.host` is always the nginx container. The slowapi limiter therefore keeps one bucket for the whole household, and HSTS is never emitted because the scheme is always `http`. | `Dockerfile:89`; `middleware/rate_limit.py:79`; `frontend/nginx.conf:60-61` | WS-2: add `--proxy-headers --forwarded-allow-ips=<frontend network>`; key the limiter on the verified username; test two `X-Forwarded-For` values get distinct buckets. |
| S-03 | High | Two non-overlapping auth schemes are live. The shared `X-API-Key` alone is sufficient for the entire billed LLM surface (`/ratings` and both recommendation explanation routes) with no Authentik identity attached, so spend is unattributable. | `api/ratings.py:114`; `api/recommendations.py:168,438`; `middleware/auth.py:54-113` | Owner decision Q2; add `get_current_identity` to billed routes regardless. |
| S-05 / B-10 | High | Read routes carry no identity dependency and no per-reviewer scoping: `GET /api/v1/evaluations` (including free-text notes), `/reviewers`, `/fragrances`, `GET /api/v1/recommendations/{reviewer_id}`. `/calibration/history` enforces recorder or manager for the same data. | `api/evaluations.py:46-79`; `api/recommendations.py:107-117`; contrast `api/recommendation_measurement.py:106-118` | Owner decision Q5, then WS-2: one `authorize_reviewer` dependency applied to every reviewer-keyed read. |
| S-06 | High | Fail-closed asymmetry: calibration and measurement routes 401 on a missing username regardless of `AUTHENTIK_REQUIRED`; evaluations, fragrances, reviewers, and imports accept `username=None` and write `recorded_by=NULL`. If the flag is ever false in a serving environment those routes become anonymous writers. | `api/calibration.py:45-57` vs `api/evaluations.py:116,171` | WS-2: one `require_identity()` dependency with the fail-closed semantics for every mutating route. |
| B-11 | High | Authorization policy (`actor()`, `manager()`, allowlist lookup) lives in a router module and is imported by two other routers; `authorize_reviewer` is a third implementation of the recorder check. Three mechanisms overlap. | `api/calibration.py:45-57`; `api/predictions.py:16`; `api/recommendation_measurement.py:12,106-118`; `api/calibration.py:491-498` | WS-2: move all of it into `core/auth.py` as dependencies. |
| S-17 | Medium | CORS defaults are development origins with `allow_credentials=True` and `allow_headers=["*"]`; no compose file sets `CORS_ALLOWED_ORIGINS`, so production runs the dev allow-list. | `core/config.py:25-29`; `middleware/security.py:434-442`; `docker-compose.prod.yml:19-24` | Set the real host (or empty, since nginx makes the API same-origin) in the prod override; have the topology validator reject `localhost` origins. |
| S-18 | Medium | `Settings` has no `environment` field, so `ENVIRONMENT=production` is silently discarded; `/docs`, `/redoc`, `/openapi.json` are always on; nothing in the app can behave differently in production. | `main.py:100-101`; `core/config.py`; `docker-compose.prod.yml:20` | Add the field; gate docs routes, HSTS, and CORS defaults on it (pairs with S-20 and S-27). |
| S-19 | Medium | `calibration_admin_usernames` lacks the `NoDecode` treatment given to CORS, so a comma-separated value crash-loops the container at import. This is the manager allowlist. | `core/config.py:250-253` vs `:289-338`; `.env.example:182-184` | Apply the same validator; test both shapes. |
| S-23 | Medium | No app-level test exercises the forward-auth boundary: `conftest.py` disables it globally, so the 401 and manager 403 paths are never hit by default. | `tests/conftest.py:29`; `core/auth.py:85-96` | WS-2: a test module with `authentik_required=True` asserting 401 on every mutating route and the manager/recorder matrix. |
| B-27 | Medium | `TrustedHostMiddleware` is never registered (`allowed_hosts` not passed), so the Host header is unvalidated. | `main.py:158`; `middleware/security.py:426-431` | Add a `TRUSTED_HOSTS` setting. |
| S-25 | Low | Correlation IDs are taken verbatim from request headers with no length cap or format check and echoed into logs. | `middleware/correlation.py:217-247` | Validate against a UUID or hex pattern; generate a fresh ID otherwise. |

### 4.3 Blind disclosure and audit

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| B-01 | High | A participant-reachable 409 body says "feedback is unavailable for a holdout version". ADR-005 forbids exposing membership role. | `services/recommendation_measurement_service.py:195`; `api/recommendation_measurement.py:234-235` | WS-3: role-neutral message; log the real reason server-side; audit every raise string reachable by a participant. |
| B-02 | High | Holdout oracle: the explain route returns 404 for a catalog fragrance that is one of the caller's holdouts, and the catalog is separately listable, so the 404 reveals holdout membership. | `api/recommendations.py:296-306` | WS-3: only allow explanation of a persisted impression id (the shape `/impressions/{id}/explanation` already has), or make the two 404s indistinguishable. |
| B-03 | High | No audit or security logging on the calibration, prediction, or measurement surfaces; the manager-only mapping route writes no record of retrieval. | `api/calibration.py:432-460`; `log_audit_event` absent from those routers | WS-3: audit activate, enroll, lock, reveal, mapping retrieval, checkpoint, prediction create and link; test that mapping logs actor and enrollment but never identity. |
| B-26 | Medium | `Cache-Control: private, no-store` is an allowlist of path prefixes; `/recommendations`, `/evaluations`, `/predictions`, `/reviewers` get no directive and no `Vary`. | `middleware/security.py:66-79` | Invert: no-store by default under the API prefix, opt out for the public catalog. |
| F-15 | Medium | Two places where the client, not the server, decides what is safe: `CalibrationPage` routes blind vs post-reveal entry from the presence of `sample.identity`; `RecommendationsPage` pulls the reviewer's full controlled history (which may include revealed identities) to fill a date dropdown. | `CalibrationPage.tsx:110-113`; `RecommendationsPage.tsx:140-143,344-357` | Carry an explicit `post_reveal_entry` flag per presentation; add a narrow linkable-outcomes endpoint. |
| S-07 | High | `setup_logging()` is never called by the API, so `JSON_LOGS`, `LOG_LEVEL`, and the correlation processor are inert in production. Audit events still fire but ordinary logs are uncorrelated console output. | `main.py` (no call); `utils/logging.py:33-132,203-207`; `docker-compose.prod.yml:21-22` | WS-10: call it in `lifespan`; test that a JSON record carries `correlation_id`. |
| S-15 | Medium | No secret-redaction processor in structlog; API keys are plain `str`, not `SecretStr`. | `utils/logging.py:92-105`; `core/config.py` | Convert keys to `SecretStr`; add a redaction processor. |

### 4.4 Product identity, dead code, and deprecated paths

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| B-21 | Medium | Two LLM stacks: `services/llm_service.py` (OpenRouter, config-driven) and `llm/client.py` (`claude-3.5-sonnet`, reads `TEST_MODE` from the raw environment, raises `RuntimeError` unconditionally outside test mode). `POST /ratings` therefore returns 503 in every real deployment, and is unreachable through nginx anyway because it is root-mounted while nginx proxies only `/api/`. | `llm/client.py:75,92-95`; `api/ratings.py:192-198`; `frontend/nginx.conf:56-57` | Q1, then WS-4: delete the route, package, Postman suite, and API-key scheme, or rebuild them on `LLMService` under `/api/v1`. |
| B-22 | Medium | `core/cache.py` (513 lines of Redis scaffolding) is imported by nothing; `redis[hiredis]` is a hard dependency because of it; the lifespan never opens or closes it. | `core/cache.py`; `pyproject.toml:149,156`; `main.py:60-76` | Q3, then WS-4: delete it and the dependency, or make it the real shared cache. |
| B-23 | Medium | `jobs/` references a missing worker module; `api/health.py` carries two never-called checks and a 40-line Kubernetes YAML docstring; `HealthStatus.version` and `cli.py` hard-code `"0.1.0"` separately from `settings.version`. | `jobs/__init__.py`; `api/health.py:140-196,253,256,51`; `cli.py:110` | WS-4. |
| B-24 | Medium | `ParfumoScraper` (largest module) is deprecated by ADR-012 but carries no flag, warning, or gate, still writes `data_source="parfumo"`, keeps its CLI commands, and is a synchronous `httpx.Client` with `time.sleep()` inside the async service package. `CalibrationService` still depends on Parfumo-written GTIN evidence. | `services/parfumo_scraper.py:228,311,401,1253`; `cli.py:188-190,294-296`; `services/calibration_service.py:100-157` | Q4, then WS-4: flag-gate behind `PARFUMO_INGESTION_ENABLED=false`, emit a deprecation warning, and move GTIN evidence into the ADR-012 `SourceSnapshot` contract before removal. |
| B-30 | Low | Root-mounted `/fragrances` stub shadows the conceptual namespace of `/api/v1/fragrances`. | `api/catalog_stub.py`; `main.py:162-165` | WS-4. |
| F-04 / F-22 | High | The generated-client script has never been run (`src/client/` does not exist, pre-excluded from lint and coverage), `@hey-api/openapi-ts` is an unused devDependency, and the undocumented `js-yaml` major-version override exists to serve it. | `frontend/package.json:18,27,47-49`; `eslint.config.js:8`; `vite.config.ts:38` | Q6, then WS-6 or delete both. |
| B-34 | Low | Real family member names are a module constant seeded through an API route. | `services/reviewer_service.py:20`; `api/reviewers.py:121-135` | Move to configuration. |

### 4.5 Backend layering, transactions, and error handling

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| B-04 | High | No single transaction owner: `get_db` commits at request end, three services only flush, one service commits mid-request, two routers commit directly, and `append_response` calls `rollback()` on the shared request session. Multi-step workflows are atomic by accident. | `core/database.py:56,74`; `services/recommendation_measurement_service.py:131,211,216,491`; `api/recommendations.py:255,421`; `api/imports.py:76` | WS-5: services never commit; `get_db` owns the unit of work; use `begin_nested()` where a partial failure must be contained. |
| B-05 | High | The ADR-009 "no checkpoint after any holdout response" gate is a read-then-write in the router; it is sound only because `service.enrollment()` happens to hold a row lock, which nothing documents or enforces. | `api/calibration.py:410-419`; `services/calibration_service.py:301-313` | WS-5: move checkpoint creation into the service directly after the locked fetch; add a PostgreSQL concurrency test. |
| B-07 | High | `core/exceptions.py` (418 lines) has no handler registered; only two services use it; a `DatabaseError` from `FragranceService.create` surfaces as an unhandled 500. | `core/exceptions.py`; `main.py:136` (only handler is `RateLimitExceeded`) | WS-5: register one `ProjectBaseError` handler emitting the documented error contract. |
| B-08 | High | Services import FastAPI: `calibration_service.reject()` raises `HTTPException` and is re-exported into the router; `fragrance_service` raises raw 409s. HTTP status is a service concern and the services cannot be reused by the CLI. | `services/calibration_service.py:9,37-39`; `services/fragrance_service.py:8,210-213,253-256` | WS-5: domain exceptions mapped once at the router boundary. |
| B-09 | High | `api/calibration.py` is a second service layer: program activation, skin-plan selection and finalization, and `ModelCheckpoint` construction happen in route bodies with hand-written queries and eight ORM imports. | `api/calibration.py:12-23,247-260,369-392,402-429` | WS-5: `activate()`, `plan_skin()`, `finalize_skin_plan()`, `create_checkpoint()` on the service. |
| B-16 | Medium | `_get_or_create_note` is read-then-insert against a unique column with no `IntegrityError` handling; concurrent creates 500. | `services/fragrance_service.py:262-281` | Savepoint plus catch-and-reselect, as `kaggle_importer.py` already does. |
| B-17 | Medium | `assert` used for control flow in request paths (16 sites); `S101` is ignored globally, not only for tests. Under `python -O` these become `AttributeError`. | `api/calibration.py:157,215,219,224,293,294,443,445,523`; `services/calibration_service.py:97,169,310,337,339,356,420`; `pyproject.toml:306` | Replace with explicit raises; scope the ignore to `tests/**`. |
| B-15 | Medium | Unbounded `select(Enrollment)` and `select(Program)` filtered in Python by recorder membership after every row is read. | `api/calibration.py:71-78,279-290` | Push the recorder filter into SQL; add limits. |
| B-14 | Medium | `get_recommendations` loads the entire live catalog with eager relationships and scores in Python; `_contributions` issues one query per controlled version; `api/calibration.py` has three more N+1 loops. Tech-spec budget is 500 ms p95. | `services/recommendation_service.py:299-306,436-482`; `api/calibration.py:156,291-292,442-445` | Batch the controlled-version fetch; joined loads for calibration; prefilter candidates before the catalog grows. |
| B-25 | Medium | Kaggle import reads the whole upload into memory with no size limit. | `api/imports.py:394-397` | Stream with a configured maximum; 413 on overflow. |
| B-29 | Low | Package cycle `utils -> middleware -> utils`, papered over by function-local imports. | `utils/logging.py:110,207`; `middleware/security.py:36` | Move correlation context-vars into `core/`. |
| B-33 | Low | `EvaluationResponse` is hand-built field-by-field four times; a new column will be silently omitted from some responses. | `api/evaluations.py:65-79,94-107,180-193,251-264` | `model_validate(obj, from_attributes=True)` as `api/predictions.py` does. |
| B-35 | Low | Three service modules use stdlib logging instead of the structlog wrapper, so their output has no correlation id. | `services/parfumo_scraper.py:40`; `services/kaggle_importer.py:32`; `services/fragella_lookup_service.py:31` | Standardize. |
| B-31 | Low | A `#CRITICAL` comment in `api/recommendations.py` is truncated mid-sentence and orphaned 165 lines from the route it describes. | `api/recommendations.py:268-270` vs `:435-455` | Restore it on the route. |

### 4.6 Scoring, provenance, and LLM contracts

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| B-12 | High | The algorithm version label is declared by a consumer (`RecommendationMeasurementService.ALGORITHM_VERSION = "affinity-v1"`) while the weights, veto threshold, `(liking-5)/2.5` map, sigmoid clamp, and subfamily factor are unversioned constants in `recommendation_service.py`. A weight change produces different frozen checkpoints under the same label, which ADR-009 exists to prevent. | `services/recommendation_measurement_service.py:49`; `services/recommendation_service.py:35-49,236,311,388-389` | WS-5: version and tunables live with the algorithm; a test fails when a tunable changes without a version bump. |
| B-13 / F-05 | High | The primary recommendation response has no `score_type`; it exposes `match_score` and `match_percent` only, while the measurement surface carries `score_type="uncalibrated-affinity"`. ADR-007 requires schemas to identify score type. The frontend types also drop `algorithm_version`, `candidate_strategy`, `score_type`, and `score_value`, so the UI shows only a percentage. | `api/recommendations.py:44-57`; `frontend/src/api/types.ts:221-237` vs `schemas/recommendation_measurement.py:65-85` | Add `score_type` to `RecommendationResponse`, rename display fields to affinity terms, and surface version, strategy, and score type on the run header and card. |
| B-06 | High | The explanation cache is per-process; invalidation fires at flush time (before commit) so a concurrent read can repopulate stale data; `CalibrationService.observe()` never invalidates; under `REPLICAS>1` invalidation is invisible across replicas, and the compose warning mentions only the rate limiter. | `services/llm_service.py:157,164,576-583`; `services/calibration_service.py:345-412`; `docker-compose.prod.yml:26-35` | Q3, then invalidate after commit, add it to `observe()` and `lock_stage()`, and either share the cache or document single-replica as a hard invariant. |
| B-19 | Medium | The cache key omits model and prompt version; changing either silently serves old explanations while `LLMInvocation.prompt_version` records the new one. | `services/llm_service.py:197-199,290,32-33` | Include both in the key. |
| B-18 | Medium | `estimated_cost_usd` is hard-coded `None` at both call sites; the OpenRouter payload does not request usage accounting; cache hits are recorded with `provider_cost_usd=0.0`, deflating cost. ADR-003's cost target cannot be measured. | `api/recommendations.py:248,415`; `services/llm_service.py:200-209,291-300,361-366` | Price table at invocation time; request usage in the payload; `NULL` cost on cache hits. |
| B-20 | Medium | The 11-field `LLMInvocation` telemetry record is built and committed inline in two route bodies. | `api/recommendations.py:239-255,405-421` | Move into `LLMService`. |
| B-28 | Low | `Evaluation.rating` has no DB `CheckConstraint` for 1-5, and `RATING_WEIGHTS.get(rating, 0.0)` silently maps a bad value to neutral. | `models/evaluation.py:84`; `services/recommendation_service.py:269` | Add the CHECK in a migration; raise on unknown ratings. |
| B-32 | Low | Unknown `primary_family` and `subfamily` are handled asymmetrically in profile building versus scoring. | `services/recommendation_service.py:234-236,362-363` | One sentinel, handled identically on both sides. |
| S-28 | Low | Model-name drift: `config.py` defaults to `claude-3-haiku`, `.env.example` and the OpenAPI description say `claude-3.5-sonnet`; compose comment says replicas default 2 while the override defaults to 1. | `core/config.py:416`; `.env.example:63`; `main.py:86-87`; `docker-compose.yml:15-18` | Reference `settings.openrouter_model`; fix the comment. |

### 4.7 API contract and frontend architecture

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| F-03 | High | All 19 calibration operations return `dict[str, object]`, so OpenAPI emits `additionalProperties: true` and there is no machine-checkable contract for the participant disclosure allowlist. | `api/calibration.py:61,68,139,274,284,331,433`; `docs/api/openapi.json` | WS-6: Pydantic response models (`AccessView`, `AssignmentView`, `ParticipantEnrollmentView`, `PresentationView`, `ObservationView`, `ProgramMemberView`, `ManagerEnrollmentView`, `MappingRowView`) with `response_model=` so FastAPI enforces the allowlist. |
| F-06 | High | `ProgramSetupPage.tsx` is a 707-line component with 10 state hooks, 12 API calls, and 5 forms covering definition, membership, enrollment, operations, mapping, labels, metrics, export, and events. `RecommendationsPage` nests a 150-line IIFE inside a `.map()`. | `pages/ProgramSetupPage.tsx:58-707`; `pages/RecommendationsPage.tsx:235-404` | WS-7: split into feature components under `pages/programs/`; hoist a `RecommendationCard`. |
| F-07 | High | Routing is a 47-line path switch with no params and no 404; unknown paths render Home under the wrong URL; selected assignment, sample, stage, program, and enrollment live only in component state, so reload loses the participant's place. P3 requires reload state; P4 requires resuming the next valid step. | `routing/routes.ts:22-28`; `CalibrationPage.tsx:29-34`; `ProgramSetupPage.tsx:59-68` | WS-7: typed param segments plus a validated not-found route, or adopt a router library. |
| F-08 | High | No cache invalidation across pages or after most mutations: `enroll()` does not reload, reveal refreshes manager state but not `useAppData`, saving an encounter never invalidates recommendations or explanations. | `ProgramSetupPage.tsx:147-159,181-185`; `RatingsPage.tsx:47-67`; `hooks/useAppData.ts:19-44` | WS-7: a keyed store with explicit invalidation after each mutation. |
| F-09 | High | Capability is derived once at mount and never re-verified; there is no 401 interceptor, so an expired session keeps rendering manager UI while every request fails. | `hooks/useAppData.ts:46-55`; `api/client.ts:29-30` | WS-7: 401 interceptor clearing access state; re-fetch access on focus or 403. |
| F-11 | High | The axios mock hard-codes `isAxiosError: () => false`, so the entire user-facing error-message branch tree is dead in every component test; `delete` and `put` are not mocked at all. | `test/App.test.tsx:9-11`; `test/api-client.test.ts:11-18`; `api/client.ts:18-32` | WS-8: MSW or a real adapter so real error objects flow. |
| F-13 | Medium | The "automated accessibility baseline" checks labelled controls, button text, unique ids, and four landmarks on two routes. No axe, no `jsx-a11y`, no 360 px assertion, no keyboard traversal. | `test/accessibility.test.tsx:15-24,40-60`; `eslint.config.js:16-19`; `gates/p3.md:26` | WS-8: `vitest-axe` over every route; `eslint-plugin-jsx-a11y`; a 360 px layout assertion. |
| F-12 | Medium | Five pages have zero dedicated test files; all coverage comes from one 986-line `App.test.tsx`. | `frontend/src/test/` | WS-7 alongside the split. |
| F-16 | Medium | Non-null assertions on `reveal_blocker` render "Reveal unavailable: undefined" when the server returns `null`. | `ProgramSetupPage.tsx:523,532`; `api/types.ts:154` | Total helper; ban `!` via lint. |
| F-17 | Medium | `explain()` swallows every error and renders a fabricated fallback, so an expired session is indistinguishable from OpenRouter being down; the 10 s global timeout makes that path routine. | `RecommendationsPage.tsx:146-159`; `api/client.ts:14` | Narrow the catch; per-request timeout. |
| F-18 | Medium | `useTask` shares one busy/error/notice triple per page; any background refresh wipes a validation error; `run` is not memoized (hence an `exhaustive-deps` suppression). | `hooks/useTask.ts:4-25`; `ProgramSetupPage.tsx:76-89` | Per-action task state; `useCallback`. |
| F-19 | Medium | Home issues one enrollment fetch per assignment purely to count locked presentations, each returning every presentation and observation. | `HomePage.tsx:29-56` | Server-side progress summary on the assignment list. |
| F-20 | Medium | Encounter history looks up fragrance names in the catalog search results; without a prior search every row reads "Saved fragrance". `EvaluationResponse` carries no name. | `RatingsPage.tsx:200-202`; `schemas/evaluation.py:133-151` | Add `fragrance_name` and `fragrance_brand` to the response. |
| F-21 | Medium | `?recommendation_run=` is written with raw `replaceState` outside `routing/` and follows the user onto every other route. | `RecommendationsPage.tsx:14-25`; `routes.ts:39-44` | Typed per-route search schema in `routes.ts`. |
| F-24 | Low | No React error boundary; any render throw blanks the app. | `main.tsx:6-10` | Boundary rendering `ErrorState` with retry. |
| F-25 | Low | `App.css` is 511 flat lines with 20 raw hex literals, zero custom properties, no dark mode, duplicated breakpoints. Family phones default to dark mode. | `App.css`; `index.css` | Token block; `prefers-color-scheme`. |
| F-26 | Low | ESLint is non-type-aware, `ecmaVersion` 2020 against an ES2022 target, no `jsx-a11y`; the `@/` alias is configured and used zero times; `setup.ts` redefines `import.meta.env`. | `eslint.config.js:10-13`; `tsconfig.app.json`; `test/setup.ts:4-10` | `recommendedTypeChecked`; align versions; delete the alias. |
| F-23 | Low | Frontend Dockerfile: deprecated `--only=production=false`, a `development` stage wedged between `builder` and `production` protected only by a comment, and full source maps published from nginx. | `frontend/Dockerfile:15,40-57,62-70`; `vite.config.ts:29` | `--include=dev`; reorder stages; hidden or no source maps. |

The full contract-drift table (14 rows) is in Appendix A.

### 4.8 Testing and CI truthfulness

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| S-11 / F-01 | Critical | No workflow in this repository lints, type-checks, tests, or builds the frontend as a blocking check; it is compiled only inside the paths-filtered `docker-publish.yml`, whose Trivy gate is off. A frontend build break reached `main` (`370c82f`). | `.github/workflows/` (no node job); `docker-publish.yml:92-113` | WS-1: a `frontend` job on every PR: `npm ci`, lint, typecheck, `test:coverage` with a floor, build. Required context. |
| S-09 | High | The 80 % coverage gate omits `api/*`, `llm/*`, and `main.py`, the layer where every auth dependency, role check, and rate-limit decorator is wired. The stated justification (Postman covers it) is not true for the v1 API. | `pyproject.toml`, `[tool.coverage.run] omit`; `codecov.yml:17-34` | WS-1: remove the omission; if coverage drops, that is information. |
| F-10 | High | No end-to-end tests (see G-01). | See G-01 | WS-8. |
| S-10 | High | Container CVE gates are disabled on both scan paths with comments deferring to "when containers are shipped"; P6 is in progress. | `container-security.yml:49-53`; `docker-publish.yml:87-90,110-113` | WS-1: fail on CRITICAL and HIGH before the P6 decision; record accepted base-image CVEs per the 60-day policy. |
| S-22 | Medium | Every substantive Python gate is delegated to an external reusable workflow; `docker-publish.yml` pins a different SHA from the other 12 callers. Whether PostgreSQL integration tests run is not visible here. | `ci.yml:33`; `docker-publish.yml:72,99` | Vendor a `docs/ci-gates.md` naming what each reusable workflow runs and blocks; refresh on SHA bumps. |
| S-29 | Low | `container-security.yml` paths filter covers only the backend `Dockerfile`; the frontend image is scanned only on the non-blocking publish path. | `container-security.yml:10-23,44` | Add frontend paths and a matrix entry. |
| S-26 | Low | `.semgrep.yml` is a single INFO placeholder rule and no workflow runs semgrep, though CLAUDE.md lists it among the scanners whose findings must be addressed. | `.semgrep.yml:5-23` | Point at real rulesets and add a job, or delete the file. |
| S-30 | Low | `[tool.bandit] exclude_dirs` contains `scripts`, defeating the `bandit-full` hook's explicit script argument. | `pyproject.toml:687-700`; `.pre-commit-config.yaml:124-134` | Drop the exclusion. |

### 4.9 Data model and migrations

Verified in this session: `alembic upgrade head` completes on a throwaway PostgreSQL 16 database,
and a reflection diff against `Base.metadata.create_all` shows zero differences in tables,
columns, types, nullability, server defaults, primary keys, unique constraints, foreign keys, and
all 41 CHECK texts. The only divergence is six index names (D-11). That parity is a real asset; the
findings below are about the tooling that will erode it and the guarantees the spec claims but the
schema does not enforce.

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| D-01 | Critical | `SourceSnapshot` has five columns and records none of the eight provenance items tech-spec D1 requires (source identifier and revision, content hash, license or permission evidence, parser version, verification reviewer, exclusions) nor any of the ADR-012 amendment fields (`source_type`, `permission_state`, `fields`, `source_reference`, nullable `source_url`). `source_url` is `NOT NULL`, so a manufacturer email reply cannot be recorded at all. The only writer is the deprecated Parfumo scraper. | `models/calibration.py:260-271`; `tech-spec.md` D1 contract; ADR-012; `services/parfumo_scraper.py:1315-1323` | WS-9: the ADR-012 migration (four columns, an "at least one of url or reference" CHECK, backfill to `excluded_legacy`), plus `content_hash` and `parser_version` in the same pass. |
| D-02 | High | `evaluations.rating` (1-5), `longevity_rating`, and `sillage_rating` have no database CHECK; the scale exists only in Pydantic. `calibration_observations` carries 17 range CHECKs. This is the highest-volume evidence table and the one whose raw scale the spec promises to preserve. | `models/evaluation.py:84,88-89`; contrast `models/calibration.py:143-174` | WS-9: named range CHECKs matching the existing `ck_<table>_<rule>` pattern. |
| D-03 | High | `Base` has no `naming_convention`, and 37 of 41 CHECK constraints are unnamed in the ORM. Against a correctly migrated database, `alembic revision --autogenerate` proposes 37 spurious `DROP CONSTRAINT` operations plus 4 index drops and 2 adds. A future agent who trusts autogenerate deletes every range CHECK on observations. The four CHECKs named identically on both sides are matched correctly, which proves naming is the whole fix. | `core/database.py:16-17`; `models/calibration.py:137-142` (unnamed) vs `:185-188` (named) | WS-9: set `naming_convention` on `Base.metadata`; one migration renaming the 37 constraints. Until then, never run autogenerate without deleting every `drop_constraint` it emits. |
| D-04 | High | `alembic/env.py` passes no `compare_type`, `compare_server_default`, `render_as_batch`, or `include_object`, so autogenerate misses type and default changes and emits operations that cannot run on SQLite, the engine every migration test uses. | `alembic/env.py:67-72,84` | WS-9: add the three flags to both `configure()` calls and an `include_object` for the legacy indexes. |
| D-05 | High | No test runs the migration chain or asserts ORM metadata equals the migrated schema. Each "migration" test builds the pre-migration state by running the current `create_all` and hand-reverting it with raw SQL, so it is tautological with respect to drift. | `tests/integration/test_calibration_migration.py:27-46`; `test_ml_prediction_snapshots_migration.py:57-90`; `test_worn_by_reviewer_migration.py:25-55` | WS-9: one test that runs `alembic upgrade head` on PostgreSQL 16 and asserts `compare_metadata(ctx, Base.metadata) == []`. Highest-leverage single change in this section. |
| D-06 | High | No PostgreSQL service in any workflow in this repository; the one PostgreSQL-gated test skips unless `P1_DATABASE_URL` is set, a variable that appears nowhere else. Untested PostgreSQL-only behavior: partial index predicates, `SELECT ... FOR UPDATE` (nine call sites), `gen_random_uuid()`, JSON semantics, FK enforcement, server defaults. | `.github/workflows/` (no `postgres`); `tests/integration/test_recommendation_measurement_postgres.py:20,24` | WS-1: a `services: postgres:16` job in this repository running `alembic upgrade head`, the D-05 parity test, and `-m integration`. |
| D-07 | High | No shared SQLite fixture issues `PRAGMA foreign_keys=ON`, so every `ondelete=RESTRICT` guard (the ADR-011 mechanism, checkpoint, observation, membership, and prediction protection) is unexercised by the unit suite. | `tests/conftest.py:223-235,252-260,372-381`; the one exception at `tests/unit/test_models/test_reviewer.py:52` | WS-9: an engine `connect` listener issuing the pragma; expect some tests to start failing, which is the point. |
| D-08 | High | None of the five immutability guarantees (append-only observations, frozen checkpoint manifests, immutable activated membership, frozen prediction snapshots, immutable assigned identity) is enforced at the database level. They rest on absent routes, service `if` statements, and one `@validates` hook whose docstring concedes it cannot see another transaction's write. | `api/calibration.py` (no PATCH or PUT); `services/calibration_service.py:161-162`; `models/prediction.py:148-177`; `services/fragrance_service.py:194-212` | Q14; then either `BEFORE UPDATE` triggers or a `REVOKE UPDATE` on an app role for the frozen tables and columns, or a tech-spec caveat stating enforcement is service-level. |
| D-09 | Medium | `evaluations` is the only evidence table still carrying `ON DELETE CASCADE` (to both `fragrances` and `reviewers`); every table since `c731b42e9a01` uses `RESTRICT`. A hard delete by an operator or repair script silently destroys encounter history. | `models/evaluation.py:78-83` | Q17; change both to `RESTRICT`. Soft delete is already the only API path. |
| D-10 | Medium | Nine FK columns have no index, all `RESTRICT`, two on hot calibration read paths (`calibration_presentations.membership_id`, `calibration_checkpoints.enrollment_id`). | Query against the migrated schema; read paths at `services/calibration_service.py:131,372-386`; `api/calibration.py:479-481` | WS-9: one migration adding the nine indexes, mirrored with `index=True`. |
| D-11 | Medium | Four legacy `idx_*` indexes exist only in migrations and two `ix_*` indexes exist only in the ORM, duplicating two of them; test databases and production have different index sets on `fragrance_notes`. Acknowledged in a migration docstring, never fixed. | `alembic/versions/001_initial_schema.py:149-173`; `models/fragrance.py:186-191`; `b954e9888344:30-34` | WS-9: one reconciliation migration. |
| D-12 | Medium | All 22 JSON columns are `json`, never `jsonb`; no GIN index or key-level query is possible on manifests, snapshots, selection, or perceived notes. The `perceived_notes` array check is a text-prefix `LIKE '[%'` hack for that reason. | `models/calibration.py:59,74,88,185-188,234,256,257,271,311`; `prediction.py:128-129`; `recommendation_measurement.py:40-42` | WS-9: `JSON().with_variant(JSONB, "postgresql")` and an in-place type migration, cheap before F1 data exists. |
| D-13 | Medium | Six of the seven "Required Before Baseline" items in the gap analysis are still open: familiarity as a controlled code, `perceived_notes` normalization against `Note`, `brands` and `accord_types` lookups, typed sample provenance, `training_eligibility`. `Membership.selection` is an untyped dict while P1.1 requires physical-sample confirmation before assignment. | `models/calibration.py:59,207,234-236`; `data-model-gap-analysis.md:568-579`; ADR-010 | Sequence sample provenance and training eligibility before F1, since they become backfills once pilot data exists. |
| D-14 | Medium | `data-model-gap-analysis.md` is stale: its summary list carries no status markers, and it contains no mention of `worn_by`, ADR-011, ADR-012, ADR-013, or `fragella_lookups`. | `data-model-gap-analysis.md:3,55-57,568-579` | WS-11: bump to v1.1 with status markers and the new tables; add the ADR-012 provenance gap as a P0-class row. |
| D-15 | Medium | Enum-shaped values are bare strings with no CHECK: `Program.status`, `Membership.role`, `Observation.stage` and `phase`, `SourceSnapshot.verification_status`, six `Fragrance` fields, `score_type`, `operation`, `predicted_scale`. `Membership.role = 'HOLDOUT'` is the leakage-prevention mechanism; a typo makes a holdout trainable. | `models/calibration.py:38,54,194,195,269`; `fragrance.py:82-90,192`; precedent at `recommendation_measurement.py:78-81,147` | WS-9: `IN (...)` CHECKs at least for role, status, stage, phase, following the existing `event_type` pattern. |
| D-16 | Medium | Every timestamp is `timestamp without time zone` and Python strips tzinfo, but five columns also have `server_default=func.now()`, which PostgreSQL converts using the session `TimeZone`. A non-UTC database container silently mixes two clocks in `evaluated_at`. | `utils/timestamps.py:36`; `models/fragrance.py:95-100`; `evaluation.py:91-96`; `reviewer.py:62-64` | Q16; at minimum `now() AT TIME ZONE 'utc'` defaults and a startup assertion that `TimeZone` is UTC; document in the tech-spec. |
| D-17 | Medium | Revision ids are inconsistent (`001`, hand-typed sequential hex patterns) and a hand-typed id was used by two PRs at once and had to be renamed in both. Table-name prefixes are inconsistent. | `alembic/versions/001_initial_schema.py:23`; `9ded7f54996c:30-36`; `2c341c369192:9-13` | Require `alembic revision` in CONTRIBUTING; keep the graph-integrity test; leave table names. |
| D-18 | Medium | Tech-spec migration and recovery requirements (record live revision and row inventory, idempotent backfills with dry-run collision reports, rehearsed restore) have no script; they exist only as prose in the readiness runbook. | `tech-spec.md` Migration and recovery; `scripts/`; `docs/deployment/p1-release-readiness.md:51-70,113-116` | WS-10: `scripts/pre_migration_inventory.py` and `scripts/verify_restore.py` as P1.2, P1.3, and P1.5 evidence generators. |
| D-19 | Medium | Four revisions raise on downgrade and one of them is eighth in the chain, so nothing can be downgraded past it. This is deliberate policy (restore, not downgrade) but no test asserts the raise and no README states it; an operator discovers it mid-incident. | `c731b42e9a01:224-230`; `e4b1c2d3f4a5:174-177`; `9ded7f54996c:360-367`; `72fe56efd128:130-137`; ADR-010:104-107 | WS-9: a test asserting the four raises; a statement at the top of `alembic/README` and in the runbook. |
| D-20 | Low | `5d2e7c9f9c92` is PostgreSQL-only (`gen_random_uuid()`, non-batch PK drop), so the chain cannot replay on SQLite at all; that is why the migration tests fake their pre-state. | `alembic/versions/5d2e7c9f9c92:49-54` | Document in `alembic/README`; wrap new migrations in `batch_alter_table`. |
| D-21 | Low | Soft-delete filtering is applied per query across 66 references with no shared helper, and three read paths omit it, including the reveal and mapping payload's fragrance lookup. | `services/calibration_service.py:513-516` vs `:165-168`; `fragella_lookup_service.py:117`; `kaggle_importer.py:431` | A `live(Model)` helper or `with_loader_criteria` default; decide the reveal-path question deliberately. |
| D-22 | Low | `calibration_observations` has no uniqueness; a double-POST from a flaky mobile connection produces two indistinguishable rows that both enter the frozen manifest. | `models/calibration.py:135-189`; `services/calibration_service.py:345-410` | Q18; prefer an idempotency key on `ResponseInput` over a unique index, to preserve genuine repeats. |
| D-23 | Low | All keys are `String(36)` UUID text rather than native `uuid`. Consistent, so a cost question only. | every model | Leave through F1; if ever changed, change every table in one migration. |

Required reading before writing the next migration:

- `alembic upgrade head` does not run on SQLite (D-20); test against PostgreSQL 16 or use batch mode.
- Do not trust autogenerate until D-03 and D-04 land; it proposes dropping 37 real constraints.
- Name every constraint explicitly and mirror it in `__table_args__` with the same name; the test
  database is built from metadata, not migrations.
- Follow the `9ded7f54996c` quarantine pattern for backfills: validate, leave NULL with a logged
  warning, never fabricate or abort.
- A lossy migration's `downgrade()` raises with a restore instruction, matching the four precedents.

### 4.10 Deployment and operations

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| S-04 | High | Neither compose file declares `env_file` or lists `FRAGRANCE_RATER_API_KEY` or `OPENROUTER_API_KEY` under `environment:`, so those values never enter the container; all billed endpoints fail closed with 503 in the production render. | `docker-compose.yml:21-41`; `docker-compose.prod.yml:19-24`; `core/config.py` | Q7; pass both from the secret store in the prod override; extend the topology validator to assert they are present and non-placeholder. |
| S-08 | High | `validate_production_topology.py` hard-codes `authentik@file` as the required middleware while the compose label takes `${AUTHENTIK_MIDDLEWARE:?}`; it never checks `replicas == 1`, the admin allowlist, CORS, or the API key. | `scripts/validate_production_topology.py:56-63`; `docker-compose.prod.yml:82`; `middleware/rate_limit.py:26-38` | Read the expected name from an argument; add the missing assertions; extend the existing tests. |
| S-12 | Medium | No base image is digest-pinned; the build pulls a mutable `latest` uv image; no image signing. | `Dockerfile:7,23,41`; `frontend/Dockerfile:7,20,40,70` | Digest-pin via Renovate's dockerfile manager; cosign keyless on publish. |
| S-13 | Medium | No runtime hardening on any compose service (`read_only`, `cap_drop`, `no-new-privileges`). Non-root is done well. | `docker-compose.prod.yml:4-130` | Add them in the prod override. |
| S-16 | Medium | `.env.example` ships a literal weak DB credential in `DATABASE_URL`, defeating the `${DB_PASSWORD:?}` guard the compose file relies on. | `.env.example:110` vs `:85-94,151-158`; `docker-compose.yml:27-31` | Comment it out with the same "generate, do not reuse" note. |
| S-20 | Medium | The `BUILD_ENV` build arg both compose files pass is a no-op; `ARG BUILD_ENV` exists only inside a trailing comment. Production and development images are byte-identical. | `Dockerfile:90-95`; `docker-compose.yml:12-13` | Declare it for real (with S-18) or delete it. |
| S-27 | Low | `TEST_MODE` silently replaces real LLM output with a fixture and is not refused in any environment. | `llm/client.py:22-23,78-108` | Refuse at startup when `environment == production` (after S-18). |
| Q-backups | High | Tech-spec Observability and P1.10 require backup status and schedule evidence, but no backup script, cron, or documented command exists in the repository; `p1-release-readiness.md` describes a manual `pg_dump` and `pg_restore` procedure only. | `docs/deployment/p1-release-readiness.md:51-59,113-121`; `scripts/` | Q10; add a scheduled backup with retention and a restore check to the operations runbook, or reference the host-level job. |

### 4.11 Documentation and repository hygiene

Covered by G-04, G-05, G-08, G-09, G-10, B-31, B-34, B-35, S-28. One addition:

| ID | Sev | Finding | Evidence | Recommended action |
| :--- | :--- | :--- | :--- | :--- |
| G-12 | Low | ADR-001 still describes a `backend/app/` and `frontend/` layout with `requirements.txt` and Tailwind that never existed in this form; it is marked Accepted without an amendment note for the structure. | `docs/planning/adr/adr-001-initial-architecture.md` Implementation section | Add an amendment note pointing at `docs/development/architecture.md`. |

## 5. What is well done

Remediation must not regress these.

- **Governance.** One authoritative plan with a current-state ledger tied to a commit, explicit
  status vocabulary, definitions of ready and done, a risk register, a full audit-finding disposition
  table, gate records per milestone, and evidence templates that say what cannot be proven from
  repository tests. `p1-release-readiness.md` and `p6-pilot-readiness.md` are specific and honest.
- **Domain semantics.** ADR-007 is implemented faithfully: latest live ordinary encounter per
  version, latest eligible controlled observation preferring skin, `(liking-5)/2.5`, averaging when
  both exist, one contribution per version, controlled evidence gated on reveal. Holdout, hidden
  repeat, and post-reveal exclusions are centralized in `preference_history.py`, including the
  subtle "a later non-detection does not resurrect an older liking" rule. ADR-011 is applied at all
  four required call sites.
- **Disclosure core.** `participant_view` is a real allowlist, never a serialized ORM row, and
  withholds holdout identity until that presentation's own lock. `/calibration/history` reuses it.
  Identity-scoped calibration and measurement reads send `private, no-store` with `Vary`.
- **Concurrency on the calibration path.** `with_for_update()` on program, enrollment, fragrance,
  and impression rows, with a re-refresh after lock acquisition; the SQLite unique-constraint race
  is translated to a 409.
- **Fail-closed defaults.** `authentik_required=True`, empty manager allowlist denies, missing API
  key yields 503 not open writes, `compare_digest` for the key, `${VAR:?}` guards in compose, a
  deliberately non-functional `DATABASE_URL` placeholder, and `recorded_by` always server-derived.
- **Supply chain.** Every action SHA-pinned including reusable workflows, `harden-runner` on every
  job, least-privilege `permissions`, Renovate digest pinning, automerge confined to safe updates.
- **Institutional memory.** The `#CRITICAL`/`#VERIFY` tags document real bugs that were found and
  fixed (duplicate CORS registration, the fabricated fallback score, the sigmoid overflow, the IPv6
  healthcheck, the Dockerfile stage order). `prediction_service.py` is the pattern the other
  services should converge on: domain exceptions, row locks with rationale, no FastAPI import.
- **Frontend fundamentals.** One axios instance and one error policy; generation counters guard
  four async races with tests; destructive transitions are confirmed with focus management; skip
  link, landmarks, focus-on-route-change, `aria-pressed`, reduced-motion, and print support for
  blind labels are present.
- **Health endpoints and LLM errors do not leak** dependency error strings or response bodies.

## 6. Decisions required from the owner

| # | Decision | Default if undecided | Blocks |
| :--- | :--- | :--- | :--- |
| Q1 | Does `POST /ratings`, the `llm/` package, `catalog_stub`, the Postman suite, and the `X-API-Key` scheme survive? They cannot function through the supported production path today. | Delete all five; retarget the contract suite at `/api/v1`. | WS-4 |
| Q2 | Is `X-API-Key` retained after ADR-008? Keeping it means two rotation stories. | Retire it; billed routes require an Authentik identity. | WS-2, WS-4 |
| Q3 | Cache substrate: Redis (fixes B-06, B-22, and the replica limit together) or process-local with single-replica as a documented hard invariant? | Process-local, delete `core/cache.py`, document the invariant. | WS-4, WS-5 |
| Q4 | Is ADR-012's Parfumo retirement due now, or is the scraper retained for GTIN re-verification? | Flag-gate now; extract GTIN evidence into the `SourceSnapshot` contract before deletion. | WS-4 |
| Q5 | May household members read each other's ordinary evaluation history and notes? | No; apply recorder or manager scoping to every reviewer-keyed read. | WS-2 |
| Q6 | Generated client: adopt (after typed calibration responses) or delete the script and dependency? | Adopt, after WS-6. | WS-6, WS-7 |
| Q7 | How do `OPENROUTER_API_KEY` and `FRAGRANCE_RATER_API_KEY` reach the container today? | Assume they do not; plumb via the prod override from the secret store. | WS-10 |
| Q8 | Which merge-gate definition is authoritative, the org ruleset or `setup_github_protection.py`? | The ruleset; delete the script. | WS-1 |
| Q9 | Which template workflows are wanted (PyPI publish, semantic release, 3.10-3.14 matrix, FIPS, SLSA, mutation)? | Keep SBOM and scorecard; retire publish and the version matrix; pin `requires-python` to 3.12. | WS-1 |
| Q10 | Where do backups run, and can the job be referenced from the runbook? | Add a compose-level scheduled `pg_dump` with retention and a monthly restore check. | WS-10 |
| Q11 | Should `PREVIOUSLY_REVEALED` observations appear in frozen checkpoint manifests? They are currently excluded from both training and the manifest, a stronger choice than the calibration guide states. | Include in the manifest with a phase marker; exclude from training. | ADR-009 amendment |
| Q12 | Is `POST /api/v1/import/kaggle` still a production surface, given ADR-012 places unverified Kaggle data in the excluded tier? | CLI only; remove the route. | WS-4 |
| Q13 | Re-close P3-P5 against real E2E evidence, or amend the gate records and carry E2E as a P6 known limitation? | Amend now; re-close when WS-8 lands. | WS-8, P6 |
| Q14 | Is service-level immutability (no route, an `if`, one `@validates`) the accepted design for append-only observations, frozen checkpoints, frozen predictions, and activated membership, or does the database enforce it? | Enforce with `BEFORE UPDATE` triggers on the frozen tables and columns; amend the tech-spec either way. | WS-9 |
| Q15 | Promote the ADR-012 `SourceSnapshot` extension to a P0 blocker? The gap analysis rates per-fact provenance deferrable; ADR-012, accepted three days later, names it a follow-up, and manufacturer replies have nowhere to land. | Promote; it is a D1 entry condition and cheap before F1 data. | WS-9 |
| Q16 | What `TimeZone` is the production PostgreSQL container set to? Server-default timestamps use it; Python writes UTC. | Assume unknown; add UTC defaults and a startup assertion. | WS-9 |
| Q17 | Change the two `evaluations` `ON DELETE CASCADE` foreign keys to `RESTRICT`, making any future hard-delete tooling fail loudly? | Yes. | WS-9 |
| Q18 | Is a duplicate observation submission from a flaky mobile connection a real F1 risk? | Yes; add an idempotency key before F1. | WS-9 |

## 7. Recommended workstreams

Order matters. WS-1 first, because nothing later can be verified until CI tells the truth. WS-2
and WS-3 next, because they are P6 blockers. WS-4 before WS-5, because deleting the scaffold shrinks
the refactor. WS-6 before WS-7, because the frontend split should target typed contracts. WS-8 can
run in parallel with WS-6 and WS-7 once WS-1 exists. Each workstream is one to three pull requests.

### WS-0: Decisions

Record answers to Q1-Q13 in this document's Section 6 (or an ADR amendment where noted). Time: one
review session. Nothing else should start on the items that depend on a decision.

### WS-1: Make CI tell the truth

Findings: S-11/F-01, S-09, S-10, G-02, G-06, G-11, S-22, S-29, S-26, S-30, D-06. (G-09, listed here in
an earlier draft, is `ruff format --check .` drift on Markdown files; none of the action items below
address it, and it is reassigned to WS-11 below, where Section 4.11 already groups it with the other
documentation and tooling hygiene findings.)

- Add a `frontend` job to `ci.yml` (or `frontend-ci.yml`) running `npm ci`, `lint`, `typecheck`,
  `test:coverage` with a floor equal to today's numbers, and `build`; make it a required context.
- Remove `api/*`, `llm/*`, and `main.py` from the coverage omit list; accept whatever number results
  and set the threshold from it.
- Turn container CVE gates on for CRITICAL and HIGH; add the frontend Dockerfile to the scan paths.
- Make the PostgreSQL integration job visible: either a `services: postgres` block in this repo or a
  documented input to the reusable workflow, and `P1_DATABASE_URL` set so the skipped test runs.
- Add unit tests for the uncovered measurement-service branches so they do not depend on PostgreSQL
  alone.
- Write `docs/ci-gates.md` recording per reusable workflow what runs and what blocks; align the two
  pinned SHAs.
- Retire workflows per Q9; pin `requires-python` to 3.12; delete or fix `setup_github_protection.py`.

Acceptance: every gate the plan's definition of done names runs on every PR from this repository's
own workflows, and a deliberately broken frontend test fails the PR.

### WS-2: Trust boundary in code, not topology

Findings: S-01, S-02, S-03, S-05/B-10, S-06, B-11, S-17, S-18, S-19, S-23, B-27, S-25.

- nginx: reset `X-Authentik-*` unless the peer is Traefik; document the exact Traefik middleware in
  `docs/deployment/`.
- uvicorn: `--proxy-headers --forwarded-allow-ips` for the frontend network; limiter keyed on the
  verified username.
- Move `actor`, `manager`, `authorize_reviewer` into `core/auth.py`; one `require_identity()` for
  every mutating route; one `authorize_reviewer` for every reviewer-keyed read (per Q5).
- Add `environment`, `trusted_hosts`, and the `NoDecode` admin-list validator to `Settings`; gate docs
  routes and CORS defaults on environment; set `CORS_ALLOWED_ORIGINS` in the prod override.
- Tests: an `authentik_required=True` suite asserting 401 on every mutating route without the
  header, the manager and recorder matrix, distinct rate-limit buckets per forwarded client, and a
  P1.6 deployed test that forges the header from a sibling container.

Acceptance: `grep -rn "Depends(get_current_identity\|require_identity" src/fragrance_rater/api`
covers every mutating and reviewer-keyed route; the forged-header test fails closed; ADR-008 is
amended to state read authorization and the header-reset control.

### WS-3: Close the disclosure leaks and add the audit trail

Findings: B-01, B-02, B-03, B-26, F-15, S-07, S-15.

- Role-neutral 409 on holdout feedback; explanation only by persisted impression id.
- `log_audit_event` on activate, enroll, lock, reveal, mapping retrieval, checkpoint, prediction
  create and link; a test that mapping logs actor and enrollment and never identity.
- No-store by default under the API prefix; opt out for the catalog.
- `setup_logging()` in lifespan; `SecretStr` keys; a redaction processor; a test for a JSON record
  with `correlation_id`.
- Extend the P1.7 disclosure matrix with the two new rows (409 bodies, 404 oracles).

Acceptance: the disclosure matrix in `docs/planning/evidence/` has a row per participant-reachable
error path, and the audit log test passes.

### WS-4: Delete the scaffold

Findings: G-03, G-07, B-21, B-22, B-23, B-24, B-30, F-04/F-22, B-34, per Q1-Q4, Q12.

- Remove `api/ratings.py`, `api/catalog_stub.py`, `llm/`, `middleware/auth.py`, the Postman
  workflow and collection (or retarget them at `/api/v1`), `core/cache.py` and the `redis`
  dependency, `jobs/`, `utils/financial.py`, the unused health checks, the `hello` and `config` CLI
  commands.
- Flag-gate the Parfumo scraper; emit a deprecation warning; move GTIN evidence into the ADR-012
  `SourceSnapshot` contract.
- Delete `@hey-api/openapi-ts` and the `js-yaml` override unless Q6 adopts generation.
- Rewrite the FastAPI app description and README overview to describe the actual product.

Acceptance: `main.py` mounts only `/health` and `/api/v1`; one auth mechanism; one LLM client;
`uv run vulture src` and an import-graph check show no unreferenced modules.

### WS-5: One owner each for transactions, errors, and authorization

Findings: B-04, B-05, B-07, B-08, B-09, B-12, B-13, B-16, B-17, B-14, B-15, B-25, B-29, B-33, B-35, B-31.

- Services never commit; `get_db` owns the unit of work; `begin_nested()` where containment is
  needed; delete `get_session` or make it the single implementation.
- Register a `ProjectBaseError` handler; replace `reject()` and raw `HTTPException` in services with
  domain exceptions.
- Move activation, skin planning, skin-plan finalization, and checkpoint creation into
  `CalibrationService`, checkpoint creation directly after the locked enrollment fetch; add the
  PostgreSQL concurrency test ADR-009 lists.
- `ALGORITHM_VERSION` and all tunables in `recommendation_service.py`; a test that fails on an
  unversioned tunable change; `score_type` on `RecommendationResponse`.
- Replace control-flow asserts; scope `S101` to tests; batch the N+1 queries; bound the import size.

Acceptance: `grep -rn "commit()" src/fragrance_rater/services src/fragrance_rater/api` returns
nothing; `grep -rn "fastapi" src/fragrance_rater/services` returns nothing; `prediction_service.py`
is no longer the only service matching that shape.

### WS-6: Typed calibration contract and generated client

Findings: F-03, F-04, F-05, B-13, contract drift Appendix A, per Q6.

- Pydantic response models for all calibration routes with `response_model=`; the participant view
  becomes a declared allowlist.
- Add provenance fields (`algorithm_version`, `candidate_strategy`, `score_type`, `score_value`,
  `recorded_by`), `fragrance_name`/`fragrance_brand` on `EvaluationResponse`, and RFC 3339 offsets on
  every timestamp (retiring the four client-side UTC helpers).
- Generate the client from `docs/api/openapi.json`, commit `src/client/`, and reduce
  `api/types.ts` to view-model types; add a CI diff between the committed spec and a fresh export.

Acceptance: `docs/api/openapi.json` contains no `additionalProperties: true` on calibration
responses; the client build fails when a schema changes without regeneration.

### WS-7: Frontend decomposition and state

Findings: F-06, F-07, F-08, F-09, F-12, F-16, F-17, F-18, F-19, F-20, F-21, F-24, F-25, F-26, F-23.

- Split `ProgramSetupPage` into feature components; hoist `RecommendationCard`; per-page tests.
- Typed route params with a not-found route; move query state into `routes.ts`.
- A keyed data store with invalidation after mutations; 401 interceptor; memoized capabilities.
- Per-action `useTask`; error boundary; design tokens with dark mode; type-aware ESLint with
  `jsx-a11y`; server-side progress summary for Home.

Acceptance: no page over 300 lines; reload on any route restores the participant's position;
`App.test.tsx` covers shell and routing only.

### WS-8: End-to-end and accessibility harness

Findings: G-01, F-10, F-11, F-13, Q13.

- Playwright with a compose-backed fixture (API, PostgreSQL, nginx, a forward-auth stub that sets
  the identity headers) covering the five P4 journeys and the P5 manager journey, including
  interruption and retry.
- MSW in Vitest so real error objects flow; `vitest-axe` on every route; a 360 px assertion.
- Re-close P4 and P5 against this evidence, or amend the gate records per Q13.

Acceptance: the gate records cite tests that exist and run in CI.

### WS-9: Data model and migrations

Findings: D-01 through D-05, D-07, D-08, D-10, D-11, D-12, D-15, D-19, D-20, D-21, D-22, per Q14-Q18.
Depends on WS-1 (a PostgreSQL job) so the parity test can run.

- Tooling first: `naming_convention` on `Base.metadata`, the three autogenerate flags in
  `alembic/env.py`, the PostgreSQL parity test (`compare_metadata == []`), the SQLite
  `foreign_keys` pragma in `conftest.py`, and the four downgrade-raise assertions. Land these before
  any schema change so the next migrations are verifiable.
- One named-constraint migration: rename the 37 unnamed CHECKs; add range CHECKs on
  `evaluations`; add `IN (...)` CHECKs on role, status, stage, phase; reconcile the six index names;
  add the nine missing FK indexes; change the two `evaluations` cascades to `RESTRICT` (per Q17).
- The ADR-012 provenance migration on `SourceSnapshot` (D-01) with `content_hash` and
  `parser_version`, and the `jsonb` type migration (D-12), both before F1 data exists.
- Immutability enforcement per Q14 (triggers or role grants) or a tech-spec caveat.
- An idempotency key on controlled observation submission (per Q18) and a `live()` select helper.
- Update `alembic/README` with the SQLite and downgrade constraints, and CONTRIBUTING with the
  "always `alembic revision`" rule.

Acceptance: `alembic revision --autogenerate` against a migrated PostgreSQL database produces an
empty migration; the parity test and FK-enforcing unit tests pass; the gap analysis is at v1.1
with status markers.

### WS-10: Operations and observability

Findings: S-04, S-08, S-12, S-13, S-16, S-20, S-27, S-28, Q-backups, per Q7 and Q10.

- Plumb secrets into the container from the prod override; extend the topology validator (expected
  middleware name from an argument, replicas, admin list, CORS, keys).
- Digest-pin base images; cosign on publish; runtime hardening in the prod override; fix
  `.env.example` and the no-op build arg.
- Scheduled backup with retention and a restore check, referenced from the P1.10 runbook.

Acceptance: `scripts/validate_production_topology.py` fails on each new class of misconfiguration
and the P6 operations drill has a backup row with evidence.

### WS-11: Documentation consolidation

Findings: G-04, G-05, G-08, G-09, G-10, G-12.

- Document the `ruff format --check .` / pre-commit hook scope mismatch (G-09) in CLAUDE.md's Quick
  Start section, or pass matching `--extension` filters so the documented command and the enforced
  hook agree. As of 2026-09-21, `ruff format --check .` still reformats 12 Markdown files (fenced
  Python blocks) that the pinned pre-commit hook scope excludes; this is open, not closed.

- Delete `CONFIG_TEMPLATES_SUMMARY.md`; move `concept.md` to `docs/research/` marked historical;
  merge `docs/ADRs/` into `docs/planning/adr/`; make `docs/project/roadmap.md` a redirect stub.
- Rewrite README's overview from vision v2 and cut unused supply-chain sections.
- Regenerate the CLAUDE.md structure section; state the real warning policy; remove agent references
  that are not configured.
- Supersede `SECURITY-FINDINGS.md`; reconcile `known-vulnerabilities.md` with `pyproject.toml`.
- Add an amendment note to ADR-001; mark pending P6 evidence pages as draft.

Acceptance: `.markdownlintignore` shrinks to template baselines only.

## 7a. Remediation status

This section is a live pointer, not a restatement: [PROJECT-PLAN.md's Milestone R sprint
table](PROJECT-PLAN.md#11a-milestone-r-review-remediation-and-ml-foundation) is authoritative for
what has actually shipped. As of 2026-09-21:

- **WS-1 / R1 (CI truthfulness) is done for the gates it added, but not yet verified against its own
  acceptance criterion.** Findings S-11/F-01, S-09, S-10, G-02, G-06, G-11, S-22, S-29, S-26, S-30,
  D-06 are closed; D-06 (no PostgreSQL service in any workflow) replaces G-09, which WS-1's own
  finding list named but none of its action items ever addressed. G-09 (`ruff format --check .`
  drift on Markdown files) remains open and is now tracked under WS-11 above.
  [`docs/ci-gates.md`](../ci-gates.md) is now the authoritative per-workflow record this review's
  Appendix B (CI gate matrix) fed into; its "Known residual gaps" section names what R1 deliberately
  left open (the `docker-publish.yml` CVE gate stays report-only; G-06/Q9's default resolved only
  PyPI publishing and the Python version matrix, not FIPS/SLSA/mutation-testing/`release.yml`; the
  PostgreSQL parity test itself belongs to R2, not R1, per the plan's sequencing note 1). WS-1's own
  acceptance criterion (Section 7) also requires "a deliberately broken frontend test fails the PR";
  no PR diff or description in R1 documents that negative control having been run, so this half of
  the acceptance criterion is unverified. Treat WS-1 as closed for the specific gates listed above,
  not as fully closed against its own stated acceptance criterion until someone exercises that
  negative control and records the result.
- R1 also surfaced one thing beyond its named findings: a coverage-measurement gap where code
  reached only through the FastAPI/ASGI test layer (`httpx.ASGITransport` + `Depends()`, the
  pattern most of `tests/unit/test_api/*` uses) does not register as covered even when confirmed to
  execute, while the same code called directly against the `async_session` fixture does. Recorded
  in `docs/ci-gates.md`'s residual-gaps section rather than root-caused here; treat this repository's
  reported coverage percentage as a floor, not an exact count.
- All other workstreams (WS-2 through WS-11) remain open; see PROJECT-PLAN.md for current status.

## 8. Template feedback

Per CLAUDE.md, the following are template-level gaps and belong in
[template_feedback.md](../template_feedback.md) when acted on: a React frontend generated with no
frontend CI job; a coverage configuration that omits the API layer by default; a root-mounted demo
API and Postman suite that outlive the real product; an unused Redis cache module and jobs package
in the runtime package; an undocumented npm override; `requires-python` and a compatibility matrix
wider than the declared target; and a `CLAUDE.md` project-structure section that is not regenerated.

## Appendix A: Frontend type versus backend schema drift

| # | Frontend | Backend | Drift |
| :--- | :--- | :--- | :--- |
| 1 | `RecommendationRun` (`types.ts:232-237`) | `RunView` (`schemas/recommendation_measurement.py:77-85`) | Missing `algorithm_version`, `candidate_strategy` (required provenance per tech-spec). |
| 2 | `RecommendationImpression` (`types.ts:221-230`) | `ImpressionView` (`:62-74`) | Missing `score_type`, `score_value`; UI shows only `match_percent`. |
| 3 | `RecommendationResponse` (`types.ts:239-251`) | `ResponseView` (`:52-59`) | Missing `recorded_by`; revision list cannot show who entered a revision. |
| 4 | `Metrics` (`types.ts:184-206`) | `MetricsView` (`:88-126`) | 15 backend fields absent (would-wear and would-buy counts, brand variety, unavailable candidates, all nine LLM cost and latency fields); an index signature hides the gap. The manager UI renders none of them. |
| 5 | `Encounter` (`types.ts:208-219`) | `EvaluationResponse` (`schemas/evaluation.py:133-151`) | Missing `reviewer_id`, `longevity_rating`, `sillage_rating`, `created_at`, `recorded_by`; the form offers no longevity or sillage input though the API accepts them. |
| 6 | `Person` (`types.ts:1`) | `ReviewerResponse` (`schemas/reviewer.py:16-22`) | Missing `created_at`, `evaluation_count`. |
| 7 | `FragranceSummary` (`types.ts:3-7`) | `FragranceResponse` (`schemas/fragrance.py:158-176`) | Frontend keeps 5 of 17 fields; the server sends notes, accords, family, and source ids on every search. Over-delivery, not a disclosure violation. |
| 8 | `Sample.identity` (`types.ts:83`) | `participant_view` (`services/calibration_service.py:540-545`) | Frontend omits `fragrance_id`, which the server sends; the type should reflect it so nobody renders it by accident. |
| 9 | `Assignment`, `Access`, `Enrollment`, `ProgramMember`, `ManagerEnrollment`, `MappingRow`, `OperationalEvent`, `OperationalStatus`, `Program` (`types.ts:9-18,87-98,129-182`) | none; bare dicts (`api/calibration.py:61,68,139,274,284,433`) | Nine client types with no server schema at all (F-03). |
| 10 | Enum duplication | | `roles[]` (`ProgramSetupPage.tsx:22-30`) vs `Role` (`calibration.py:9-17`); `sampling_state`, `event_type`, `reveal_blocker` each duplicated or client-only. |
| 11 | `would_wear` / `would_buy` | | `int` 0-10 on calibration observations vs `bool` on recommendation feedback under identical names. |
| 12 | Timestamps | | Every `datetime` is `string` and the API emits naive UTC, so four ad-hoc normalising helpers exist (`RatingsPage.tsx:8-14`, `RecommendationsPage.tsx:27-29`, `ProgramSetupPage.tsx:42-56`, test fixtures). |
| 13 | `useAppData.ts:6` defensive union | `GET /api/v1/reviewers` returns an array | Handles a shape the API never returned. |
| 14 | `MembershipInput.selection` (`calibration.py:42`) | `identity_evidence` stored inside `selection` (`api/calibration.py:169`) | Input and read shapes are asymmetric and undocumented. |

## Appendix B: CI gate matrix

| Workflow | Trigger | Checks | Blocks merge? |
| :--- | :--- | :--- | :--- |
| `ci.yml` | PR, push, merge_group | Delegated to `python-ci.yml@cb0742cf`: tests, lint, types, coverage 80, integration and security tests | Yes, via bare `CI Gate`; contents not reviewable here |
| `pr-validation.yml` | PR, merge_group | Title format, non-empty body, standards sync | Yes; gate accepts `cancelled` |
| `security-analysis.yml` | PR, push, weekly | Bandit, CodeQL, dependency review, OSV; fail on high | Yes |
| `reuse.yml` | PR, push | REUSE and SPDX | Yes |
| `container-security.yml` | Dockerfile paths, weekly | Trivy and Hadolint, backend only | No (`fail-on-vulnerabilities: false`) |
| `docker-publish.yml` | after CI on main, PR on paths | Build and push both images, Trivy, SBOM | No (`trivy-fail-on-vuln: false`); post-merge |
| `postman-api-tests.yml` | PR and push to main | Newman against root routes with `TEST_MODE` | Runs on PR; not a required context; does not exercise forward-auth |
| `codecov.yml`, `coverage.yml`, `qlty.yml` | after CI | Coverage uploads | No (post-merge) |
| `sbom.yml`, `fips-compatibility.yml`, `python-compatibility.yml`, `docs.yml` | PR, push, schedules | SBOM, FIPS check, 3.10-3.14 matrix, MkDocs build | Run on PR; not named required contexts |
| `scorecard.yml`, `mutation-testing.yml`, `release.yml`, `publish-pypi.yml`, `slsa-provenance.yml`, `claude-baseline-review.yml` | schedules, post-merge, dispatch | Scorecard, mutmut, semantic release, PyPI, SLSA, advisory review | No |
| none | | Frontend lint, typecheck, test, build | Absent |

All `uses:` references are SHA-pinned; `permissions:` blocks and `harden-runner` are present on every workflow.

## Appendix C: Backend import map

Package-level edges (statement counts): `main -> api(3), core(1), middleware(1)`;
`api -> services(19), core(18), models(7), schemas(6), utils(7), middleware(3), llm(1)`;
`services -> models(29), utils(8), core(6), schemas(5)`; `models -> core(7), utils(3)`;
`middleware -> core(2), utils(1)`; `utils -> middleware(1)` (the only cycle, deferred by
function-local imports); `cli -> services(4), core(2), utils(1)`.

Exceptions to clean layering: routers importing routers for auth helpers (`api.predictions` and
`api.recommendation_measurement` import `api.calibration`); routers importing ORM models and
SQLAlchemy directly (`api/calibration.py` eight model classes; `api/recommendations.py`;
`api/recommendation_measurement.py`); services importing FastAPI (`calibration_service.py:9`,
`fragrance_service.py:8`); a service returning a Pydantic wire model
(`recommendation_measurement_service.py:29`).

## Related documents

- [ML Structure Review 2026-09](ml-structure-review-2026-09.md)
- [Authoritative Project Plan](PROJECT-PLAN.md)
- [Technical Specification](tech-spec.md)
- [ADR Index](adr/README.md)
- [Data Model Gap Analysis](data-model-gap-analysis.md)
- [P6 Integrated Pilot Readiness Gate](gates/p6.md)
