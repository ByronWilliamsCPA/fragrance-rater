"""Export the FastAPI OpenAPI document to docs/api/openapi.json.

Run with::

    uv run python scripts/export_openapi.py

The output is committed so that downstream tooling (Postman
collection generation, contract tests, docs site) can consume the
spec without needing to boot the application.
"""

from __future__ import annotations

import json
from pathlib import Path

from fragrance_rater.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi.json"


def main() -> None:
    """Write ``app.openapi()`` to ``docs/api/openapi.json``."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()
    OUTPUT.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(OUTPUT.parent.parent.parent)}")


if __name__ == "__main__":
    main()
