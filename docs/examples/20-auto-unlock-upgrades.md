# 20 — Auto-grant every armory upgrade at its unit's unlock mission (rule 2)

> Have every armory upgrade already applied the moment its unit is available — even *during* the
> unit's unlock mission — bypassing the campaign's "only after you've reached this tech group"
> gate, and extending each upgrade to the heroes the campaign's upgrade lists omit.

**Maps to (request):** design rule 2 ("armory upgrades auto-unlocked from each unit's unlock
mission"). [learnings.md §CampaignLib](../learnings.md). **Status:** [STATIC] done (the grant
loop + the CUpgrade extensions resolve and compile); the *applied value in game* is [GAME].

---

## Result
Open any mission and the player's units already have every armory upgrade that pertains to a
unit unlocked so far — weapon/armor levels, ability unlocks, the lot — with no armory visit
required, and the heroes (Swann, etc.) get the same boosts their base unit does.

## Mechanism
The campaign applies story tech via `libCamp_gf_ApplyCampaignTech(player)`.
`libCamp_gf_TS_BuyAllTech()` marks all 44 armory techs purchased — **but**
`TS_UpdateTechStates()` then *reverts* any tech whose tech-group (unit category) the story hasn't
introduced yet, so in a unit's own unlock mission nothing actually applies. The bypass: **loop
`libCamp_gv_tS_TechID[]` and grant each tech's rewards directly**, skipping the group gate —
`libCamp_gf_StoryTechAbilityCommand(...)` → `TechTreeAbilityAllow(...)` for ability unlocks, and
`libCamp_gf_StoryTechUpgrade(...)` → `libNtve_gf_SetUpgradeLevelForPlayer(...)` for level
upgrades ([learnings.md §CampaignLib](../learnings.md)). Mercs stay group-gated so rule 3 holds.

The second half is **reach**: a campaign `CUpgrade`'s `EffectArray` already lists the *merc*
units it should buff (e.g. CombatShield covers WarPig) but never the *heroes*. So an armory
upgrade buffs the base unit and merc but skips the hero. The fix is an **XML `CUpgrade` append**
— add the hero's unit id as a new `EffectArray` entry on the upgrade
(`src/mod/Base.SC2Data/GameData/UpgradeData.xml`). This is a static-XML append on an
upgrade-effect list (a pure definition extension), not a per-player runtime edit.

