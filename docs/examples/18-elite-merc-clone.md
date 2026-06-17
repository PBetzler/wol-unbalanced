# 18 — Define a player-only buffed CLONE of a base unit (an elite merc)

> Add a brand-new, player-exclusive unit that is a buffed copy of an existing base unit —
> with the right name, a real portrait, a real model, and no sphere — by cloning with
> `parent=` in static XML.

**Maps to (request):** the 6 "elite merc" calldowns (Skibi's Angels / Death Heads / Condor /
Jotun / Winged Nightmares / Senior Ghost) — owner request, in spirit from the Moebius bonus-merc
pack. **Status:** [STATIC] done (ids resolve, actors exist, audit-clean); the portrait/model
*render* is [EDITOR]/[GAME] parked.

---

## Result
A new unit id (e.g. `MercThor`, "Jotun") that exists **only for the player**: it has the base
unit's model + portrait, its own buffed stats (HP/armor/shields), its own display name, and is
summoned via the Merc Compound. It never appears in any enemy roster and never trips a mission
unit-type check.

## Mechanism
The 6 elite mercs are `parent="<base unit>"` **clones** defined in static XML
(`src/mod/Base.SC2Data/GameData/UnitData.xml:498-618`). A `parent=` clone inherits the base
unit's entire static definition at load — its `WeaponArray`, `AbilArray`, `BehaviorArray`,
`CardLayouts` — then the clone body overrides only what changes (stats, name). This is the
**only** way to add a structurally-new player unit: `CatalogFieldValueModify` can never *create*
a unit, and static XML is global so cloning is the rule-9-safe path (the clone is summoned only
by the player). See [implementation-patterns.md §0.1-B](../implementation-patterns.md) and
[learnings.md §"Never clone unit types"](../learnings.md).

Three pieces are mandatory or the clone is broken in a way the static gate catches:
1. **An explicit `<Name>`** — a `parent=` clone otherwise inherits the *parent's* name, so the
   Jotun would read "Thor". (open-issue Resolved, v0.2.4 parent-name bug.)
2. **A real model + a `##unitName##Portrait` token, set on a `CActorUnit` in ActorData** — NOT
   on the `CUnit`. A new unit id with no `CActorUnit` renders as a **grey sphere** (audit
   CHECK1; the v0.2.1 sphere bug). `PortraitModel` is an **actor** field — it does not exist on
   vanilla `CUnit` entries either (CHECK6).
3. **The "never clone unit TYPES" carve-out** — cloning a unit type normally breaks mission
   scripts ("all your Marines are dead", drop-pod spawns). Elite-merc ids never appear in any WoL
   map, so cloning them is safe ([learnings.md](../learnings.md)).

## Worked example (real, from this repo)
**The Jotun = `MercThor`**, a buffed Thor clone:
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:538-548 -->
<CUnit id="MercThor" parent="Thor">
    <Name value="Unit/Name/MercThor"/>      <!-- (1) explicit name; else inherits "Thor" -->
    <LifeMax value="500"/>
    <LifeStart value="500"/>
    <LifeArmor value="2"/>
    <ShieldsMax value="100"/>                <!-- elite-merc shields (merc-only) -->
    <ShieldsStart value="100"/>
    <ShieldArmorName value="Unit/ShieldArmorName/WoLUDefensiveMatrix"/>
    <LifeArmorName value="Unit/LifeArmorName/TerranVehiclePlating"/>
    ...
</CUnit>
```
The model + portrait live on a **separate `CActorUnit`** in ActorData, NOT on the `CUnit`:
```xml
<!-- src/mod/Base.SC2Data/GameData/ActorData.xml:55-57 -->
<CActorUnit id="MercThor" parent="GenericUnitBase" unitName="MercThor">
    <Model value="Thor"/>                    <!-- (2a) explicit model — else sphere -->
    <PortraitModel value="ThorPortrait"/>    <!-- (2b) base unit's portrait token (CHECK6) -->
    ... <!-- Thor's weapon-anim events copied verbatim (ActorData.xml:58-71) so the
            inherited ThorsHammer/JavelinMissileLaunchers attacks animate, since a bare
            GenericUnitBase actor only has the generic attack bracket -->
</CActorUnit>
```
Walk through *why each piece is there*:
- `parent="Thor"` gives the clone Thor's weapons, abilities, behaviors, and card for free —
  that's the whole value of the clone (no re-specifying the kit).
- `<Name value="Unit/Name/MercThor"/>` points at a GameStrings key (the display name "Jotun");
  without it the merc reads "Thor". The `Unit/Name/MercThor` key lives in
  `src/mod/enUS.SC2Data/LocalizedData/GameStrings.txt`.
- The stat overrides (`LifeMax=500`, shields, armor) are **static XML literals on a
  player-exclusive unit** — safe there because no enemy ever fields a `MercThor`.
- `<Model value="Thor"/>` + `<PortraitModel value="ThorPortrait"/>` on the **actor** make it look
  like a Thor and show the Thor portrait. The convention (ActorData.xml:33-35 comment) is that the
  engine loads each unit's portrait via the `##unitName##Portrait` token (`Medic` → `MedicPortrait`,
  `Thor` → `ThorPortrait`); we just name the base unit's token explicitly. Senior Ghost wears the
  variant `GhostAlternate` model with the base `GhostPortrait` (ActorData.xml:79-81).

