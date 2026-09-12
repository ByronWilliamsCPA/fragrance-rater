# Project Scripts

Utility scripts for Fragrance Rater.

## Available Scripts

### validate_p6_readiness.py

Validates that the P6 closure record identifies immutable release images, marks P6.1-P6.6 as
passed, references every private evidence artifact, contains no unresolved blocking limitation,
and records an attributable UTC `go` decision.

```bash
uv run python scripts/validate_p6_readiness.py /secure/path/p6-readiness.json
```

Start from `data/pilot/p6-readiness.template.json`. The completed record belongs in the private
evidence directory because its references can reveal deployment details.

### update-claude-standards.sh

Updates the Claude Code standards from the upstream repository.

**Usage**:
```bash
./scripts/update-claude-standards.sh
```

**What it does**:
- Pulls the latest Claude Code standards from [williaby/.claude](https://github.com/williaby/.claude)
- Updates the `.claude/standard/` directory via git subtree
- Preserves project-specific configuration in `.claude/claude.md`

**When to run**:
- Periodically to get latest standards and best practices
- When new Claude Code features are announced
- When security or quality updates are released

**Note**: The update uses `git subtree pull --squash` to maintain a clean commit history.

## Adding New Scripts

When adding new scripts to this directory:

1. Make them executable: `chmod +x scripts/your-script.sh`
2. Add shebang line: `#!/bin/bash` (or appropriate interpreter)
3. Add usage documentation to this README
4. Use `set -e` to exit on errors
5. Add colorized output for better UX

## Script Conventions

- **Exit codes**: 0 for success, non-zero for errors
- **Output**: Use colors (GREEN for success, YELLOW for warnings, RED for errors)
- **Error handling**: Always check preconditions (e.g., git repo exists)
- **User interaction**: Confirm destructive operations
- **Documentation**: Include usage examples in this README
