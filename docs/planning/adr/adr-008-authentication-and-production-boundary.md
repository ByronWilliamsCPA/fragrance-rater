# ADR-008: Authentication and Production Trust Boundary

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

The original LAN-only MVP assumed public endpoints. Controlled mappings, recorder attribution,
holdouts, and manager actions require authenticated identities and role enforcement. Trusting
forwarded headers while leaving the backend directly reachable would permit proxy bypass.

## Decision

Use Authentik forward-auth through Traefik as the production authentication boundary.

- Production sets `AUTHENTIK_REQUIRED=true`.
- Only the proxy path can reach the backend.
- Forwarded username, UID, and email headers are accepted only because network topology prevents
  clients from reaching the API directly.
- `CALIBRATION_ADMIN_USERNAMES` supplies an explicit manager allowlist; empty is secure.
- Mutating routes require a verified identity.
- Manager-only routes protect mappings, program control, and checkpoints.
- Reviewer identity and authenticated recorder identity remain independent.
- Local tests may disable Authentik explicitly, but this is not a production mode.

## 2026-10-21 amendment: header trust enforced in nginx (R3)

The original decision trusted the forwarded identity headers "because network topology prevents
clients from reaching the API directly". Architecture review S-01 showed that was not enough:
nginx copied whatever `X-Authentik-*` headers it received, so anything able to reach nginx other
than Traefik (a container wrongly attached to the edge network, a sibling on the private network)
could act as any user, including a manager.

- nginx forwards `X-Authentik-Username`, `-Uid`, and `-Email`, and Traefik's `X-Forwarded-For` and
  `X-Forwarded-Proto`, only when the connecting peer is inside `FRAGRANCE_TRAEFIK_CIDR`, the
  subnet of the dedicated edge network that holds only Traefik and the frontend. For any other
  peer it clears the identity headers and resets the forwarding headers to the peer itself. The
  owner chose this peer-subnet check over a Traefik-injected shared secret or verifying
  Authentik's signed JWT in the API (2026-10-21); JWT verification remains the stronger
  long-term option.
- nginx refuses to start without `FRAGRANCE_TRAEFIK_CIDR`, and the production Compose render and
  `scripts/validate_production_topology.py` both require it, narrower than /16 (IPv4) or /48
  (IPv6). The validator also takes the edge network's live subnet from `docker network inspect`
  and rejects a CIDR that differs from it.
- uvicorn trusts forwarding headers only from the private app network and that subnet
  (`FORWARDED_ALLOW_IPS`), and the rate limiter keys on the verified username before the client
  address, so household members no longer share one bucket.
- Production also sets `ENVIRONMENT=production` (no interactive docs or schema, no development
  CORS origins) and an explicit `TRUSTED_HOSTS` list.

Read authorization (which identities may read whose evidence, architecture review Q5) is decided
in the second 2026-10-21 amendment below.

Validation for this amendment: `tests/integration/test_nginx_trust_boundary.py` runs the real
nginx configuration and shows forged headers are dropped from an untrusted peer and kept from
Traefik; the P1.6 forged-header check in `docs/deployment/p1-release-readiness.md` repeats it on
the deployed topology.

## 2026-10-21 amendment: one identity rule and reviewer-scoped reads (R3)

The original decision required a verified identity only on "mutating routes". Reads of personal
data (ordinary evaluation history and notes, recommendations, preference profiles) required none,
some writes accepted a missing username when `AUTHENTIK_REQUIRED` was false, and three separate
authorization helpers lived in router modules (architecture review S-05/B-10, S-06, B-11).

- Every route except health checks, the API root, and the root-mounted sample catalog (removed in
  R9) depends on `core.auth.require_identity`. It returns 401 without a non-empty username whatever
  `AUTHENTIK_REQUIRED` says, so a misconfigured serving environment cannot accept anonymous writes
  or reads, and every write records who made it.
- Read policy, decided by the owner on 2026-10-21 (Q5): household members do not read each other's
  evidence. A manager (`CALIBRATION_ADMIN_USERNAMES`) reads every reviewer; any other user reads
  only reviewers whose calibration enrollment lists them in `recorder_usernames`; everyone else
  gets 403. This covers ordinary evaluations (by reviewer, by id, and by fragrance, which is
  filtered to readable reviewers), recommendations, the preference profile, and explanations. A
  user with no recorder assignment therefore cannot read any history, their own included, until a
  manager enrolls them; the owner accepted this over linking Authentik users to reviewers.
- Reviewer names and the fragrance catalog are household-wide and need only a named caller.
- Billed LLM routes (`POST /ratings`, profile, explain) need a named caller as well as the
  household API key, so spend is attributable (S-03); retiring the key itself is R9's (Q2).
- `actor`, `manager`, and `authorize_reviewer` live in `core/auth.py`; routers import them.

Validation: `tests/unit/test_api/test_authorization_matrix.py` walks the live route table and
expects 401 from every protected route without an identity, then checks the manager, assigned
recorder, and unassigned user matrix on every reviewer-keyed read.

## 2026-10-30 amendment: audit trail, caching, and log hygiene (R4)

R4 makes the Validation bullet below on logs true in code. It covers architecture review B-03,
B-26, S-07, and S-15:

- **Audit trail.** One `audit_event` records actor, target, and correlation ID for each of these:
  program activation, enrollment, stage and skin-plan locks, reveal, checkpoint creation, every
  retrieval of the blind mapping, and prediction create and outcome link. The mapping record names
  who retrieved which enrollment and nothing it returned. Prediction records leave out the
  fragrance, because a prediction may target a holdout.
- **Caching.** Everything under `/api/v1` is `Cache-Control: private, no-store` with
  `Vary: X-Authentik-Username` by default; only the public catalog opts out. The previous allowlist
  named two prefixes and left evaluations, recommendations, predictions, and reviewers cacheable.
- **Logging configured.** The app lifespan calls `setup_logging`, so `LOG_LEVEL`, `JSON_LOGS`, and
  the correlation processor take effect. Before this they were inert.
- **Secrets.** The household API key and the OpenRouter and Fragella keys are `SecretStr`, read
  only at the point of use. A structlog processor masks secret-named fields, the configured key
  values, and URL passwords before any renderer runs.

Validation: `tests/unit/test_api/test_calibration_audit.py`, `tests/unit/test_security.py`
(`TestNoStoreDefault`), and `tests/unit/test_logging.py` (a JSON record carries `correlation_id`;
secrets are redacted; keys are masked in dumps; the lifespan applies the settings).

## Consequences

- Production Compose and Unraid networking must prevent direct backend exposure.
- Application-level dependency tests are necessary but cannot prove the deployed boundary.
- Header trust, TLS, proxy configuration, and port exposure become release concerns.
- Remote access uses the authenticated proxy or an approved private-network path that preserves
  the same boundary.

## Validation

- P1 includes network reachability and direct-backend bypass tests.
- Route tests cover missing identity, recorder, manager, and participant roles.
- Logs record authorized actions without recording secrets, private response bodies, or blind
  mappings.
- Deployment documentation identifies the only supported request path.

## Supersedes

This ADR supersedes the “no authentication/authorization” portions of ADR-001 and the original
technical specification.

## Related

- [ADR-001](adr-001-initial-architecture.md)
- [ADR-005](adr-005-controlled-calibration.md)
