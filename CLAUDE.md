# CLAUDE.md

Source of truth for AI coding agents working on **WoL Unbalanced** — a funnily overpowered, player-only StarCraft II: Wings of Liberty campaign mod for GiantGrantGames' Custom Campaign Manager. Not to be taken seriously; balance is a non-goal by design.

What lives where: [docs/HANDOFF.md](docs/HANDOFF.md) (**START HERE on a new/fresh instance** — current state + prioritized next steps), [docs/SETUP.md](docs/SETUP.md) (**new machine? read first** — cross-platform environment setup, Windows-first), [README.md](README.md) (overview, credits, license, build), [plan.md](plan.md) (architecture & work packages — the *how*), [unit-table.md](unit-table.md) (the spec — per-unit changes; the user's Comments column is authoritative, never overwrite it), [docs/unit-status.md](docs/unit-status.md) (the LIVING per-unit status view — what's changed / works / buggy; update it whenever a decision or change alters the mod's effect), [docs/learnings.md](docs/learnings.md) (hard-won SC2 modding gotchas), [docs/open-issues.md](docs/open-issues.md) (the bug tracker — confirmed defects), [docs/BACKLOG.md](docs/BACKLOG.md) (forward feature work, prioritized), [docs/verification-checklist.md](docs/verification-checklist.md) (the in-game test plan), [docs/debug-toolkit.md](docs/debug-toolkit.md) (symptom→fix recipes + what `audit.py` auto-catches), [docs/examples/](docs/examples/README.md) (the **worked-example cookbook** — reusable, verified "to get result X, make change Y" recipes covering every request that came into the mod, + the Editor verification runbook & bunch-verify queue; add a recipe when a new request has none).

**Dev machine: Windows 11** (moved from a Mac — the SC2 Editor crashed on startup there but runs on Windows). The pure-Python dev loop runs identically on both OSes (`build.py` is OS-aware: Windows `C:\Program Files (x86)\StarCraft II` / macOS `/Applications/StarCraft II`, `WOLU_SC2_DIR` override, `mpqpatch.exe` vs `mpqpatch`). The Windows move unlocks the **SC2 Editor validation path** (Previewer renders portraits/models; Test Document Ctrl+F9 runs the mod in-game) — see [docs/learnings.md](docs/learnings.md) §Verification tooling + [docs/debug-toolkit.md](docs/debug-toolkit.md). The SC2 client API for live reads remains a confirmed dead end.

## Session-Start Protocol

0. **New machine / fresh instance?** Read [docs/HANDOFF.md](docs/HANDOFF.md) (current state + next steps) and [docs/SETUP.md](docs/SETUP.md) (environment setup) — the committed repo is the source of truth; engram/Mac-local memory may be absent on Windows.
1. Read this file end to end.
2. Read [plan.md](plan.md) — at minimum the Status section and "Open next".
3. Load session memory: engram `mem_context` / `mem_search` for the area you'll touch (project `wol-unbalanced`; skip gracefully if the engram MCP server is unavailable — e.g. on Windows it may not be running).
4. Skim [docs/learnings.md](docs/learnings.md) — these gotchas cost real debugging sessions; don't re-derive them.
5. `git status` — this repo works directly on `main`.

## Dev Loop

```sh
python3 scripts/genlib.py        # regenerate the per-player apply script from reference XML
python3 scripts/galaxy_lint.py   # MANDATORY before build — catches black-map compile bugs
python3 scripts/audit.py         # static catalog/actor audit — catches sphere-no-model + dead calldowns
python3 scripts/preview.py --check  # CHECK8: every per-player edit sits on a verified-applying field class (no no-op runtime edits). Plain `preview.py` writes build/preview/buff-manifest.md (every buff value)
python3 scripts/build.py build   # patch maps + assemble campaign into build/
python3 scripts/build.py install # copy into /Applications/StarCraft II
```

- **You cannot run the game.** The user verifies in game. Always tell them exactly what to check and in which mission. `galaxy_lint.py` + `audit.py` are the only *automatic* debugging we have (no SC2 MCP); runtime debugging is the in-game diag line + the owner — see [docs/debug-toolkit.md](docs/debug-toolkit.md).
- Run `scripts/hooks/install.sh` once to wire the pre-commit gate (lint + audit + untracked warning) — a broken commit becomes a broken auto-release.
- **Load canary**: the subtitle message "WoL Unbalanced: data applied …" at ~1 s/10 s into a mission. Absent ⇒ our library didn't run. Black map with no error ⇒ Galaxy compile failure (see learnings).
- Reference data (vanilla catalogs, CampaignLib sources, reference mods) lives under `mods/_reference/` and `mods/` — gitignored, never committed.

## PM Orchestration & Delegation (how the top-level agent works)

The top-level / open-chat agent is the **Product Manager / orchestrator by default**. It plans, delegates the leaf work to **Opus engineers**, and reviews — it does not hand-write the bulk of the implementation itself. Quality compounds when judgment work runs on the strongest model and the rules are *enforced*, not just described.

- **The dispatch triad — research → implement → validate.** Every non-trivial change goes through up to three dispatch kinds, each at the right model tier:
  1. **Research** (when investigation is needed first) — a read-only `Explore` agent on a **lighter** model maps the area (reference catalogs, merged card layouts, id resolution) and returns findings. Don't pre-read whole subsystems in the PM context; dispatch the look.
  2. **Implement** — an **Opus** engineer (`model: "opus"`) makes the change against the PM's brief.
  3. **Validate** — an **independent Opus reviewer** (`subagent_type: "Code Reviewer"`, `model: "opus"`) reads the diff **before build/commit**, separate from the PM's own review. The author never validates their own work. (This session's audit gate caught a shipped `YamatoWoLU` bug exactly this way — static review finds what the owner's playtest shouldn't have to.)
