# CLAUDE.md

Source of truth for AI coding agents working on **WoL Unbalanced** — a funnily overpowered, player-only StarCraft II: Wings of Liberty campaign mod for GiantGrantGames' Custom Campaign Manager. Not to be taken seriously; balance is a non-goal by design.

What lives where: [README.md](README.md) (overview, credits, license, build), [plan.md](plan.md) (architecture & work packages — the *how*), [unit-table.md](unit-table.md) (the spec — per-unit changes; the user's Comments column is authoritative, never overwrite it), [docs/learnings.md](docs/learnings.md) (hard-won SC2 modding gotchas), [docs/open-issues.md](docs/open-issues.md) (the bug tracker — confirmed defects), [docs/BACKLOG.md](docs/BACKLOG.md) (forward feature work, prioritized), [docs/verification-checklist.md](docs/verification-checklist.md) (the in-game test plan), [docs/debug-toolkit.md](docs/debug-toolkit.md) (symptom→fix recipes + what `audit.py` auto-catches).

## Session-Start Protocol

1. Read this file end to end.
2. Read [plan.md](plan.md) — at minimum the Status section and "Open next".
3. Load session memory: engram `mem_context` / `mem_search` for the area you'll touch (project `wol-unbalanced`; skip gracefully if the engram MCP server is unavailable).
4. Skim [docs/learnings.md](docs/learnings.md) — these gotchas cost real debugging sessions; don't re-derive them.
5. `git status` — this repo works directly on `main`.

## Dev Loop

```sh
python3 scripts/genlib.py        # regenerate the per-player apply script from reference XML
python3 scripts/galaxy_lint.py   # MANDATORY before build — catches black-map compile bugs
python3 scripts/audit.py         # static catalog/actor audit — catches sphere-no-model + dead calldowns
python3 scripts/build.py build   # patch maps + assemble campaign into build/
python3 scripts/build.py install # copy into /Applications/StarCraft II
```

- **You cannot run the game.** The user verifies in game. Always tell them exactly what to check and in which mission. `galaxy_lint.py` + `audit.py` are the only *automatic* debugging we have (no SC2 MCP); runtime debugging is the in-game diag line + the owner — see [docs/debug-toolkit.md](docs/debug-toolkit.md).
- Run `scripts/hooks/install.sh` once to wire the pre-commit gate (lint + audit + untracked warning) — a broken commit becomes a broken auto-release.
- **Load canary**: the subtitle message "WoL Unbalanced: data applied …" at ~1 s/10 s into a mission. Absent ⇒ our library didn't run. Black map with no error ⇒ Galaxy compile failure (see learnings).
- Reference data (vanilla catalogs, CampaignLib sources, reference mods) lives under `mods/_reference/` and `mods/` — gitignored, never committed.

## Design Rules (the contract)

All changes affect **only the player** (rule 9) — enemies stay vanilla. (1) No new units. (2) Armory upgrades auto-unlocked from each unit's unlock mission. (3) Mercs unlock with their counterpart. (4) Mercs keep their % advantage and inherit counterpart upgrades. (5) Build-time cap 60 s. (6) Merc calldowns: unlimited charges, ready at mission start (Compound still required). (7) Attack windup ≤ 0.1 s. (8) Cloak is always free. (10) Heroes inherit base-unit changes & abilities (Raynor=Marine, Tychus=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost, Tosh=Spectre, Odin=Thor). Every either/or choice grants **both** sides. Full details + per-unit spec: [unit-table.md](unit-table.md).

## Hard Rules (violations cost whole sessions — details in docs/learnings.md)

- Galaxy is **single-pass**: forward-declare or define before use. A compile error = black map, **no error message**. `galaxy_lint.py` before every build, no exceptions.
- `CatalogFieldValueModify` can **edit** existing fields per player but never **create** array entries; behavior-class abilities **cannot autocast**. Structural changes go through the **clone architecture**: `*WoLU` clones in static XML, gated by the `WoLUnbalancedFlag` upgrade, wired by per-player swaps of existing links. **Never clone unit types** (mission scripts check them).
- Cloned/added area-damage effects **friendly-fire by default** — always set explicit `SearchFilters` (Crucio pattern).
- Static XML is global: direct stat edits there leak to enemies. XML is for definitions and player-exclusive units (heroes, mercs) only.

## Repo Hygiene & Releases

- Never commit third-party or generated content: `mods/`, `vendor/`, `build/`, `dist/`, `.claude/`, compiled `tools/mpqpatch` (all gitignored — keep it that way; CI enforces).
- Commits authored as **PBB** (repo-local config; never push the full real name). Lint + build green before push.
- Releases: bump `VERSION` in `scripts/build.py`; mod-only changes → push a `v*` tag (workflow repacks the previous release zip); **map-affecting changes** (dependency line, popup text, MapScript injection) → local `python3 scripts/build.py package` + manual `gh release create`.

## Session Memory (Engram)

Engram (MCP server `engram`, project `wol-unbalanced`) is the cross-session memory and the **primary** store. Non-negotiables:

- When you re-derive or discover a non-obvious fact (engine limitation, id mapping, ordering constraint, "do not do X"), save a typed `mem_save` entry — **What / Why / Where / Learned**.
- Before the session ends, save a `mem_session_summary` (goal, done, verified vs pending, open items). A Stop hook ([scripts/hooks/stop-engram-summary-check.sh](scripts/hooks/stop-engram-summary-check.sh)) fires a reminder if no engram write happened recently — tripwire, not a gate.
- [docs/learnings.md](docs/learnings.md) is **curated public documentation**, not a memory mirror: promote a fact there only when it's stable, repo-relevant, and useful to anyone modding WoL — no per-session bookkeeping duty.

## Subagent Briefs

Any dispatched subagent brief must start with: **FIRST ACTION: read `CLAUDE.md` and `docs/learnings.md`** and follow both throughout — especially the Hard Rules and the learnings contribute-back rule.
