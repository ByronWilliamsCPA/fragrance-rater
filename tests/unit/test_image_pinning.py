"""Base images are digest-pinned and published images are signed by digest (S-12)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

DOCKERFILES = ("Dockerfile", "frontend/Dockerfile")
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")
SIGN_JOBS = {"sign-backend": "backend", "sign-frontend": "frontend"}

_DIGEST = r"@sha256:[0-9a-f]{64}"
_PINNED = re.compile(rf"^[^\s@]+:[^\s@:]+{_DIGEST}$")
_FULL_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")

# The identity a deployer verifies against, as documented in image-signing.md.
_IDENTITY_FRAGMENT = r"\.github/workflows/docker-publish\.yml@refs/heads/(main|master)"
_OIDC_ISSUER = "https://token.actions.githubusercontent.com"


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Compose's ``!reset`` and ``!override`` tags."""


for _tag in ("!reset", "!override"):
    _ComposeLoader.add_constructor(
        _tag,
        lambda loader, node: (
            loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode)
            else loader.construct_scalar(node)
        ),
    )


def is_pinned(reference: str) -> bool:
    """Return True for ``name:tag@sha256:<64 hex>``, False for anything looser."""
    return bool(_PINNED.match(reference))


def unpinned_from_references(dockerfile_text: str) -> list[str]:
    """Return every external base image in a Dockerfile that lacks a pinned digest.

    A ``FROM`` that names an earlier build stage is not an external image, so it
    is skipped; ``scratch`` has no digest to pin.
    """
    stages: set[str] = set()
    bad: list[str] = []
    for line in dockerfile_text.splitlines():
        match = re.match(
            r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?\s*$",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue
        image, stage = match.group(1), match.group(2)
        if image not in stages and image.lower() != "scratch" and not is_pinned(image):
            bad.append(image)
        if stage:
            stages.add(stage)
    return bad


def unpinned_copy_sources(dockerfile_text: str) -> list[str]:
    """Return ``COPY --from=<image>`` sources that name an image without a digest."""
    stages = set(re.findall(r"\bAS\s+(\S+)", dockerfile_text, re.IGNORECASE))
    sources = re.findall(r"^\s*COPY\s+--from=(\S+)", dockerfile_text, re.MULTILINE)
    return [
        s for s in sources if s not in stages and not s.isdigit() and not is_pinned(s)
    ]


def _read(file: str) -> str:
    return (ROOT / file).read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.safe_load(_read(".github/workflows/docker-publish.yml"))


# ---- Dockerfiles ------------------------------------------------------------


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_every_dockerfile_base_image_is_pinned_by_digest(dockerfile: str) -> None:
    assert unpinned_from_references(_read(dockerfile)) == []


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_every_dockerfile_copy_source_image_is_pinned_by_digest(
    dockerfile: str,
) -> None:
    assert unpinned_copy_sources(_read(dockerfile)) == []


def test_the_uv_copy_source_is_a_version_tag_plus_digest_not_latest() -> None:
    sources = re.findall(
        r"COPY\s+--from=(ghcr\.io/astral-sh/uv\S*)", _read("Dockerfile")
    )
    assert sources, "the backend Dockerfile no longer copies uv from its image"
    for source in sources:
        assert is_pinned(source), source
        assert ":latest@" not in source, source
        assert re.search(r":\d+\.\d+\.\d+@", source), source


def test_pin_check_rejects_floating_and_tag_only_references() -> None:
    """Negative controls: the helper must not wave through a loose reference."""
    digest = "a" * 64
    assert is_pinned(f"python:3.12-slim@sha256:{digest}")
    assert not is_pinned("python:3.12-slim")
    assert not is_pinned(f"python@sha256:{digest}")  # a digest with no readable tag
    assert not is_pinned("python:3.12-slim@sha256:abc123")  # truncated digest
    assert unpinned_from_references("FROM python:3.12-slim AS builder\n") == [
        "python:3.12-slim"
    ]
    assert unpinned_copy_sources(
        "COPY --from=ghcr.io/astral-sh/uv:latest /uv /u\n"
    ) == ["ghcr.io/astral-sh/uv:latest"]


def test_pin_check_skips_stage_references_and_scratch() -> None:
    digest = "b" * 64
    text = (
        f"FROM node:22-alpine@sha256:{digest} AS deps\n"
        "FROM deps AS builder\n"
        "FROM scratch\n"
        "COPY --from=builder /out /out\n"
    )
    assert unpinned_from_references(text) == []
    assert unpinned_copy_sources(text) == []


# ---- Compose ----------------------------------------------------------------


@pytest.mark.parametrize("file", COMPOSE_FILES)
def test_every_pulled_compose_image_is_pinned_by_digest(file: str) -> None:
    """Services with a ``build`` key produce a local image; the rest are pulled."""
    services = yaml.load(_read(file), Loader=_ComposeLoader)["services"]  # noqa: S506 - SafeLoader subclass
    pulled = {
        name: service["image"]
        for name, service in services.items()
        if "image" in service and "build" not in service
    }
    assert pulled, f"{file} declares no pulled image to check"
    for name, image in pulled.items():
        assert is_pinned(image), f"{file}:{name} -> {image}"


def test_the_database_and_backup_services_share_one_postgres_digest() -> None:
    """A backup client of a different build than the server is an avoidable skew."""
    found: set[str] = set()
    for file in COMPOSE_FILES:
        services = yaml.load(_read(file), Loader=_ComposeLoader)["services"]  # noqa: S506 - SafeLoader subclass
        for service in services.values():
            image = service.get("image", "")
            if image.startswith("postgres:"):
                found.add(image)
    assert len(found) == 1, found


# ---- Renovate ---------------------------------------------------------------


def test_renovate_keeps_container_digests_current_without_automerge() -> None:
    config = json.loads(_read("renovate.json"))
    assert {"dockerfile", "docker-compose"} <= set(config["enabledManagers"])
    rules = [
        rule
        for rule in config["packageRules"]
        if {"dockerfile", "docker-compose"} <= set(rule.get("matchManagers", []))
    ]
    pin_rules = [rule for rule in rules if rule.get("pinDigests")]
    assert pin_rules, "no package rule enables pinDigests for the docker managers"
    for rule in pin_rules:
        assert rule.get("automerge") is False, "base image bumps must not automerge"
    assert any(
        rule.get("enabled") is False and rule.get("matchUpdateTypes") == ["major"]
        for rule in rules
    ), "container image major bumps are not held"


# ---- Signing workflow -------------------------------------------------------


def test_signing_jobs_exist_run_after_their_build_and_skip_pull_requests() -> None:
    jobs = _workflow()["jobs"]
    for sign, build in SIGN_JOBS.items():
        assert sign in jobs, sign
        assert jobs[sign]["needs"] == build
        condition = jobs[sign]["if"]
        assert "github.event_name != 'pull_request'" in condition
        assert f"needs.{build}.result == 'success'" in condition
        assert f"needs.{build}.outputs.image-digest != ''" in condition


def test_only_the_signing_jobs_can_mint_an_oidc_token() -> None:
    workflow = _workflow()
    assert "id-token" not in (workflow.get("permissions") or {})
    for name, job in workflow["jobs"].items():
        granted = (job.get("permissions") or {}).get("id-token")
        if name in SIGN_JOBS:
            assert granted == "write", name
        else:
            assert granted is None, f"{name} must not hold id-token"


@pytest.mark.parametrize("sign", SIGN_JOBS)
def test_signing_is_keyless_by_digest_and_self_verified(sign: str) -> None:
    job = _workflow()["jobs"][sign]
    commands = [step.get("run", "") for step in job["steps"]]
    signing = [c for c in commands if "cosign sign" in c]
    verifying = [c for c in commands if "cosign verify" in c]

    assert len(signing) == 1, "expected exactly one cosign sign step"
    assert '"${IMAGE}@${DIGEST}"' in signing[0], "must sign the digest, not a tag"
    assert "--key" not in signing[0], "keyless signing takes no key"

    assert len(verifying) == 1, "the job must verify what it just signed"
    assert _IDENTITY_FRAGMENT.replace("\\.", r"\.") in verifying[0]
    assert _OIDC_ISSUER in verifying[0]
    assert '"${IMAGE}@${DIGEST}"' in verifying[0]
    assert job["env"]["DIGEST"].startswith("${{ needs.")


@pytest.mark.parametrize("sign", SIGN_JOBS)
def test_signing_job_actions_are_pinned_to_a_full_commit_sha(sign: str) -> None:
    for step in _workflow()["jobs"][sign]["steps"]:
        if "uses" in step:
            assert _FULL_SHA.match(step["uses"]), step["uses"]


def test_signing_job_installs_cosign_before_it_is_used() -> None:
    steps = _workflow()["jobs"]["sign-backend"]["steps"]
    uses = [step.get("uses", "") for step in steps]
    install = next(i for i, u in enumerate(uses) if "cosign-installer" in u)
    sign = next(i for i, s in enumerate(steps) if "cosign sign" in s.get("run", ""))
    assert install < sign


# ---- Documentation ----------------------------------------------------------


def test_the_documented_verify_command_matches_the_workflow_identity() -> None:
    doc = _read("docs/deployment/image-signing.md")
    assert "--certificate-identity-regexp" in doc
    assert f"--certificate-oidc-issuer {_OIDC_ISSUER}" in doc
    assert _IDENTITY_FRAGMENT in doc
    assert "ByronWilliamsCPA/fragrance-rater" in doc