- **The validation chain for this project.** independent Opus review (static) → `galaxy_lint.py` + `audit.py` + `build.py build` green → **the owner verifies in game** (the ultimate gate — there is no SC2 MCP, the PM cannot run the game). Static review + the gate exist to catch everything catchable *before* the owner's playtest, never to replace it.
- **Hard boundary, with a solo-project carve-out.** The PM delegates substantive implementation (XML/galaxy/genlib edits, new tooling) and reserves its context for sequencing, briefs, review, commits, builds, and releases. **Trivial mechanical edits** (a one-line value, a rename, a doc tweak) and quick fixes the PM may do in-place — name the triviality when you do. When in doubt, dispatch.
- **Model tier (the rule the hook enforces):** implement + validate dispatches use `model: "opus"`; only a read-only research dispatch (`subagent_type: "Explore"`) may run on a lighter model.
- **Enforced, not just described.** The dispatch hook ([scripts/hooks/agent-pretool-brief-check.sh](scripts/hooks/agent-pretool-brief-check.sh)) **blocks (exit 2)** a Task whose brief is missing the required headers or the `## Result` block, or an implement/validate dispatch that isn't Opus. `scripts/check_dispatch_doctrine.py` (pre-commit + CI) keeps this doctrine and the hook in sync, so the rules can't silently drift out of the prose.

## Design Rules (the contract)

All changes affect **only the player** (rule 9) — enemies stay vanilla. (1) No new units. (2) Armory upgrades auto-unlocked from each unit's unlock mission. (3) Mercs unlock with their counterpart. (4) Mercs keep their % advantage and inherit counterpart upgrades. (5) Build-time cap 60 s. (6) Merc calldowns: unlimited charges, ready at mission start (Compound still required). (7) Attack windup ≤ 0.1 s. (8) Cloak is always free. (10) Heroes inherit base-unit changes & abilities (Raynor=Marine, Tychus=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost, Tosh=Spectre, Odin=Thor). Every either/or choice grants **both** sides. Full details + per-unit spec: [unit-table.md](unit-table.md).

## Hard Rules (violations cost whole sessions — details in docs/learnings.md)

- Galaxy is **single-pass**: forward-declare or define before use. A compile error = black map, **no error message**. `galaxy_lint.py` before every build, no exceptions.
- `CatalogFieldValueModify` can **edit** existing fields per player but never **create** array entries; behavior-class abilities **cannot autocast**. Structural changes go through the **clone architecture**: `*WoLU` clones in static XML, gated by the `WoLUnbalancedFlag` upgrade, wired by per-player swaps of existing links. **Never clone unit types** (mission scripts check them).
- Cloned/added area-damage effects **friendly-fire by default** — always set explicit `SearchFilters` (Crucio pattern).
- Static XML is global: direct stat edits there leak to enemies. XML is for definitions and player-exclusive units (heroes, mercs) only.

## Don't-guess discipline (how we stop repeating the same mistakes)

Most recurring bugs were one of two things: **referencing an id/path that doesn't exist** (guessed model `.m3` paths, a "Valkyrie"/"Liberator" model not in WoL, a clone whose `<Effect>` re-defaulted to a nonexistent id, a wrong `ShieldArmorName` format) or a **wrong command-card index** (overriding a passive button, appending into a gap/collision). The rule: **verify against the reference catalogs or a tool — never ship a guess as "fixed".**

- **Resolve every id before you write it.** Any `parent=`, `Effect=`, `AbilCmd` target, validator/behavior/weapon link must exist in our XML or `mods/_reference/` (use `scripts/xmlq.py ids/get`). `scripts/audit.py` now **FAILS** on unresolved parents (CHECK3) and the clone-Effect trap (CHECK4) — run it; a FAIL is a real bug, not noise.
- **Card edits are merge-aware.** Vanilla cards are built across base→campaign→story layers (campaigns *edit* arrays: `removed="1"` tombstones, index-less appends to the end). Compute the EFFECTIVE merged card before choosing an index — `audit.py` CHECK5 simulates the merge and warns on passive-as-action / button-with-no-ability / cell collisions. Don't eyeball indices.
- **Assets you can't verify are NOT "done".** `.m3`/`.dds`/model/portrait tokens resolve only in-game (the reference dump has no ActorData/ModelData). `audit.py` lists them as `UNVERIFIED — confirm in game`. Prefer an id the engine already loads (e.g. the base unit's `MedicPortrait` over a hand-typed path); when you must use a new asset, say "pending owner confirmation", never "fixed".
- **Separate "verified" from "needs in-game".** In summaries and [docs/open-issues.md](docs/open-issues.md), state plainly which fixes are statically proven and which await the owner's playthrough. Static-only confidence ≠ shipped-and-working.
- The gate runs in the pre-commit hook + CI. Treat `galaxy_lint.py` + `audit.py` green as necessary, not sufficient — they catch structure, not balance or visuals.

