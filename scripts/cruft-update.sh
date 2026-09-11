#!/bin/bash
# Wrapper script for cruft update that also cleans up conditional files.
#
# USAGE:
#   ./scripts/cruft-update.sh [cruft-options]
#
# DESCRIPTION:
#   This script wraps `cruft update` to address a fundamental limitation:
#   cruft only syncs file contents - it does NOT re-run post-generation
#   hooks that clean up conditional files.
#
#   Running this script ensures that:
#   1. Template updates are applied via `cruft update`
#   2. Orphaned conditional files are removed based on .cruft.json context
#
# EXAMPLES:
#   # Standard update
#   ./scripts/cruft-update.sh
#
#   # Update without prompts (skip conflicts)
#   ./scripts/cruft-update.sh --skip
#
#   # Update from specific commit
#   ./scripts/cruft-update.sh --checkout abc123
#
# SEE ALSO:
#   scripts/cleanup_conditional_files.py - Standalone cleanup script
#   scripts/check_orphaned_files.py - Validation script (used in CI)

set -euo pipefail

echo "========================================"
echo "🔄 Cruft Update with Cleanup"
echo "========================================"
echo ""

# Check if cruft is available
if ! command -v cruft &> /dev/null; then
    echo "❌ cruft is not installed"
    echo "   Install with: pip install cruft"
    exit 1
fi

# Check if we're in a cruft-managed project
if [ ! -f ".cruft.json" ]; then
    echo "❌ .cruft.json not found"
    echo "   This script must be run from a cruft-managed project root"
    exit 1
fi

# Run cruft update with any passed arguments
echo "📥 Running cruft update..."
echo ""
set +e  # Temporarily disable exit on error to capture cruft result
cruft update "$@"
update_result=$?
set -e  # Re-enable exit on error

if [ $update_result -ne 0 ]; then
    echo ""
    echo "⚠️  cruft update returned non-zero exit code: $update_result"
    echo "   This may indicate conflicts or skipped files"
    echo ""
fi

# Run conditional file cleanup
echo ""
echo "🧹 Running conditional file cleanup..."
echo ""

if [ -f "scripts/cleanup_conditional_files.py" ]; then
    set +e  # Temporarily disable exit on error to capture cleanup result
    python scripts/cleanup_conditional_files.py
    cleanup_result=$?
    set -e  # Re-enable exit on error

    if [ $cleanup_result -ne 0 ]; then
        echo ""
        echo "⚠️  Cleanup script returned non-zero exit code: $cleanup_result"
    fi
else
    echo "⚠️  Cleanup script not found: scripts/cleanup_conditional_files.py"
    cleanup_result=1
fi

if [ "$update_result" -ne 0 ] || [ "${cleanup_result:-0}" -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "❌ Cruft update or cleanup failed"
    echo "========================================"
    if [ "$update_result" -ne 0 ]; then
        exit "$update_result"
    fi
    exit "$cleanup_result"
fi

echo ""
echo "========================================"
echo "✅ Cruft update complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Test your project: pytest"
echo "  3. Commit if OK: git add -A && git commit -m 'chore: update from template'"
echo ""
