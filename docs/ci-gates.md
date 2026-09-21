---
title: "CI Gates"
schema_type: common
status: published
owner: core-maintainer
purpose: >
  Record, per workflow, what actually runs and what actually blocks a merge -
  so this document, not tribal knowledge or a stale script, is the source of
  truth for CI. Written for architecture review finding S-22 (Milestone R,
  sprint R1: "CI truthfulness").
tags:
  - ci_cd
  - security
  - compliance
---

> **Keep this current.** Every workflow change that adds, removes, or changes whether a
> job blocks a merge must update the matching row below in the same pull request. This
> document exists because [`scripts/setup_github_protection.py`](../scripts) (deleted in
> R1) hardcoded required-check names that drifted from reality and would have configured
> branch protection no PR could ever satisfy (architecture review G-11). Do not repeat
> that mistake here by letting this table drift.

## How "blocks a merge" is decided

Two independent things both have to be true for a check to actually block a PR:

1. **The workflow's `fail-on-*` / exit-code inputs are set to fail** (this file's "Fails
   on" column). A workflow that reports findings but always exits 0 can be green forever
   regardless of what it finds.
2. **GitHub's branch protection / org-level ruleset for `main` names the job's bare check
   name as required.** This repository does not control that from its own files - it is
   an org/repo GitHub Settings configuration, not YAML in this tree. This table's "Blocks
   merge?" column states what *should* be required given (1); verify the actual ruleset
   in GitHub Settings if the two ever seem to disagree.

Jobs that call an org-level reusable workflow (`uses: ByronWilliamsCPA/.github/...`)
publish their check under `"<caller job name> / <reusable job name>"`, not the bare
caller name, except where a caller adds its own aggregating "gate" job specifically to
re-publish a bare name the ruleset can match on (`ci.yml`'s `CI Gate` job is the
example). Bare job names without a caller prefix are simple checks defined directly in
this repository's own `.github/workflows/*.yml`.

## Reusable-workflow pin

Every caller in this repository except `scorecard.yml` pins
`ByronWilliamsCPA/.github/.github/workflows/<name>.yml` to the same commit SHA,
`b7c661ec3bfeb04370ce3a9c748bd8c4e93bfe89` (tagged `# main`). Before R1 this had drifted:
`docker-publish.yml` was two commits ahead of the other ten callers that share the pin
(S-22). Bump *all* callers together when updating this pin, and diff the reusable
workflows between the old and new SHA first: the two commits this pin skipped when it
drifted touched only `python-docker.yml`, so the bump was a no-op for every other caller,
but that will not always be true. `scorecard.yml` pins a different SHA entirely
(`f05c26a424a708a73fc445a0ebb5b3ce476c1793`, no `# main` tag comment) and was out of
scope for the R1 alignment sweep; see "Known residual gaps" below.

## Workflows in this repository

