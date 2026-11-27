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
  fragrance, because a prediction may target a holdout. Audit events go through the
  `fragrance_rater.audit` logger, which stays at INFO whatever `LOG_LEVEL` says.
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

## Proposed amendment (2026-11-27): linking logins to reviewers

> **Status of this section: Proposed.** The Accepted decision text above is unchanged and stays in force until the
> owner reviews the design and accepts this amendment. Nothing here changes program `v3.2`, the F1 procedure or any
> gate; for F1 the single recorder login transcribes every evaluator's sheets.

**History, as recorded in the repo.** The R3 amendment of 2026-10-21 (commit `10bd5d8`, PR #144, merged 2026-10-30)
closed architecture review items S-05 and B-10. It applied the owner's Q5 decision of 2026-10-21 ("household members
do not read each other's evidence") by reusing `recorder_usernames` as the read grant, and it recorded one side effect
in these words: "A user with no recorder assignment therefore cannot read any history, their own included, until a
manager enrolls them; the owner accepted this over linking Authentik users to reviewers." PR #144 lists the same side
effect as a "Behavior change, accepted by the owner" and leaves write scoping unchanged. Neither this ADR nor the PR
description discusses linking beyond that clause or states a reason against it, so the repo documents a scope choice
made inside a security remediation.

**History, the owner's recollection (2026-11-27; not verified in the repo).** The underlying reason for keeping
reviewer and login independent was that the owner did not want an app that other people may eventually be allowed to
use to depend on logging in through the owner's personal Authentik account. For an earlier app the owner used Supabase
for login and the database.

**Why it needs to change.** On 2026-11-27 the owner required that, after F1, each evaluator can be linked to her own
login and that mixed entry is possible (the facilitator enters some of an evaluator's sessions, the evaluator enters
others). The owner has indicated that the "accepted this over linking" clause will have to be overturned. The design is
in [PROJECT-PLAN section 11a](../PROJECT-PLAN.md#post-f1-follow-up-evaluator-login-linkage-proposed-2026-11-27) and is
not decided.

**Proposed change, kept narrow.**

1. Supersede only the clause "the owner accepted this over linking Authentik users to reviewers".
2. Design principle: link a reviewer to a provider-neutral external identity, an (issuer, subject) pair, not to an
   Authentik username. Today `recorder_usernames` matches the trimmed `X-Authentik-Username` header value exactly and
   case-sensitively; that string is the coupling to the owner's Authentik account the owner's recollection says to
   avoid. The first slice may link family evaluators who are already inside the owner's Authentik, which does not
   conflict with that concern; a path for people outside it is designed for but built only when outsiders are in scope.
3. Keep Q5. A linked participant reads only her own reviewer's evidence; household members still do not read each
   other's evidence, and a manager still reads every reviewer. Linking also removes the side effect the clause
   accepted, because a linked participant can read her own history without a recorder assignment.
4. Keep "Reviewer identity and authenticated recorder identity remain independent." A link maps an external identity
   to a reviewer without merging the two: every write is still stamped with the login that made it (`recorded_by`),
   and whose experience is recorded is still `reviewer_id`.
5. Keep reveal, mapping, checkpoints and guardian consent for minors manager-controlled. Under shared blind codes one
   evaluator's reveal would unblind the others.
6. Keep the trust boundary above. Forwarded identity headers stay trusted only because topology and the nginx header
   rule make the proxy the sole path to the backend. A token-based path for non-Authentik identities must verify
   signatures itself in the backend (JWKS, issuer, audience, expiry), must not accept a client-supplied identity header,
   and must not weaken the header-trust boundary.

**Status.** Proposed. It becomes Accepted only after the design review, and any implementation needs a migration, a
backend change and a new frontend build under the build-freeze rule.

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
