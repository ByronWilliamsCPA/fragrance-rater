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

Record the physical bottle's barcode as `gtin` when it has one - the strongest identity signal
available, since it is assigned per exact SKU by the manufacturer rather than inferred from text.
It is optional (a decant or some indie houses carry no scannable barcode), but when present it
must be a real, check-digit-valid GTIN-8/12/13/14; the same validator (`fragrance_rater.utils.
gtin`) enforces this both here and in the live Program setup API, where a scanned GTIN that
contradicts the fragrance's own recorded source evidence is rejected outright.

Validate the completed file:

```bash
uv run python scripts/validate_calibration_manifest.py /secure/path/baseline-manifest.json
```

Two people should compare the validated manifest with bottle, decant, or retailer labels before
program membership is locked. Retain the report and manifest hash.

## Restore and pre-upgrade inventory

The production render runs a scheduled backup job; see [Backup and Restore](backup-and-restore.md)
for how it works and for `scripts/verify_restore.py`, which automates the restore-and-compare steps
below.

1. Take a native PostgreSQL custom-format backup and verify that the command exits successfully.
2. Restore it into a new PostgreSQL 16 database with no route from application clients.
3. Record `alembic_version`, PostgreSQL version, table row counts, minimum and maximum
   timestamps, duplicate natural keys, and invalid foreign keys.
4. Hash a sorted, redacted export of every column for `fragrances`, `reviewers`, and
   `evaluations`, one digest per column so an added column is a non-event but a changed value
   or a dropped column is not.
5. Run `pg_restore --list` and retain the output with the backup hash.

