#!/bin/sh
set -e

# #CRITICAL: concurrency: running `alembic upgrade head` from more than one
# concurrent replica on first boot into a fresh revision can race (two
# containers both read the same starting version and try to apply it).
# #VERIFY: keep docker-compose.prod.yml's app replicas at 1 until migrations
# move to a dedicated one-shot release step (tracked under Milestone R, R2).
alembic upgrade head

exec "$@"
