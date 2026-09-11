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
