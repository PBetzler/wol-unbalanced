# 27 — Galaxy-side per-player logic (the apply lib, canary/diag, cloak-On, resource timers)

> Do the per-player things that **cannot be data**: grant the campaign's tech/mercs per player,
> prove the mod ran (canary + diag), issue orders (cloak-On), and run periodic effects
> (graduating siege range, Vespene synthesis) — all scoped to the human player (rule 9).

**Maps to (request):** the rule-2/3/6 grant ("all upgrades + mercs from start"), the visible
canary (debug-toolkit), rule-8 cloak-On UI sync ([23](23-free-cloak.md)), and the BACKLOG
"Predator Vespene Synthesis". **Status:** [STATIC] compiles + ships; the runtime effects
(grant, canary visible, gas ticking) are [GAME]. learnings §"Galaxy script" + §"CampaignLib
internals".

---

## Result
At mission start the human player gets the full armory, every merc, both lab-research halves,
and the `WoLUnbalancedFlag` upgrade — and a subtitle **"WoL Unbalanced: data applied, …"**
proves it ran. Then periodics keep adding cloak buffs, growing sieged-tank range +1/3 s, and
synthesizing +5 gas per living Predator per 3 s — all for player 1 only.

## Mechanism
Galaxy is the home for anything `CatalogFieldValueModify` can't express: calling CampaignLib
functions, issuing unit orders, reading/writing player resources, and timed/periodic logic. The
build pipeline injects `include "LibWoLUnbalanced"` + a `libWoLU_InitLib()` call into every map's
`MapScript.galaxy` (maps are never re-saved in the editor — learnings §"Maps are the only
injection point").

**Galaxy is single-pass** (like C): a function used before it's defined is a compile error, and a
MapScript compile failure kills *every* trigger → the mission loads as a **black map with no error
message** (the campaign suppresses the script-error dialog). The lib therefore **forward-declares**
every function called before its definition
(`LibWoLUnbalanced.galaxy:18-25`), and `scripts/galaxy_lint.py` (CI + pre-commit) guards brace
balance and declaration order. Run it before every build, no exceptions. (learnings §"Galaxy
script".)

The two pure-data edits live in the **generated** lib `libWoLUGen_Apply(p)`
(`LibWoLUnbalancedGen.galaxy`, produced by `scripts/genlib.py`); the hand-written
`LibWoLUnbalanced.galaxy` calls it and adds the logic-that-isn't-data.

## Worked example (real, from this repo)

### a) The apply entry point + the grant
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:27-29
void libWoLU_ApplyPlayer (int p) {
    libWoLUGen_Apply(p);          // all per-player CatalogFieldValueModify edits (genlib output)
}
```
The grant (`libWoLU_GrantCampaignTech`, `LibWoLUnbalanced.galaxy:44-156`) re-applies the
campaign's *own* code paths so the UI stays consistent — `libCamp_gf_TS_BuyAllTech()` (rule 2),
`libCamp_gf_SetMercStatus(..., Purchased)` per merc (rule 6), the lab-research pairs
(`libCamp_gv_tSX_ResearchState[i]`, `LibWoLUnbalanced.galaxy:59-66`), then grants the flag:
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:130
TechTreeUpgradeAddLevel(p, "WoLUnbalancedFlag", 1);   // the clone-gate the player alone satisfies
```
(learnings §"CampaignLib internals" — `BuyAllTech` is reverted by the engine for un-introduced
tech groups, so `libWoLU_ForceGrantAllTechRewards` grants each tech's rewards *directly*,
`LibWoLUnbalanced.galaxy:158-181`.)

### b) The canary + the runtime diag (your only no-MCP debugging window)
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:200-204
bool libWoLU_OnGrantTech (bool testConds, bool runActions) {
    libWoLU_GrantCampaignTech(libWoLU_Player);
    UIDisplayMessage(PlayerGroupAll(), c_messageAreaSubtitle,
        StringToText("WoL Unbalanced: data applied, upgrades & mercs granted."));
    ...
```
The **canary** is this subtitle at ~1 s / ~10 s game time (the trigger fires on both timers —
`libWoLU_InitLib`, `LibWoLUnbalanced.galaxy:406-408`). **Absent ⇒ the lib didn't run** (black map
= a compile failure). The **diag** lines (`LibWoLUnbalanced.galaxy:210,215,221`) read values back
with `CatalogFieldValueGet(...)` — the way to confirm a per-player edit actually applied when you
can't run the game (debug-toolkit §"When you can't repro locally"). E.g. `diag3` reads
`C10CanisterRifle.AttributeBonus[Light]` back to prove the indexed-array no-op
([02](02-no-op-traps.md)).

### c) Cloak-On order (a thing only Galaxy can do — issue an order)
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:305-307
if ((u != null) && (UnitOrderCount(u) == 0)) {
    UnitIssueOrder(u, Order(AbilityCommand(cloakAbil, 0)), c_orderQueueAddToFront);
}
```
The permanent-cloak buff leaves the toggle ability OFF (card reads "Cloak On"); this issues the
On command (cmd index 0) — **`Order(...)`** (no-target form), **`AddToFront`** (not `Replace`,
which clobbers the move/attack queue), guarded to idle units. Full rationale in
[23](23-free-cloak.md). Driven from the 2 s periodic
(`libWoLU_OnPeriodic`, `LibWoLUnbalanced.galaxy:384-392`).

### d) Resource timer — Predator Vespene Synthesis (a thing only Galaxy can do — write a resource)
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:333-341
void libWoLU_SynthesizeVespene (int p) {
    unitgroup g;
    int n;
    g = UnitGroup("Predator", p, RegionEntireMap(), UnitFilter(0,0,0,(1<<(c_targetFilterDead-32))), 0);
    n = UnitGroupCount(g, c_unitCountAll);
    if (n > 0) {
        PlayerModifyPropertyInt(p, c_playerPropVespene, c_playerPropOperAdd, n * 5);
    }
}
```
Fired on the 3 s `libWoLU_OnGraduateRange` tick (`LibWoLUnbalanced.galaxy:343-351,412`) → **+5 gas
per living player Predator per 3 s**. `PlayerModifyPropertyInt` + `c_playerPropVespene` are engine
built-ins (the co-injected CampaignLib uses them, so they resolve in this compile). The same tick
runs `libWoLU_GraduateSiegeRange` (+1 `WoLUGraduatingRange` stack/3 s up to 5,
`LibWoLUnbalanced.galaxy:315-327`).

### Per-player scoping (rule 9)
Every periodic is gated `if (PlayerRace(libWoLU_Player) == "Terr")` and every `UnitGroup`/edit is
scoped to `libWoLU_Player` (= player 1, `LibWoLUnbalanced.galaxy:14`). Enemies are never touched.

## Reusable snippet (swap the logic)
```galaxy
// 1) FORWARD-DECLARE before any use (single-pass!) — put near the top of LibWoLUnbalanced.galaxy:
void libWoLU_MyNewThing (int p);

// 2) Define it later; scope every group/edit to p (rule 9):
void libWoLU_MyNewThing (int p) {
    // ... UnitGroup(p,...) / UnitIssueOrder / PlayerModifyPropertyInt / TechTree* ...
}

// 3) Wire it to a trigger in libWoLU_InitLib():
TriggerAddEventTimePeriodic(TriggerCreate("libWoLU_OnMyTick"), 3.0, c_timeGame);
//    (libWoLU_OnMyTick is a `bool (...)` handler that guards race == "Terr" then calls the above)
```
> RESOLVE FIRST: any CampaignLib id (`libCamp_*`) must exist in
> `mods/_reference/campaigns/libertystory.sc2campaign/TriggerLibs/CampaignLib.galaxy`; any catalog
> id you `CatalogFieldValueGet`/`Modify` must resolve (`xmlq.py`).

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **Use-before-define = black map, no error.** Forward-declare; run `galaxy_lint.py`.
- **A subtitle at map-init is invisible** — intro cinematics swallow it; that's why the canary
  fires on a 1 s/10 s *timer* via `libWoLU_OnGrantTech`, not at init.
- **`Order(...)` vs `OrderTargetingNone`** and **`AddToFront` vs `Replace`** — wrong choice
  freezes the unit ([23](23-free-cloak.md)).
- **Periodic edits don't replace data edits.** Stat changes go through `genlib`/`CatalogFieldValueModify`
  ([01](01-per-player-scalar-stat-edit.md)); Galaxy is for orders, resources, tech grants, and
  timed behavior maintenance (the cloak/charge buffs are re-added every 2 s so mid-mission spawns
  get them).

## Verify
- **Static:** `python scripts/galaxy_lint.py` (compile/brace/decl-order — the black-map guard) +
  `python scripts/audit.py`. **Does not prove** the grant ran or gas ticked. `[STATIC]`
- **In-game (Test Document / owner):** the **canary** subtitle appears ~10 s in (skip the intro);
  read the **diag** line values; spawn a Predator and watch gas climb +5/3 s; siege a tank and
  watch range grow. Any campaign mission. `[GAME]`
- **Editor (Previewer):** n/a — these are runtime/order/resource effects, not a render. `[GAME]`.

## Parked for bunch-verify
- `[GAME]` — canary subtitle "WoL Unbalanced: data applied…" appears ~10 s into a mission
  (absent ⇒ lib didn't run / black-map compile failure).
- `[GAME]` — with ≥1 player Predator alive, Vespene rises +5 per Predator every 3 s; enemy
  Predators (if any) give no gas (rule 9).
- `[GAME]` — sieged player tank range grows +1/3 s up to +5; resets on unsiege.
