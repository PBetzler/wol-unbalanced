# 09 — Broaden what an ability can target (heal mechanical + air)

> Let an ability hit targets it normally refuses — e.g. the Medic heals **mechanical and air**,
> not just biological ground units.

**Maps to (request):** unit-table Tech Lab "Adaptive Medpacks" / open-issues **Bug 2** /
v0.3.7 #5 (#13). **Status:** [STATIC] — the mechanism is statically **complete** (traced below;
implementation-patterns §4). If Bug 2 persists in game it's **button-wiring/observation**, NOT a
missing filter — do **not** add a `SmartValidator`.

---

## Result
The Medic's heal (manual *and* autocast) targets a damaged Viking, Hellion, Marauder, Medivac —
any unit, mechanical or air — instead of only biological ground units.

## Mechanism
What an ability can target is its **`TargetFilters`** string. `TargetFilters` is a **STRING
field**, and per-player edits of string fields are **silent no-ops** — the genlib attempt to edit
it at runtime never took ([02](02-no-op-traps.md)). So you can't broaden targeting per player by
editing the value; you must **clone the ability** with the broadened string baked in.

The fix is a `parent="heal"` clone (`HealWoLU`) that **drops the `Ground,Biological` tokens** from
`TargetFilters`, plus an **explicit `Effect index="0" value="heal"`** so the clone runs the real
healer effect rather than re-defaulting to its own (nonexistent) id — the clone-Effect trap
([07](07-clone-flag-gate.md), CHECK4). The button is gated on `WoLUHaveFlag` like every clone
([07](07-clone-flag-gate.md)). (learnings.md; implementation-patterns §4.)

## Worked example (real, from this repo)
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:553-560 -->
<CAbilEffectTarget id="HealWoLU" parent="heal">
    <Effect index="0" value="heal"/>   <!-- explicit, or it re-defaults to "HealWoLU" (nonexistent) -->
    <TargetFilters value="Visible;Self,Enemy,Structure,Missile,UnderConstruction,Dead,Hidden,Invulnerable"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="MedicHeal" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
```
The vanilla gate, for contrast (reference catalog — confirmed):
```xml
<!-- mods/_reference/.../AbilData.xml  (vanilla "heal" ability) -->
<TargetFilters value="Ground,Biological,Visible;Self,Enemy,Air,Structure,Missile,UnderConstruction,Dead,Hidden,Invulnerable"/>
```
`HealWoLU` **drops `Ground,Biological`** from the require-list — that's the entire change. With
those gone, nothing in the chain re-imposes a bio/mech gate.

### Wiring it onto the Medic
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:319,328 -->
<AbilArray index="6" Link="HealWoLU"/>
<LayoutButtons index="6" AbilCmd="HealWoLU,Execute"/>   <!-- re-point the single visible heal button -->
```
(Stetmann gets its own re-point at UnitData.xml:337,348.)

### Why this is statically COMPLETE (the surprise — don't add more filters)
The brief's instinct is "add a SmartValidator". That would be chasing a non-bug. Every gate that
*could* still block mechanical was traced and **none survives the clone** (implementation-patterns
§4, contradiction #1):
1. **`HealWoLU.TargetFilters`** drops `Ground,Biological` — no bio/ground requirement remains.
   `[STATIC]`
2. The **`heal` effect** (`CEffectCreateHealer`) validators are
   `noMarkers/NotWarpingIn/HiddenCompareAB/BA/NotVortexd` — **none gate by attribute**.
   `[STATIC]`
3. The inherited **`SmartValidatorArray="healSmartTargetFilters"`** is
   `CValidatorUnitFilters Filters="-;Enemy"` — excludes **enemies only**, no attribute gate.
   `[STATIC]`
4. The inherited **`AutoCastFilters="Visible;Neutral,Enemy"`** excludes neutral/enemy only — no
   attribute gate. `[STATIC]`

**Conclusion:** `HealWoLU` SHOULD heal mechanical + air, manual AND autocast. If Bug 2 persists,
the cause is the **button wiring / observation**, not the filters — start by confirming the
Medic's **visible** heal button cell is the one re-pointed to `HealWoLU,Execute`
(implementation-patterns §4). Do **not** add a `SmartValidatorArray` override.

### Merc/hero reach
Skibi's Angels = `MercMedic parent="Medic"` inherits `HealWoLU` via the `AbilArray` (kind B —
[18](18-elite-merc-clone.md)). Stetmann is a distinct unit → gets its own re-point (above).
`[STATIC]`

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: get the vanilla ability's TargetFilters and its Effect id
     (python scripts/xmlq.py get <VANILLA_ABIL> mods/_reference/.../AbilData.xml).
     Identify the token(s) to drop (Biological / Ground / Air / etc.). -->
<CAbilEffectTarget id="<ABIL>WoLU" parent="<VANILLA_ABIL>">
    <Effect index="0" value="<VANILLA_EFFECT>"/>            <!-- explicit, always -->
    <TargetFilters value="<vanilla filters MINUS the tokens you want to allow>"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="<Face>" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
<!-- then re-point the unit's visible button: <LayoutButtons index="<cell>" AbilCmd="<ABIL>WoLU,Execute"/> -->
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **Per-player edit of `TargetFilters` is a string no-op** — that's why this is a clone, not a
  runtime edit.
- **Missing `<Effect>` re-defaults** to the clone's own id → heals nothing (CHECK4 FAIL). Always
  set it explicitly even on a `parent=` clone.
- **Don't over-fix.** The `TargetFilters` token-drop is the *complete* mechanism — the effect's
  validators, the smart-validator, and the autocast filter do **not** gate by attribute. Adding a
  `SmartValidatorArray` to "also allow mechanical" is chasing a non-bug.
- **Re-point the *visible* button.** If the merged card's visible heal cell isn't the one you
  re-pointed, the new targeting never reaches the player (most-likely cause of a persisting Bug 2)
  — verify with the card-merge sim ([26](26-command-card-edits.md)).

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (`parent=heal` resolves), CHECK4 (explicit
  `<Effect>`), CHECK5 (the heal button cell is an action `AbilCmd` on the merged card). **Does not
  prove** the heal lands on a mech in game. `[STATIC]`
- **In-game (owner / Test Document):** damage a Viking/Hellion, select a Medic, manual-heal it —
  the heal applies; then leave it idle near the damaged mech and confirm **autocast** fires.
  Mission with a Medic + mech (e.g. a mid-campaign Terran mission). `[GAME]`
- **Editor (Previewer):** the re-pointed heal button shows on the Medic's merged card (static).
  `[EDITOR]`

## Parked for bunch-verify
- `[GAME]` — Medic manually heals a damaged **mechanical** unit (Viking/Hellion); autocast heals
  it when idle nearby. (Confirm first via card-merge sim that the visible heal cell is the
  re-pointed one — if not, that's the bug, not the filters.)
- `[EDITOR]` — the Medic/Stetmann merged card shows a single heal button pointing at
  `HealWoLU,Execute`.