The other 5 mercs follow the identical shape: `MercMedic`/`MercReaper`/`MercHellion` (infantry,
`TerranInfantryArmor`), `MercWraith` (ship, `TerranShipPlating`), `MercSeniorGhost`
(infantry, +damage behavior) — `UnitData.xml:498-618`; actors `ActorData.xml:36-82`.

### Merc/hero reach (critical — read [01 §reach](01-per-player-scalar-stat-edit.md))
A `parent=` clone inherits the base's **shared sub-ids** (the *same* weapon/ability/behavior
*ids*). So a per-player edit on a **shared id** reaches the clone automatically:
- `MercThor` inherits Thor's `ThorsHammer` weapon id → the per-player windup/Period edits on
  `ThorsHammer` ([03](03-attack-windup-cap.md)) reach the Jotun for free
  ([implementation-patterns.md §0.1-B](../implementation-patterns.md)).
- But a per-**unit-id** edit on `Thor` (e.g. `("Unit","Thor","Sight","2","Add")`) does **NOT**
  reach `MercThor` — it's a different unit id. Elite-merc per-unit stats must be set on the
  `Merc*` id itself (the static literals above, or a genlib edit on `MercSeniorGhost`). This is
  the exact opposite of the standard-merc case ([06](06-merc-hero-parity.md)), which shares
  *nothing* by inheritance.

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: confirm <BASE> exists (xmlq.py get <BASE> .../UnitData.xml) and find its
     portrait token = "<BASE>Portrait". Add a Unit/Name/<NEW> GameStrings key. -->
<!-- UnitData.xml: the unit clone -->
<CUnit id="<NEW>" parent="<BASE>">
    <Name value="Unit/Name/<NEW>"/>           <!-- MANDATORY: else inherits parent's name -->
    <LifeMax value="<HP>"/><LifeStart value="<HP>"/>
    <!-- + any merc-only shields/armor; both *Name fields are string KEYS, see [25] -->
</CUnit>
<!-- ActorData.xml: the actor (else the new id renders as a sphere) -->
<CActorUnit id="<NEW>" parent="GenericUnitBase" unitName="<NEW>">
    <Model value="<BASE-or-variant-model>"/>
    <PortraitModel value="<BASE>Portrait"/>
</CActorUnit>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **No `<Name>` ⇒ the clone inherits the parent's display name** (Jotun read "Thor"). [STATIC,
  v0.2.4]
- **No `CActorUnit` ⇒ grey sphere.** `audit.py` CHECK1 **FAILs** on a clone unit with no proper
  actor. [STATIC, v0.2.1 sphere bug]
- **`PortraitModel` belongs on the `CActorUnit`, not the `CUnit`** — our `CUnit` clones carry
  none (zero matches), and neither do vanilla units. Putting it on the unit does nothing.
- **A bare `GenericUnitBase` actor loses weapon-specific attack animations** — the Thor's ground
  attack binds to `WeaponStart.ThorsHammer.AttackStart`; the actor must copy those events
  verbatim (ActorData.xml:58-71) or the model plays the wrong pose / never muzzles. (Visuals bind
  to ids — [24](24-clone-visuals.md).)
- **Don't blanket-add decorative passive cards** to the clone — it already inherits the base's
  real cards via `parent=`; a vehicle-hull face on the Medic is nonsense ([learnings.md](../learnings.md);
  audit #3-class WARN).

## Verify
- **Static:** `python scripts/audit.py` — CHECK1 (FAIL) proves the actor exists (no sphere);
  CHECK3 (FAIL) proves `parent=` resolves; CHECK6 promotes the `PortraitModel` token to
  `portrait-ok` if a vanilla actor references the same token; CHECK7 (WARN) proves the armor
  keys resolve. **Does not prove** the model/portrait actually *render*. `[STATIC]`
- **Editor (Previewer):** open the Data module, select `MercThor`, Preview Object → switch aspect
  to **Portrait**. Expected: the Thor model + Thor portrait (not a heart, not a sphere), name
  "Jotun". `[EDITOR]` — add to queue.
- **In-game (owner):** summon the merc from the Merc Compound; confirm model, portrait, name, and
  the buffed HP/shields read on the unit panel. `[GAME]` — add to queue.

## Parked for bunch-verify
- `[EDITOR]` Previewer: each of the 6 elite mercs (`MercMedic`/`MercReaper`/`MercHellion`/
  `MercThor`/`MercWraith`/`MercSeniorGhost`) renders its base model + portrait (not a
  sphere/heart); display name correct.
- `[GAME]` Summon each elite merc; confirm model/portrait/name and buffed stats in mission.
