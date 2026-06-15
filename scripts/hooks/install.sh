#!/usr/bin/env bash
# Install this repo's git hooks. Opt-in because .git/hooks is not versioned.
# Symlinks so edits to the tracked hook scripts take effect immediately.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
hooks="$root/.git/hooks"
mkdir -p "$hooks"

for h in pre-commit; do
  src="$root/scripts/hooks/$h"
  [ -f "$src" ] || continue
  chmod +x "$src"
  ln -sf "../../scripts/hooks/$h" "$hooks/$h"
  echo "installed: .git/hooks/$h -> scripts/hooks/$h"
done

chmod +x "$root/scripts/hooks/agent-pretool-brief-check.sh" 2>/dev/null || true

# Claude Code hooks (NOT git hooks) are wired via .claude/settings.json (local — .claude/
# is gitignored, so this isn't auto-installed on a fresh clone):
#   * Stop            -> scripts/hooks/stop-engram-summary-check.sh  (engram-summary tripwire)
#   * PreToolUse/Task -> scripts/hooks/agent-pretool-brief-check.sh  (dispatch-brief gate:
#                        FIRST ACTION + ROLE + ## Result + Opus model tier; see CLAUDE.md
#                        §"Agent Dispatch Brief Template"). Re-add the block on a fresh clone.
echo "done. Bypass a git hook with: git commit --no-verify"
