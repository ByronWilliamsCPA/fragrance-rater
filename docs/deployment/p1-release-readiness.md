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
fragrance UUID, exact display name, brand, concentration/version key, HTTPS `source_url` or a `source_reference`,
human-readable verification evidence, physical-sample confirmation, role, and repeat membership
relationship. A hidden repeat uses the exact fragrance UUID and version key of its referenced
original. An unresolved version is left out of the program rather than guessed.

The file also records who verified it and when: top-level `verified_by` (a name) and `verified_at` (a UTC timestamp
written `YYYY-MM-DDTHH:MM:SSZ`, optionally with fractional seconds, such as `2026-11-08T14:30:00Z`). End it with `Z`;
an offset such as `+00:00` is rejected. The template ships both as `null` and the validator rejects `null`, so a
manifest cannot pass without them.

Record the physical bottle's barcode as `gtin` when it has one - the strongest identity signal
available, since it is assigned per exact SKU by the manufacturer rather than inferred from text.
It is optional (a decant or some indie houses carry no scannable barcode), but when present it
must be a real, check-digit-valid GTIN-8/12/13/14; the same validator (`fragrance_rater.utils.
gtin`) enforces this both here and in the live Program setup API, where a scanned GTIN that
contradicts the fragrance's own recorded source evidence is rejected outright.

Validate the completed file:

```bash
uv run python scripts/validate_calibration_manifest.py /secure/path/baseline-manifest.json \
  --expect-shape baseline=33,hidden_repeat=6,holdout=10,total=49 --require-label-check
sha256sum /secure/path/baseline-manifest.json
```

`--expect-shape` checks the number of memberships per role against the planned program (33 universal baseline, 6 hidden
repeat and 10 holdout memberships, 49 in all over 43 fragrances). `total=49` counts every membership whatever its role, so
an extra membership of another role fails too. Leave the option out if the reviewed program differs.
`--require-label-check` demands `label_checked_by` on every entry (see the decant section below). The command exits 0
when valid, 1 with one line per violation, and 2 when the file cannot be read. Retain the output and the `sha256sum`
line with the manifest as the verification report.

Two people should compare the validated manifest with bottle, decant, or retailer labels before
program membership is locked. Retain the report and manifest hash.

### Creating the exact catalog versions

A manifest entry needs an existing `fragrance_id`, and Program setup only searches rows that already exist. A version
that is not in the catalog is created before the manifest is authored:

- **Path:** `POST /api/v1/fragrances` by a verified caller (use the manager). The required fields are `name`, `brand`,
  `concentration`, `primary_family` and `subfamily`. Set `version_key` explicitly: it defaults to `legacy`, and the
  manifest entry's `version_key` must be the one the catalog row carries. Use the `Unclassified` family sentinel when no
  Michael Edwards family applies (ADR-014, `core/vocabulary.py`).
- **Duplicates:** a live row with the same name, brand, concentration and version key is refused with a 409
  `FRAGRANCE_EXISTS`. Two concentrations of one name are separate versions and do not collide. (The 409 message names
  only name and brand; the stored rule is the unique index `uq_fragrance_version`.)
- **Then:** copy the returned `id` into the manifest entry. Parfumo capture is deprecated and refuses to write, and
  Fragella is reference-only, so neither creates these rows. Do not enter a value for a fragrance whose exact version
  is not yet verified.

### Source reference format and decant verification (owner decision, 2026-11-01)

An entry needs a `source_url` or a `source_reference`. A `source_reference` is three parts separated by
`|`: `who | YYYY-MM-DD | evidence or scope`, for example
`B. Williams | 2026-11-02 | decant label and split record checked against the parent bottle`. The validator
rejects anything else.

All 43 baseline and holdout fragrances were obtained as decants from an initial split between sources, so there is
no manufacturer packaging to read a barcode or batch from. Identity therefore rests on the decant source's own
provenance. For each entry, retain in the private evidence directory: the split organizer's or source's record of the
parent product (brand, name, concentration), the parent bottle's batch code when the source gives one, the decant
date, and a two-person check of the decant label against that record. Set the presentation's
`sample_source_type` to `decant` and fill `sample_decanted_on` when known. Omit `gtin` or set it to `null` (an empty string is rejected).

The owner accepted this as sufficient proof for P1.1 on 2026-11-01. For a decant entry, `verification_evidence`
is a statement of that record and label check, and `physical_sample_confirmed: true` means the labelled decant is in
hand and was checked by two people. Manufacturer or packaging confirmation is not required.

Record that check on the entry as `label_checked_by`, a list of the two people who did it. The validator accepts it on
any entry, rejects a list with fewer than two different names (comparison ignores case and surrounding spaces), and
`--require-label-check` makes it mandatory, which is the setting for an all-decant manifest.

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
validate it against the live edge subnet; a `FRAGRANCE_TRAEFIK_CIDR` that differs from it fails.
Set `INSTRUMENT_VERSION` first (to the commit SHA of the build you deploy, in `.env` or the shell): an
unset value renders blank and fails the validator, and a source-built frontend takes the same value as
its `VITE_INSTRUMENT_VERSION` build argument.

```bash
# The render contains both API keys in plaintext: write it straight to a
# private file (never to the terminal or CI output) and delete it afterwards.
umask 077
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --format json \
  > /secure/path/compose.json
uv run python scripts/validate_production_topology.py /secure/path/compose.json \
  "$(docker network inspect "$FRAGRANCE_TRAEFIK_NETWORK" --format '{{(index .IPAM.Config 0).Subnet}}')" \
  ${AUTHENTIK_MIDDLEWARE:+--authentik-middleware "$AUTHENTIK_MIDDLEWARE"}
```

