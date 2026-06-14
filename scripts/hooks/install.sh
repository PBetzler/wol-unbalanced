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

# The Stop hook (engram summary) is wired via .claude/settings.json, not git.
echo "done. Bypass a hook with: git commit --no-verify"
