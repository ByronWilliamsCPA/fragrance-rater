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

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
