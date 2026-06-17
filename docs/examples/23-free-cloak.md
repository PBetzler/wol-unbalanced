# 23 — Free cloak + spawn cloaked (rule 8)

> Cloak costs **nothing** to activate and **never drains** energy; every cloak-capable
> player unit **spawns already cloaked** — and still shows a working decloak button.

**Maps to (request):** design rule 8 ("Cloak is always free") + the owner's rule-11 extension
("EVERY cloak-capable player unit spawns + stays permanently cloaked, for free"); open-issues
**#11** (units don't spawn cloaked) and **#7** (cloaked-on-spawn units don't show the decloak
button). **Status:** [STATIC] done · [GAME] parked (the *visible* cloak + the decloak button —
see Verify).

---

## Result
The player's Ghost / Banshee / Wraith / Spectre / Reaper / Medivac / Predator (and the cloak
heroes Nova/Tosh + cloak mercs Dusk Wing / Winged Nightmare / Senior Ghost):
- activate cloak for **0 energy** and **never lose energy** while cloaked (rule 8);
- are **invisible from the instant they spawn** (no manual toggle needed);
- still display a usable **decloak ("Cloak Off")** button (not a stuck "Cloak On").

Enemies keep vanilla cloak (costs energy, drains) — rule 9.

## Mechanism
Three independent pieces, each the *only* one that works for its job:

1. **Free activation + no drain (rule 8)** — two per-player scalar edits. The cloak ability's
   activation cost is `Cost[0].Vital[Energy]`; the cloak buff's per-second drain is
   `Modification.VitalRegenArray[Energy]` (a negative regen). Both are **scalar-ish indexed
   fields** → `CatalogFieldValueModify` reaches them per player (the §[01](01-per-player-scalar-stat-edit.md)
   engine). Set both to `0`.