| Workflow | Triggers | What it runs | Fails on | Blocks merge? |
| :--- | :--- | :--- | :--- | :--- |
| `ci.yml` | PR, push to main/master/develop, merge_group, dispatch | `ci` job delegates to `python-ci.yml`: Ruff, BasedPyright (strict), unit + integration + security pytest tiers, 80% coverage floor. `frontend` job: `npm ci`, lint, typecheck, `test:coverage`, build. `frontend-e2e` job: mocked-API Playwright suite (5 P4 journeys + P5 manager journey) plus the axe-core accessibility scan. `postgres-integration` job (added R1/D-06): a real `postgres:16` service, `alembic upgrade head`, then `pytest tests/integration -m integration` so `P1_DATABASE_URL`-gated tests actually run instead of skipping. `ci-gate` aggregates all four. | Any of `ci`, `frontend`, `frontend-e2e`, `postgres-integration` failing | **Yes**, via the bare `CI Gate` check (required org-ruleset context) |
| `pr-validation.yml` | PR, merge_group | `PR Title Format` (conventional-commit regex), `PR Body Non-Empty`, `Dependency & Standards Validation` (lockfile/requirements sync) | Any check failing (title-check/body-check skip cleanly, not fail, under merge_group) | Yes, as the three bare check names |
| `security-analysis.yml` | PR, push, weekly schedule, dispatch | `Security Analysis` job: CodeQL, Bandit, Safety/pip-audit, OSV Scanner, dependency review (PR only). `Security Gate Validation` aggregates. | High/critical findings from any scanner | Yes |
| `reuse.yml` | PR, push, merge_group | `Check REUSE Compliance` (REUSE/SPDX licensing), `Validate License Files` (LICENSE/REUSE.toml existence) | Either check failing | Yes |
| `container-security.yml` | Push/PR touching Dockerfile paths (both backend and frontend, R1/S-29), weekly schedule, dispatch | Matrixed `Container Security Scan (backend)` / `(frontend)`: builds each image, Trivy vuln scan at CRITICAL/HIGH, Hadolint, SBOM, and a suppression-revisit-date check (`.trivyignore.yaml`, 90-day horizon) | **Partial (R1/S-10)**: the reusable workflow's CVE gate exists (`fail-on-vulnerabilities` input) and was briefly flipped to `true` in R1, but a live run surfaced 52 HIGH findings with no `.trivyignore.yaml` suppression entries in place to triage them first, so it was reverted to `false` (report-only) pending a real baseline. Not fixed yet; flip back once entries exist. | No while report-only; would be a candidate for a required context once the gate is flipped back on |
| `docker-publish.yml` | `workflow_run` after CI succeeds on main/master, PR on image-relevant paths, dispatch | Builds and (outside PRs) pushes both images to GHCR via the org's `python-docker.yml`; runs its own Trivy pass | **No**, `trivy-fail-on-vuln: false` for both backend and frontend. Left this way deliberately: unlike `container-security.yml`, the reusable `python-docker.yml` passes no `trivyignores` to its Trivy step, so there is no way to accept a specific CVE here; flipping this on would block every future image publish on any CRITICAL/HIGH finding with no recovery but reverting the flag. Revisit if `python-docker.yml` gains the same `.trivyignore.yaml` mechanism `python-container-security.yml` has. | No (post-merge publish path; PR runs never push) |
| `codecov.yml`, `coverage.yml` | `workflow_run` after CI | Upload `coverage.xml` to Codecov / Qlty | Upload failures only (`report-failure` job surfaces a CI-side failure if the upload step failed) | No (post-merge reporting) |
| `qlty.yml` | `workflow_run` after CI | Calls the org's `python-qlty-coverage.yml` to upload `coverage.xml` to Qlty (`coverage-format: cobertura`). Duplicates `coverage.yml`'s upload job: both call the same reusable workflow with the same coverage file for the same CI run, `coverage.yml` restricted to `main`/`master` and `qlty.yml` unrestricted by branch | Upload failures only | No (post-merge reporting; not deduplicated against `coverage.yml`, see "Known residual gaps") |
| `sbom.yml` | PR/push touching `pyproject.toml`/`uv.lock`, weekly, dispatch | CycloneDX SBOM generation, Trivy scan, license compliance, SARIF | Not currently gating (report/SBOM generation) | No |
| `fips-compatibility.yml` | Push/PR, weekly, dispatch | `FIPS Compliance Check` (static scan for MD5/SHA-1/DES/etc.) + `FIPS Runtime Test` | Prohibited-algorithm usage | Runs on PR; verify ruleset before assuming required |
| `python-compatibility.yml` | *(retired in R1/G-06)* | n/a | n/a | Deleted: this app targets Python 3.12 only (`requires-python = "==3.12.*"`), it is a self-hosted deployment not a library needing a version matrix |
| `publish-pypi.yml` | *(retired in R1/G-06)* | n/a | n/a | Deleted: this is a private, self-hosted personal-use app, never distributed via PyPI |
| `scorecard.yml` | Schedule, push, `branch_protection_rule`, dispatch | OpenSSF Scorecard analysis | Not gating | No |
| `mutation-testing.yml` | Weekly schedule, dispatch | mutmut mutation testing (report-only by default; `fail_under_threshold` opt-in on manual dispatch) | Only if manually dispatched with `fail_under_threshold=true` | No (weekly report; deliberately not per-PR, see the workflow's own header comment on the ~60 min runtime) |
| `postman-api-tests.yml` | PR, push to main | Newman contract tests against `/health` and root routes | Newman failures | Runs on PR but is **not** a required context (per the architecture review's CI gate matrix); does not exercise forward-auth |
| `docs.yml` | Push/PR touching `docs/**`/`mkdocs.yml`, dispatch | MkDocs Material build; deploys to GitHub Pages on push to main | Build failures | Runs on PR; verify ruleset before assuming required |
| `release.yml` | `workflow_run` after CI on main/master, dispatch | Semantic-release versioning and GitHub Release creation (`publish-to-pypi: false`) | Release pipeline failures | No (post-merge) |
| `slsa-provenance.yml` | GitHub Release, dispatch | SLSA provenance generation for release artifacts | Provenance generation failures | No (post-release) |
| `claude-baseline-review.yml` | PR | Claude-based baseline/advisory review | Not gating | No |

## Analysis outside GitHub Actions

- **SonarCloud** runs via project-level Automatic Analysis, not a workflow file in this
  repository (see `sonar-project.properties`, project key
  `ByronWilliamsCPA_fragrance-rater`; also documented this way in `PROJECT_SETUP.md` and
  `OPENSSF_COMPLIANCE.md`). It has no row in the table above because it has no caller to
  describe, but it is in scope for S-22 CI truthfulness: verified live against the
  SonarQube API, its quality gate is currently **ERROR** (`new_security_rating` and
  `new_security_hotspots_reviewed` both failing). Neither of the two active org-level
  branch rulesets for this repository names a SonarCloud check context as required, so it
  does not block merges today, but the failing gate itself is unresolved.

## Known residual gaps

- **`container-security.yml`'s CVE gate is currently report-only again; S-10 is partial,
  not closed.** R1 flipped `fail-on-vulnerabilities` to `true`, but the first live run
  surfaced 52 HIGH findings with no `.trivyignore.yaml` entries in place to triage them,
  so it was reverted to `false` pending a real suppression baseline (see its row above).
  Add dated entries per finding, confirm the gate passes clean, then flip the input back
  to `true`. Only once that happens does whether GitHub's ruleset marks the check required
  become the open question: this repository's files cannot show that, so confirm in the
  ruleset settings once the gate itself is back on.
- **`docker-publish.yml` stays report-only on CVEs** for the reason given in its row
  above (no suppression mechanism upstream). This is an accepted, documented gap, not an
  oversight.
- **`scorecard.yml` pins a different reusable-workflow SHA than every other caller**
  (`f05c26a424a708a73fc445a0ebb5b3ce476c1793`, no `# main` tag comment), and was not
  touched by the R1 SHA-alignment sweep (S-11/F-01 and related findings). Align it to the
  shared pin, or document why it must diverge, in a follow-up.
- **`qlty.yml` and `coverage.yml` both upload the same `coverage.xml` to Qlty via the same
  reusable workflow** after the same CI run, one unrestricted by branch and one restricted
  to `main`/`master`. Not currently deduplicated; harmless today (both just re-upload the
  same report) but worth collapsing into one caller.
- **`docker-publish.yml` grants `packages: write` at the workflow level, applied even to
  PR and `workflow_dispatch` runs that never push an image.** A CodeRabbit review comment
  on PR #93 flagged this as broader than needed; it was explicitly deferred there
  ("requires a new pinned revision of the reusable workflow with split read/write jobs;
  cross-repo, out of scope") rather than fixed, and remains open. Revisit once the org's
  `python-docker.yml` supports scoping `packages: write` to only the jobs that actually
  push.
- **Coverage measurement undercounts code reached only through the FastAPI/ASGI test
  layer.** During R1 (G-02), a service method's execution was confirmed with a temporary
  `print()` statement while `pytest`'s coverage report still listed the same lines as
  uncovered, when the only test exercising them went through
  `httpx.ASGITransport` + FastAPI `Depends()` (as `tests/unit/test_api/*` does
  throughout this suite) rather than calling the service directly. The same lines
  register as covered once a direct unit test calls the service against the
  `async_session` fixture instead (see
  `tests/unit/test_services/test_recommendation_measurement_service.py`). The root cause
  was not tracked down further in R1; the practical implication is that this repository's
  reported coverage percentage is a **floor**, not an exact count, and a low number on a
  service that has real `tests/unit/test_api/*` coverage is not necessarily a real gap -
  check whether a direct service-level test would change the picture before trusting the
  report literally.
- **`ByronWilliamsCPA/.github`'s `python-ci.yml`, `python-security-analysis.yml`, and the
  other reusable workflows are not reviewable from this repository.** This table
  describes what they do based on reading that repository directly at the pinned SHA
  (architecture review S-22); re-verify after any SHA bump if this table's "What it runs"
  column stops matching observed CI behavior.
- **`python-compatibility.yml` and `publish-pypi.yml`'s retirement (R1/G-06) resolved
  only the two items the owner-decision default explicitly named** ("retire publish and
  the version matrix"). `fips-compatibility.yml`, `slsa-provenance.yml`,
  `mutation-testing.yml`, and `release.yml`'s semantic-release automation were not
  addressed by that default and remain as they were; a future sprint should get an
  explicit owner decision on those rather than assuming the same default extends to them.
