# Claude Code Agents

This file documents the Claude Code subagents configured for the fragrance-rater
project. Each agent lives in `.claude/agents/` and is invoked by the Claude Code
supervisor when the described task type arises.

## Agents

### code-reviewer

**File**: `.claude/agents/code-reviewer.md`

**Purpose**: Automated code review specialist focused on code quality, standards
compliance, and best practices.

**When to invoke**: Before merging any pull request or after completing a feature
branch to validate adherence to the project's Ruff, BasedPyright, and architectural
conventions. Also useful for reviewing AI-generated code before committing.

---

### merge-standards

**File**: `.claude/agents/merge-standards.md`

**Purpose**: Merges updated baseline files from `.standards/` into project root
configuration files after a `cruft update`.

**When to invoke**: After running `cruft update` whenever `.standards/*.baseline.*`
files change. Run before committing the post-update state so that project
customizations in `CLAUDE.md` and `REUSE.toml` are reconciled with the new template
baseline.

---

### security-auditor

**File**: `.claude/agents/security-auditor.md`

**Purpose**: Security analysis specialist for vulnerability detection, threat
assessment, and compliance validation.

**When to invoke**: When adding new dependencies, before releases, after any
change to authentication or data-handling code, or when `pip-audit`/Bandit findings
need triage. Also used during the OpenSSF release gate check.

---

### test-engineer

**File**: `.claude/agents/test-engineer.md`

**Purpose**: Comprehensive testing specialist for test strategy, generation, and
quality assurance targeting the project's 80% coverage threshold.

**When to invoke**: When writing tests for a new feature or bug fix, when coverage
drops below 80%, or when designing integration or end-to-end test scenarios.

---

## Usage Pattern

The Claude Code supervisor automatically routes tasks to the appropriate agent. You
can also invoke an agent explicitly by describing the task in your prompt, for
example: "Review this PR for security issues" routes to `security-auditor`.

For manual invocation, reference the agent name in your Claude Code session prompt.

Last updated: 2026-05-16
