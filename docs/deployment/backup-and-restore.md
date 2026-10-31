---
title: "Backup and Restore"
schema_type: common
status: published
owner: core-maintainer
purpose: "How the database is backed up on a schedule and how a backup is proven to restore."
tags:
  - deployment
  - validation
---

A backup is only a backup once it has been restored. This page covers the scheduled job that takes
dumps, the check that tells you when it stops, and the restore verification that proves a dump is
usable. It implements architecture review D-18 and the recovery steps of the
[P1 release readiness runbook](p1-release-readiness.md).

## What runs on a schedule

The production override (`docker-compose.prod.yml`) includes a `backup` service built on the
`postgres:16` image. It runs `scripts/backup_database.sh backup` at start and then every
`BACKUP_INTERVAL_HOURS` (default 24). Each run:

1. takes a custom-format `pg_dump`;
2. refuses to record it unless the dump exited cleanly, is non-empty, and `pg_restore --list` can
   read it back;
3. writes `fragrance_rater-<UTC timestamp>.dump` plus a `.sha256` checksum and a `.json` manifest
   (size, checksum, and the Alembic revision of the database it came from) into the `backups`
   volume, readable only by its owner;
4. moves the `latest.ok` marker, which happens only after the steps above succeed;
5. prunes dumps older than `BACKUP_RETENTION_DAYS` (default 14), never below the newest
   `BACKUP_KEEP_MIN` (default 3).

A failed run leaves no dump, no partial file, and does not move the marker, so the failure cannot
be mistaken for a backup.

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `BACKUP_INTERVAL_HOURS` | 24 | Hours between backups |
| `BACKUP_RETENTION_DAYS` | 14 | Dumps older than this may be pruned |
| `BACKUP_KEEP_MIN` | 3 | The newest dumps are never pruned |
| `BACKUP_MAX_AGE_HOURS` | 30 | The health check fails if the last backup is older |

## Noticing when it stops

The service's healthcheck runs `backup_database.sh check` hourly. It fails when no backup was ever
recorded, the last success is older than `BACKUP_MAX_AGE_HOURS`, or the recorded dump has
disappeared. Alert on the `backup` container being unhealthy:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps backup
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backup
```

## Getting backups off the host

The `backups` volume lives on the same host as the database. That protects against a corrupted
database, not against losing the host. Copy the dumps somewhere else on your own schedule and keep
the `.sha256` files with them. The project does not choose a destination for you.

## Proving a backup restores

Run this against a server that is **not** the live one (or one where a short-lived scratch database
is acceptable), using an account that can create and drop databases:

```bash
export P1_ADMIN_DATABASE_URL='postgresql://<user>:<password>@<restore-host>/postgres'
uv run python scripts/verify_restore.py \
  --backup /path/to/fragrance_rater-20261031T020000Z.dump \
  --output /secure/path/restore-evidence.json \
  --source-inventory /secure/path/live-inventory.json
```

`--source-inventory` is optional. Produce it from the live database with
`scripts/p1_migration_inventory.py --output ...`; with it, the restored data must match the live
data (row counts, timestamp ranges, duplicate keys, invalid foreign keys, and redacted hashes of the
preserved tables).

The script restores the dump into a scratch database, takes the same inventory, compares, and drops
the scratch database. The evidence records the checksum result, the backup's age (the recovery
point you actually have), and how long the restore took (the recovery time). The connection URL is
read from the environment and the password reaches `pg_restore` through `PGPASSWORD`, so it never
appears in a process listing.

| Exit code | Meaning |
| :--- | :--- |
| 0 | Verified |
| 1 | The restore did not match the source, or the dump does not match its checksum |
| 2 | The tool could not do its job (missing dump, unreachable server, failed restore) |

Only 0 means verified. Run it after the first backup, after every migration, and on a regular
schedule; keep the evidence with the release records.

## Restoring for real

Create an empty PostgreSQL 16 database, then:

```bash
sha256sum --check fragrance_rater-<timestamp>.dump.sha256
pg_restore --no-owner --no-privileges --exit-on-error --dbname <new-database> \
  fragrance_rater-<timestamp>.dump
```

Stop the application first, restore into a **new** database, check it with
`scripts/p1_migration_inventory.py`, and only then point the application at it. Never restore over
the only copy of the data you have.
