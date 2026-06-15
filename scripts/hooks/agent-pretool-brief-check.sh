#!/usr/bin/env bash
# Claude Code PreToolUse hook for the Task (Agent) tool — the dispatch-brief gate.
#
# Enforces CLAUDE.md §"Agent Dispatch Brief Template" + §"PM Orchestration &
# Delegation" mechanically, so the rules can't decay into ignored prose:
#
#   (a) FIRST ACTION: marker within the first 500 chars of the brief,
#   (b) CLAUDE.md referenced within the first 500 chars,
#   (c) ROLE: marker within the first 1000 chars (ROLE sits after FIRST ACTION),
#   (d) a `## Result` block instruction anywhere in the brief (report contract),
#   (e) the Opus model tier: any dispatch that is NOT a read-only research
#       `subagent_type: "Explore"` must run on `model: "opus"` (or leave model
#       absent, which inherits the Opus PM). An explicit non-Opus model on an
#       implement/validate dispatch is blocked.
#
# Wire it in .claude/settings.json (local — .claude/ is gitignored):
#   "hooks": { "PreToolUse": [ { "matcher": "Task", "hooks": [
#     { "type": "command",
#       "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/hooks/agent-pretool-brief-check.sh\"" } ] } ] }
#
# Hook contract (Claude Code PreToolUse):
#   stdin  = JSON {"tool_input": {"prompt": "...", "model": "...", "subagent_type": "..."}}
#   exit 0 = allow ; exit 2 = block (stderr surfaced to the model)
#
# Graceful degradation: if neither jq nor python3 is available, emit a notice and
# exit 0 — broken tooling must never block the workflow.

set -uo pipefail

HEADER_WINDOW=500    # FIRST ACTION + CLAUDE.md must appear within this many chars
ROLE_WINDOW=1000     # ROLE: must appear within this many chars

input_json="$(cat 2>/dev/null || true)"
[ -z "$input_json" ] && exit 0

# --- extract one tool_input field (jq preferred, python3 fallback) ------------
field() { # $1 = field name
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input_json" | jq -r --arg k "$1" '.tool_input[$k] // ""' 2>/dev/null || true
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$input_json" | python3 -c '
import json, sys
k = sys.argv[1]
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
sys.stdout.write(str((d.get("tool_input") or {}).get(k) or ""))
' "$1" 2>/dev/null || true
  else
    printf '__NO_PARSER__'
  fi
}

prompt="$(field prompt)"
if [ "$prompt" = "__NO_PARSER__" ]; then
  printf 'agent-pretool-brief-check: neither jq nor python3 available; skipping.\n' >&2
  exit 0
fi
[ -z "$prompt" ] && exit 0   # Task with no prompt — not our problem, don't block.

model="$(field model)"
subagent_type="$(field subagent_type)"

# lowercase helper (parity: model + subagent_type compared case-insensitively)
lc() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
model_lc="$(lc "$model")"
st_lc="$(lc "$subagent_type")"

header_window="$(printf '%s' "$prompt" | head -c "$HEADER_WINDOW")"
role_window="$(printf '%s' "$prompt" | head -c "$ROLE_WINDOW")"

problems=()
case "$header_window" in *"FIRST ACTION:"*) ;; *) problems+=("missing 'FIRST ACTION:' in the first $HEADER_WINDOW chars");; esac
case "$header_window" in *"CLAUDE.md"*) ;; *) problems+=("missing a 'CLAUDE.md' reference in the first $HEADER_WINDOW chars");; esac
case "$role_window"   in *"ROLE:"*) ;; *) problems+=("missing 'ROLE:' in the first $ROLE_WINDOW chars");; esac
case "$prompt"        in *"## Result"*) ;; *) problems+=("missing the '## Result' report-contract block instruction");; esac

# Model tier: non-Explore dispatches must be Opus (or model absent = inherits Opus).
if [ "$st_lc" != "explore" ] && [ -n "$model_lc" ] && [ "$model_lc" != "opus" ]; then
  problems+=("implement/validate dispatch uses model='$model' — must be 'opus' (or 'subagent_type: \"Explore\"' for read-only research)")
fi

[ "${#problems[@]}" -eq 0 ] && exit 0

{
  printf 'agent-pretool-brief-check: dispatch blocked — the brief violates CLAUDE.md §"Agent Dispatch Brief Template".\n\n'
  for p in "${problems[@]}"; do printf '  * %s\n' "$p"; done
  printf '\nFix the brief and re-issue. Required, in order:\n'
  printf '  > **FIRST ACTION:** Read `CLAUDE.md` and `docs/learnings.md` ... (first ~500 chars)\n'
  printf '  > **ROLE:** You are taking the role of ... (first ~1000 chars)\n'
  printf '  ... brief body ... ending with a `## Result` block (STATUS/ARTIFACTS/RISKS/LEARNINGS/NEXT)\n'
  printf '  model: "opus" for implement/validate; subagent_type: "Explore" for read-only research.\n'
} >&2
exit 2
