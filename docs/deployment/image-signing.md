---
title: "Image Pinning and Signing"
schema_type: common
status: published
owner: core-maintainer
purpose: "How base images are pinned by digest, how published images are signed, and how a deployer verifies them."
tags:
  - deployment
  - security
---

Two controls cover the supply chain of the container images (architecture review S-12, R14 PR 3b):
every image the build starts from is pinned by digest, and every image published to GHCR is signed
by digest. This page says what each control proves, how to check it, and what it does not cover.

## Base images are pinned by digest

Each `FROM` in `Dockerfile` and `frontend/Dockerfile`, the `uv` source in the backend `COPY --from`,
and the `postgres` image in both compose files is written as `name:tag@sha256:<digest>`. The tag stays
for people to read; the digest is what Docker resolves, so a tag that is re-pointed upstream cannot
change what gets built or run.

`renovate.json` keeps the pins current. A package rule enables `pinDigests` for the `dockerfile` and
`docker-compose` managers, never auto-merges, and holds major-version bumps (PostgreSQL 16 and Node 22 change
deliberately, not through Renovate) and restricts the Python image to the 3.12 line. A base-image update arrives as a pull request
that moves the tag and digest together.

To resolve a digest by hand, read the top-level `Digest:` line, which is the multi-platform index:

```bash
docker buildx imagetools inspect postgres:16-alpine | grep -m1 '^Digest:'
```

`tests/unit/test_image_pinning.py` fails if any `FROM`, the `uv` copy source or a compose image loses
its digest.

## Published images are signed

`.github/workflows/docker-publish.yml` has a `sign-backend` and a `sign-frontend` job. After the build
job pushes an image on `main` (never on pull requests), the signing job:

1. takes the pushed image digest from the reusable workflow's `image-digest` output;
2. signs `ghcr.io/byronwilliamscpa/<image>@<digest>` with cosign, keyless, using the job's GitHub OIDC
   token (the signing job alone holds `id-token: write`);
3. verifies the signature it just wrote, so a signature that does not verify fails the job.

Signing is by digest, never by tag: a tag can move, a digest cannot. The signatures live in the registry
beside the image; there is no key to store or rotate.

| Image | Reference |
| :--- | :--- |
| Backend | `ghcr.io/byronwilliamscpa/fragrance_rater` |
| Frontend | `ghcr.io/byronwilliamscpa/fragrance_rater-frontend` |

## Verifying an image before you run it

Run this on the deployment host, or on any machine that can read the registry, before the image is
started. It needs [cosign](https://docs.sigstore.dev/cosign/system_config/installation/) v3; the workflow signs
with v3.0.6, which writes the newer bundle format, and no older client has been shown to verify it.
Use the digest you intend to deploy, not a tag:

```bash
IMAGE=ghcr.io/byronwilliamscpa/fragrance_rater
DIGEST=sha256:<digest-recorded-for-the-release>
COMMIT=<the 40-character release candidate commit>

cosign verify \
  --certificate-identity-regexp '^https://github\.com/ByronWilliamsCPA/fragrance-rater/\.github/workflows/docker-publish\.yml@refs/heads/main$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-github-workflow-sha "${COMMIT}" \
  "${IMAGE}@${DIGEST}"
```

Repeat with `IMAGE=ghcr.io/byronwilliamscpa/fragrance_rater-frontend` and its digest, with the same
`COMMIT`. A zero exit status means the image at that digest was signed by this repository's
`docker-publish.yml` running on `main` at that commit, which is what ties each digest to the release
candidate: an app and a frontend digest from different publishes cannot both pass with one `COMMIT`.
Any other result (no signatures found, an identity or commit mismatch, a missing registry login) means do
not deploy it. `--certificate-github-workflow-sha` is a documented `cosign verify` option; it has not been
exercised against a real certificate from this repository's workflow, so treat the first verification of
a published image as the check that it matches.

Then deploy by digest, so what runs is what was verified. `docker-compose.release.yml` is the override
for this: layered last, it drops the source build of `app` and `frontend` and pulls
`ghcr.io/byronwilliamscpa/fragrance_rater` and `ghcr.io/byronwilliamscpa/fragrance_rater-frontend` at the
digests you give it, and Compose refuses to render while either is unset.

```bash
export APP_IMAGE_DIGEST=sha256:<digest verified for the app image>
export FRONTEND_IMAGE_DIGEST=sha256:<digest verified for the frontend image>
export INSTRUMENT_VERSION=<the commit SHA both images were published from>
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.release.yml up -d
```

`INSTRUMENT_VERSION` is the commit SHA `docker-publish.yml` baked into the frontend and the value the backend
records on each program at activation. After the first program is activated, compare the UI footer
("Instrument build ...") with `program.instrument_version` in the evidence export; they must match.

For the P6 rehearsal and F1, record each verified digest with the other release evidence described in
[P6 pilot readiness](p6-pilot-readiness.md).

## What this does and does not cover

- **It proves provenance, not safety.** A valid signature says this repository's workflow produced the
  image. It does not say the image is free of vulnerabilities; the Trivy scan in the publish workflow
  is a separate, report-only control.
- **The committed compose files build from source.** `docker-compose.yml` and `docker-compose.prod.yml`
  build `app` and `frontend` on the host rather than pulling the signed images, so verification applies
  only when you also layer `docker-compose.release.yml` as shown above. A source build is protected by the pinned
  base images, not by these signatures.
- **The signing identity is the workflow file path and branch.** Renaming `docker-publish.yml`, or
  publishing from another branch, changes the identity; update the regexp here and in
  `tests/unit/test_image_pinning.py` in the same change.
- **Only the first run on `main` proves the live path.** The workflow is checked with `actionlint`
  and YAML parsing, and `tests/unit/test_image_pinning.py` guards its shape. Separately, the sign and
  verify mechanics were run once by hand against a throwaway local registry with a key; that transcript
  is in the pull request description, not in the repository. That run signs with a key, so it never
  exercised the keyless identity regexp against a real Fulcio certificate, which is the risky part.
  Keyless signing needs a real GitHub OIDC token and Sigstore's public services and cannot be
  reproduced off GitHub. The first `main` publish after this merges is the evidence; if the in-workflow
  verify step passes there, the command above passes for a deployer too.
