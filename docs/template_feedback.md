---
title: "Template Feedback"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document template issues for upstream fixes."
tags:
  - documentation
  - tooling
---

> **Purpose**: Document issues discovered in this project that should be addressed in the [cookiecutter-python-template](https://github.com/ByronWilliamsCPA/cookiecutter-python-template).
>
> **Generated From**: cookiecutter-python-template v0.1.0
> **Project Created**: __PROJECT_CREATION_DATE__

---

## How to Use This File

When working on this project, if you discover any issue that originates from the template itself (not project-specific), add it here with the following format:

```markdown
### [Short Title]

- **Priority**: Critical / High / Medium / Low
- **Category**: [Configuration / Documentation / Tooling / Structure / CI/CD / Security / Other]
- **Discovered**: YYYY-MM-DD

**Issue**: [Clear description of what's wrong or missing]

**Context**: [How was this discovered? What were you trying to do?]

**Suggested Fix**: [What should the template do differently?]

**Affected Files**: [List template files that need changes]
```

---

## Feedback Items

<!-- Add your feedback below this line -->

### Generated planning set lacks an authority and status lifecycle

- **Priority**: High
- **Category**: Documentation
- **Discovered**: 2026-09-11

**Issue**: The generated project plan, roadmap, technical specification, vision, and
project-specific section in `CLAUDE.md` can each present independent scope and completion
status. The scaffold does not identify one execution authority, require an audited commit for
implementation state, or define how superseded ADRs and historical roadmaps are retired.

**Context**: During the Fragrance Rater P0 planning review, the project plan called a merged
calibration workflow pending, the roadmap called implemented foundation work planned, the
technical specification still declared no authentication, and `CLAUDE.md` called all planning
complete. All documents were individually plausible, making the contradiction difficult to
detect during implementation.

**Suggested Fix**: Generate one authoritative execution plan with a current-state ledger,
milestone evidence links, definitions of ready/done, and change-control rules. Generate other
roadmap views as explicit mirrors. Add an ADR supersession index and require planning status to
be updated in feature pull requests that change architecture or scope.

**Affected Files**:

- `{{cookiecutter.project_slug}}/docs/planning/PROJECT-PLAN.md`
- `{{cookiecutter.project_slug}}/docs/planning/roadmap.md`
- `{{cookiecutter.project_slug}}/docs/planning/tech-spec.md`
- `{{cookiecutter.project_slug}}/CLAUDE.md`

### Planning documents are excluded from normal documentation validation

- **Priority**: Medium
- **Category**: Tooling
- **Discovered**: 2026-09-11

**Issue**: The generated pre-commit and markdownlint configuration excludes `docs/planning/**`
from front-matter and Markdown validation, while the example project-plan template is published
in the documentation navigation. This allows active planning documents to drift in formatting
and links while exposing template material as project guidance.

**Context**: P0 had to invoke markdownlint with the ignore file disabled to find duplicate
headings in the authoritative project plan. The strict documentation build also showed that the
actual controlled-calibration design was absent from navigation while the generic plan template
was included.

**Suggested Fix**: Validate active planning documents using the same Markdown/front-matter
contracts as other documentation. Exclude only explicitly archived examples, and do not publish
the generic project-plan template in project navigation by default.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.pre-commit-config.yaml`
- `{{cookiecutter.project_slug}}/.markdownlintignore`
- `{{cookiecutter.project_slug}}/mkdocs.yml`
- Planning document templates that currently omit front matter

### Incorrect `$schema` URL in `.claude/settings.json`

- **Priority**: Medium
- **Category**: Configuration
- **Discovered**: 2026-05-19

**Issue**: The generated `.claude/settings.json` uses `"$schema": "https://json.schemastore.org/claude-code-config.json"`, but the Claude Code VS Code extension expects `https://json.schemastore.org/claude-code-settings.json`. The wrong URL causes the extension to report "Settings file failed to parse" and silently disables permission rules and other settings from the file.

**Context**: This regression has now been observed twice in this project. It was reintroduced by the repo-compliance standards-alignment sweep on 2026-05-16 (CLAUDE-005 / commit `a02d3e8`), implying the cookiecutter template or the compliance standards manifest still emits the incorrect URL.

**Suggested Fix**: Update the template's `.claude/settings.json` (and any standards-manifest remediation logic that writes this file) to use `claude-code-settings.json` rather than `claude-code-config.json`.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.claude/settings.json` (template)
- Any compliance/remediation script that emits or rewrites this file (likely in the `claude-docs-auditor` remediation path for CLAUDE-005)

### `coverage.json` not in `.gitignore`

- **Priority**: Low
- **Category**: Configuration
- **Discovered**: 2026-05-19

**Issue**: The template's `.gitignore` covers `.coverage`, `.coverage.*`, and `coverage.xml`, but omits `coverage.json`. `coverage.py` writes `coverage.json` when invoked with `--format=json` (used by Codecov's JSON reporter, several IDE integrations, and the `test-coverage` skill), leaving an untracked artifact in the working tree after every coverage run.

