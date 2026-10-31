#!/bin/sh
# Take, verify, and prune a PostgreSQL backup; or check that a recent one exists.
#
#   backup_database.sh backup   dump, verify, checksum, record, prune
#   backup_database.sh check    exit 0 only if the last backup is recent
#
# It runs inside the postgres:16 image (see the `backup` service in
# docker-compose.prod.yml), which has pg_dump, pg_restore, and psql but not
# Python. Connection settings come from the standard PG* environment variables;
# nothing secret is ever put on a command line.
#
# A backup counts only once it has been verified: the dump must exit cleanly, be
# non-empty, and `pg_restore --list` must be able to read it. The strongest
# check, an actual restore into a scratch database with a before/after
# comparison, is scripts/verify_restore.py; run it on a schedule of its own.
#
# Environment (defaults in brackets):
#   BACKUP_DIR              where backups are written [/backups]
#   BACKUP_RETENTION_DAYS   prune dumps older than this [14]
#   BACKUP_KEEP_MIN         never prune the newest N dumps [3]
#   BACKUP_MAX_AGE_HOURS    `check` fails if the last backup is older [30]
#
# Exit codes: 0 success; 1 the backup or the check failed.

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
KEEP_MIN="${BACKUP_KEEP_MIN:-3}"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-30}"
PREFIX="fragrance_rater"
STATUS_FILE="$BACKUP_DIR/latest.ok"

die() {
    echo "backup: $*" >&2
    exit 1
}

require_number() {
    case "$2" in
        '' | *[!0-9]*) die "$1 must be a whole number, got '$2'" ;;
    esac
}

require_number BACKUP_RETENTION_DAYS "$RETENTION_DAYS"
require_number BACKUP_KEEP_MIN "$KEEP_MIN"
require_number BACKUP_MAX_AGE_HOURS "$MAX_AGE_HOURS"

# Remove dumps beyond the newest KEEP_MIN that are also older than the
# retention window, together with their checksum and manifest.
prune() {
    count=0
    # Names embed a UTC timestamp, so reverse lexical order is newest first.
    for dump in $(ls -1r "$BACKUP_DIR"/"$PREFIX"-*.dump 2>/dev/null); do
        count=$((count + 1))
        [ "$count" -le "$KEEP_MIN" ] && continue
        if [ -n "$(find "$dump" -mtime +"$RETENTION_DAYS" 2>/dev/null)" ]; then
            rm -f "$dump" "$dump.sha256" "$dump.json"
            echo "backup: pruned $(basename "$dump")"
        fi
    done
}

do_backup() {
    umask 077
    mkdir -p "$BACKUP_DIR"

    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    final="$BACKUP_DIR/$PREFIX-$stamp.dump"
    partial="$BACKUP_DIR/.$PREFIX-$stamp.dump.partial"
    # A failed run leaves nothing that could be mistaken for a backup.
    trap 'rm -f "$partial"' EXIT

    pg_dump --format=custom --file="$partial" || die "pg_dump failed"
    [ -s "$partial" ] || die "the dump is empty"
    pg_restore --list "$partial" >/dev/null || die "the dump cannot be read back"

    revision="$(psql -X -At -c 'SELECT version_num FROM alembic_version' 2>/dev/null || true)"
    [ -n "$revision" ] || revision="unknown"
    bytes="$(wc -c <"$partial" | tr -d ' ')"
    digest="$(sha256sum "$partial" | cut -d' ' -f1)"

    mv "$partial" "$final"
    printf '%s  %s\n' "$digest" "$(basename "$final")" >"$final.sha256"
    printf '{"file": "%s", "created_at": "%s", "bytes": %s, "sha256": "%s", "alembic_revision": "%s"}\n' \
        "$(basename "$final")" "$stamp" "$bytes" "$digest" "$revision" >"$final.json"
    # The marker moves only after the dump is complete and recorded, so `check`
    # reflects the last backup that actually succeeded.
    basename "$final" >"$STATUS_FILE"

    echo "backup: wrote $(basename "$final") ($bytes bytes, revision $revision)"
    prune
}

do_check() {
    [ -f "$STATUS_FILE" ] || die "no successful backup has been recorded"
    recent="$(find "$STATUS_FILE" -mmin -"$((MAX_AGE_HOURS * 60))" 2>/dev/null)"
    [ -n "$recent" ] || die "the last successful backup is older than $MAX_AGE_HOURS hours"
    latest="$(cat "$STATUS_FILE")"
    [ -s "$BACKUP_DIR/$latest" ] || die "the recorded backup $latest is missing"
    echo "backup: ok ($latest)"
}

case "${1:-}" in
    backup) do_backup ;;
    check) do_check ;;
    *) die "usage: $0 backup|check" ;;
esac
