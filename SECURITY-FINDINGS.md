# Security Findings: Re-verification Against the Real Tree

**Date**: 2026-10-31
**Verified against**: `main` at `a7443a4` (the branch point of R14 PR 3a)
**Supersedes**: the 2026-05-15 review of this file ("OWASP LLM Top 10 (2025) Focused Review"), which is kept in
the repository history and is no longer accurate.

## Why the earlier document was withdrawn

The 2026-05-15 review was written when `src/` was a template skeleton. Several of its statements are now false:

- It stated that no auth code exists in `src/`. There is a full identity and authorization layer (section 1).
- It cited `src/fragrance_rater/core/sentry.py`. That file is not in the tree.
- Its prototype findings (P1 to P14) point at `docs/planning/backend/`, which was deleted on 2026-09-09. They were
  never re-verified against `src/fragrance_rater/services/llm_service.py` and `api/ratings.py`.

Architecture review finding G-10 (`docs/planning/architecture-review-2026-09.md`) recorded this. This page
replaces the file so that nobody reads the old assertions as current.

## Scope and limits of this re-verification

This is a read of the code and its tests on the date above, not a penetration test and not a scanner run. The
deployed forged-header check belongs to P1.6 (`docs/deployment/p1-release-readiness.md`) and has no retained
evidence yet. The LLM prompt-injection and output-handling items from the 2026-05-15 review (LLM01, LLM02, LLM06)
and the GitHub Actions hardening items were **not** re-verified here and remain open for a future pass; do not
treat the old conclusions as current.

## 1. Authentication and authorization

| Control | Where it lives | What was checked |
| :------ | :------------- | :--------------- |
| Identity from Authentik forward-auth | `src/fragrance_rater/core/auth.py` (`get_current_identity`, `require_identity`, `VerifiedIdentity`) | A blank or missing `X-Authentik-Username` is not an identity. `require_identity` answers 401 whatever `AUTHENTIK_REQUIRED` says. |
| Fail-closed default | `src/fragrance_rater/core/config.py` (`authentik_required`, default `True`); `docker-compose.prod.yml` sets `AUTHENTIK_REQUIRED: "true"` | The base `docker-compose.yml` does not set it; the default applies. |
| Manager allow-list | `core/auth.py` (`is_manager`, `manager`), `Settings.calibration_admin_usernames` | Empty list means no managers. |
| Reviewer-scoped reads | `core/auth.py` (`authorize_reviewer`, `assigned_reviewer_ids`) | Managers read every reviewer; recorders only reviewers whose enrollment lists them; others get 403. |
| Shared household key on billed routes | `src/fragrance_rater/middleware/auth.py` (`require_api_key`) | Constant-time compare; 503 when the key is unset (fails closed), 401 when wrong. Used on `POST /ratings` and the profile and explain routes in `api/recommendations.py`, each together with a named caller. |
| External house accounts fenced | `src/fragrance_rater/middleware/house_fence.py`, registered in `main.py` | House contributors are confined to the house-intake routes; a username may not be both manager and house contributor (`Settings` validator). |
| Header trust boundary | `frontend/nginx.conf`, ADR-008 amendments of 2026-10-21 | nginx forwards `X-Authentik-*` only from peers inside `FRAGRANCE_TRAEFIK_CIDR` and clears them otherwise. |

Routers: every router under `src/fragrance_rater/api/` applies `require_identity` or `VerifiedIdentity`, except
`health.py` and the root-mounted sample catalog in `catalog_stub.py` (see "Open items" for the latter).

Test coverage that pins this: `tests/unit/test_api/test_authorization_matrix.py` builds its list from the live
route table and expects 401 for every route outside an explicit public allow-list (`/` and the four health
routes, plus the `catalog_stub` module), and checks the reviewer read policy; `tests/unit/test_core/test_auth.py`
covers the identity dependency; `tests/integration/test_nginx_trust_boundary.py` runs the real nginx
configuration and shows forged headers from an untrusted peer are dropped.

## 2. Security headers, hosts and CORS

- `SecurityHeadersMiddleware` (`src/fragrance_rater/middleware/security.py`) sets `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `X-XSS-Protection`, `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`,
  adds HSTS only when the request scheme is https, and marks identity-scoped paths `Cache-Control: private,
  no-store` with `Vary: X-Authentik-Username`.
- `add_security_middleware` is the only CORS registration; the allow-list is `settings.cors_allowed_origins`, and
  `Settings._apply_production_defaults` empties it in production and requires `TRUSTED_HOSTS`.
- `main.py` serves `/docs`, `/redoc` and `/openapi.json` only outside production.
- The CSP keeps `style-src 'unsafe-inline'`, and `X-XSS-Protection` is a legacy header; both are noted, not fixed.

## 3. Rate limiting

`src/fragrance_rater/middleware/rate_limit.py` keys buckets on the forwarded username before the client address
(`rate_limit_key`), applies `RATINGS_RATE_LIMIT` (10 per minute) to the billed route and `DEFAULT_RATE_LIMIT` to
everything else. The store is slowapi's in-memory, process-local one, so the topology validator and compose
comments hold the app at one replica until a shared store exists.

## 4. Secrets handling

- `OPENROUTER_API_KEY`, `FRAGELLA_API_KEY` and `FRAGRANCE_RATER_API_KEY` are `SecretStr` settings read through
  `secret_value`, so a settings dump or log line does not print them (`core/config.py`).
- `docker-compose.prod.yml` requires `FRAGRANCE_RATER_API_KEY` and `OPENROUTER_API_KEY` with `:?` guards, so a
  production render without them fails; `.env.example` ships no default credential (S-16).
- `TEST_MODE` is refused when `ENVIRONMENT=production` (`Settings._apply_production_defaults`, S-27).

## 5. Dependency vulnerabilities

See [SECURITY.md](SECURITY.md) for reporting and [docs/known-vulnerabilities.md](docs/known-vulnerabilities.md)
for the ignore ledger. The ledger is stale in one respect, recorded there: `pyproject.toml` still carries a
pip-audit ignore for `PYSEC-2022-42969` whose reassessment date (2026-07-16) has passed.

## 6. Open items from this pass

- `src/fragrance_rater/middleware/auth.py` module docstring still says read-only `GET /fragrances*` is left
  unauthenticated. Since R3 those routes require an identity; the docstring is stale (code change, not made here).
- `api/catalog_stub.py` is intentionally public and root-mounted for the Postman suite; the authorization matrix
  lists it as public pending its removal (R9).
- Re-verify the LLM surface (prompt construction, output validation, error bodies) and the GitHub Actions
  hardening items against the current tree.
- The deployed forged-header check (P1.6) still needs retained evidence.