Steps 3-4 above are steps `scripts/p1_migration_inventory.py` automates instead of hand-run SQL.
The connection string comes from the `P1_DATABASE_URL` environment variable (plain
`postgresql://` scheme, not the application's `postgresql+asyncpg://` SQLAlchemy URL), never
from the command line, so credentials stay out of `ps` and shell history:

```bash
read -rs P1_DATABASE_URL
# paste postgresql://<user>:<password>@<clone-host>/<db>, then press Enter
export P1_DATABASE_URL
uv run python scripts/p1_migration_inventory.py --output /secure/path/before.json
```

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

Repeat the inventory and compare against the pre-upgrade snapshot:

```bash
uv run python scripts/p1_migration_inventory.py \
  --output /secure/path/after.json --compare /secure/path/before.json
```

Exit code 1 means a preservation violation; do not proceed. Exit code 2 means the tool could not
do its job (unreachable database, unwritable `--output`, unreadable `--compare`); treat that the
same as a failed check, not a pass. Only exit 0 means verified. A violation names the exact
column that changed (for example `evaluations.rating: content hash changed`), a dropped column,
a row-count or timestamp-range mismatch, a duplicate-natural-key count delta, or an
invalid-foreign-key count delta; it does not require every column to be byte-identical, since a
migration may legitimately add columns. New calibration tables must have their declared
constraints and indexes. Run `EXPLAIN (ANALYZE, BUFFERS)` for participant history,
recommendation history, and program dashboard queries using representative cardinality.
Re-running `upgrade head` must be a no-op.

## Concurrency and disclosure

Against the clone, run simultaneous ordinary encounter inserts for one reviewer/version and
simultaneous observation, lock, reveal, and membership mutation attempts. Valid encounter
inserts must all persist. Only one invalid state transition may win; frozen membership and
locked observations must remain unchanged.

`tests/integration/test_calibration_concurrency_postgres.py` (gated on `P1_DATABASE_URL`, same
as the recommendation-measurement gate) exercises two of these races against real PostgreSQL row
locking: a holdout-membership assignment race and a duplicate-enrollment race. It runs against
any reachable PostgreSQL 16 instance, including the clone; it is not a substitute for the
representative-cardinality concurrency pass this section still requires against production-scale
data.

Exercise every participant-visible surface before reveal: catalog search, ordinary history,
preference profile, recommendation list, explanation, caches, errors, exports, structured logs,
and browser network responses. Search for membership role, repeat relationship, holdout marker,
blind mapping, hidden source fields, and internal IDs that allow the mapping to be reconstructed.
Retain a redacted pass/fail matrix.

## Production topology

Create the external Docker network named by `FRAGRANCE_TRAEFIK_NETWORK` and attach only the
Traefik service and this deployment's frontend. A shared proxy network lets unrelated containers
reach nginx with forged identity headers and does not satisfy the P1 trust-boundary gate.

nginx forwards `X-Authentik-*` identity headers, and Traefik's `X-Forwarded-For` and
`X-Forwarded-Proto`, only from peers inside `FRAGRANCE_TRAEFIK_CIDR`; from any other peer it clears
the identity headers (the API then answers 401) and resets the forwarding headers. Set it to the
edge network's subnet, which the production Compose render requires:

```bash
docker network inspect "$FRAGRANCE_TRAEFIK_NETWORK" --format '{{(index .IPAM.Config 0).Subnet}}'
```

The same render sets `ENVIRONMENT=production` (no `/docs`, `/redoc`, or `/openapi.json`; no
development CORS origins), `TRUSTED_HOSTS` (the public host plus `localhost` for the healthcheck),
and `FORWARDED_ALLOW_IPS` (the private app network and the edge subnet, so rate limits and logs see
the real client). The validator below rejects a render missing any of them or using `*`.

Render the exact deployment configuration and save it to the private evidence directory, then
validate it against the live edge subnet; a `FRAGRANCE_TRAEFIK_CIDR` that differs from it fails:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --format json
uv run python scripts/validate_production_topology.py /secure/path/compose.json \
  "$(docker network inspect "$FRAGRANCE_TRAEFIK_NETWORK" --format '{{(index .IPAM.Config 0).Subnet}}')" \
  --authentik-middleware "$AUTHENTIK_MIDDLEWARE"
```

The middleware name defaults to `$AUTHENTIK_MIDDLEWARE`, then to `authentik@file`; pass the name the
Traefik router label actually carries. Besides the network and proxy checks above, the validator
also rejects a render in which:

- the app runs more than one replica (its rate limiter is process-local, so more replicas multiply
  the effective limit on the billed endpoint);
- `CALIBRATION_ADMIN_USERNAMES` is missing, empty, malformed, or contains a wildcard;
- `CORS_ALLOWED_ORIGINS` is set to a wildcard or to a non-`https` origin (unset is fine: production
  defaults to none);
- `FRAGRANCE_RATER_API_KEY` or `OPENROUTER_API_KEY` is missing, blank, or a placeholder copied from
  an example. The production override requires both, and neither compose file has an `env_file`, so
  a value that is not named there never reaches the container and every billed endpoint answers 503;
- `TEST_MODE` is enabled (the app also refuses to start with it in production).

From every reachable network, verify that only Traefik's TLS entry point is open. Requests
without an Authentik session must be challenged. Requests sent directly to the app container IP
from an untrusted network must be unreachable. Inside the private Docker network, a mutation
without the verified identity header must return 401 when `AUTHENTIK_REQUIRED=true`. Confirm the
manager and participant role matrix with separate Authentik accounts.

Forged-header check (architecture review S-01): from a throwaway container on the private app
network, which is outside `FRAGRANCE_TRAEFIK_CIDR`, send a mutation through nginx with a forged
manager identity. It must return 401, not succeed. Send the public host name as `Host`: nginx
passes it through, and a host outside `TRUSTED_HOSTS` (such as `frontend`) gets 400 before identity
is checked, which proves nothing. Compose prefixes the network with the project name;
`docker network ls | grep fragrance_rater-network` shows it:

```bash
docker run --rm --network <project>_fragrance_rater-network curlimages/curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST -H "Host: $FRAGRANCE_HOST" -H 'Content-Type: application/json' \
  -H 'X-Authentik-Username: <a manager username>' \
  -d '{"name":"forged-header probe"}' http://frontend/api/v1/reviewers
```

Record the status code in the redacted evidence. Anything other than 401 fails P1.6.

## Recovery drill

Destroy only the isolated clone, create a second empty PostgreSQL 16 database, restore the same
verified pre-upgrade backup, and repeat the pre-upgrade inventory (`scripts/p1_migration_inventory.py`
against the restored database, compared to the original `before.json`). Record elapsed time and
the recovery point and recovery time achieved. Recovery uses restore; the intentionally lossy
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
