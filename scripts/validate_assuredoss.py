#!/usr/bin/env python
"""---
title: "Validate Assured OSS Credentials"
name: "validate_assuredoss.py"
description: "Validates ADC for Assured OSS and lists available packages."
category: script
usage: "uv run python scripts/validate_assuredoss.py"
behavior: "Checks ADC credentials and enumerates OSS packages"
inputs: "GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_CLOUD_PROJECT"
outputs: "Console output of credential path, project ID, and package list"
dependencies: "google-auth, google-cloud-assuredoss, google-api-core, python-dotenv"
author: "Byron Williams"
last_modified: "2025-12-29"
changelog: "Add front-matter metadata and module docstring"
tags: [scripts, tools, assuredoss, validation]
---

Module: validate_assuredoss

This script verifies that Google Application Default Credentials (ADC)
are correctly configured for Assured OSS, and lists available OSS packages
for the configured project.

Functions:
    main(): Entry point for credential validation and package listing.
    setup_credentials(): Decode and setup credentials from environment.
"""

from __future__ import annotations

import base64
import binascii
import importlib
import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def setup_credentials() -> Path | None:
    """Set up Google Cloud credentials from environment variables.

    Handles both file-based credentials (GOOGLE_APPLICATION_CREDENTIALS)
    and base64-encoded credentials (GOOGLE_APPLICATION_CREDENTIALS_B64).

    For CI/CD environments, base64 encoding is preferred:
        base64 -w 0 service-account-key.json

    Raises:
        ValueError: If neither credential method is configured.
    """
    # Check if credentials are already set via file path
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print(
            "✅ Using credentials from file:",
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        )
        return None

    # Try to use base64-encoded credentials
    cred_b64 = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")
    if not cred_b64:
        msg = (
            "❌ No credentials found. Set either:\n"
            "   GOOGLE_APPLICATION_CREDENTIALS (file path)\n"
            "   GOOGLE_APPLICATION_CREDENTIALS_B64 (base64 encoded JSON)"
        )
        raise ValueError(msg)

    # Decode base64 credentials and write to temp file
    try:
        cred_json = base64.b64decode(cred_b64, validate=True).decode("utf-8")
        json.loads(cred_json)  # Validate JSON

        # mkstemp uses an unpredictable name and creates the file with mode 0600.
        descriptor, raw_path = tempfile.mkstemp(
            prefix="gcp-credentials-", suffix=".json"
        )
        temp_cred_file = Path(raw_path)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as credential_file:
                credential_file.write(cred_json)
        except Exception:
            temp_cred_file.unlink(missing_ok=True)
            raise
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(temp_cred_file)

        print("✅ Using base64-encoded credentials from a restricted temporary file")
        return temp_cred_file

    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
        msg = f"❌ Invalid base64 credentials: {e}"
        raise ValueError(msg) from e


def list_assured_oss_packages() -> None:
    """List packages while keeping optional Google dependencies lazy-loaded."""
    try:
        api_exceptions = importlib.import_module("google.api_core.exceptions")
        auth_exceptions = importlib.import_module("google.auth.exceptions")
        assured_oss = importlib.import_module("google.cloud.assuredoss")
    except ImportError as exc:
        message = (
            "Assured OSS validation dependencies are unavailable; install the "
            "project's assured-oss dependencies before enabling USE_ASSURED_OSS"
        )
        raise RuntimeError(message) from exc

    try:
        client = assured_oss.V1Client()
        print("🔍 Connecting to Assured OSS...")
        response = client.list_packages()
    except auth_exceptions.DefaultCredentialsError as exc:
        print(f"❌ Could not load credentials: {exc}")
        raise
    except api_exceptions.GoogleAPICallError as exc:
        print(f"❌ Failed to list packages: {exc}")
        raise

    print(f"✅ Connected! Found {len(response.packages)} packages:\n")
    for index, package in enumerate(response.packages, 1):
        version = getattr(package, "version", "unknown")
        print(f"  {index:3d}. {package.name:40s} (v{version})")
    print("\n" + "=" * 70)
    print(f"✅ Validation successful! Total packages: {len(response.packages)}")
    print("=" * 70)


def main() -> None:
    """Validate ADC credentials and list Assured OSS packages.

    Reads the `GOOGLE_APPLICATION_CREDENTIALS` and
    `GOOGLE_CLOUD_PROJECT` environment variables, initializes the
    Assured OSS client, and prints the retrieved package list.

    Raises:
        DefaultCredentialsError: If ADC cannot be loaded.
        GoogleAPICallError: If the API call fails.
        ValueError: If required environment variables are missing.
    """
    # Load environment variables from .env file
    load_dotenv()

    use_assured_oss = os.environ.get("USE_ASSURED_OSS", "true").lower() == "true"
    if not use_assured_oss:
        print("⚠️  Assured OSS is disabled (USE_ASSURED_OSS=false)")
        print("📦 Using PyPI as the only package source")
        return

    temporary_credentials: Path | None = None
    try:
        # Setup credentials (from file or base64)
        temporary_credentials = setup_credentials()

        # Validate required environment variables
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("❌ GOOGLE_CLOUD_PROJECT not set")

        region = os.environ.get("ASSURED_OSS_REGION", "us")
        repository = os.environ.get("ASSURED_OSS_REPOSITORY", "assuredoss")

        print("\n" + "=" * 70)
        print("🔐 Google Assured OSS Validation")
        print("=" * 70)
        print(f"📦 Project:    {project_id}")
        print(f"🌍 Region:     {region}")
        print(f"📚 Repository: {repository}")
        print(f"✨ Enabled:    {use_assured_oss}")
        print("=" * 70 + "\n")

        list_assured_oss_packages()

    except ValueError as e:
        print(f"\n{e}\n")
        print("💡 Setup Instructions:")
        print("   1. Copy .env.example to .env")
        print("   2. Set GOOGLE_CLOUD_PROJECT to your GCP project ID")
        print("   3. Set up credentials (one of the following):")
        print("      a) GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        print("      b) GOOGLE_APPLICATION_CREDENTIALS_B64=<base64-encoded-json>")
        raise

    finally:
        if temporary_credentials is not None:
            temporary_credentials.unlink(missing_ok=True)
            if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == str(
                temporary_credentials
            ):
                os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS")


if __name__ == "__main__":
    main()