2. **Spawn cloaked** — `PersonalCloakingFree` / `SpectreCloakingFree` are **permanent-cloak
   BUFFS**, not cost-reducers: each is a `CBehaviorBuff` with `Modification > StateFlags[Cloak]=1`
   and **no energy drain**. `UnitBehaviorAdd`-ing one makes the unit cloaked from that instant
   and stay cloaked for free. It's **generic** across cloak-capable units (Ghost/Banshee/Wraith/
   Reaper/…), not just the spectre/personal originals. This is a **galaxy** add (a per-player
   `CatalogFieldValueModify` can't add a behavior to a unit type) run on a 2 s periodic so
   mid-mission spawns also get it. (learnings.md §"`PersonalCloakingFree`…are permanent-cloak
   BUFFS"; [implementation-patterns.md §13](../implementation-patterns.md).)

3. **The toggle-order quirk** — the buff cloaks the unit but leaves its **toggle cloak ability**
   in the OFF state, so the card shows "Cloak **On**" and never offers the decloak button. Fix:
   issue the toggle's **On** command from the lib —
   `UnitIssueOrder(u, Order(AbilityCommand("GhostCloak", 0)), c_orderQueueAddToFront)`. The
   **no-target** `Order(...)` form (NOT `OrderTargetingNone`), **`AddToFront`** (NOT `Replace`,
   which clobbers the unit's move/attack queue and freezes it), and a `UnitOrderCount(u)==0`
   guard so only idle units are toggled (never interrupts a busy one). Pattern lifted verbatim
   from liberty's own AI cloak triggers. (learnings.md §"Cloaking via the buff leaves the TOGGLE
   ability OFF".)

## Worked example (real, from this repo)

### (1) Free activation + no drain — genlib per-player edits
The ability/behavior id lists are declared explicitly so the output is reviewable:
```python
# scripts/genlib.py:50-53
CLOAK_ABILS = ["GhostCloak", "BansheeCloak", "WraithCloak", "RogueGhostCloak",
               "DuskWingBansheeCloakingField", "SpectreCloak"]
CLOAK_BEHAVIORS = ["GhostCloak", "BansheeCloak", "WraithCloak", "SpectreCloaking",
                   "PredatorCloaking", "BansheeCloakCrossSpectrumDampeners"]
```
```python
# scripts/genlib.py:146-149
for a in CLOAK_ABILS:
    lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "{a}", "Cost[0].Vital[Energy]", p, "0", c_upgradeOperationSet);')
for b in CLOAK_BEHAVIORS:
    lines.append(f'    CatalogFieldValueModify(c_gameCatalogBehavior, "{b}", "Modification.VitalRegenArray[Energy]", p, "0", c_upgradeOperationSet);')
```
- `Cost[0].Vital[Energy] Set 0` zeroes the **activation** cost on every toggle-cloak ability.
- `Modification.VitalRegenArray[Energy] Set 0` zeroes the **drain** on the cloak behavior (the
  thing that bleeds energy while cloaked). Note the two lists overlap but differ — the *ability*
  ids and the *behavior* ids aren't always the same (e.g. `RogueGhostCloak`/`SpectreCloak`
  abilities vs `SpectreCloaking` behavior).

### (2) Spawn cloaked — the permanent-cloak buff, added in galaxy
The buff itself (vanilla campaign data we attach, not redefine):
```xml
<!-- mods/_reference/campaigns/liberty.sc2campaign/BehaviorData.xml:478-485 -->
<CBehaviorBuff id="PersonalCloakingFree">
    <Alignment value="Positive"/>
    <Modification>
        <StateFlags index="Cloak" value="1"/>   <!-- permanently cloaked, no <VitalRegenArray> = no drain -->
    </Modification>
</CBehaviorBuff>
```
The generic adder + the per-type calls (player-scoped by construction, rule 9):
```c
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:265-277  (the generic behavior adder)
void libWoLU_AddBehaviorToType (int p, string unitType, string behavior) {
    ...
    if ((u != null) && (UnitBehaviorCount(u, behavior) == 0)) {
        UnitBehaviorAdd(u, behavior, u, 1);
    }
}
```
```c
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:362-376  (run on the 2 s periodic, line 409)
libWoLU_AddBehaviorToType(libWoLU_Player, "Ghost",   "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Spectre", "SpectreCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Banshee", "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Wraith",  "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Reaper",  "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Medivac", "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Predator","PersonalCloakingFree");
// heroes inherit base cloak: Nova=Ghost, Tosh=Spectre …
libWoLU_AddBehaviorToType(libWoLU_Player, "Nova", "PersonalCloakingFree");
libWoLU_AddBehaviorToType(libWoLU_Player, "Tosh", "SpectreCloakingFree");
// mercs inherit counterpart cloak: DuskWing(Banshee)/MercWraith(Wraith)/MercSeniorGhost(Ghost)
```

### (3) The toggle-order quirk — sync the card to "Cloak Off"
```c
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:291-309
void libWoLU_ToggleCloakOn (int p, string unitType, string cloakAbil) {
    ...
    if ((u != null) && (UnitOrderCount(u) == 0)) {                       // idle-only guard
        UnitIssueOrder(u, Order(AbilityCommand(cloakAbil, 0)), c_orderQueueAddToFront);
    }                                                                    // cmd index 0 = "On"
}
```
```c
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:384-392  (unit -> its toggle ability id)
libWoLU_ToggleCloakOn(libWoLU_Player, "Ghost",   "GhostCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "Banshee", "BansheeCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "Wraith",  "WraithCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "Spectre", "RogueGhostCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "Nova",    "GhostCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "Tosh",    "RogueGhostCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "DuskWing","DuskWingBansheeCloakingField");
libWoLU_ToggleCloakOn(libWoLU_Player, "MercWraith","WraithCloak");
libWoLU_ToggleCloakOn(libWoLU_Player, "MercSeniorGhost","GhostCloak");
```
**Unit → toggle-ability map** (cmd index 0 = On, 1 = Off): Ghost=`GhostCloak`,
Banshee=`BansheeCloak`, Wraith=`WraithCloak`, Spectre=`RogueGhostCloak`,
DuskWing=`DuskWingBansheeCloakingField`; heroes/mercs inherit the base's id. Units with **no
toggle** (Reaper / Medivac / Predator) keep the permanent buff only — they're correctly absent
from the `ToggleCloakOn` calls (nothing to sync).

### Merc/hero reach
Heroes/mercs are added by their **own unit ids** in the galaxy calls (Nova, Tosh, DuskWing,
MercWraith, MercSeniorGhost) — a per-type `UnitBehaviorAdd` reaches only the type you name, so
each cloak hero/merc is listed explicitly. The free-cost genlib edits reach mercs/heroes that
**link the same cloak ability id** (e.g. Senior Ghost inherits `GhostCloak` via `parent="Ghost"`)
per the §0.2 rule. [STATIC]

## Reusable snippet (swap the ids)
```python
# Free cloak for a NEW cloak unit (genlib): add its toggle-ability id + drain-behavior id.
# RESOLVE FIRST: grep the ref catalogs for the unit's CAbilBehavior cloak id and its buff id.
CLOAK_ABILS     += ["<ToggleCloakAbilId>"]      # zeroes Cost[0].Vital[Energy]
CLOAK_BEHAVIORS += ["<CloakBuffId>"]            # zeroes Modification.VitalRegenArray[Energy]
```
```c
// Spawn cloaked + sync the toggle (galaxy, in libWoLU_OnPeriodic):
libWoLU_AddBehaviorToType(libWoLU_Player, "<UnitType>", "PersonalCloakingFree"); // or SpectreCloakingFree
libWoLU_ToggleCloakOn  (libWoLU_Player, "<UnitType>", "<ToggleCloakAbilId>");    // OMIT if no toggle ability
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **Don't try to autocast/auto-cloak a behavior-class ability.** Toggle cloaks are `CAbilBehavior`
  → they **cannot autocast at all** (no Blizzard data does it). "Spawn cloaked" is solved by the
  **buff** (`UnitBehaviorAdd`), not by autocast. ([02](02-no-op-traps.md) row "Autocast on a
  behavior-class ability".)
- **`Replace` freezes the unit.** Issue the On order with `c_orderQueueAddToFront`, never
  `c_orderQueueReplace` — Replace clobbers the move/attack queue and the unit stops dead.
- **No idle guard → interrupts everything.** Without `UnitOrderCount(u)==0` the periodic re-issues
  the toggle every 2 s and a busy unit never finishes an order.
- **A per-player edit can't add a behavior.** Spawn-cloaked must be `UnitBehaviorAdd` in galaxy;
  there is no scalar field for "has this behavior". (The cost/drain *zeroing* IS a scalar edit —
  that part stays in genlib.)
- **Wrong toggle id = a stuck "Cloak On".** The ability id in `ToggleCloakOn` must be the unit's
  *real* toggle (Spectre is `RogueGhostCloak`, not `SpectreCloak`). A wrong id is a silent no-op
  and the decloak button never appears.

## Verify
- **Static:** `python scripts/galaxy_lint.py` proves the lib (the `Order`/`UnitIssueOrder` calls,
  the forward-declared `libWoLU_ToggleCloakOn`) compiles — a compile error here = black map.
  `python scripts/audit.py` confirms the cited cloak ids resolve. **Does not prove** the unit is
  actually invisible or that the button flips. `[STATIC]`
- **In-game (Test Document / owner):** spawn a Ghost — it should appear **already cloaked**, lose
  **no energy** over time, and its card should read **"Cloak Off"** (a usable decloak), not "Cloak
  On". Toggle off → it's visible; the energy bar never moves. Confirm an **enemy** Ghost still
  drains/costs energy (rule 9). Mission: any with a Ghost/Banshee available. `[GAME]`
- **Editor (Previewer):** the Previewer renders the *static* catalog — it can't show a runtime
  `UnitBehaviorAdd` or the energy edit, so it can't confirm "spawns cloaked." Don't expect it here.

## Parked for bunch-verify
- `[GAME]` — Spawn a player Ghost: invisible on spawn, energy bar static while cloaked, card shows
  a working "Cloak Off" button (not a stuck "Cloak On"); enemy Ghost still pays/drains. (open-issues
  #11 + #7.)