## Worked example (real, from this repo)
**The direct-grant loop** (bypasses `TS_UpdateTechStates`'s group revert):
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:158-181
void libWoLU_ForceGrantAllTechRewards (int p) {
    int i; int j; int techID;
    i = libCamp_gv_TSC_TECH_FIRST;
    while (i <= libCamp_gv_TSC_TECH_LAST) {
        techID = libCamp_gv_tS_TechID[i];
        j = 1;
        while (j <= libCamp_gv_tSC_TECH_AC_COUNT) {                 // ability unlocks
            if ((libCamp_gf_StoryTechAbilityCommand(techID, j) != null)) {
                TechTreeAbilityAllow(p, libCamp_gf_StoryTechAbilityCommand(techID, j), true);
            }
            j = j + 1;
        }
        j = 1;
        while (j <= libCamp_gv_tSC_TECH_UG_COUNT) {                 // level upgrades
            if ((libCamp_gf_StoryTechUpgrade(techID, j) != null)) {
                libNtve_gf_SetUpgradeLevelForPlayer(p, libCamp_gf_StoryTechUpgrade(techID, j), 1);
            }
            j = j + 1;
        }
        i = i + 1;
    }
}
```
It's called at `LibWoLUnbalanced.galaxy:126`, right after the comment that explains *why*
BuyAllTech alone is insufficient ("BuyAllTech is undone by the engine for tech groups the story
hasn't introduced yet … grant every armory tech's rewards directly, bypassing the group gate.
Mercs stay group-gated (rule 3)."). The CampaignLib functions it leans on are real:
`libCamp_gf_ApplyCampaignTech` (`CampaignLib.galaxy:6952`), `libCamp_gf_TS_BuyAllTech`
(`CampaignLib.galaxy:7953`), `libCamp_gf_TS_UpdateTechStates` (`CampaignLib.galaxy:7343`).

**The CUpgrade append that reaches a hero** — Kinetic Foam (`MarauderLifeBoost`, +life) reaches
Swann (the Marauder hero), which the campaign's list omits:
```xml
<!-- src/mod/Base.SC2Data/GameData/UpgradeData.xml:27-30 -->
<CUpgrade id="MarauderLifeBoost">
    <EffectArray Reference="Unit,Swann,LifeMax" Value="25"/>
    <EffectArray Reference="Unit,Swann,LifeStart" Value="25"/>
</CUpgrade>
```
The sibling extensions follow the same shape: `FirebatJuggernautPlating` adds Tychus variants'
armor (`UpgradeData.xml:20-23`), `JuggernautPlating` adds Swann's armor (`UpgradeData.xml:24-26`).
These `EffectArray` entries *append* to the vanilla upgrade's effect list (the base game already
lists the base unit + merc in `liberty.sc2campaign/UpgradeData.xml`), pulling the hero into the
same upgrade.

### Merc/hero reach
- **Mercs** are already in most campaign upgrade `EffectArray`s → covered by the direct-grant
  loop with no extra work.
- **Heroes** are the gap — each hero is added by a `CUpgrade` `EffectArray` append (above). Note
  the per-player **value** still flows through the campaign upgrade system, so this is the
  rule-9-safe path (the upgrade level is granted per player by `SetUpgradeLevelForPlayer`).

## Reusable snippet (swap the ids)
```xml
<!-- Extend a vanilla armory CUpgrade to also buff a hero/extra unit.
     RESOLVE FIRST: confirm <UPGRADE> and <UNIT> ids + the <FIELD> the upgrade modifies
     (xmlq.py get <UPGRADE> mods/_reference/.../UpgradeData.xml shows its EffectArray shape). -->
<CUpgrade id="<UPGRADE>">
    <EffectArray Reference="Unit,<HERO_UNIT>,<FIELD>" Value="<DELTA>"/>
    <!-- for HP-class fields, add both Max and Start (see [01]) -->
</CUpgrade>
```

## Variant — CHANGE an existing upgrade Value (not just append a hero)
The same-id `<CUpgrade>` override above *appends* new `Reference=` keys (heroes the vanilla
list omits). To instead **change an EXISTING entry's `Value`** (e.g. buff a rate the upgrade
already sets for the base units), re-state the entry with its **explicit `index=`** — an
indexed `EffectArray` entry overrides the same array slot in place (proven by libertystory's
`TwinLinkedFlameThrowers`: `<EffectArray index="0" Operation="Set" Reference="..." Value="0.5"/>`).
Index-*less* re-statements of an existing key are ambiguous (may append a fighting duplicate),
so for a Value change re-state the **complete** EffectArray with explicit indices `0..N` in
vanilla order — duplicates become impossible and your value wins. Real use:
`RegenerativeBioSteel`'s `LifeRegenRate` 0.6015 → 20 (`UpgradeData.xml`), plus 4 mechanical
player-exclusive units (Odin/MercThor/MercWraith/MercHellion) appended at the tail indices.
**Ordering caveat:** an auto-granted upgrade's `Operation="Set"` is the *last writer* of its
field (granted on the 1 s/10 s timers, after genlib's MapInit edits) — so a genlib per-player
edit of the same field is silently overwritten. Buff the **upgrade's EffectArray**, not the
per-player field, when a granted upgrade also sets it. (learnings.md §CampaignLib).

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`BuyAllTech` alone silently reverts** — `TS_UpdateTechStates` un-buys any tech whose group the
  story hasn't introduced, so during a unit's *own* unlock mission nothing applies. You MUST grant
  rewards directly per tech id. [STATIC; learnings]
- **Heroes are absent from campaign upgrade `EffectArray`s** — an upgrade that "works" still
  leaves the hero unbuffed until you append the hero's unit id. (Mercs are usually already listed.)
- **A `CUpgrade` `EffectArray` append is a static-XML definition extension**, not a runtime
  `CatalogFieldValueModify` — so it does NOT hit the indexed-array no-op trap (it's an XML array
  entry, applied at load, on a player-exclusive grant path).

## Verify
- **Static:** `python scripts/galaxy_lint.py` (the grant loop compiles); `python scripts/audit.py`
  CHECK3 (FAIL on a bad `<UNIT>`/`<UPGRADE>`/`<FIELD>` reference in the EffectArray). **Does not
  prove** the upgrade's effect is actually present on the unit in game. `[STATIC]`
- **In-game (owner):** start a unit's unlock mission *fresh*; confirm the unit (and its hero)
  already shows the armory upgrade (e.g. +armor on the unit panel, the unlocked ability button
  present) without visiting the armory. `[GAME]` — add to queue.

## Parked for bunch-verify
- `[GAME]` In a unit's unlock mission, the unit + its hero already carry every relevant armory
  upgrade (weapon/armor level, ability unlock) at mission start, no armory visit.