When deploying the signed images by digest (see [Image pinning and signing](image-signing.md)), add
`-f docker-compose.release.yml` after `docker-compose.prod.yml` in the render and in `up`, with
`APP_IMAGE_DIGEST`, `FRONTEND_IMAGE_DIGEST` and `INSTRUMENT_VERSION` set. The override drops the source
build, so what runs is what was verified, and Compose refuses to render while either digest is unset.

The middleware name defaults to `$AUTHENTIK_MIDDLEWARE`, then to `authentik@file`; the flag is passed
only when the variable is set, because an empty name would override the default. Pass the name the
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
- `INSTRUMENT_VERSION` is blank, the `unpinned-app-` fallback, or not a commit SHA or release tag
  (letters, digits, `.`, `_` and `-`, at most 100 characters), or a frontend built from source carries a
  different `VITE_INSTRUMENT_VERSION` build argument. The backend records this value on each program at
  activation and the F1 gate refuses a program recorded as unpinned, so set it to the commit SHA of the
  build you deploy. A frontend deployed by digest has no build block and is not compared; see below.
- the `backup` service is missing, has no healthcheck, keeps its dumps anywhere other than a volume
  mounted at `/backups`, publishes a host port, or joins the authenticated edge (see
  [Backup and restore](backup-and-restore.md); a deployment with no backup job has no recovery point);
- any of `app`, `frontend`, `db` or `backup` lacks a read-only root filesystem (`read_only: true`),
  `cap_drop: [ALL]` or `no-new-privileges:true`, adds back `ALL`, `SYS_ADMIN`, `SYS_MODULE`,
  `SYS_PTRACE`, `SYS_RAWIO`, `DAC_READ_SEARCH`, `NET_ADMIN` or `BPF` (with or without the `CAP_`
  prefix), or runs `privileged` (architecture review S-13). Writable scratch space is a `tmpfs:` entry, not a
  `volumes:` entry, because the validator also refuses a source mount on `app` and `frontend`.

### Runtime hardening of the production services

`docker-compose.prod.yml` applies one `x-hardened` block (read-only root, all capabilities dropped,
`no-new-privileges`) to `app`, `frontend`, `db` and `backup`. The development file is unchanged on
purpose. The writable paths and the one non-default setting each service needs, as measured with
`docker diff` on a running stack under traffic (the output is in the pull request that introduced them):

| Service | Runs as | Writable (tmpfs unless noted) | Capabilities added back |
| --- | --- | --- | --- |
| `app` | 1000:1000 | `/tmp` (the Kaggle CSV import writes a temp file; Starlette spools uploads) | none |
| `frontend` | 1001:1001 | `/var/cache/nginx`, `/run` (pid file), `/etc/nginx/conf.d` (rendered config) | none (see below) |
| `db` | 70:70 (`postgres`) | `/run/postgresql` (socket), plus the `postgres-data` volume | none |
| `backup` | root | the `backups` volume | none |

Three decisions behind that table:

- `db` runs as the image's `postgres` user instead of the image default of root-then-`gosu`. The
  root path is what would otherwise need `CHOWN`, `SETUID`, `SETGID`, `FOWNER` and `DAC_OVERRIDE`.
  The data volume is already `postgres`-owned: a fresh named volume copies the image's ownership,
  and a volume first initialised by the root path was chowned to `postgres` by that entrypoint. Both
  were run: a fresh volume under the production stack, and a throwaway volume first initialised by the
  image default and then restarted as `70:70` with a read-only root and no capabilities, where the row
  written beforehand was intact. The cost is that the container can no longer repair ownership
  itself, so a file-level restore of the volume made as root must be followed by `chown -R 70:70` (see
  [Backup and restore](backup-and-restore.md#restoring-for-real)).
- `frontend` binds port 80 as a non-root user without `NET_BIND_SERVICE`. The service sets the
  namespaced sysctl `net.ipv4.ip_unprivileged_port_start: 0` for its own network namespace, which is
  also Docker's default, so the dependency is stated instead of inherited.
- `backup` keeps root because the `backups` volume is created root-owned. With every capability
  dropped it can touch only its own files. Running it as a non-root user would need a root-owned
  init step to change the volume's owner, a larger privileged surface than the one it removes.

Verify a running stack (each container must report `true`, `[ALL]`, `[]` and `[no-new-privileges:true]`,
and an effective capability mask of zero in every service):

```bash
docker inspect \
  -f '{{.Name}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.CapAdd}} {{.HostConfig.SecurityOpt}} user={{.Config.User}}' \
  $(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q)
for service in app frontend db backup; do
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T "$service" \
    grep -E 'CapEff|NoNewPrivs' /proc/1/status
done
```

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
external services, and the upgrade rollback decision point. The consent text states that
OpenRouter does not retain what it receives; the owner confirmed on 2026-11-01 that zero data
retention is enforced at the API-key level, so confirm it on the production key. OpenRouter or
LLM failure must leave capture, history, and deterministic recommendation scoring operational.
Record who receives an alert and the manual/offline capture procedure during a
home-connectivity outage.

P1 closes only after the core maintainer reviews the manifest, restore logs, before/after
assertions, concurrency output, disclosure matrix, topology tests, target-environment CI, parser
fixture provenance, operations checks, and timed recovery drill.
