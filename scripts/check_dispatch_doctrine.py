#!/usr/bin/env python3
"""Guard the PM-orchestration / dispatch doctrine — the "enforce, don't just describe" layer.

CLAUDE.md mandates how the top-level agent delegates (PM → Opus engineers, the
research→implement→validate triad, the dispatch brief template) and the PreToolUse
hook enforces it. This check keeps the two in sync so neither can silently drift:

  PART A — CLAUDE.md still states the doctrine (the prose can't be quietly deleted).
  PART B — the hook script still enforces it (the checks can't be quietly removed).

Run in the pre-commit gate and CI (alongside galaxy_lint + audit). Exit non-zero on
any failure with a pointed message. This is the sc2-mod equivalent of a CLAUDE.md
invariant test — cheap insurance that the rules and their enforcement move together.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_MD = os.path.join(ROOT, "CLAUDE.md")
HOOK = os.path.join(ROOT, "scripts", "hooks", "agent-pretool-brief-check.sh")

# (label, substring that must be present) — phrased to survive reasonable rewording
# while still catching deletion of the rule. Update BOTH the doc and this list together.
CLAUDE_MUST_CONTAIN = [
    ("PM orchestration section", "PM Orchestration & Delegation"),
    ("PM-by-default role", "Product Manager / orchestrator by default"),
    ("the dispatch triad", "research → implement → validate"),
    ("independent validator", "independent Opus reviewer"),
    ("Opus model tier", 'model: "opus"'),
    ("research tier (Explore)", 'subagent_type: "Explore"'),
    ("dispatch brief template", "Agent Dispatch Brief Template"),
    ("FIRST ACTION header", "FIRST ACTION"),
    ("ROLE header", "**ROLE:**"),
    ("Result contract", "## Result"),
    ("hook is named", "agent-pretool-brief-check.sh"),
]

HOOK_MUST_CONTAIN = [
    ("checks FIRST ACTION", "FIRST ACTION:"),
    ("checks CLAUDE.md ref", "CLAUDE.md"),
    ("checks ROLE", "ROLE:"),
    ("checks Result block", "## Result"),
    ("reads subagent_type", "subagent_type"),
    ("reads model", "field model"),
    ("Explore carve-out", "explore"),
    ("requires opus", "opus"),
    ("blocks with exit 2", "exit 2"),
]


def check(path, label, must_contain):
    if not os.path.exists(path):
        return [f"{label}: missing file {os.path.relpath(path, ROOT)}"]
    text = open(path, encoding="utf-8", errors="replace").read()
    return [
        f"{label}: '{os.path.relpath(path, ROOT)}' no longer contains the {what} "
        f"(looked for {needle!r}). If you intentionally changed the doctrine, update "
        f"CLAUDE.md AND this check together — don't let them drift."
        for what, needle in must_contain
        if needle not in text
    ]


def main():
    fails = check(CLAUDE_MD, "CLAUDE.md doctrine", CLAUDE_MUST_CONTAIN)
    fails += check(HOOK, "dispatch hook", HOOK_MUST_CONTAIN)
    if fails:
        for f in fails:
            print(f"FAIL {f}")
        print(f"\ncheck_dispatch_doctrine: {len(fails)} failure(s).")
        return 1
    if "--quiet" not in sys.argv:
        print("check_dispatch_doctrine: ok (CLAUDE.md doctrine + hook enforcement in sync).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
