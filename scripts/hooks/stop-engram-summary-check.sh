#!/usr/bin/env bash
# Stop hook — tripwire for CLAUDE.md §"Session Memory (Engram)": a
# `mem_session_summary` MUST be saved before each session ends.
#
# Because the Engram CLI offers no cheap "summary saved this session?"
# query, this hook uses the modification time of the local Engram DB as
# a best-effort proxy: if the DB has not been written to within the last
# RECENT_WRITE_THRESHOLD_SECONDS seconds, no Engram memory was saved
# recently and the reminder fires.
#
# This is a TRIPWIRE, not a gate:
#   * If engram is not installed → exit 0 silently (pilot inactive on
#     this machine; no noise for non-pilot machines).
#   * If the DB does not yet exist → warn once (engram installed but
#     never used — save at least one mem_save / mem_session_summary).
#   * If the DB mtime is stale → warn to stderr.
#   * Always exit 0 — never block session stop.
#
# False positives / negatives are acceptable for a tripwire. The user
# only owes `mem_session_summary` if they did substantive work this
# session; a brief no-op session is fine to skip (and this hook will
# still fire — that is the acceptable false-positive rate for a
# reminder-only signal).
#
# Hook contract (Claude Code Stop):
#   * stdin: JSON with session metadata (not used here)
#   * exit 0 = allow stop, no message
#   * exit 1 = soft warning (stderr surfaced)
#   * exit 2 = block (do not use — never block session stop)

set -uo pipefail

# ── Step 1: Pilot inactive on this machine ──────────────────────────
# If engram is not installed at all, exit silently so non-pilot
# machines get zero noise from this hook.
if ! command -v engram >/dev/null 2>&1; then
  exit 0
fi

# ── Step 2: Resolve the DB path ─────────────────────────────────────
# Authoritative local SQLite at ~/.engram/engram.db; override with
# ENGRAM_DATA_DIR.
data_dir="${ENGRAM_DATA_DIR:-$HOME/.engram}"
db="$data_dir/engram.db"

# ── Step 3: DB does not exist yet ───────────────────────────────────
if [ ! -f "$db" ]; then
  {
    printf '────────────────────────────────────────────────────────────\n'
    printf 'stop-engram-summary-check: engram is installed but has no database yet.\n'
    printf '\n'
    printf 'Save at least one `mem_save` or `mem_session_summary` this session.\n'
    printf 'See CLAUDE.md §"Session Memory (Engram)".\n'
    printf '────────────────────────────────────────────────────────────\n'
  } >&2
  exit 0
fi

# ── Step 4: Check DB mtime ──────────────────────────────────────────
# Best-effort proxy: a DB write within the last 15 minutes suggests
# Engram was used this session. The threshold is deliberately generous
# — it is a reminder, not a gate.
#
# RECENT_WRITE_THRESHOLD_SECONDS: 900 (15 minutes). This is a
# heuristic; the CLI offers no direct "session summary saved?" query,
# so DB-write recency at session stop is the best available signal.
RECENT_WRITE_THRESHOLD_SECONDS=900

# Get the most recent mtime among engram.db, engram.db-wal, engram.db-shm
# (WAL and SHM may be absent — ignore missing files).
newest_mtime=0
for candidate in "$db" "${db}-wal" "${db}-shm"; do
  if [ ! -f "$candidate" ]; then
    continue
  fi
  # macOS: stat -f %m; Linux: stat -c %Y. Try macOS first; fall back.
  mtime=""
  if mtime=$(stat -f %m "$candidate" 2>/dev/null); then
    : # macOS succeeded
  elif mtime=$(stat -c %Y "$candidate" 2>/dev/null); then
    : # Linux succeeded
  else
    # stat not available or unknown OS — skip this file
    continue
  fi
  if [ -n "$mtime" ] && [ "$mtime" -gt "$newest_mtime" ] 2>/dev/null; then
    newest_mtime="$mtime"
  fi
done

if [ "$newest_mtime" -eq 0 ]; then
  # Could not determine mtime (stat unavailable on this OS) — exit silently.
  exit 0
fi

now=$(date +%s 2>/dev/null || true)
if [ -z "$now" ]; then
  # date +%s not supported — exit silently.
  exit 0
fi

age_seconds=$(( now - newest_mtime ))

if [ "$age_seconds" -le "$RECENT_WRITE_THRESHOLD_SECONDS" ]; then
  # DB was written recently — no warning needed.
  exit 0
fi

# ── Stale DB: warn ──────────────────────────────────────────────────
{
  printf '────────────────────────────────────────────────────────────\n'
  printf 'stop-engram-summary-check: no recent Engram write detected at session stop.\n'
  printf '\n'
  printf '  DB last written: %d seconds ago (threshold: %d s / ~%d min)\n' \
    "$age_seconds" "$RECENT_WRITE_THRESHOLD_SECONDS" \
    "$(( RECENT_WRITE_THRESHOLD_SECONDS / 60 ))"
  printf '\n'
  printf 'Per CLAUDE.md §"Session Memory (Engram)":\n'
  printf '  * `mem_session_summary` is MANDATORY before the session ends.\n'
  printf '  * If you made decisions, fixed bugs, or discovered non-obvious facts,\n'
  printf '    save typed `mem_save` entries first, then `mem_session_summary`.\n'
  printf '  * If `.engram/` chunks changed, commit them with the session PR.\n'
  printf '────────────────────────────────────────────────────────────\n'
} >&2

# Tripwire only. Never block stop.
exit 0