## Repo Hygiene & Releases

- **Third-party / generated content is excluded by default** (allowlist model): `mods/`, `vendor/`, `build/`, `dist/`, `.claude/`, compiled `tools/mpqpatch` are gitignored, and large binaries (zips/maps) are NEVER committed into git history. A third-party item may be **bundled into a distributed release zip** only if it's listed **Allowed** in [docs/third-party-allowlist.md](docs/third-party-allowlist.md) — basis is either a redistribution license on file OR an explicit owner decision per CCM fan-mod norm (bundle + credit + link source). **Allowed:** Rhyme's Nightmare pack (owner decision; no license published, so credited + GGG-Discord source linked). It's fetched locally and bundled into the **Nightmare** release zip at build time (`build.py package nightmare`), never committed. Release artifacts are GitHub *release assets* (outside the repo); CI auto-builds the **default** variant on a `v*` tag, the **Nightmare** variant is built locally + uploaded (CI has no third-party inputs).
- Commits authored as **PBB** (repo-local config; never push the full real name). Lint + build green before push.
- Releases: bump `VERSION` in `scripts/build.py`; mod-only changes → push a `v*` tag (workflow repacks the previous release zip); **map-affecting changes** (dependency line, popup text, MapScript injection) → local `python3 scripts/build.py package` + manual `gh release create`.
- **Credits check (every release / git upload):** before tagging, confirm [README.md](README.md) §Credits still lists every third-party source you newly relied on this round — any reference mod under `mods/` whose data you copied a blueprint from (e.g. Moebius, RaynorRogue kit, NCO), and the **base** mod if a build variant bundles it (the optional Nightmare build bundles Rhyme's pack → must credit Rhyme + keep the License note accurate). Run `python3 scripts/check_credits.py` for a quick coverage warning.

## Session Memory (Engram)

Engram (MCP server `engram`, project `wol-unbalanced`) is the cross-session memory and the **primary** store. Non-negotiables:

- When you re-derive or discover a non-obvious fact (engine limitation, id mapping, ordering constraint, "do not do X"), save a typed `mem_save` entry — **What / Why / Where / Learned**.
- Before the session ends, save a `mem_session_summary` (goal, done, verified vs pending, open items). A Stop hook ([scripts/hooks/stop-engram-summary-check.sh](scripts/hooks/stop-engram-summary-check.sh)) fires a reminder if no engram write happened recently — tripwire, not a gate.
- [docs/learnings.md](docs/learnings.md) is **curated public documentation**, not a memory mirror: promote a fact there only when it's stable, repo-relevant, and useful to anyone modding WoL — no per-session bookkeeping duty.

## Agent Dispatch Brief Template

Dispatched subagents do NOT auto-load `CLAUDE.md` — they get only the brief plus their `subagent_type` definition. The brief is the only way to bind them to the project's rules and role. Every dispatch brief MUST contain, in this order:

1. A **FIRST ACTION** header (within the first ~500 characters), e.g.:
   > **FIRST ACTION:** Read `CLAUDE.md` and `docs/learnings.md` end to end before anything else, and follow both throughout — especially the Hard Rules, the Don't-guess discipline, and the learnings contribute-back rule.
2. A **ROLE** header (within the first ~1000 characters) naming the role and its conventions, e.g.:
   > **ROLE:** You are taking the role of [Senior SC2-data engineer / Code Reviewer / Explore researcher / …]. Apply that role's conventions throughout.
3. The **`## Result` block** instruction (in the brief body, after the headers) — every brief tells the subagent to end its final report with exactly:
   ```
   ## Result
   - STATUS: success | partial | blocked
   - ARTIFACTS: files created/modified, or none
   - RISKS: known risks/uncertainties, or none
   - LEARNINGS: docs/learnings.md entry contributed, or "none re-derived"
   - NEXT: recommended follow-up, or none
   ```
   A report without this block is treated as `STATUS: partial` — verify the work directly before accepting it.
4. The right **model tier** (see [§PM Orchestration & Delegation](#pm-orchestration--delegation)): `model: "opus"` for implement/validate; `subagent_type: "Explore"` (lighter) for read-only research.

These are enforced mechanically by [scripts/hooks/agent-pretool-brief-check.sh](scripts/hooks/agent-pretool-brief-check.sh) (a Claude Code `PreToolUse(Task)` hook, wired in `.claude/settings.json`): a brief missing FIRST ACTION / `CLAUDE.md` / ROLE / `## Result`, or a non-`Explore` dispatch with an explicit non-Opus `model`, is **rejected at the harness (exit 2)** before the subagent runs. Run `scripts/hooks/install.sh` notes; the hook itself needs the `.claude/settings.json` wiring (local, since `.claude/` is gitignored).
