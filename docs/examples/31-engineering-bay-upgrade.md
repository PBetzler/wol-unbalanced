# 31 — Engineering Bay weapon/armor upgrades (30 s, propagated to all unit types)

> Cut the Engineering Bay's weapon/armor research to 30 s each, and make completing an **infantry**
> level also grant the **vehicle** and **ship** level — so one research click upgrades your whole
> army. **HONESTY:** read "What's shipped vs. what's only designed" before citing this — the
> owner's full request is **not** fully built.

**Maps to (request):** unit-table "Weapon/armor levels" Comment — *"Make one upgrade for attack
AND defense on each tier at the engineering bay. The upgrade should work as attack upgrade or
defense upgrade for all infantry, vehicles and ships. It should keep the infantry costs and take
30 seconds each."* (`unit-table.md:102`). **Status:** PARTIAL — see the honesty section.
implementation-patterns §1 (per-player scalar edit); learnings §"CampaignLib internals".

---

## What's shipped vs. what's only designed (read this first)

| Owner asked for | Built? | How / why-not |
|---|---|---|
| **30 s each** | ✅ SHIPPED | Per-player `InfoArray[Research3-9].Time = 30` (`genlib.py:514-516`). |
| **Works for infantry, vehicles AND ships** | ✅ SHIPPED (via a different mechanism) | A **galaxy** propagation: completing infantry weapon/armor level N grants the vehicle + ship level N (`libWoLU_SyncWeaponArmorLevels`, `LibWoLUnbalanced.galaxy:228-252`). Not "one upgrade *targets* all three" — it's "infantry upgrade *cascades* to all three". |
| **Keep the infantry costs** | ✅ (trivially) | Research3-9 **are** the infantry weapon/armor researches; their `Resource` costs are unedited, so they already cost the infantry amounts. |
| **ONE upgrade combining ATTACK and DEFENSE per tier** | ❌ **NOT BUILT** `[ASSUMPTION]`/design | Weapons and armor remain **separate** research buttons: Research3/4/5 = `TerranInfantryWeaponsLevel1/2/3`, Research7/8/9 = `TerranInfantryArmorsLevel1/2/3` (`liberty.sc2mod/AbilData.xml:1699-1734`). No catalog entry merges a weapon level + an armor level into a single research, so the player still clicks weapons and armor separately. The "one upgrade for attack **and** defense" wording is **unmet**. |

Net: the **30 s** cut and the **all-three-unit-types** cascade are real and shipped; the
**single-combined-attack+defense-button** is **design-only**. Do not call this recipe "fully done".

## Result (as actually shipped)
The player's Engineering Bay researches each infantry weapon/armor level in **30 s** (vanilla
160/190/220), and the moment an infantry **weapon** or **armor** level completes, the matching
**vehicle** and **ship** level is also granted — so the player upgrades all three unit classes by
researching one (still costs the vanilla infantry minerals/gas).

## Mechanism

**(a) 30 s time** — `EngineeringBayResearch` is a `CAbilResearch` whose `InfoArray[ResearchN]`
entries each carry a `Time`. `InfoArray[<idx>].Time` is an **indexed *scalar*** (like
`InfoArray[Train6].Time`, [01](01-per-player-scalar-stat-edit.md)) → a per-player
`CatalogFieldValueModify` **applies**. Set it to 30 on the weapon levels (Research3/4/5) and armor
levels (Research7/8/9). (Research6 = Neosteel Frame, Research1/2 = HiSec/Building Armor — left
alone.)

**(b) all-three-types cascade** — this can't be data (`CatalogFieldValueModify` can't add a new
"grants vehicle+ship too" effect to a research), so it's done in **galaxy**: a periodic checks
whether the player completed infantry weapon/armor level N and, if so, grants the vehicle and ship
equivalents via `TechTreeUpgradeAddLevel`. The Armory's own (now-redundant) weapon/armor research
commands are disabled (`libWoLU_DisableArmoryResearch`).

## Worked example (real, from this repo)

### (a) The 30 s time cut (generated per-player)
```python
# scripts/genlib.py:514-516
lines.append("    // --- Engineering Bay: combined upgrades research in 30 s (weapon/armor levels) ---")
for idx in ("Research3", "Research4", "Research5", "Research7", "Research8", "Research9"):
    lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "EngineeringBayResearch", "InfoArray[{idx}].Time", p, "30", c_upgradeOperationSet);')
```
Generated (`LibWoLUnbalancedGen.galaxy:357-362`):
```galaxy
CatalogFieldValueModify(c_gameCatalogAbil, "EngineeringBayResearch", "InfoArray[Research3].Time", p, "30", c_upgradeOperationSet);
// ... Research4, Research5, Research7, Research8, Research9 ...
```
What each index *is* (base liberty, `liberty.sc2mod/AbilData.xml:1699-1734`):
`Research3/4/5 → TerranInfantryWeaponsLevel1/2/3` (orig Time 160/190/220);
`Research7/8/9 → TerranInfantryArmorsLevel1/2/3` (orig 160/190/220). So this only edits the
**infantry** weapon/armor researches — confirming "keep the infantry costs" is automatic (costs
untouched) and "attack + defense" stay **separate** entries (the design gap).

