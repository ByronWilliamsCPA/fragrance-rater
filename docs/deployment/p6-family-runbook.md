---
title: "P6 family MVP runbook"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Ordered, copy-paste run order for one non-specialist owner to execute the family MVP version of P6 on the real host with six people."
tags:
  - deployment
  - validation
  - planning
---

!!! warning "Reading this closes nothing"
    This runbook executes the family MVP profile of P6 (the owner decisions of 2026-11-25 that scale P6.1 to P6.6 for
    the owner's own household) once the profile pull request is merged. Until then it is a draft procedure and the
    full [P6 pilot readiness](p6-pilot-readiness.md) criteria still stand. **No gate is closed by reading it, and
    following it records no evidence by itself.** It contains no results, no pass marks and no private values. Evidence
    goes to a private directory outside the repository, and the evidence templates in `docs/planning/evidence/` are
    filled only after the steps have actually run, by the owner. A change to the participant build, the session sheet or
    the conditions slip after the rehearsal voids it.

## How to read this page

Every step carries one or more tags:

| Tag | Meaning |
| :--- | :--- |
| **HOST** | Needs the real deployment: docker-host, Portainer, the public Authentik URL. Not repeatable on a laptop. |
| **ROOM** | Needs the six people in one room, with printed paper and water or other unmistakably synthetic samples. |
| **ALONE** | The owner can do it alone in minutes, at the laptop. |

Statements marked **Verified** were checked against the code, the live host (read-only calls) or the repository on
2026-11-25, at main commit `ab47dd3`. Statements marked **Judgement call** are choices this runbook makes where no
repository document decides; the owner may overrule them. Anything not marked was read from a repository document and
is cited by file and section.

### Run order at a glance

| Step | What | Tags | Roughly |
| :--- | :--- | :--- | :--- |
| 0 | Freeze, deploy main through Portainer, record commit and image digests | HOST, ALONE | 30 to 60 min |
| 1.1 | P1.6 forged-header check | HOST, ALONE | 5 min |
| 1.2 | P1.8 target-host smoke report | HOST, ALONE | 15 min |
| 1.3 | The one timed backup, restored to a scratch database (covers P1.2, P1.3, P1.5) | HOST, ALONE | 30 min |
| 1.4 | P1.10 restore log and alert-recipient confirmation | ALONE | 10 min |
| 2 | P6.2 one-device pass: synthetic program setup and manager actions on the facilitator laptop | HOST, ALONE | 60 to 90 min |
| 3 | P6.3 light dry run, one evening, six people | HOST, ROOM | 3 to 4 hours |
| 4 | P6.4 light checks on the facilitator's pages | HOST, ALONE (reload check during step 3) | 30 min |
| 5 | P6.5 shared restore and one-line secret ownership | ALONE | 10 min |
| 6 | P6.6 one-paragraph decision | ALONE | 15 min |

Step 3 needs a day on which the room, the people and a roughly four hour block exist. Everything before it can be done
on separate days. Steps 0 to 2 must be done before step 3, and step 0 again whenever the build changes.

## Conventions used in every step

### Private evidence location

Create one private directory outside any git checkout and keep every artifact in it: command output, exports, scans,
logs, mapping files, spray sheets. Nothing from it is committed. The rule is the same as
[P1 release readiness, Evidence directory](p1-release-readiness.md) (lines 17 to 22) and
[P6 pilot readiness, Evidence handling](p6-pilot-readiness.md) (lines 18 to 27).

```bash
export EVID=~/p6-evidence-$(date -u +%Y%m%d)
mkdir -p -m 700 "$EVID"
if git -C "$EVID" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "STOP: $EVID is inside a git checkout; choose another directory"
fi
```

Blind codes, the mapping, the spray sheets, scans and exports are private even when the data is synthetic.

### Reaching the application from the laptop (the helper)

**Verified.** The production database and the app have no published port. Operator calls go over ssh into the app
container, with the manager username that the app already trusts from `CALIBRATION_ADMIN_USERNAMES`. The same call
without the header is refused with 401 (`AUTHENTIK_IDENTITY_REQUIRED`), which is also a quick reachability check.

```bash
export P6_HOST=byron@192.168.1.209
export P6_MGR=$(ssh -o LogLevel=ERROR "$P6_HOST" docker exec fragrance-rater-app \
  printenv CALIBRATION_ADMIN_USERNAMES | jq -r '.[0]')

# api METHOD /path [json-body]   (path is under /api/v1; prints the body, then "HTTP <status>")
api() {
  local method="$1" path="$2" body="${3-}"
  local cmd="docker exec -i fragrance-rater-app curl -sS -w '\nHTTP %{http_code}\n' -X $method \
-H 'Host: localhost' -H 'X-Authentik-Username: $P6_MGR' -H 'Content-Type: application/json'"
  if [ -n "$body" ]; then
    printf '%s' "$body" | ssh -o LogLevel=ERROR "$P6_HOST" "$cmd --data-binary @- 'http://localhost:8000/api/v1$path'"
  else
    ssh -o LogLevel=ERROR "$P6_HOST" "$cmd 'http://localhost:8000/api/v1$path'"
  fi
}
# apij: the same without the trailing status line, for piping into jq
apij() { api "$@" | sed '$d'; }

api GET /calibration/access   # expect: {"username":"...","manager":true}  then  HTTP 200
```

**Judgement call.** This is an operator path that uses the host login you already hold and a manager username. It does
not use a browser Authentik session cookie, which the owner has rejected for writes. It exercises the same service
code as the browser, but not the proxy, so the participant-facing path (the laptop through Authentik and Traefik) is
exercised separately in steps 2 and 3, and the proxy itself in step 1.1. The routes below are the application's real
routes (verified in `src/fragrance_rater/api/calibration.py`, `capture.py`, `reviewers.py`, `fragrances.py`).

Define the variables each step needs once the objects exist:

```bash
declare -A ENR            # evaluator reference to enrollment id, filled in step 2
PROG=""                   # program id, filled in step 2
```

## Step 0. Freeze and deploy (HOST, ALONE)

**Why.** F1 must run on the exact build that was rehearsed. A deployment that moves under you is the most common way
to void the rehearsal.

### 0.1 Freeze

Confirm that no further change to the participant build, the session sheet or the conditions slip is planned. Pick the
`main` commit that will be deployed and wait until its publish run has finished:

```bash
git fetch origin main
COMMIT=$(git rev-parse origin/main); echo "$COMMIT"
gh run list --workflow docker-publish.yml --branch main --limit 3 \
  --json headSha,status,conclusion,displayTitle
gh run list --workflow ci.yml --branch main --limit 1 --json headSha,status,conclusion
```

Pass rule: the `docker-publish.yml` run for `$COMMIT` is `completed` and `success`, and remote CI on it passed.
**Verified:** every push to `main`, documentation-only ones included, publishes new images and moves `:latest`; the
host only changes when you redeploy, so the digest recorded in 0.4 is what counts, never the tag.

### 0.2 Look at what runs now (read only)

```bash
ssh -o LogLevel=ERROR "$P6_HOST" 'docker ps --format "{{.Names}} {{.Image}} {{.Status}}" | grep fragrance
for c in fragrance-rater-app fragrance-rater-frontend; do
  img=$(docker inspect "$c" --format "{{.Image}}")
  docker image inspect "$img" --format "$c {{index .RepoDigests 0}} revision={{index .Config.Labels \"org.opencontainers.image.revision\"}}"
done'
```

**Verified on 2026-11-25:** four healthy containers (`fragrance-rater-app`, `-frontend`, `-db`, `-db-backup`) and a
running build older than main (revision `d87c89a`), so a redeploy is required and its entrypoint will run
`alembic upgrade head` (`docker-entrypoint.sh`). That migration changes the production schema, which is why step 1.3
takes its backup first.

### 0.3 Take the pre-deploy backup now

Do step 1.3 "Take and copy the backup" before redeploying, so the restore proof covers the schema that is live today
and the migration chain that the deployment will apply. Then return here.

### 0.4 Deploy through Portainer

**Verified (homelab notes).** The stack is `fragrance-rater` (stack 131) on docker-host; Traefik is stack 18. Portainer
does not poll git and does not load `stack.env`, so merging is not deploying. In the Portainer UI: Pull and redeploy
stack 18 (Traefik) first only if the homelab compose changed, then stack 131. The compose file uses `:latest` with
`pull_policy: always`, so the redeploy pulls the newest published images.

### 0.5 Record what is running and verify it

```bash
ssh -o LogLevel=ERROR "$P6_HOST" 'for c in fragrance-rater-app fragrance-rater-frontend; do
  img=$(docker inspect "$c" --format "{{.Image}}")
  docker image inspect "$img" --format "$c {{index .RepoDigests 0}} revision={{index .Config.Labels \"org.opencontainers.image.revision\"}}"
done' | tee "$EVID/release-running.txt"
```

Pass rule: both `revision=` values equal `$COMMIT` (40 characters). Add the commit as a first line of
that file (`echo "commit $COMMIT" | cat - "$EVID/release-running.txt" > "$EVID/release.txt"`); the commit and the two
`sha256:` digests are the "release commit and image digests" the rehearsal log and the readiness record name.

Signature check (recommended, **Judgement call**: the family profile does not waive it, and cosign is not installed on
the development machine). On any machine with cosign v3 and registry access, run the two `cosign verify` commands in
[Image pinning and signing, Verifying an image](image-signing.md) (lines 55 to 83) with `DIGEST` set to each recorded
digest and `COMMIT` set to `$COMMIT`. On the first use of each image, also run it once with a different 40-character
`COMMIT`, which must fail. If cosign cannot be run, write "digests unsigned-verified: not run" in the decision
paragraph (step 6).

### 0.6 Confirm the instrument pin (a known gap, stop here if it fails)

```bash
ssh -o LogLevel=ERROR "$P6_HOST" 'docker exec fragrance-rater-app printenv INSTRUMENT_VERSION' ; echo "exit=$?"
```

Pass rule: the output equals `$COMMIT`. **Verified on 2026-11-25: it is unset** (exit 1). The deployed Portainer stack
does not pass `INSTRUMENT_VERSION` to the app, and it does not use `docker-compose.release.yml` or digest pins, which
[P6 pilot readiness, Entry check](p6-pilot-readiness.md) (lines 50 to 53) assumes. Consequences if left unset:

- A program activated now records `unpinned-app-<package version>` as its instrument build.
- `summarize_evidence_export.py --expect-instrument <SHA>` and the F1 gate refuse that value, so the R7b acceptance
  export in step 3 cannot name the build.

The fix is a change to the homelab compose file in `homelab-infra`, outside this repository, so this runbook cannot make
it: pass `INSTRUMENT_VERSION` through to the `app` service environment and set it to `$COMMIT` in the Portainer stack
variables (a non-secret value), then redeploy and repeat 0.5 and 0.6. Do not activate the synthetic program (step 2)
until this prints the commit, because the value is frozen at activation.

Also check the footer of the page loaded through the public URL says "Instrument build" followed by the commit; the
frontend bakes `VITE_INSTRUMENT_VERSION` at publish time.

## Step 1. P6.1 keep-list (family scope)

Waived by owner decision (not run): P1.4 representative-volume concurrency, and the P1.1 second label check.
P1.9 is already closed as historical (ADR-012). P1.7 is gathered during step 3.

### 1.1 P1.6 deployed forged-header check (HOST, ALONE)

Source: [P1 release readiness](p1-release-readiness.md), "Forged-header check", lines 301 to 315. The throwaway
container must sit on the private app network, which is outside the Traefik edge network, never on
`fragrance-rater-ingress`.

**Verified for this host:** the app network is `fragrance-rater_backend-net`; the frontend answers there under the
name `frontend`; `http://frontend/health` with the public host name returned 200. Run the check:

```bash
FRAGRANCE_HOST=fragrance.williamshome.family
ssh -o LogLevel=ERROR "$P6_HOST" "docker run --rm --network fragrance-rater_backend-net curlimages/curl \
  -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Host: $FRAGRANCE_HOST' -H 'Content-Type: application/json' \
  -H 'X-Authentik-Username: $P6_MGR' -d '{\"name\":\"forged-header probe\"}' http://frontend/api/v1/reviewers" \
  | tee "$EVID/p1-6-forged-header.txt"
```

Expected result: `401`. Pass rule: exactly `401`; anything else fails P1.6. Also confirm the public edge challenges an
unauthenticated caller (the P1 runbook's "must be challenged", lines 295 to 297):

```bash
curl -s -o /dev/null -m 15 -w '%{http_code} %{redirect_url}\n' https://$FRAGRANCE_HOST/ | cut -c1-90
```

Expected: `302` to the Authentik host. If the forged-header probe returned anything but 401, a reviewer named
"forged-header probe" may exist: list `GET /reviewers` and delete it with `DELETE /api/v1/reviewers/{id}` (a soft
delete, verified in `reviewers.py`), then treat P1.6 as failed.

Where the result goes: `$EVID/p1-6-forged-header.txt` (status code, UTC time, operator). Not the repository.

### 1.2 P1.8 target-host smoke report (HOST, ALONE)

**Judgement call.** There is no committed smoke script for the target host; the P1 gate row only requires a "target-host
smoke report". This is the minimum report for a four-container household stack. Run it after step 0, from the laptop:

```bash
{
  echo "utc: $(date -u +%FT%TZ)"
  echo "== containers"; ssh -o LogLevel=ERROR "$P6_HOST" 'docker ps --format "{{.Names}} {{.Status}}" | grep fragrance'
  echo "== app readiness (in container)"
  ssh -o LogLevel=ERROR "$P6_HOST" 'for p in live ready startup; do
    printf "%s " $p; docker exec fragrance-rater-app curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health/$p; done'
  echo "== public edge challenges the unauthenticated"
  curl -s -o /dev/null -m 15 -w '%{http_code}\n' https://fragrance.williamshome.family/
  echo "== manager identity reaches the app"; api GET /calibration/access | sed -E 's/"username":"[^"]*"/"username":"<masked>"/'
  echo "== schema head"
  ssh -o LogLevel=ERROR "$P6_HOST" 'docker exec -e PGOPTIONS="-c default_transaction_read_only=on" fragrance-rater-db \
    psql -U fragrance_rater -d fragrance_rater -tAc "select version_num from alembic_version"'
  echo "== backup freshness (seconds since last success)"
  ssh -o LogLevel=ERROR "$P6_HOST" 'echo $(( $(date -u +%s) - $(cat /mnt/unraid/backups/fragrance-rater/.last_success) ))'
} 2>&1 | tee "$EVID/p1-8-smoke.txt"
( cd ~/dev/fragrance-rater && uv run alembic heads )   # compare with the schema head above, from the deployed commit
```

Pass rule: four containers healthy; `live`, `ready` and `startup` all 200; the public URL answers 302; `access` shows
`manager: true`; the database revision equals the head of `alembic heads` at `$COMMIT`; the last backup is under 48 hours
old (the sidecar's own health rule). Then open the public URL in the laptop browser, sign in through Authentik, and
confirm the footer reads "Instrument build" followed by `$COMMIT`. Write "pass" or the failing line in the note beside
`p1-8-smoke.txt`.

### 1.3 The one timed backup, restored to a scratch database (HOST, ALONE; covers P1.2, P1.3, P1.5)

Sources: [P1 release readiness](p1-release-readiness.md), "Restore and pre-upgrade inventory" (lines 101 to 129) and
"Migration and data assertions" (lines 131 to 158); [Backup and restore](backup-and-restore.md), "Proving a backup
restores" (lines 87 to 128).

**Verified on 2026-11-25 against the real dump, and it changes the procedure:**

- The homelab backup sidecar writes `pg_dump -Fc -n public` dumps (daily, 14 days kept, with no `.sha256` or json
  sidecar) to `/mnt/unraid/backups/fragrance-rater/` on docker-host. Restoring such a dump into a fresh database always
  reports one error, `CREATE SCHEMA public;` (the schema already exists). `scripts/verify_restore.py` restores with
  `--exit-on-error`, so it **fails with `pg_restore failed (exit 1)` on this dump** and cannot be used as it stands.
  This runbook therefore restores with plain `pg_restore` and treats exactly that one error as expected.
- The docker-host does not allow ssh port forwarding to the scratch database and does not open database ports to the
  laptop, so the scratch server is a throwaway local cluster on the laptop (PostgreSQL 16 binaries are installed:
  `pg_restore` 16.15 matches the 16 server).
- The pre-deploy production schema is `736b7db082fb` and the repository head is later, so the restored copy is also
  the migration test (P1.3): `alembic upgrade head` ran cleanly on it for the three newer revisions, and a second run
  was a no-op.

#### Take and copy the backup (HOST, ALONE; do this before step 0.4)

```bash
BK="$EVID/pre-deploy-$(date -u +%Y%m%dT%H%M%SZ).dump"
ssh -o LogLevel=ERROR "$P6_HOST" 'docker exec fragrance-rater-db pg_dump -U fragrance_rater -Fc -n public fragrance_rater' > "$BK"
echo "exit=$?"; ls -l "$BK"; sha256sum "$BK" | tee "$EVID/backup.sha256"
pg_restore --list "$BK" | head -3 | tee "$EVID/pg_restore-list-head.txt"
```

This is the same command shape as the sidecar's and takes a fresh recovery point of "now", so the backup age is zero by
construction; also record the newest sidecar dump (`ls -l --time-style=full-iso /mnt/unraid/backups/fragrance-rater | tail -3`
on the host) as the unattended recovery point that exists today. Pass rule: exit 0, non-empty, `pg_restore --list`
reads it.

#### Restore it, timed (ALONE)

```bash
PGB=/usr/lib/postgresql/16/bin
SCR=$(mktemp -d)                       # scratch cluster directory, deleted at the end
$PGB/initdb -D "$SCR/data" -U scratch --auth=trust -E UTF8 >/dev/null
$PGB/pg_ctl -D "$SCR/data" -o "-p 55432 -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" \
  -l "$SCR/log" -w start
export PGHOST=127.0.0.1 PGPORT=55432 PGUSER=scratch
$PGB/createdb p6_restore
START=$(date +%s)
$PGB/pg_restore --no-owner --no-privileges -d p6_restore "$BK" 2>&1 | tee "$EVID/pg_restore.log"
echo "restore seconds: $(( $(date +%s) - START ))" | tee "$EVID/restore-time.txt"
$PGB/psql -d p6_restore -tAc "select version_num from alembic_version"
```

Expected: `pg_restore: warning: errors ignored on restore: 1` and the one error naming `CREATE SCHEMA public;`, and nothing
else. Any other error line means the restore failed. Pass rule: only that expected error; the revision printed is
`736b7db082fb` (or whatever step 0.2 showed as live); the elapsed time is written in `restore-time.txt` (this is the
recovery time).

Compare the restored data with the live data: row counts per table, live first, then restored.

```bash
LIVE_SQL="select relname, n_live_tup from pg_stat_user_tables order by 1"      # fast but approximate; use exact counts below
for t in fragrances reviewers calibration_programs evaluations; do
  live=$(ssh -o LogLevel=ERROR "$P6_HOST" "docker exec -e PGOPTIONS='-c default_transaction_read_only=on' fragrance-rater-db \
    psql -U fragrance_rater -d fragrance_rater -tAc 'select count(*) from $t'")
  rest=$($PGB/psql -d p6_restore -tAc "select count(*) from $t")
  echo "$t live=$live restored=$rest"
done | tee "$EVID/row-counts.txt"
```

Pass rule: every pair is equal. **Verified on 2026-11-25:** production held 43 `fragrances` rows (the P1.1 catalog rows
created on 2026-11-24), 0 `reviewers` and 0 `calibration_programs`. The family profile text says production holds no
fragrance rows; the live database disagrees, so state the real counts in the log rather than the profile's wording.
Row counts are a lighter check than the hashed inventory in `scripts/p1_migration_inventory.py`; that script needs a
direct database connection to the live server, which does not exist here, so it can only be run against the restored
copy (it is not needed for the family pass, and omitting it is a **Judgement call**).

#### Apply the migration chain to the restored copy (P1.3)

```bash
export DATABASE_URL="postgresql+asyncpg://scratch@127.0.0.1:55432/p6_restore"
git -C ~/dev/fragrance-rater checkout --detach "$COMMIT" 2>/dev/null || true   # or run from a checkout at $COMMIT
uv run alembic current
uv run alembic upgrade head 2>&1 | tee "$EVID/alembic-upgrade.log"
uv run alembic current
uv run alembic upgrade head          # must be a no-op
```

Pass rule: `current` after the upgrade is the head at `$COMMIT`; the second `upgrade head` prints no `Running upgrade`
line; row counts on the restored copy are unchanged after the upgrade (rerun the count loop's `rest=` line).
Run it from a checkout of `$COMMIT`, not from a branch with other changes; do not move your working checkout if it has
local edits (use a separate worktree instead).

Finally stop and delete the scratch server and drop the variables:

```bash
$PGB/pg_ctl -D "$SCR/data" -m fast stop && rm -rf "$SCR"
unset PGHOST PGPORT PGUSER DATABASE_URL
```

Where the results go: the files above in `$EVID`; the dump and its hash stay private (it contains the catalog rows and,
later, would contain evaluations). The one exercise answers P1.2 (restore of a real backup with an inventory), P1.3
(the chain on real data) and P1.5 (timed recovery) for the family profile.

**Note for the maintainer, not an owner task.** `verify_restore.py` and the repository's own
`backup_database.sh` (a whole-database dump) assume a different backup shape from the homelab sidecar's `-n public`
dump. Reconciling them (for example a restore flag that tolerates the existing `public` schema) is a code change and is
not part of this runbook.

### 1.4 P1.10 restore log and alert-recipient confirmation (ALONE)

The restore log is the set of files from step 1.3. Add one line of your own to `$EVID/p1-10-operations.txt`:

```text
Alert recipient: <who is notified, and how, when fragrance-rater-db-backup or fragrance-rater-app becomes unhealthy>
Confirmed on: <UTC date>, by: <name>
```

The sidecar's health rule is "last successful backup under 172800 seconds old" (verified in the homelab compose), and
the stack has no alerting of its own that this repository can see. If nobody is notified, write that, and carry it
into the known limitations in step 6; do not invent a recipient. OpenRouter zero retention, the secret-rotation drill
and the log-correlation checks of [P1 release readiness, Operations checks](p1-release-readiness.md) (lines 325 to 334)
are outside the family keep-list.

## Step 2. P6.2 one-device pass: set up the synthetic program (HOST, ALONE)

**Scope.** One device: the facilitator's laptop, through the public Authentik and Traefik URL, signed in as yourself.
It covers the single recorder login and the manager actions the format needs: session-plan preview, non-blind call,
checkpoints, readiness view, household reveal. Evaluators have no logins, so there is no evaluator device matrix.
Do the setup here and the checkpoint, readiness and reveal actions during step 3 (they need the paper to exist).

Use clearly synthetic names everywhere. They remain in the production database afterwards; F1 uses a new program, and the
`SYNTH` prefix makes them easy to find and ignore.

### 2.1 Create six evaluators and six sample versions (API, because no screen creates them)

**Verified.** No page creates evaluators or catalog rows, so these twelve objects are created through the helper. The
fragrance fields below are the required ones (`name`, `brand`, `concentration`, `primary_family`, `subfamily`); the
`Unclassified` family value is what the existing 43 catalog rows already use, and the bodies below passed the
application's own request models.

```bash
for n in 1 2 3 4 5 6; do
  api POST /reviewers "{\"name\":\"SYNTH Evaluator E$n\"}"
done
for l in A B C D E F; do
  api POST /fragrances "{\"name\":\"SYNTH water $l\",\"brand\":\"SYNTHETIC REHEARSAL\",\"concentration\":\"water\",\"version_key\":\"synthetic-rehearsal-$l\",\"primary_family\":\"Unclassified\",\"subfamily\":\"Unclassified\"}"
done | tee "$EVID/synthetic-fragrances.txt"
```

Expected: `HTTP 201` twelve times. A `409 REVIEWER_EXISTS` means a name was already used.

**Judgement call: the physical samples.** Six vials of unmistakably synthetic liquid, labelled by the owner with the six
names above (water, or a coloured water; never a real fragrance). The vial label is the only place the mapping lives on
paper and is facilitator-only.

### 2.2 Program setup on the laptop (UI)

Sign in through the public URL, open **Program setup** (manager only). Use these labels (verified in
`ProgramSetupPage.tsx`).

1. **1. Program definition**: Name `SYNTHETIC REHEARSAL 2026-11`, Version `rehearsal-1`, Description `Light dry run, water
   samples only`, Blotter mode `INDIVIDUAL` (the default), press **Create draft**.
2. In the reveal policy control of the checkpoints panel (select **Reveal policy**, option "Whole household together,
   after the final samples", then **Save reveal policy**). It can only be changed while the program is a draft.
3. **Find catalog version** (search `SYNTH water`), pick the exact version in **Exact catalog version**, set **Role**
   `UNIVERSAL_BASELINE` for A, B, C (Group `Baseline`) and `HOLDOUT` for D, E, F (Group `Holdout`), fill **Version
   verification evidence** with `Synthetic water sample; no real product`, press **Add version**. Six times.
4. Review **Frozen definition preview**, press **Activate and lock definition**, then **Confirm activation**.

Pass rule: activation succeeds, the program status is active, and before pressing activate you have confirmed step 0.6
(a pinned instrument). Then read the pin that was recorded:

```bash
PROG=$(apij GET /calibration/programs | jq -r '.[] | select(.name=="SYNTHETIC REHEARSAL 2026-11") | .id'); echo "$PROG"
```

Expected: one id. The recorded `instrument_version` is checked in the export in step 3.12; it must equal `$COMMIT`.

### 2.3 Session-plan preview and enrollment (UI)

In **2. Enrollment**: pick **Evaluator** `SYNTH Evaluator E1`; **Authorized recorder usernames**: the Authentik username you
sign in with (the one `CALIBRATION_ADMIN_USERNAMES` names); **Samples per session** `3`; **Session order** option "Shared
sessions, balanced order per evaluator (facilitated)"; press **Preview session plan** and open the "Session plan
preview" region (with "Show fragrance identities (manager only)"). Expected: two sessions of three, the first with the
three baseline versions, the second with the three holdouts (holdouts form the last block, `shared_triples.py`).
Press **Enroll evaluator**; the notice reads "Evaluator enrolled; sessions and blind codes are ready."

Enroll E2, E3, E4, E5 and E6 the same way, **in that order**: each evaluator's order within a session comes from a
balanced Latin-square row chosen by the enrollment's ordinal, and every enrollment reuses the program's recorded
session composition. Then read the ids:

```bash
for n in 1 2 3 4 5 6; do
  ENR[E$n]=$(apij GET /calibration/manager/enrollments | jq -r --arg n "SYNTH Evaluator E$n" '.[] | select(.reviewer_name==$n) | .id')
done
declare -p ENR
```

Expected: six distinct ids. These are not secret, but the mapping reachable through them is.

### 2.4 Non-blind call for the holder (UI), before any exposure

In **Evaluator who holds the answer key** (the non-blind panel): select **Evaluator who holds the mapping**
`SYNTH Evaluator E1`; **Written reason**: `Declared mapping holder; facilitates, transcribes and controls the reveal
(synthetic rehearsal)`; press **Mark evaluator non-blind**, then **Confirm non-blind**. Write the UTC date and time in
`$EVID/non-blind-call.txt`: it must precede the first exposure of step 3, and the same date goes into the private
pre-exposure declaration. The route behind it is `POST /api/v1/calibration/enrollments/{id}/non-blind` and is
idempotent (it returns `flagged` and `already_flagged` session lists).

### 2.5 Readiness view (UI) and a first look

Open the checkpoints panel (heading "Checkpoints and reveal") and press **Refresh readiness**. Expected before any
sheet is entered: six rows, Checkpoint column showing a blocker label (not "Frozen"), Reveal column not "Ready to
reveal". Cross-check with the API (it also shows the per-evaluator `holdouts_open`, which the screen does not name):

```bash
apij GET /calibration/programs/$PROG/readiness | jq '{reveal_policy,blotter_mode,household_reveal_ready,enrollments_missing_checkpoint:(.enrollments_missing_checkpoint|length),rows:[.enrollments[]|{reviewer_name,checkpoint_blocker,holdouts_open,reveal_blocker}]}'
```

Expected: `reveal_policy` `HOUSEHOLD`, `blotter_mode` `INDIVIDUAL`, `household_reveal_ready` false, every `holdouts_open`
false.

### 2.6 Prepare the paper (ALONE, the day before step 3)

Pull the mapping for all six evaluators into the private directory and build the facilitator spray sheets and the
per-evaluator headers. **Verified:** the mapping route is manager-only and audited, and its output carries blind codes
and fragrance names, so it never leaves the private directory.

```bash
for n in 1 2 3 4 5 6; do apij GET /calibration/enrollments/${ENR[E$n]}/mapping > "$EVID/map-E$n.json"; done
for n in 1 2 3 4 5 6; do
  jq --arg ev "E$n" 'map({session:(if .role=="HOLDOUT" then "holdout" else "baseline" end), vial:.fragrance_name, evaluator:$ev, position:.position, blind_code:.blind_code})' "$EVID/map-E$n.json"
done | jq -s 'add' > "$EVID/mapping.json"
jq length "$EVID/mapping.json"        # expect 36 (six evaluators, six positions each)
cd ~/dev/fragrance-rater && uv run python scripts/make_spray_sheets.py --mapping "$EVID/mapping.json" --output-dir "$EVID/spray-sheets"
```

**Judgement call:** the `session` key is `baseline` or `holdout` because this program has exactly one session of each
(the sessions of one enrollment have no guaranteed order in the mapping output, so the role is a safer key than the
position in the list). The script writes `facilitator-only/` spray sheets and `paper-record-index.csv` (vial numbers,
facilitator only) and `evaluator-headers/` files (paper record ID, evaluator reference, blind codes only). It refuses to
write inside a git repository unless the directory is ignored; `$EVID` is outside one.

Print the forms (needs pandoc and Google Chrome; the default output directory is the gitignored `tmp_cleanup/print`, so
give it the private directory):

```bash
cd ~/dev/fragrance-rater && scripts/print_forms.sh "$EVID/print"
```

Expected: four PDFs; the session sheet is four pages (two duplex sheets) and the script fails if it is not.

| Print | Version | Count for the evening |
| :--- | :--- | :--- |
| Session sheet | `facilitated-session-sheet v2.1` | 12 (six evaluators, two sittings), plus 2 spares |
| Conditions slip | `facilitated-conditions-slip v1.0` | 12, for the evaluators who accept session context, plus 2 spares |
| Spray sheets and headers | from `make_spray_sheets.py` | one header per evaluator per sitting (12); two facilitator sheets |
| Property guide | `facilitated-property-guide v1.0` | optional; it is outside the P6.3 instrument, so if it is handed out, write that down and do not count it as rehearsed |
| Run sheet | `facilitated-run-sheet` | one, for the facilitator |

Before the evening, fill in each printed sheet from its header: Part A (paper record ID, evaluator reference, blotter
mode `Individual trays`, Data classification `Synthetic rehearsal`) and the blind code row of Part B, and have a second
person check every code against the header file. **Judgement call:** the repository renders the blank sheet and a
separate header file; how the pre-printed values reach the paper is not stated, so time how long hand filling takes
and write it in the log (the real F1 has the same job at 17 sessions).

## Step 3. P6.3 light dry run: the evening script (HOST, ROOM)

**People.** Six, one per evaluator reference. E1 is the owner: the declared mapping holder, flagged non-blind, who also
facilitates, transcribes and controls the reveal, and who does **not** evaluate in the sitting of the other five. E2 to
E6 are the five others. E1's own two sittings are separate, single-blind with observer cues; one of the five acts as
the observer. **Samples.** The six synthetic liquids. Everyone, facilitator included, wears no fragrance.
Source for the room and the procedure: [`facilitated-run-sheet.md`](../facilitated-run-sheet.md) ("Room setup and
ventilation", "Individual blotters (F1)", "Order of operations for one session", "Transcription window"). Read it
before the evening; this script is the dry-run order, not a replacement.

**Phase order, fixed:** baseline sitting, transcription of the baseline sheets, one checkpoint per enrollment, then the
holdout sitting, transcription, and the household reveal last. The four deliberate failures are placed inside it.

### 3.0 Before anyone arrives (ROOM, 30 min)

- Ventilation running from 15 minutes before the first spray; no cooking, candles or air fresheners. Six seats about
  1.5 m apart, facing away from each other; at each: a pen, the evaluator's own sheet on a clipboard, the evaluator's own
  tray of three coded blotters in that evaluator's order (from the header), a clock everyone can see.
- A lidded jar outside the room for finished blotters. Water for comfort only. Phones out of the room.
- Read the room thermometer for the slips if you have one (optional; a hygrometer is not needed, leave humidity blank
  and note that no reading was taken). Write on a facilitator sheet: date, start time, who is E1 to E6
  by paper record ID only (never names next to codes).
- Open the laptop on the application, signed in through the public URL, **Calibration**, with the evaluator selector
  ready. Confirm the readiness view still shows all six rows without a checkpoint.
- Start the log (see "What to write in the rehearsal log" at the end of this step). Note the clock difference between the
  wall clock, the laptop and the phone used for timing; paper times are hh:mm:ss on the wall clock.

### 3.1 Consent, once per evaluator, with the evaluator present (ROOM, 20 min)

Each person in turn, at the laptop with the owner: choose their evaluator in the wizard, read the consent text shown
("Before you begin"), tick **I agree to answer questions about my conditions** only if they accept session context,
enter "Where the evaluator wrote their consent" (for example `paper sheet`), and record the consent. Do **not**
press **Continue to the samples** yet (that starts the session; its start time comes from the sheet later).

**Judgement call.** Consent has no screen of its own; it lives in the session intro. The run sheet says to record it once
before session 1, so this step records it before the sitting and stops short of starting the session. Write down what you
saw when the same evaluator's intro appears again during transcription (expected: consent already shown as given, no
second request).

Record in the log: the consent time per evaluator (the declaration needs the date for each).

### 3.2 Baseline sitting, five evaluators on paper, E2 to E6 (ROOM, 30 min)

Run the sheet's order of operations, steps 1 to 11, for sample 1, 2, 3. For each sample: on the facilitator's signal
each evaluator sprays their own blotter (one spray from about 15 cm or 6 in, pointed away from faces and other
blotters), writes their own spray time, smells once, writes their own first-smell time, completes the column and
initials it. The facilitator helps with blotters and trays, keeps the clock, removes finished blotters to the jar, and
signals the next round only after the clean-air interval (at least 2 minutes after the last sniff; about 5 after a
persistent or aversive sample).

Counted and recorded during this sitting:

- Spray to first smell for each evaluator and sample against the **2 minute ceiling** (from that evaluator's own spray to
  their own first smell). Do not confuse it with the clean-air interval.
- Vial access (owner decision, 2026-11-26): evaluators walk up to the vials as they are ready; the facilitator does not
  schedule or control turns at the vials. Record how often evaluators queued or crowded at the vials. If the walk-up
  approach had to be changed, note it in the rehearsal log (that would be a new owner decision).
- **At least one fresh blotter**: tell one evaluator (E4) to let the 2 minutes pass before smelling sample 1. They must
  not smell it, spray a fresh blotter of the same sample (same blind code), write the new spray time on the sheet, and
  smell that one. Count it.
- One ambiguous mark (an evaluator circles two values): to be entered as blank plus a flag.

Collect all five sheets at the end. Note the end time. Say only that the sitting is finished and when the next is.

### 3.3 E1's own baseline sitting (ROOM, 20 min)

The observer (one of the five) hands over blotters with a neutral face and the same routine; E1 does not look at the
vial mapping. Same sheet, same ceiling, same routine. Collect E1's sheet.

E6's paper is set aside untouched. It is transcribed later, on purpose, to rehearse failure (4).

### 3.4 Transcription of E1 to E5 through the single recorder login (ALONE at the laptop, ROOM stays)

For each of E1, E2, E3, E4, E5 (the owner alone; nobody else touches the laptop), in the Calibration wizard:

1. Select the evaluator in the **Evaluator** selector; check the evaluator name and the paper record ID on the paper
   against the enrollment on the screen **before saving anything** (this is the owner decision on the wrong-evaluator
   case).
2. **Before you begin**: record the conditions from that evaluator's slip, **Save conditions** (only if they accepted);
   enter **Session start time written on the sheet**; press **Continue to the samples**.
3. For each sample: type the code from the paper column into **Blind code printed on the sheet**, then **Time sprayed**,
   **Time first smelled**, **Time this column finished** and the scores; compare the screen with the paper; **Save
   observation**. A saved observation cannot be edited. An ambiguous mark is entered blank plus a flag.
4. **Lock blotter responses**, then **Confirm blotter lock**; do the ranking (**Save ranking**, or the "rather not
   rank" options); **Facilitator: continue** with the session end time; complete Part E on the paper sheet and sign.
5. Skin plan: **Finalize skin-test plan**, then **Confirm final plan**. **Judgement call:** the dry run does not rehearse
   skin tests; all six finalize an empty plan, which the household policy needs before a checkpoint. In F1 only the
   owner (E1) does skin tests.

Times: a spray or smell time typed that is before the session existed, or more than 7 days ago, is refused as a probable
typo; this evening's times are fine. A column whose first smell is more than 2 minutes after the spray is saved and
raises the `spray_to_smell_ceiling_exceeded` flag; it is not refused.

#### Deliberate failure (1): a sheet entered under the wrong evaluator

While transcribing E3, before saving the first column, do this once in the browser: type E4's blind code for the same
position into **Blind code printed on the sheet**. **Verified:** the screen stops the entry before any request is sent.
Write down the message shown. Then capture the server's own answer through the helper, using E3's first presentation id
and E4's code for the same sample position:

```bash
E3_P=$(apij GET /calibration/enrollments/${ENR[E3]} | jq -r '[.presentations[]|select(.available)][0].id')
E4_CODE=$(jq -r '.[0].blind_code' "$EVID/map-E4.json")   # any code that is not E3's code for this sample
api POST /calibration/presentations/$E3_P/exposure \
  "{\"stage\":\"BLOTTER\",\"at\":\"$(date -u +%FT%TZ)\",\"confirmed_blind_code\":\"$E4_CODE\"}" | tee "$EVID/failure-1.txt"
```

Expected: `HTTP 409` with the body detail `The blind code entered does not match this sample`; nothing is saved (the check runs
before anything is written). Pass rule: 409 and that message. If the call is accepted (the code happened to be E3's own,
which random codes make vanishingly unlikely, or the check did not run), record it honestly as a failure of the guard.
This guard shows that the codes belong to the enrollment on screen; it is not proof of which person wrote the paper,
which is why step 1 above (name and record ID checked by eye) stays.

### 3.5 Freeze checkpoints: one per enrollment that is ready (ALONE, laptop)

In the checkpoints panel press **Refresh readiness**, then **Freeze checkpoints** and **Confirm checkpoints**
(`POST /programs/{id}/checkpoints`; it freezes every ready enrollment that has none and skips the others).

Expected now: E1 to E5 created; **E6 skipped** (its baseline blotters are not locked, so the Checkpoint column keeps a
blocker label such as "Blotter responses remain"). The panel's table and the API show it:

```bash
apij GET /calibration/programs/$PROG/readiness | jq '{enrollments_missing_checkpoint, rows:[.enrollments[]|{reviewer_name,checkpoint_count,checkpoint_blocker,holdouts_open}]}'
for n in 1 2 3 4 5; do
  echo -n "E$n checkpoint created_at (UTC): "; apij GET /calibration/enrollments/${ENR[E$n]}/checkpoints | jq -r '.[0].created_at'
done | tee "$EVID/checkpoint-times.txt"
```

Write each created time into the private declaration ("checkpoint creation times per enrollment"). The readiness view
shows who is missing a checkpoint, not when each was created; this call is the only place the time appears.

#### Deliberate failure (4): a holdout write with no checkpoint of its own

E6 has no checkpoint. Its holdout samples are present in its enrollment payload but unavailable. Try an exposure on one:

```bash
E6_H=$(apij GET /calibration/enrollments/${ENR[E6]} | jq -r '[.presentations[]|select(.available==false)][0].id')
E6_HCODE=$(apij GET /calibration/enrollments/${ENR[E6]} | jq -r '[.presentations[]|select(.available==false)][0].blind_code')
api POST /calibration/presentations/$E6_H/exposure \
  "{\"stage\":\"BLOTTER\",\"at\":\"$(date -u +%FT%TZ)\",\"confirmed_blind_code\":\"$E6_HCODE\"}" | tee "$EVID/failure-4.txt"
```

Expected: `HTTP 409` and the detail `This sample is not open yet: it opens after the organizer freezes this evaluator's checkpoint`.
Pass rule: 409 with that message. The same refusal applies to an observation, a lock, a session start and a ranking on
that holdout. The wizard never offers a closed holdout, which is why this is an API call.

#### Deliberate failure (3): a holdout whose times pre-date the evaluator's own checkpoint

E2 has a checkpoint now. Use a first-smell time one minute **before** that checkpoint was created, with E2's correct
blind code, so that the code check and the "is it open" check pass and only the evidence-time check can refuse:

```bash
CP=$(apij GET /calibration/enrollments/${ENR[E2]}/checkpoints | jq -r '.[0].created_at')   # naive UTC
BEFORE=$(date -u -d "${CP%.*}Z 1 minute ago" +%FT%TZ)
```

The participant payload hides roles on purpose, so take the holdout from the facilitator's private mapping: in
`$EVID/map-E2.json` the entries with `"role":"HOLDOUT"` give the blind codes; find the presentation whose `blind_code`
matches in the E2 payload.

```bash
E2_HCODE=$(jq -r '[.[]|select(.role=="HOLDOUT")][0].blind_code' "$EVID/map-E2.json")
E2_H=$(apij GET /calibration/enrollments/${ENR[E2]} | jq -r --arg c "$E2_HCODE" '.presentations[]|select(.blind_code==$c)|.id')
api POST /calibration/presentations/$E2_H/exposure \
  "{\"stage\":\"BLOTTER\",\"at\":\"$BEFORE\",\"confirmed_blind_code\":\"$E2_HCODE\"}" | tee "$EVID/failure-3.txt"
```

Expected: `HTTP 422` and a detail that begins `The first-smell time is earlier than the checkpoint that opens this sample;
evidence for it cannot pre-date the checkpoint`. Pass rule: 422 with that message, and the holdout presentation still has
no `presented_at` (confirm in the E2 payload). The same refusal applies to a spray time ("The spray time"), a column-finished
time ("The column-finished time") and a ranking time ("The ranking time"). The wizard cannot show a closed holdout, so this
is an API call. If `$BEFORE` falls before the session existed the server answers a different 422 (`... is before this
session existed`); then the enrollment was less than a minute older than the checkpoint, so pick a time between them.

### 3.6 E6's sheet and the second checkpoint (ALONE)

Transcribe E6's baseline sheet exactly as in 3.4, including locking and the empty skin plan. Press **Freeze checkpoints**
again: expected `created` holds E6 only and `skipped` is empty. Refresh readiness: all six rows show "Frozen", and each
`holdouts_open` is true. Record E6's created time as in 3.5.

**Do not run the holdout sitting until all six rows show `holdouts_open` true.** A holdout smelled before its checkpoint
cannot be made prospective afterwards, and the server cannot know when a blotter was smelled on paper. If it happens,
do not transcribe it as prospective; record it in the deviation log.

### 3.7 Holdout sitting (ROOM, 30 min)

Same room, same routine, E2 to E6 on paper with the holdout trays, then E1 on their own. Ask the five to run it as in
3.2, with one change: tell one evaluator (E3) to smell sample 2 after the 2 minutes without telling the facilitator
beforehand. They write the true time and report it. **Do not** re-spray to repair it; nothing is dropped or adjusted.
Count it (it is the "breach" the log needs). **Withdrawal of one of the six (failure 2):** E5 does not attend this
sitting; the owner says E5 "has withdrawn" and removes E5's tray. Four evaluators plus E1 sit it.

### 3.8 Transcribe the holdouts and rehearse the withdrawal gap (ALONE)

Transcribe E1, E2, E3, E4, E6 as in 3.4 (their holdout columns, locks, rankings). E3's late smell enters with the true
times; expect the ceiling flag. Do not transcribe E5.

#### Deliberate failure (2): withdrawal documents the known gap

Refresh readiness: E5 shows a blocker ("Final samples remain" or similar), the others "Ready to reveal"; the reveal
button is disabled. Try the reveal through the API anyway:

```bash
api POST /calibration/programs/$PROG/reveal | tee "$EVID/failure-2.txt"
```

Expected: `HTTP 409` and a detail of the form `1 of 6 evaluators still have blind work, a checkpoint, or final samples outstanding`
(1 blocked, 6 not yet revealed). Pass rule: 409 with that message and nobody revealed. Then write down the known gap
exactly: **there is no route to withdraw an enrolled evaluator** (verified: none exists in `api/calibration.py`), so the
household reveal waits until that evaluator finishes; there is no code change for it and the owner decides at that time
what to do (owner decision, 2026-11-25). For the rehearsal to continue, E5 now "returns": run a short make-up holdout
sitting for E5 alone (3.7's routine, one evaluator), transcribe it as in 3.4, and refresh readiness: all six ready.

### 3.9 Household reveal (ALONE, laptop)

Press **Reveal the household**, then **Confirm household reveal** (`POST /programs/{id}/reveal`). Expected: success,
`household_revealed` true, every row revealed. Afterwards the wizard shows identities for the samples (post-reveal
entry). Verify with the API that the revealed state is program-wide:

```bash
apij GET /calibration/programs/$PROG/readiness | jq '{household_revealed, rows:[.enrollments[]|{reviewer_name,revealed}]}'
```

A reveal of one enrollment alone must be refused for this program (`This program reveals every evaluator together; a
manager reveals it from the program`); optional, not part of the four failures.

### 3.10 P1.7 disclosure evidence, gathered now (ALONE)

Before step 3.9 (or on a spare enrollment if the reveal has passed), a participant payload must carry no identity and no
fragrance name:

```bash
apij GET /calibration/enrollments/${ENR[E2]} | jq 'any(.presentations[]; has("identity"))'
apij GET /calibration/enrollments/${ENR[E2]} | grep -c 'SYNTH water'
```

Pass rule (before the reveal): `false` and `0`. After the reveal `identity` appears on each presentation. Also confirm the
error bodies captured in `failure-1.txt`, `failure-3.txt` and `failure-4.txt` contain no sample name, no code of another
evaluator and no role. The facilitator pages that reveal identity are the mapping route and the "Show fragrance
identities (manager only)" preview, which only a manager can open. Save the outputs in `$EVID`.

### 3.11 Paper, scans and retention (ALONE)

Scan every page of every session sheet (all four pages; the second sheet is Part E and the instructions), keep the
originals, scan the slips into a different folder, keep sheets and slips in separate folders and never write an
identity, role or mapping on a sheet or a filename. Paper, scans and slips are kept 12 months after the evaluation ends
and destroyed together with the database and its backups (owner decision, matching the consent text). Keep the deviation
log with the sheets, apart from the mapping.

### 3.12 The R7b acceptance export, naming the exact build (ALONE)

```bash
for n in 1 2 3 4 5 6; do apij GET /calibration/enrollments/${ENR[E$n]}/evidence-export > "$EVID/export-E$n.json"; done
cd ~/dev/fragrance-rater
uv run python scripts/summarize_evidence_export.py --require-each-field-once \
  --expect-instrument "$COMMIT" "$EVID"/export-E?.json | tee "$EVID/r7b-summary.txt"
```

Pass rule (from [P6 pilot readiness](p6-pilot-readiness.md), lines 93 to 108): exit 0, every captured field non-null at
least once, and the program records the build you named. Exit 1 means a field is null everywhere or the pin differs (an
`unpinned-app-` value is refused, which is the known gap of step 0.6); exit 2 means a file is not a readable export. The
tool prints each file's size and SHA-256: copy them into the export manifest. The export is private even though it is
synthetic. Confirm in the output that E1 carries a non-blind quality flag, that the ceiling flag appears for the late
smell, and that no session carries `group_shared_blotter` (individual mode).

### What to write in the rehearsal log

The private copy of [`p6-synthetic-rehearsal.md`](../planning/evidence/p6-synthetic-rehearsal.md) is completed **by the
owner, after the evening**, from `$EVID`. This runbook does not fill it and marks nothing passed. Fields to be ready with:

| Log field | Where it comes from |
| :--- | :--- |
| Private evidence location | `$EVID` (a reference, not the path's contents) |
| Release commit and image digests | step 0.5 (`release-running.txt`) |
| R7b participant-instrument build exercised | same commit and digests, plus the footer text and `instrument_version` in the export |
| Operator, UTC start and end | the evening log |
| Sheet and slip versions rehearsed | `facilitated-session-sheet v2.1`, `facilitated-conditions-slip v1.0` (and a note that the property guide was outside the instrument) |
| Shared-triple enrollment of six | step 2.3 preview and readiness output |
| Paper session for six, transcribed through one login | 3.2, 3.4 |
| Blind-code confirmation, ambiguous marks | `failure-1.txt`, and how the ambiguous mark was entered |
| Individual blotter flow and ceiling | spray-to-first-smell for each evaluator and sample, count of breaches, whether 2 minutes held |
| Fresh blotter | count of fresh blotters and which evaluator |
| Vial access | how often evaluators queued or crowded at the vials, and whether the walk-up approach had to be changed |
| No group flag | the export summary |
| Non-blind holder | `non-blind-call.txt` and the export flag |
| Checkpoints before holdouts | `checkpoint-times.txt`, `failure-4.txt` (409), `failure-3.txt` (422) |
| Household reveal | `failure-2.txt` (refused while E5 outstanding), then the successful reveal |
| Skin-absent by design | empty plans finalized for all six |
| Export manifest note | file names, SHA-256, byte counts, redaction reviewer, private location from `r7b-summary.txt` |
| Rehearsal result, reviewer, UTC date | the owner's, written last |

Rows of the general table that need the recommendation and measurement surfaces (interest, sampling, impressions,
outcome linking) are not part of the family profile's light run unless the owner decides they are; say which rows were
not run rather than leaving them blank.

## Step 4. P6.4 light checks on the facilitator's pages (HOST, ALONE; the reload check during step 3)

Pages in scope: the transcription wizard (**Calibration**) and the manager screens (**Program setup**, the checkpoints
panel). No evaluator-facing screen exists in the facilitated format. Use the laptop and its normal browser.

- **Keyboard.** Transcribe one evaluator's column using only the keyboard: Tab order follows the visual order, focus is
  always visible, every field has a label, the confirmation dialogs ("Confirm blotter lock", "Confirm checkpoints",
  "Confirm household reveal") can be reached and dismissed from the keyboard, and a refused save (the 409 or 422 case)
  is announced in text.
- **Responsive layout on the facilitator's laptop.** At the laptop's real window size and at 200 percent zoom: no
  horizontal scrolling, no clipped control, no hidden required field in the wizard, the readiness table and the
  program setup form.
- **Disclosure.** The page text, the network responses you opened in step 3.10, the browser cache, the printed labels
  ("Print labels") and the error messages show no fragrance identity or role before the reveal.
- **Reload mid-sheet.** During step 3.4, partway through a column (some numeric and time fields typed, not saved), reload
  the page and confirm the recorder lands on the same evaluator, sample and keeps unsaved fields. **Verified in the code
  (PR #228):** the position is rebuilt from the server, and the chosen evaluator, the passed session screens and the
  numeric and time fields of the column being typed are kept in the browser session for 12 hours; free-text notes are
  deliberately not kept, so a lost note is expected and is recorded as an observation, not a failure. Do it for a
  second evaluator too, and once after saving a column (expected: no stale half-typed column reappears).

Pass rule: each bullet either passes or is written down with what actually happened. A failure is a documented limitation
for step 6, or a blocker if the owner says so.

## Step 5. P6.5 shared restore and one-line secret ownership (ALONE)

The timed backup and restore is step 1.3 (shared). Nothing is run twice. The printable outage procedure is the paper
sheets themselves: they are retained, so data can be re-entered after an outage. The alert and log-redaction exercises are
skipped by owner decision. Write one line in `$EVID/p6-5-secrets.txt`:

```text
Secret owner: <name> sets and rotates DB_PASSWORD, CALIBRATION_ADMIN_USERNAMES, FRAGRANCE_RATER_API_KEY, FRAGELLA_API_KEY and OPENROUTER_API_KEY, only in the Portainer UI for stack 131; no value is written in any file.
```

The five names come from the required (`:?`) variables of the homelab compose file. Confirm the line is true before
writing it; this runbook cannot know who the owner is.

## Step 6. P6.6 readiness decision: one paragraph for the owner to sign (ALONE)

Write this paragraph in the private copy of [`p6-readiness-decision.md`](../planning/evidence/p6-readiness-decision.md),
completing every blank yourself:

```text
On <UTC date>, I, <owner>, reviewed the P6 family MVP run for commit <40 characters> (app image <sha256>, frontend image
<sha256>) and decide: <go | no-go>. The family profile waived the P1.4 concurrency run and the second P1.1 label
check, and skipped the alert and log-redaction exercises. Known limitations: <list, one clause each; or "reviewed,
none identified">. In particular: there is no withdraw route for an enrolled evaluator, so a withdrawal holds the
household reveal and I decide then; the consent text has no guardian clause, the application is for my own
household only; <the alert recipient, or that there is none>; <anything that failed in steps 1 to 4>. Signed <owner>.
```

For the machine-checked closure record, copy `data/pilot/p6-readiness.template.json` into `$EVID`, complete it from the
private records (`r7b_build` and `release` must name the same commit and digests; an empty `known_limitations` needs a
non-empty `known_limitations_review`), and check it:

```bash
cd ~/dev/fragrance-rater && uv run python scripts/validate_p6_readiness.py "$EVID/p6-readiness.json"
```

The validator checks completeness and consistency only; it does not decide whether an observation is true. Only a `go`
with every kept item passed and no unresolved release-blocking limitation closes P6 for the family profile. A missing
artifact, a stale deployment or a `no-go` keeps F1 blocked, and any later change to the participant build, the session
sheet or the conditions slip voids the affected evidence.

## Assumptions and open judgement calls

These are production-risk assumptions in the repository's Response-Aware Development form.

- `#CRITICAL` security: the in-container helper trusts the `X-Authentik-Username` header because the app is reachable
  only inside the private network. `#VERIFY`: step 1.1 proves nginx refuses a forged header from the app network, and
  `api GET /calibration/access` without the header returns 401.
- `#CRITICAL` data integrity: the instrument pin is frozen on a program at activation. `#VERIFY`: step 0.6 before step 2.
- `#CRITICAL` timing: a holdout smelled on paper before its checkpoint cannot be repaired. `#VERIFY`: step 3.6 (all six
  `holdouts_open` true) before step 3.7; the server enforces only each evaluator's own checkpoint.
- `#ASSUME` external resources: the homelab sidecar's daily dump and the NFS share are healthy. `#VERIFY`: step 1.2
  backup freshness and step 1.3's fresh dump.
- `#ASSUME` consent entry: the session intro shows consent as already given when it was recorded before the sitting.
  `#VERIFY`: step 3.1 note.
- `#EDGE` the 3-hour gap between same-day sittings is not enforced by the server and is not rehearsed; the transcription
  breaks stand in for it.
- `#EDGE` the synthetic reviewers, versions and program remain in production; they are named `SYNTH` or
  `SYNTHETIC REHEARSAL`, and F1 uses a new program.

Contradictions with existing documents found while writing this, none resolved here:

1. [P6 pilot readiness](p6-pilot-readiness.md) (lines 50 to 53) assumes `docker-compose.release.yml`, digest pins and
   `INSTRUMENT_VERSION`; the deployed Portainer stack uses `:latest` and does not pass `INSTRUMENT_VERSION`.
2. The family profile says production holds no fragrance rows; the live database held 43 on 2026-11-25.
3. `scripts/verify_restore.py` cannot restore the homelab sidecar's `-n public` dump (one expected error vs
   `--exit-on-error`); step 1.3 uses plain `pg_restore`.
4. [P1 release readiness](p1-release-readiness.md) (lines 301 to 315) names the network `<project>_fragrance_rater-network`;
   on this host it is `fragrance-rater_backend-net`.
