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
  (IPv6).
- uvicorn trusts forwarding headers only from the private app network and that subnet
  (`FORWARDED_ALLOW_IPS`), and the rate limiter keys on the verified username before the client
  address, so household members no longer share one bucket.
- Production also sets `ENVIRONMENT=production` (no interactive docs or schema, no development
  CORS origins) and an explicit `TRUSTED_HOSTS` list.

Read authorization (which identities may read whose evidence, architecture review Q5) is decided
in R3's second pull request, which amends this ADR again.

Validation for this amendment: `tests/integration/test_nginx_trust_boundary.py` runs the real
nginx configuration and shows forged headers are dropped from an untrusted peer and kept from
Traefik; the P1.6 forged-header check in `docs/deployment/p1-release-readiness.md` repeats it on
the deployed topology.

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