**Context**: Discovered during a "final check" repo audit. `coverage.json` was the only untracked file in an otherwise-clean working tree on `main` and had been produced silently by a prior coverage run.

**Suggested Fix**: Add `coverage.json` to the "Unit test / coverage reports" block in `.gitignore` alongside `coverage.xml`.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.gitignore`

### FIPS compatibility checker matches cipher names as substrings, and cannot fail the workflow

- **Priority**: High
- **Category**: Tooling
- **Discovered**: 2026-09-19

**Issue**: `scripts/check_fips_compatibility.py`'s cipher-detection visitor flags a function/method
call as a non-FIPS cipher if the call's attribute name merely *contains* an entry from
`NON_FIPS_CIPHERS` as a substring (`any(c in func_name for c in NON_FIPS_CIPHERS)`), rather than
matching it as a whole identifier. `"des"` and `"seed"` are both real entries in that set, and both
are common substrings of ordinary, non-cryptographic identifiers: SQLAlchemy's `.desc()` ordering
call contains `"des"`, and any function named with a `seed_`/`_seed` prefix (e.g.
`seed_default_reviewers`, a normal database-seeding helper) contains `"seed"`. The `FIPS Compliance
Check` CI job is non-blocking (its gating "Check result" step is configured to not fail the job), so
this produces a persistently red-looking report ("❌ FAILED") on the PR timeline without ever
blocking merge, training reviewers to ignore it. Separately,
`.github/workflows/fips-compatibility.yml` captures `EXIT_CODE=$?` after piping the checker
through `tee`, which yields `tee`'s own status rather than the checker's, so `exit_code` is
always `0` and the "Check result" step that is meant to fail the job never runs regardless of
how many errors the checker reports.

**Context**: Discovered independently on two PRs. On fragrance-rater PR #104, the bot comment
reported 28 errors (25 on the branch, 23 already on `main`) although the check run reported
success. On PR #105, discovered while running `/pr-fix`: the job's PR comment reported 26 errors,
"Status: FAILED"; every single flagged site was either a `.desc()` call or a call to
`seed_default_reviewers`, neither of which touches cryptography. Re-running
`scripts/check_fips_compatibility.py --fix-hints` locally after removing the substring-containment
branch (keeping only the exact-match `func_name in NON_FIPS_CIPHERS` check, which already covers a
literal `des()`/`rc4()`/etc. call) reduced the report to 0 errors on the same code.

**Suggested Fix**: In `FipsCodeVisitor.visit_Call`, drop the `or any(c in func_name for c in
NON_FIPS_CIPHERS)` clause and rely on the exact-match check alone (`if func_name in
NON_FIPS_CIPHERS:`), or match cipher names as whole tokens (word boundaries, or an allowlist of
module-qualified call targets such as `Crypto.Cipher.DES`) if a broader match than exact-string
is still wanted. The `visit_Import` module-name check a few lines below has the same
substring-matching shape but is already gated behind `"crypto" in module`, which keeps its false-
positive surface much smaller (it only fires on imports that already mention "crypto"); it does
not need the same fix but is worth a second look if this pattern class recurs. Separately, use
`set -o pipefail` or `${PIPESTATUS[0]}` when capturing the checker's exit status in the workflow
so the "Check result" step actually reflects the checker's verdict instead of `tee`'s.

**Affected Files**:

- `{{cookiecutter.project_slug}}/scripts/check_fips_compatibility.py`
- `{{cookiecutter.project_slug}}/.github/workflows/fips-compatibility.yml`

---

### PlanningFM `component` enum is domain-specific and has no general-engineering category

- **Priority**: Medium
- **Category**: Tooling
- **Discovered**: 2026-09-18

**Issue**: `tools/frontmatter_contract/models.py`'s `PlanningFM.component` field is a closed
`Literal` with values `Strategy`, `Development-Tools`, `Context`, `Request`, `Examples`,
`Augmentations`, `Tone-Format`, `Evaluation`. These read as categories for an LLM
prompt-engineering project, not a general software project. A planning document for
ordinary engineering work (e.g. a frontend testing/documentation improvement plan) has no
accurate value to choose; the least-wrong option (`Strategy`) is a forced mismatch, not a fit.

**Context**: Writing a `schema_type: planning` frontend testing plan document under
`docs/superpowers/plans/` and needing a valid `component` value for the required frontmatter.

**Suggested Fix**: Either make `component` an open `str` (validated only for non-emptiness) with
the current values kept as a documented convention, or add general-engineering categories
(e.g. `Architecture`, `Testing`, `Frontend`, `Backend`, `Infrastructure`) to the enum so the
schema isn't implicitly scoped to one project type.

**Affected Files**:

- `{{cookiecutter.project_slug}}/tools/frontmatter_contract/models.py`

---

### `__PROJECT_CREATION_DATE__` placeholder is never substituted in `template_feedback.md`

- **Priority**: Low
- **Category**: Documentation
- **Discovered**: 2026-09-19

**Issue**: `docs/template_feedback.md` ships the literal string `__PROJECT_CREATION_DATE__` on its
`Project Created` line; no cookiecutter substitution replaces it. Besides leaving a visible
placeholder in published documentation, the surrounding double underscores parse as emphasis, so
the file fails the template's own `MD050/strong-style` rule from the moment it is generated. The
failure is present on an untouched checkout, which trains contributors to ignore markdownlint
output on this file.

**Context**: Running `markdownlint-cli2` over this file after appending feedback entries, and
confirming against `git show HEAD:docs/template_feedback.md` that both errors predate the edit.

**Suggested Fix**: Render the line as `{{ cookiecutter.creation_date }}` (or drop it, since
`.cruft.json` already records the commit the project was generated from). If a placeholder must
remain, use a form that does not parse as emphasis, such as `TODO: project creation date`.

**Affected Files**:

- `{{cookiecutter.project_slug}}/docs/template_feedback.md`

---

### Frontend `format:check` can never pass because Prettier lints the generated API client

- **Priority**: Medium
- **Category**: Tooling
- **Discovered**: 2026-09-19

**Issue**: With `include_frontend: react`, the generated `frontend/package.json` defines
`"format:check": "prettier --check \"src/**/*.{ts,tsx,css,json}\""` and `generate-client` writes
`@hey-api/openapi-ts` output to `./src/client`. No `frontend/.prettierignore` is generated, so
Prettier checks that generated output. `frontend/eslint.config.js` *does* ignore `src/client`, so
the two tools disagree about whether generated code is the project's to format. The first time a
developer runs `npm run generate-client`, `npm run format:check` starts failing on a file nobody
should hand-edit, and it cannot be fixed by reformatting because the next client regeneration
reverts it.

**Context**: Running `npm run format:check` while verifying a frontend redesign. The only two
failures were `src/client/types.gen.ts` (generated) and a pre-existing source file; the generated
one is unfixable by design.

**Suggested Fix**: Generate a `frontend/.prettierignore` containing `src/client/` and `dist/`, so
Prettier and ESLint agree on the same ignore set. Alternatively, scope the `format`/`format:check`
globs to exclude the client-output directory that `generate-client` already targets.

**Affected Files**:

- `{{cookiecutter.project_slug}}/frontend/package.json`
- `{{cookiecutter.project_slug}}/frontend/eslint.config.js`
- `{{cookiecutter.project_slug}}/frontend/.prettierignore` (missing)

---

### React scaffold ships no design-token layer, theme support, or contrast contract

- **Priority**: Low
- **Category**: Structure
- **Discovered**: 2026-09-19

**Issue**: The `include_frontend: react` scaffold generates `src/App.css` and `src/index.css` with
literal colour values and no custom-property layer. Projects that later need a coherent palette,
dark mode, or a WCAG conformance target have to retrofit all three at once, and by then literal
colours are spread across every component. The scaffold also has no accessibility conformance
target, so a project inherits none until somebody chooses one.

**Context**: A design pass on this project replaced the scaffold's two stylesheets with a
token layer plus base/layout/component files, and added a unit test that parses the token file and
re-derives every colour pair's contrast ratio in both themes. That test caught four WCAG 2.2 AA
failures that a fully passing axe-core suite could not see, because axe does not evaluate focus
indicator or control-boundary contrast and only ever sees one theme.

**Suggested Fix**: Generate a minimal `src/styles/tokens.css` with `--color-*`, spacing and radius
custom properties plus a `prefers-color-scheme` dark block, and have the scaffold's stylesheets
consume it. Optionally include the token-parsing contrast test as a starting example; it is about
80 lines and is the only tier that covers the non-text contrast criteria.

**Affected Files**:

- `{{cookiecutter.project_slug}}/frontend/src/App.css`
- `{{cookiecutter.project_slug}}/frontend/src/index.css`

---

### Branch-protection setup script drifts from actual required-check contexts with no way to detect the drift

- **Priority**: High
- **Category**: CI/CD
- **Discovered**: 2026-09-21

**Issue**: The generated `scripts/setup_github_protection.py` hardcodes a list of required
status-check contexts (e.g. `CI / CI Pipeline`, `PR Validation / Validate Requirements Sync`)
at generation time. Nothing keeps that list in sync with the check names the project's own
`.github/workflows/*.yml` actually emit as they evolve, and running the script with a stale
list configures branch protection that no PR could ever satisfy, since GitHub will wait
forever for a check context that no workflow publishes. The script has no test or CI step
that would catch this drift before someone runs it against a live repository.

**Context**: Discovered during the fragrance-rater R1 architecture review (finding G-11/Q8).
The script's required-check contexts had never matched this repository's actual workflow job
names. The project resolved this by deleting the script entirely and moving branch protection
to an org-level GitHub ruleset (configured once, centrally, outside per-repo generated code),
documenting the current required checks in a hand-maintained `docs/ci-gates.md` instead of a
script that can silently drift.

**Suggested Fix**: Either stop scaffolding a bespoke branch-protection script and instead
document the org-level (or per-repo) GitHub ruleset UI/API as the recommended setup path, or,
if a script is kept, generate it so its required-check list is derived from the repository's
own `.github/workflows/*.yml` job names at run time (e.g. by parsing the workflow files)
rather than hardcoded at cookiecutter-generation time, and add a CI step that fails when the
script's list and the live ruleset disagree.

**Affected Files**:

- `{{cookiecutter.project_slug}}/scripts/setup_github_protection.py`
- `{{cookiecutter.project_slug}}/docs/PROJECT_SETUP.md`

### Scaffolded `.semgrep.yml` is never wired into the Qlty scanning pipeline

- **Priority**: High
- **Category**: Tooling
- **Discovered**: 2026-09-21

**Issue**: The template scaffolds a `.semgrep.yml` configuration file, and downstream
documentation (README.md's Qlty tool list) describes Semgrep as one of the SAST tools Qlty
runs in its unified pass. In practice, `.qlty/qlty.toml`'s `[plugins] enabled` list never
included `semgrep`, so the scaffolded config file was inert from the moment the project was
generated: nothing in the CI or pre-commit pipeline ever invoked it. This gives a false
impression of SAST coverage: the config file and the README both suggest Semgrep runs, but it
never did.

**Context**: Discovered during the fragrance-rater R1 architecture review's CI-truthfulness
sprint while auditing what the project's documented security scanners actually run versus
what `.qlty/qlty.toml` and `.pre-commit-config.yaml` actually invoke. The project resolved
this by deleting `.semgrep.yml` rather than wiring it in, since no owner decision had been
made to add Semgrep as an actual gate.

**Suggested Fix**: Either wire the scaffolded `.semgrep.yml` into `.qlty/qlty.toml`'s enabled
plugins (or into `.pre-commit-config.yaml`, matching the pattern the template already uses for
other security tools) so it actually runs, or stop scaffolding a config file that looks active
but isn't. If Semgrep is meant to be optional/opt-in, say so explicitly in the generated
README rather than listing it as if it already runs.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.semgrep.yml`
- `{{cookiecutter.project_slug}}/.qlty/qlty.toml`
- `{{cookiecutter.project_slug}}/README.md`

---

### Database scaffold has no naming convention, autogenerate flags, or schema-parity test

- **Priority**: High
- **Category**: Tooling
- **Discovered**: 2026-10-02

**Issue**: The generated `core/database.py` declares `class Base(DeclarativeBase)` with no
`MetaData(naming_convention=...)`, the generated `alembic/env.py` passes neither
`compare_type`, `compare_server_default`, nor `render_as_batch`, and nothing tests that
`alembic upgrade head` produces the schema the models declare. PostgreSQL then invents names
for every unnamed constraint, so later migrations cannot address them by a known name and SQLite
batch migrations silently omit unnamed CHECKs. Alembic's `compare_metadata` also ignores CHECK
constraints and primary/foreign-key names, so even a structural parity test misses a dropped
CHECK. The generated `alembic/script.py.mako` emits `typing.Union`/`Sequence` imports that the
template's own Ruff configuration rejects, so every `alembic revision` output fails lint until
hand-edited. The shared SQLite test fixtures also never set `PRAGMA foreign_keys=ON`, so no
`ondelete="RESTRICT"` guard is exercised by unit tests.

**Context**: Found in fragrance-rater sprint R2 (architecture review D-03, D-04, D-05, D-07). It
took a migration renaming 84 constraints to retrofit a convention after 20 migrations had
shipped.

**Suggested Fix**: Ship `Base` with a naming convention whose generated names fit PostgreSQL's
63-character limit; set the three flags in both `context.configure()` calls; ship a
PostgreSQL-gated test asserting `compare_metadata(...) == []` plus reflected-name equality
with the models; ship a ruff-clean `script.py.mako`; and add a `connect` listener enabling SQLite
foreign keys to the test engine fixtures. A project adopting a convention late must also keep it
away from historical migrations: Alembic applies `target_metadata`'s convention to every unnamed
constraint an `op.*` call creates, so `env.py` should pass the model metadata only for
`revision --autogenerate` and `check`, not for upgrade or downgrade.

**Affected Files**:

- `{{cookiecutter.project_slug}}/src/{{cookiecutter.project_slug}}/core/database.py`
- `{{cookiecutter.project_slug}}/alembic/env.py`
- `{{cookiecutter.project_slug}}/alembic/script.py.mako`
- `{{cookiecutter.project_slug}}/tests/conftest.py`

---

### Coverage under-reports async SQLAlchemy code (no greenlet concurrency)

**Priority**: Medium

**Issue**: `[tool.coverage.run]` sets no `concurrency`, so coverage.py traces only the main thread.
SQLAlchemy's asyncio engine resumes ORM code inside greenlets, so almost every line after an
`await session...` call reads as uncovered, even when tests exercise and assert on it. Reported
coverage is therefore lower than real coverage for any async database code, and line-level
reports point reviewers at code that is in fact tested.

**Context**: Discovered while adding house-intake review tests in fragrance-rater. Every test
submitted a record, yet `HouseIntakeService.submit` showed as unexecuted (51.7% for the module).
With `concurrency = ["greenlet", "thread"]` the same test run measured 97%; the review service
went from 67.0% to 93%. This project now sets the option; project-wide reported coverage rose
from 87.9% to 93.2% with no test changes.

**Suggested Fix**: Add `concurrency = ["greenlet", "thread"]` to `[tool.coverage.run]` in the
generated `pyproject.toml` whenever the template includes SQLAlchemy's asyncio extra (greenlet is
already a transitive dependency there).

**Affected Files**:

- `{{cookiecutter.project_slug}}/pyproject.toml`

---

### Stacked pull requests get no CI, and retargeting does not start it

**Priority**: Medium

**Issue**: `ci.yml`, `security-analysis.yml`, and `postman-api-tests.yml` trigger on `pull_request`
with `branches: [main, ...]`, and `ci.yml` lists only the `opened`, `synchronize`, and `reopened`
types. A pull request whose base is another feature branch (a stacked pair) therefore runs only
the workflows that have no base filter (docs, REUSE, license), and never the test, security, or
contract suites, nor `pr-validation.yml`, which filters the same way. Retargeting it to `main`
afterwards starts `pr-validation.yml` (it also listens for `edited`) but not the heavy workflows,
which stay unrun until the next push. CodeRabbit also skips non-default bases. The reviewer sees a mostly green PR that never ran its
tests.

**Context**: Discovered opening fragrance-rater's R6 PR 1 stacked on a docs PR. After retargeting to
`main`, 12 of the usual ~35 checks existed and none was a test job.

**Suggested Fix**: Add `edited` to the `pull_request` types of every workflow that gates merging,
guarded so it runs only when the base actually changed
(`github.event.changes.base != null || github.event.action != 'edited'`), or drop the `branches`
filter on `pull_request` so stacked PRs are tested. Document in `docs/ci-gates.md` that a stacked
PR should be retargeted to `main` before review and re-pushed.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.github/workflows/ci.yml`
- `{{cookiecutter.project_slug}}/.github/workflows/security-analysis.yml`
- `{{cookiecutter.project_slug}}/.github/workflows/postman-api-tests.yml`

---

### `uv run ruff format .` rewrites Python snippets in every Markdown file

**Priority**: Low

**Issue**: Ruff 0.16.6 and later format fenced Python blocks in `.md` files by default. The
pre-commit hook pins `types_or: [python, pyi, jupyter]` to keep the old scope, but
`[tool.ruff]` in `pyproject.toml` does not, so the gate command CLAUDE.md lists
(`uv run ruff format .`) rewrites 14 unrelated Markdown files (CLAUDE.md, ADRs, plans) the first time it
runs on a checkout, and an agent following the gate list commits an unreviewed docs diff.

**Context**: Running the CLAUDE.md gate sequence on fragrance-rater's R7a PR 1 (ruff 0.17.2)
touched only Python sources, yet the working tree gained 14 modified Markdown files.

**Suggested Fix**: Add `extend-exclude = ["*.md"]` to `[tool.ruff]`, or `exclude = ["*.md"]` to
`[tool.ruff.format]` for formatter-only scope, in the template until Markdown snippet formatting is
adopted deliberately, matching the pre-commit hook's pinned scope.

**Affected Files**:

- `{{cookiecutter.project_slug}}/pyproject.toml`

---

### Docs workflow deploys to GitHub Pages by default

**Priority**: Medium

**Issue**: `docs.yml` sets `deploy-to-pages` true on every push to main. When Pages is not enabled
(for org-owned repos it requires verified domains), the "Setup Pages" step fails and the Documentation
check is red on every main run even though the MkDocs build passes.

**Context**: fragrance-rater's Documentation workflow failed on every main push since at least
2026-09-21 with `Get Pages site failed... Not Found` from `actions/configure-pages`.

**Suggested Fix**: Add a cookiecutter option (e.g. `deploy_docs_to_pages`, default false) that drives
`deploy-to-pages`, so projects opt in once Pages is enabled.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.github/workflows/docs.yml`

### Template ships stale root and docs-home content that no one owns

- **Priority**: Medium
- **Category**: Documentation
- **Discovered**: 2026-10-31

**Issue**: The generated `README.md` was 736 lines, about ten of them product overview, and carried Assured OSS and
Google Cloud setup the project never used. `docs/index.md` still tells readers to `pip install fragrance-rater` and run
a `hello` command that does not exist. A `CONFIG_TEMPLATES_SUMMARY.md` describing the cookiecutter run itself (with a
cookiecutter checkout path) was left at the repository root.

**Context**: Found while consolidating documentation in R14 PR 3a (architecture review G-04). The README was rewritten
and `CONFIG_TEMPLATES_SUMMARY.md` deleted there; `docs/index.md` was left as found and still needs the same treatment.

**Suggested Fix**: Generate a short README from the project description, keep optional supply-chain material behind a
cookiecutter flag that defaults off, do not emit template-run summaries into the project, and generate `docs/index.md`
from the same description instead of a fictional install and CLI example.

**Affected Files**:

- `{{cookiecutter.project_slug}}/README.md`
- `{{cookiecutter.project_slug}}/docs/index.md`
- `{{cookiecutter.project_slug}}/CONFIG_TEMPLATES_SUMMARY.md`

---

### Two ADR directories whose guides disagree

- **Priority**: Low
- **Category**: Structure
- **Discovered**: 2026-10-31

**Issue**: The template creates `docs/ADRs/` (a generic guide and template) while the planning generator writes real
ADRs to `docs/planning/adr/`. The result is two homes, the guide's naming scheme (`0001-title.md`) contradicting the
generated files (`adr-001-title.md`), and the generated `docs/planning/adr/README.md` pointing at the template in the
other directory.

**Context**: Merged into `docs/planning/adr/` in R14 PR 3a (architecture review G-04).

**Suggested Fix**: Pick one location (`docs/planning/adr/`), ship the template and the process notes there, and make the
generator, the guide and the naming convention agree.

**Affected Files**:

- `{{cookiecutter.project_slug}}/docs/ADRs/`
- `{{cookiecutter.project_slug}}/docs/planning/adr/README.md`

---

### Baseline CLAUDE.md names agent tools and policies the project does not provide

- **Priority**: Medium
- **Category**: Documentation
- **Discovered**: 2026-10-31

**Issue**: The baseline Supervisor section assigns work to `mcp__zen__*` tools although the template's `.mcp.json` does
not configure them, and says "address ALL type checker warnings" although a strict BasedPyright run on real code carries
a baseline of warnings. Agents following the file either fail to find tools or are told to do something the repository
does not enforce. The "Project Structure" section is also a fixed sketch that was never regenerated.

**Context**: Architecture review G-05; fixed in this project's `CLAUDE.md` in R14 PR 3a (`uv run basedpyright src/`
reports 0 errors and 132 warnings; the policy is that the count must not rise).

**Suggested Fix**: Generate the agent mapping from the subagents, commands and skills the template actually ships, state a
ratchet policy for type warnings, and either generate the structure section from the tree or drop it in favor of a
pointer to the tree.

**Affected Files**:

- `{{cookiecutter.project_slug}}/CLAUDE.md`
- `{{cookiecutter.project_slug}}/.standards/CLAUDE.baseline.md`
- `{{cookiecutter.project_slug}}/.mcp.json`

---

### `status: draft` is not honoured by MkDocs, and the front-matter hook skips `docs/planning/`

- **Priority**: Low
- **Category**: Tooling
- **Discovered**: 2026-10-31

**Issue**: The front-matter schema allows `draft | in-review | published`, but the MkDocs configuration has no plugin that
reads it, so a `draft` page is still built and searchable; keeping it out of the public navigation is a manual nav edit.
Separately, the `validate-front-matter` hook (`files: ^docs/(?!planning/)`) and `tools/validate_front_matter.py` exclude
`docs/planning/`, so the pages most likely to change status are never validated.

**Context**: Marking the P6 evidence placeholders `draft` in R14 PR 3a (architecture review G-08) only took effect by
removing them from `mkdocs.yml` nav.

**Suggested Fix**: Add a small MkDocs hook that excludes `status: draft` pages from the nav and search (or documents that
it does not), and validate planning documents against the planning schema instead of skipping them.

**Affected Files**:

- `{{cookiecutter.project_slug}}/mkdocs.yml`
- `{{cookiecutter.project_slug}}/tools/validate_front_matter.py`
- `{{cookiecutter.project_slug}}/.pre-commit-config.yaml`

---

### Ignore ledgers carry reassessment dates that nothing checks

- **Priority**: Medium
- **Category**: Security
- **Discovered**: 2026-10-31

**Issue**: `pyproject.toml` `[tool.pip-audit] ignore-vuln` and `docs/known-vulnerabilities.md` both record a "reassess by"
date, but no hook or workflow fails when the date passes, and the two files can disagree. Here the OSV advisory was
withdrawn and the OSV-Scanner ignore removed, while the pip-audit ignore stayed and its 2026-07-16 date lapsed for 107
days unnoticed.

**Context**: Found while superseding `SECURITY-FINDINGS.md` in R14 PR 3a (architecture review G-10).

**Suggested Fix**: Add a check that parses the reassessment dates in `pyproject.toml` and the ledger, fails on an overdue
or ledger-less ignore, and (optionally) runs the audit with the ignore disabled to report ignores that are no longer
needed.

**Affected Files**:

- `{{cookiecutter.project_slug}}/pyproject.toml`
- `{{cookiecutter.project_slug}}/docs/known-vulnerabilities.md`
- `{{cookiecutter.project_slug}}/.github/workflows/security-analysis.yml`

---

### Assured OSS and Google Cloud scaffolding is on by default

- **Priority**: Low
- **Category**: Configuration
- **Discovered**: 2026-10-31

**Issue**: A project that does not use Google Assured OSS still ships `scripts/validate_assuredoss.py`, an `assuredoss`
nox session, and a `GOOGLE_CLOUD_PROJECT=assured-oss-...` line in `.env.example`.

**Context**: Noticed while removing the Assured OSS material from the README in R14 PR 3a. The script, session and
`.env.example` line were left in place because that pass is documentation only.

**Suggested Fix**: Gate all Assured OSS and GCP files and settings behind one cookiecutter flag that defaults off.

**Affected Files**:

- `{{cookiecutter.project_slug}}/scripts/validate_assuredoss.py`
- `{{cookiecutter.project_slug}}/noxfile.py`
- `{{cookiecutter.project_slug}}/.env.example`

---

### Ruff ISC003 and BasedPyright implicit-concatenation rules conflict

**Priority**: Low

**Issue**: Ruff's ISC rules (selected in the PyStrict group) flag an explicitly concatenated string
(`"a " + "b"`, ISC003) and ask for implicit concatenation, while BasedPyright strict mode reports
`reportImplicitStringConcatenation` on implicit concatenation (`"a " "b"`). A long literal that must
wrap therefore fails one tool or the other; the only clean forms are one over-long line or a
`str.join`, and the warning baseline silently absorbs the BasedPyright side.

**Context**: R8 PR 2 (2026-10-31): a long CHECK body and a filter description could not be wrapped
without adding a BasedPyright warning above the 132-warning baseline.

**Suggested Fix**: Pick one side in the template: either disable `reportImplicitStringConcatenation`
(and keep ISC) or ignore ISC003 and document `" ".join((...))` as the house pattern.

**Affected Files**:

- `{{cookiecutter.project_slug}}/pyproject.toml` (`[tool.ruff.lint]`, `[tool.basedpyright]`)

---

### Worktree guidance covers the Python environment but not the frontend

**Priority**: Low

**Issue**: The generated CLAUDE.md "Git Worktree Workflow" says each worktree needs
`uv sync --all-extras`, but a project with a `frontend/` also needs `npm ci` there. Without it,
`npx tsc -b` resolves a global TypeScript and reports missing `@playwright/test` and Node types, and
`npx eslint` fails to load `@eslint/js`, which reads like a code problem rather than a missing install.

**Context**: R8 PR 2 (2026-10-31), run in a fresh agent worktree.

**Suggested Fix**: When the template generates a frontend, add `cd frontend && npm ci` to the worktree
checklist (and to any session-start hook it ships).

**Affected Files**:

- `{{cookiecutter.project_slug}}/CLAUDE.md` (Git Worktree Workflow)

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
