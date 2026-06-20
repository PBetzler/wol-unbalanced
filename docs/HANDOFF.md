# START HERE — current state + next steps (machine handoff)

Fresh-instance orientation for WoL Unbalanced. The dev machine moved **Mac → Windows 11**.
**The committed repo is the source of truth** — Mac-local memory and engram (the MCP memory
server) may be ABSENT on Windows; everything you need is in the docs indexed below.

> First 10 minutes? Jump to §"Windows quickstart" at the bottom.

---

## Project state (one paragraph)

**WoL Unbalanced** is a funnily-overpowered, **player-only** StarCraft II: Wings of Liberty
campaign mod for GiantGrantGames' Custom Campaign Manager (CCM) — your army is buffed every which
way, enemies stay vanilla (rule 9). **v0.3.18 is the current batch** (on `main`). The headline of the
v0.3.14–v0.3.18 arc: v0.3.14 added the **Skip Prophecy (Zeratul) missions** button (+ a passive-icon
truth pass / train-button collision fix / Senior Ghost clone), then **v0.3.15–v0.3.17 chased a phantom**
— the owner reported "nothing works / no canary", and I shipped speculative fixes assuming a code bug.
**The REAL root cause (found in v0.3.18, settled by CCM's source): the install TARGET.** CCM installs
custom content into the GAME INSTALL dir — `sc2BasePath` = the SC2.exe dir from the registry
(`C:\Program Files (x86)\StarCraft II`), maps → `sc2BasePath\Maps\Campaign`, mods → `sc2BasePath\Mods\`
(github.com/7thAce/SC2CCM `CCM/FormMain.cs`). Mid-spiral a session flipped `build.py install` to
`Documents\StarCraft II` on a verbal hunch (commit 867a718) → CCM reported "no mod installed" and the
campaign loaded vanilla. Re-pointed to the install dir + reinstalled correctly; re-enabled `WoLUSmartServos` (a
false suspect I'd disabled in v0.3.16); removed the pre-grant diagnostic canary. So the mod's FEATURES
(Skip-Prophecy button, merc behaviour, faster Viking transform) are now installed correctly and
**[GAME]-pending the owner's FIRST real (loading) playtest** — none were ever actually tested because
the mod wasn't loading. Process guards added so this can't recur: **CHECK12** (never re-identify a
vanilla unit), a **SessionStart engram hook** (load cross-session memory first), and CLAUDE.md Hard
Rules ("verify the mod is LOADED before debugging the code"). See [open-issues.md](open-issues.md)
§v0.3.18.
The mechanism: the WoL campaign maps stay vanilla except one patched dependency line + a one-line
`MapScript.galaxy` include, and a component-folder `.SC2Mod` whose Galaxy library applies every
change **per player** at mission start (catalog modifications + the campaign's tech-granting
functions). The **verification model**: (1) the static gate — `genlib.py` + `galaxy_lint.py` +
`audit.py` (CHECK1–7 + a card-merge simulator) catches structural bugs before a build ships;
(2) the **owner's in-game playtest** is the ultimate gate (you cannot run the game from the dev
box, and the SC2 client API is a confirmed dead end on retail 5.x); (3) **NEW on Windows — the SC2
Editor** (Previewer renders portraits/models; Test Document Ctrl+F9 runs the mod in-game) is now
an available local validation lever. Static-green ≠ shipped-and-working: many fixes are statically
proven but still `[GAME]`-pending the owner's playthrough.

---

## Where the context lives (read in this order)

| Doc | What it is |
|---|---|
| [SETUP.md](SETUP.md) | **Environment setup** — Windows-first; tools, the gitignored inputs, local-build recipe, hooks, Editor path. **New machine? read this first.** |
| [../CLAUDE.md](../CLAUDE.md) | **The contract** — design rules, hard rules, the don't-guess discipline, PM/dispatch doctrine, session protocol. Read end to end. |
| [../plan.md](../plan.md) | Architecture + work packages (the *how*); **§7 Status** is the running changelog of what shipped; "Open next" at the very end. |
| [implementation-patterns.md](implementation-patterns.md) | **VERIFIED "how to implement X"** with `file:line` cites + `[STATIC]`/`[GAME]`/`[ASSUMPTION]` confidence legend. Compare a change against it before writing. |
| [examples/](examples/README.md) | **The worked-example cookbook** (NEW) — 30+ reusable, independently-reviewed "to get result X, make change Y" recipes covering every request that came into the mod, each statically verified with `file:line` cites. Includes the **SC2-Editor verification runbook** and the **[bunch-verify queue](examples/_QUEUE.md)** (the parked [EDITOR]/[GAME] checks). Add a recipe when a new request has none. |
| [open-issues.md](open-issues.md) | **The bug tracker** — confirmed defects + root-cause notes, newest batch first. The `[GAME]` items are what's pending playtest. |
| [unit-status.md](unit-status.md) | **LIVING per-unit status** — per unit, what changed and whether it's proven / awaiting-game / broken. Update it when a change alters the mod's effect. |
| [learnings.md](learnings.md) | **Hard-won SC2 modding gotchas** — each cost a real debugging session. Read the relevant section before touching an area; contribute back when you re-derive something. |
| [verification-checklist.md](verification-checklist.md) | The mission-ordered **in-game test plan** (canary/diag values, ~9 priority missions). |
| [debug-toolkit.md](debug-toolkit.md) | **symptom → diagnosis → fix** recipes + exactly what `audit.py` auto-catches. |
| [BACKLOG.md](BACKLOG.md) | Forward feature work, prioritized; "Recently done" rolling log. |
| [../unit-table.md](../unit-table.md) | The spec — per-unit intent; **the owner's Comments column is authoritative, never overwrite it.** |

> **Memory note:** engram (project `wol-unbalanced`) and the Mac auto-memory hold session history
> that does **not** transfer to Windows. Don't rely on them being present. If engram is up, great —
> `mem_context` / `mem_search`; if not, the docs above are complete on their own.

---

## Pending `[GAME]` verification — v0.3.13 batch (awaiting the owner's playtest)

These shipped in the v0.3.13 batch and are **statically settled/complete** (gate green: genlib +
lint + audit + CHECK8 + CHECK9 + CHECK10 + CHECK11) but need in-game confirmation. Full root-cause
notes in [open-issues.md](open-issues.md) §"v0.3.13"; the test steps are in
[verification-checklist.md](verification-checklist.md) (Media Blitz AA section + the new "Flier/vehicle
upgrade scaling" block + the Viking-ground items):

1. **Flier/vehicle upgrade scaling** — Banshee/BC/Viking (air+ground) weapons + Banshee/BC/Viking/
   Medivac/Raven/Thor/SiegeTank/Hellion armor + elite-merc armor now scale with the combined Eng Bay
   upgrade. ⚠ owner confirms a Banshee/BC/Viking gains weapon/armor levels; reads the `diagUpg`
   subtitle (`infW=1/0` before-lab, `0/1` after-lab, `vehW>=1 shipW>=1`).
2. **Viking ground projectile/impact restored** — the gatling launch/impact sound + blood are back
   (had detached after the `TwinGatlingCannon` Effect reroute). ⚠ owner confirms visible/audible
   ground hits on the player Viking + Hel's Angels.
3. **Thor/Jotun AA impact sound restored** — the AA impact sound is back (had detached after the
   `JavelinMissileLaunchersLM` `ImpactEffect` reroute). ⚠ owner confirms.
4. **Thor/Jotun/Odin AA barrage** — 8 missiles per attack (was 4) at ~2/3 cadence; card reads "×8".
   ⚠ owner confirms the doubled volley + cadence.
5. **Two card-number fixes** — Thor/Jotun AA card reads **flat 35** (no "+4 vs Light"); Viking/Hel's
   Angels ground card reads **14 "+20 vs Mechanical"** (CHECK11-gated). ⚠ owner confirms the panels.

> **Still OPEN — owner-decision-pending (not blockers):** Ghost/Spectre rifle "+vs Light/Armored"
> flatten (a per-player `AttributeBonus` edit is a no-op class → needs a Shaped-Blast effect clone)
> and Senior Ghost +50% panel under-show (needs a Senior-Ghost-specific weapon clone). See
> [open-issues.md](open-issues.md) §"Damage display + values".

## Pending `[GAME]` verification — v0.3.9 batch (older; still awaiting the owner's playtest)

These shipped in v0.3.9 and are **statically settled/complete** but need in-game confirmation
(from [open-issues.md](open-issues.md) §"v0.3.9 batch" — full root-cause notes there). A death/UI
mechanism can't be statically proven; the static checker can't observe "fires both at once" /
"renders a portrait" / "the card shows the button":

1. **Bug 1 — Hammer Securities (Marauder merc) super stim** — appended a fresh `Type=AbilCmd`
   stim button (index 7, cell 2,2) `Face="Stim" AbilCmd="StimpackMarauderWoLU,Execute"`. ⚠ owner
   confirms the stim button **shows** on Hammer Securities and **autocasts** in combat.
2. **Bug 4a — Jotun (Thor merc) Immortality Protocol** — parallel merc-exclusive death chain
   (`MercThorDontDie` → `MercThorWreckage` → `MercThorReborn`, gas zeroed). ⚠ owner confirms a
   fatal hit drops the Jotun to a wreck, it **rebuilds AS A JOTUN** (merc actor/name), **no gas**
   in the tooltip, **single HP bar**.
3. **Bug 4b — Jotun windup (time to first shot)** — `DamagePoint`≤0.1 confirmed capped on BOTH
   Thor weapons. ⚠ if sluggishness persists, the suspect is the AA weapon's `Period` (3.0 s, a
   cadence not a first-shot delay) or turn-to-face — read `MercThor`'s `ThorsHammer`/
   `JavelinMissileLaunchers` `DamagePoint`+`Period` to disambiguate.
4. **Bug 4c — Jotun simultaneous air+ground fire** — the three independent-fire `Options[]` flags
   are present/correct in static `WeaponData.xml`. ⚠ owner confirms it fires both at once.
5. **Bug 2 — Medic/Stetmann heal mechanical** — card simulator confirms ONE visible heal button
   pointing at the mechanical-capable `HealWoLU` clone. ⚠ owner manually heals a Marauder/Viking.
6. **Bug 3 — shielded-merc normal armor sign** — each elite merc's `LifeArmorName` matches its
   base unit's vanilla value; `ShieldArmorName` kept. CHECK7 green. ⚠ owner confirms the inspect
   panel renders BOTH the life-armor icon AND the shield icon side-by-side.
7. **Long-standing — elite-merc portraits** (the 6 `Merc*` clones) — **✅ EDITOR-CONFIRMED
   2026-06-17 (representative case).** Loaded the mod in the SC2 Editor Previewer: `MercThor`
   (Jotun) resolves to body model "Thor" + portrait "Portrait - Thor" (the real Thor portrait,
   not a heart; renders, not a sphere); `Condor` renders as a Hellion; armor signs resolve
   ("Defensive Matrix" + "Terran Vehicle Plating"). Mechanism proven + CHECK6 covers all 6 tokens.
   ⚠ One flag: `MercWraith` (Winged Nightmares) did **not** appear in the *standalone-mod* Editor
   view (statically identical to siblings; likely a missing-campaign-dep artifact) — see
   [open-issues.md](open-issues.md) §"Editor verification pass". Build + Previewer details there
   and in [SETUP.md §3](SETUP.md).

> Earlier batches (v0.3.5–v0.3.8) also carry `[GAME]`/⚠ items in open-issues.md (bunker capacity,
> cloak-on-spawn decloak button, Jackson's Revenge autocasts, etc.). The v0.3.9 list above is the
> newest; sweep open-issues.md top-to-bottom for the complete pending set.

---

## Prioritized NEXT STEPS

1. **Verify the v0.3.9 `[GAME]` items** (above) — the single highest-value action. Two levers now:
   - **The owner's playtest** via the release zip (per [verification-checklist.md](verification-checklist.md),
     mission-ordered; watch for the canary + diag subtitle lines first).
   - **The Windows SC2 Editor** (NEW): **Previewer** renders the elite-merc portraits/models
     locally (settles #7 and any sphere question without a playtest); **Test Document (Ctrl+F9)**
     runs the mod in-game via Battle.net's license path. See [debug-toolkit.md](debug-toolkit.md) +
     [learnings.md](learnings.md) §"Verification tooling".
2. **Clear the rest of [open-issues.md](open-issues.md)** — the still-open flagged-mechanism items
   (Yamato structure discrimination, Graduating-Range stack count, `Button.Requirements` per-player
   edit no-op risk, assumption values) and any new bugs the owner reports from a fresh playthrough.
3. **Owner-blocked decisions** ([open-issues.md](open-issues.md) §"Blocked — needs owner"):
   Marauder Tech Lab / Hercules Fusion Core drop (accept losing the Compound gate, or leave
   prereqs?).
4. **Deferred backlog** ([BACKLOG.md](BACKLOG.md)) — all need in-game iteration, not blind shipping:
   **BC smart-batteries** (fully blueprinted from the RaynorRogue kit; single-target fallback
   already works), Viking Wild Missiles, Tank Transport Hook. Open data: "Resource Efficiency"
   exact per-unit values (currently the canonical −25/−25/−1 assumption).
5. **Adopt the Editor-validation workflow as the new verification lever** — fold Previewer +
   Test Document into the loop so portrait/model/card questions get answered locally before
   bothering the owner. This is the main capability the Windows move unlocks.

---

## Windows quickstart (first 10 minutes)

```sh
# 1. Clone / pull the repo (works directly on main)
git clone <repo-url> sc2-mod && cd sc2-mod      # or: git pull

# 2. Bring over the ONE must-have gitignored input (see SETUP.md §2):
#    copy mods/_reference/ from the Mac repo  ->  mods/_reference/  here
#    (platform-independent catalog dumps; needed for the full static gate)

# 3. Run the static gate (Python 3.x; no third-party deps for the gate)
python scripts/genlib.py
python scripts/galaxy_lint.py
python scripts/audit.py
#    genlib must write the Gen.galaxy; audit must end "audit: ok (…)".

# 4. Read this file + CLAUDE.md (the contract) + plan.md §7 (what shipped).

# 5. (OPTIONAL) set up the local build for faster iteration — SETUP.md §3:
#    copy mods/Tactical_Arsenal/ + vendor/StormLib/, build tools/mpqpatch.exe,
#    then: python scripts/build.py build && python scripts/build.py install
#    NOT required — the owner playtests via the release zip (push a v* tag).

# 6. (RECOMMENDED) wire the hooks — SETUP.md §6:
#    bash scripts/hooks/install.sh            # git pre-commit gate (Git Bash)
#    + create .claude/settings.json           # dispatch + Stop hooks (template in SETUP.md §6b)
```

Then pick up at **NEXT STEPS** above — most likely confirming the v0.3.9 `[GAME]` items via the
owner's playtest and/or the now-available Windows SC2 Editor.
