#!/usr/bin/env bash
# SessionStart hook — ENFORCE CLAUDE.md Session-Start Protocol step 3 ("load engram memory").
#
# THE failure this prevents (it happened — the v0.3.14–v0.3.17 install-path spiral): an agent
# skips loading cross-session memory at session start and repeats mistakes earlier sessions
# already solved. A line buried in CLAUDE.md is easy to skim past; a SessionStart hook's stdout
# is injected FRESH into the agent's context at the TOP of every session, so the directive is
# unmissable. That's the enforcement: the instruction is in context every time, not relying on
# the agent remembering to read the protocol.
#
# Why a DIRECTIVE (call mem_context) and not a data dump: the engram CLI `search` is
# relevance-ranked with no "recent timeline" command, and we deliberately do NOT couple this
# hook to engram's SQLite schema (same conservative choice as stop-engram-summary-check.sh,
# which only reads file mtime). The MCP tool `mem_context` DOES return recency — so we direct
# the agent to call it FIRST, rather than printing an arbitrary (possibly stale) CLI sample.
#
# Tripwire semantics (match the other engram hook):
#   * engram CLI not installed  -> exit 0 silently (non-pilot machines get zero noise).
#   * never block                -> always exit 0 (SessionStart must not abort a session).

set -uo pipefail

# engram CLI lives in the Go bin dir on this setup; add it so the hook works regardless of the
# parent shell's PATH. If still absent, this machine isn't running engram → exit silently.
export PATH="$PATH:$HOME/go/bin"
command -v engram >/dev/null 2>&1 || exit 0

# Project key: engram detects it from cwd; the repo dir name matches the engram project here.
proj="$(basename "${CLAUDE_PROJECT_DIR:-$PWD}")"

cat <<EOF
────────────────────────────────────────────────────────────
ENGRAM CROSS-SESSION MEMORY IS ACTIVE for this project (${proj}).

MANDATORY FIRST ACTION — CLAUDE.md Session-Start Protocol step 3. Do this BEFORE reading
code or making any change:
  1. mem_context(project="${proj}")              → recent sessions + observations (recency-ordered)
  2. mem_search(query="<the area you'll touch>") → prior decisions / bug root-causes / "do not do X" gotchas

Earlier sessions stored the hard-won lessons here. Skipping this load is exactly how known
mistakes get repeated — load it first, then work.
────────────────────────────────────────────────────────────
EOF
exit 0
