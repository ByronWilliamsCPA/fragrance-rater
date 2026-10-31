# Fragrance Rater

Fragrance Rater helps the Williams family make better fragrance choices. It preserves what each person
actually experienced, ties those observations to verified fragrance versions, and tests recommendation
strategies prospectively. It is a self-hosted application for family use, not a published package or a
public service.

The product succeeds when it reduces expensive trial and error while giving each evaluator a clear,
trustworthy record of their preferences. Recommendation explanations and catalog views support that outcome;
they do not replace measured experience. See [docs/planning/project-vision.md](docs/planning/project-vision.md)
for the vision, scope, principles and success measures.

## What it keeps apart

The system records three kinds of evidence without conflating them:

1. Published catalog metadata and its source provenance.
2. Ordinary and controlled observations recorded by an evaluator, including blind calibration programs.
3. Model interpretations, candidate scores and explanations derived from frozen inputs.

## Status

Delivery runs as a sequence of milestones with explicit gates and retained evidence. The authoritative
sequence, current status, gates, risks and evidence locations are in
[docs/planning/PROJECT-PLAN.md](docs/planning/PROJECT-PLAN.md). This README deliberately carries no status
text of its own, so it cannot go stale; read the plan.

## Architecture

A Docker Compose monolith: a React frontend, a FastAPI backend and PostgreSQL
([ADR-001](docs/planning/adr/adr-001-initial-architecture.md)). In production the only authenticated path to
the backend is Traefik with Authentik forward-auth in front of the frontend's nginx, and nginx forwards
identity headers only from the dedicated edge network
([ADR-008](docs/planning/adr/adr-008-authentication-and-production-boundary.md)). OpenRouter is used only for
optional recommendation explanations; deterministic scoring works without it. See
[docs/development/architecture.md](docs/development/architecture.md) for the components and boundaries,
[docs/planning/tech-spec.md](docs/planning/tech-spec.md) for the technical contracts and
[docs/planning/adr/README.md](docs/planning/adr/README.md) for every decision record.

Repository layout:

| Path | Contents |
| :--- | :------- |
| `src/fragrance_rater/` | FastAPI application, services, models, schemas, ML scoring, LLM client, CLI |
| `alembic/` | Database migrations |
| `frontend/` | React + TypeScript (Vite) application and its unit and e2e tests |
| `tests/` | Backend unit and integration tests |
| `scripts/` | Operational and validation scripts (backup, restore verification, topology and readiness checks) |
| `data/` | Curated calibration, alias and vocabulary data |
| `docs/` | Documentation (built with MkDocs Material) |

## Quick start (development)

Requirements: Docker with Compose, plus [uv](https://docs.astral.sh/uv/) and Python 3.12 for backend work, and
Node.js with npm for frontend work.

```bash
git clone https://github.com/ByronWilliamsCPA/fragrance-rater.git
cd fragrance-rater
cp .env.example .env
# Compose refuses to start without DB_PASSWORD. Generate one and set it in .env:
python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up -d
```

The backend container runs `alembic upgrade head` on start. The API is then at `http://localhost:8000`
(interactive docs at `/docs` outside production) and the frontend at `http://localhost:3000`. `.env.example`
documents every setting, including the optional OpenRouter and Fragella keys. The production override is
`docker-compose.prod.yml`; read [docs/deployment/p1-release-readiness.md](docs/deployment/p1-release-readiness.md)
before using it.

## Development commands

Backend (Python 3.12, managed with uv):

```bash
uv sync --all-extras                 # install runtime and dev dependencies
uv run pre-commit install            # install the git hooks
uv run pytest                        # tests (coverage gate configured in pyproject.toml)
uv run ruff format .                 # format
uv run ruff check .                  # lint
uv run basedpyright src/             # type check
uv run bandit -r src                 # security lint
uv run pip-audit                     # dependency audit
uv run mkdocs build --strict         # build the documentation
uv run uvicorn fragrance_rater.main:app --reload   # run the API (needs a reachable PostgreSQL)
uv run fragrance-rater --help        # CLI (catalog imports)
```

Frontend (from `frontend/`, after `npm install`):

```bash
npm run dev              # Vite dev server
npm run build            # type-check and production build
npm run test:run         # unit tests (Vitest)
npm run lint             # ESLint
npm run typecheck        # TypeScript
npm run test:e2e         # Playwright e2e
npm run generate-client  # regenerate the API client from a running backend
```

CI workflows and what each one blocks are listed in [docs/ci-gates.md](docs/ci-gates.md).

## Documentation

Run `uv run mkdocs serve` for a local preview. Good starting points:

- [Project vision](docs/planning/project-vision.md) and [project plan](docs/planning/PROJECT-PLAN.md)
- [Technical spec](docs/planning/tech-spec.md) and [architecture decision records](docs/planning/adr/README.md)
- [Controlled calibration v1](docs/calibration-v1.md): the workflow and deployment constraints
- [Pilot participant guide](docs/guides/pilot-participant.md) and
  [pilot manager guide](docs/guides/pilot-manager.md)
- [Backup and restore](docs/deployment/backup-and-restore.md)
- [Known vulnerabilities](docs/known-vulnerabilities.md)
- [Original concept (historical, superseded)](docs/archive/concept.md)

## Security and contributing

- Report vulnerabilities as described in [SECURITY.md](SECURITY.md). A dated review of the authentication and
  hardening code is in [SECURITY-FINDINGS.md](SECURITY-FINDINGS.md).
- Contribution workflow, branch naming and commit conventions are in [CONTRIBUTING.md](CONTRIBUTING.md);
  project guidelines for AI-assisted work are in [CLAUDE.md](CLAUDE.md).
- Governance is described in [GOVERNANCE.md](GOVERNANCE.md) and conduct expectations in
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

Code is licensed under the [MIT License](LICENSE). Documentation and data carry the licenses recorded in
[REUSE.toml](REUSE.toml).
