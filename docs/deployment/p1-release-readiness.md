---
title: "P1 Calibration Release Readiness"
schema_type: common
status: published
owner: core-maintainer
purpose: "Evidence procedure for the PostgreSQL migration and authenticated deployment gate."
tags:
  - deployment
  - validation
  - planning
---

P1 is an evidence gate. Run this procedure against an isolated restoration of the production
database and the target Authentik/Traefik host. Never test migrations or recovery against the
only production copy.

## Evidence directory

Create a private, access-controlled evidence directory outside the repository. Record the Git
commit, image digests, operator, UTC start time, host platform, Python version, PostgreSQL
version, and redaction rules. Logs committed to this repository must contain no secrets,
personal notes, blind codes, mappings, or source payloads.

## Baseline identity manifest

Copy `data/calibration/baseline-manifest.template.json` to the private evidence directory. One
entry is required for each program membership. Record a stable membership key, the existing
fragrance UUID, exact display name, brand, concentration/version key, HTTPS source,
human-readable verification evidence, physical-sample confirmation, role, and repeat membership
relationship. A hidden repeat uses the exact fragrance UUID and version key of its referenced
original. An unresolved version is left out of the program rather than guessed.

Validate the completed file:

```bash
uv run python scripts/validate_calibration_manifest.py /secure/path/baseline-manifest.json
```

Two people should compare the validated manifest with bottle, decant, or retailer labels before
program membership is locked. Retain the report and manifest hash.

## Restore and pre-upgrade inventory

1. Take a native PostgreSQL custom-format backup and verify that the command exits successfully.
2. Restore it into a new PostgreSQL 16 database with no route from application clients.
3. Record `alembic_version`, PostgreSQL version, table row counts, primary-key counts, minimum
   and maximum timestamps, duplicate natural keys, and invalid foreign keys.
4. Hash a sorted, redacted export of IDs and timestamps for `fragrances`, `reviewers`, and
   `evaluations`.
5. Run `pg_restore --list` and retain the output with the backup hash.

The restore itself is the first backup test. A backup file that has not been restored is not
release evidence.

## Migration and data assertions

Point `DATABASE_URL` at the isolated PostgreSQL 16 clone using the
`postgresql+asyncpg://` scheme. Run:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic current
```

Repeat the inventory. Historical evaluation IDs, encounter counts, ratings, reviewer/fragrance
links, and timestamps must match. New calibration tables must have their declared constraints
and indexes. Run `EXPLAIN (ANALYZE, BUFFERS)` for participant history, recommendation history,
and program dashboard queries using representative cardinality. Re-running `upgrade head` must
be a no-op.

## Concurrency and disclosure

Against the clone, run simultaneous ordinary encounter inserts for one reviewer/version and
simultaneous observation, lock, reveal, and membership mutation attempts. Valid encounter
inserts must all persist. Only one invalid state transition may win; frozen membership and
locked observations must remain unchanged.

Exercise every participant-visible surface before reveal: catalog search, ordinary history,
preference profile, recommendation list, explanation, caches, errors, exports, structured logs,
and browser network responses. Search for membership role, repeat relationship, holdout marker,
blind mapping, hidden source fields, and internal IDs that allow the mapping to be reconstructed.
Retain a redacted pass/fail matrix.

## Production topology

Create the external Docker network named by `FRAGRANCE_TRAEFIK_NETWORK` and attach only the
Traefik service and this deployment's frontend. A shared proxy network lets unrelated containers
reach nginx with forged identity headers and does not satisfy the P1 trust-boundary gate.

Render the exact deployment configuration and save it to the private evidence directory:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --format json
uv run python scripts/validate_production_topology.py /secure/path/compose.json
```

From every reachable network, verify that only Traefik's TLS entry point is open. Requests
without an Authentik session must be challenged. Requests sent directly to the app container IP
from an untrusted network must be unreachable. Inside the private Docker network, a mutation
without the verified identity header must return 401 when `AUTHENTIK_REQUIRED=true`. Confirm the
manager and participant role matrix with separate Authentik accounts.

## Recovery drill

Destroy only the isolated clone, create a second empty PostgreSQL 16 database, restore the same
verified pre-upgrade backup, and repeat the pre-upgrade inventory. Record elapsed time and the
recovery point and recovery time achieved. Recovery uses restore; the intentionally lossy
calibration migration has no downgrade path and must never be bypassed with `alembic stamp`.

## Operations checks

Confirm liveness and readiness probes, structured-log ingestion, disk and database growth
alerts, backup schedule and retention, restore ownership, secret rotation for PostgreSQL and
external services, and the upgrade rollback decision point. OpenRouter or LLM failure must leave
capture, history, and deterministic recommendation scoring operational. Record who receives an
alert and the manual/offline capture procedure during a home-connectivity outage.

P1 closes only after the core maintainer reviews the manifest, restore logs, before/after
assertions, concurrency output, disclosure matrix, topology tests, target-environment CI, parser
fixture provenance, operations checks, and timed recovery drill.