### (b) The galaxy cascade to vehicle + ship
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:228-252  (per level n = 1..3)
if (TechTreeUpgradeCount(p, "TerranInfantryWeaponsLevel" + lvl, c_techCountCompleteOnly) > 0) {
    if (TechTreeUpgradeCount(p, "TerranVehicleWeaponsLevel" + lvl, c_techCountCompleteOnly) == 0) {
        TechTreeUpgradeAddLevel(p, "TerranVehicleWeaponsLevel" + lvl, 1);
    }
    if (TechTreeUpgradeCount(p, "TerranShipWeaponsLevel" + lvl, c_techCountCompleteOnly) == 0) {
        TechTreeUpgradeAddLevel(p, "TerranShipWeaponsLevel" + lvl, 1);
    }
}
// ... identical block for TerranInfantryArmorsLevel -> Vehicle/Ship Armors ...
```
Run from both the 2 s periodic and the grant pass (`LibWoLUnbalanced.galaxy:105,355`). The Armory's
redundant duplicates are disabled (`libWoLU_DisableArmoryResearch`, `LibWoLUnbalanced.galaxy:254-261`).

### Merc/hero reach
Weapon/armor *levels* are player-global upgrades (granted to the player, not a unit id), so every
player unit that scales with them — infantry, vehicles, ships, mercs, heroes — benefits
automatically. No per-unit mirroring needed.

## Reusable snippet (swap the ids)
```python
# 30 s research time — indexed scalar, per-player (genlib stat-emit):
#   CatalogFieldValueModify(c_gameCatalogAbil, "<ResearchAbil>", "InfoArray[<ResearchIdx>].Time", p, "30", c_upgradeOperationSet)
# Cascade one completed upgrade to siblings (galaxy, in a periodic):
if (TechTreeUpgradeCount(p, "<SrcUpgrade>", c_techCountCompleteOnly) > 0
    && TechTreeUpgradeCount(p, "<DstUpgrade>", c_techCountCompleteOnly) == 0) {
    TechTreeUpgradeAddLevel(p, "<DstUpgrade>", 1);
}
```
> To actually build the **combined attack+defense single research** the owner asked for: define a
> new `CUpgrade`/research entry whose effect grants BOTH the weapon and armor level (and let the
> cascade above fan it to all three unit types). That entry does **not** exist yet — design only.

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **`InfoArray[idx].Time` is an indexed *scalar* → it applies**; but `InfoArray[idx].Upgrade` (a
  **link**) or adding a new `InfoArray` entry would be a no-op — you can't merge weapon+armor into
  one research via a per-player edit. That needs a new static `CUpgrade`/research definition.
- **Don't confuse "cascade" with "combined".** What's shipped grants the vehicle/ship levels when
  infantry completes — it does **not** make one button research attack+defense together.
- **Static XML edit of the research time would be global** (enemy Eng Bays too) — that's why the
  time cut is a per-player runtime edit ([01](01-per-player-scalar-stat-edit.md)).

## Verify
- **Static:** `python scripts/audit.py` (CHECK3 — `EngineeringBayResearch` resolves) +
  `galaxy_lint.py` (the cascade compiles). **Does not prove** the time shows 30 s, the cascade
  fired, or — crucially — that the unbuilt combined-upgrade exists. `[STATIC]`
- **In-game (Test Document / owner):** research an infantry weapon level — bar reads ~30 s; on
  completion, confirm the player's **vehicles and ships** also show +1 weapons; repeat for armor.
  Note that attack and defense are still **two** separate researches (expected — the combined
  single-upgrade is not built). A mission with an Engineering Bay. `[GAME]`.
- **Editor (Previewer):** the static merged `EngineeringBayResearch` shows the (static) Times; it
  cannot show the per-player 30 s edit nor the runtime cascade. `[EDITOR]` limited.

## Parked for bunch-verify
- `[GAME]` — Eng Bay infantry weapon/armor research completes in ~30 s; completing it grants the
  matching **vehicle + ship** level to the player (cascade).
- `[GAME]` / design — confirm with the owner whether the **separate** attack/defense researches are
  acceptable, or whether the **combined single attack+defense upgrade** still needs building (NOT
  shipped — a new `CUpgrade`/research entry).
