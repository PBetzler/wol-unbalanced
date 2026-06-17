# 22 — A fatal hit rebuilds the unit AS ITSELF, free (Immortality Protocol)

> Make a player-only clone (an elite merc) survive a killing blow by morphing into a wreck that
> rebuilds **the merc**, not the base unit — with no gas cost and a single HP bar — via a
> three-link death-response chain.

**Maps to (request):** the Jotun (`MercThor`) Immortality Protocol (owner reversed the v0.3.7
strip and asked for it to *work*). open-issues v0.3.7 #9 / v0.3.9 #4a;
[implementation-patterns.md §7](../implementation-patterns.md);
[learnings.md §"A death-response RESURRECT chain has THREE links"](../learnings.md).
**Status:** [STATIC] chain wired + audit-clean; the death-response *effect* is **GAME-only**
(it can't be statically proven). Say so loudly.

---

## Result
When the Jotun takes a fatal hit it doesn't die — it collapses into a wreck and rebuilds **as a
Jotun** (not a base Thor), charging **no gas**, with a **single** HP bar. (Before the fix it
revived as a base Thor and showed "costs gas" + a double HP bar.)

## Mechanism
The Thor Immortality Protocol is a **three-link chain**, and a `parent="Thor"` clone inherits the
whole thing — so it revives *as a base Thor*. To revive **as the merc** you must clone all three
links with merc-targeted ids:

1. **The behavior** `ThorDontDie` — a `CBehaviorBuff` whose `DamageResponse Fatal=1
   Handled="<wreck>"` turns a lethal hit into a morph-into-wreck. `Handled=` points at a **unit
   id** (the wreck to become).
2. **The wreck unit** `ThorWreckage` — a `CUnit` (immobile wreck) whose `AbilArray[0]` is the
   rebuild morph.
3. **The morph** `ThorReborn` — a `CAbilMorph` whose `InfoArray Unit="<who-to-become>"` sets the
   rebuilt identity.

Two non-obvious facts that bite:
- **The gas cost lives on the REBUILT UNIT, not the morph.** Both `ThorReborn`/`ThorWreckage`
  morphs have no `<Cost>`; the "costs gas" tooltip + double HP bar came from the rebuilt unit's
  `CostResource` (base Thor = 300/200) being shown/charged during the rebuild. Fix: zero the merc
  unit's `CostResource` (a free calldown unit should be 0 anyway).
- **The wreck is a NEW unit id → it needs its OWN `CActorUnit`** or it renders as a sphere
  (audit CHECK1), with the morph-birth events re-bound to the new id.

Also: re-state the `DamageResponse` struct and the morph `InfoArray` **in full** on the clones —
a partial override on a struct/nested field doesn't reliably merge
([learnings.md §`removed="1"`](../learnings.md)).

## Worked example (real, from this repo)
**Link 1 — the behavior** (full struct re-stated; only `Handled` differs from vanilla):
```xml
<!-- src/mod/Base.SC2Data/GameData/BehaviorData.xml:114-122 -->
<CBehaviorBuff id="MercThorDontDie" parent="ThorDontDie">
    <DamageResponse>
        <Chance value="1"/>
        <Fatal value="1"/>
        <Handled value="MercThorWreckage"/>   <!-- merc wreck, not ThorWreckage -->
        <ModifyFraction value="0"/>
    </DamageResponse>
    <Requirements value="UseMechanicalRebirth"/>   <!-- auto-granted by the lib -->
</CBehaviorBuff>
```
**Link 2 — the wreck unit** (`AbilArray[0]` re-pointed to the merc morph; card button re-pointed):
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:576-581 -->
<CUnit id="MercThorWreckage" parent="ThorWreckage">
    <AbilArray index="0" Link="MercThorReborn"/>
    <CardLayouts index="0">
        <LayoutButtons index="0" Face="ImmortalityProtocol" Type="AbilCmd"
                       AbilCmd="MercThorReborn,Execute" Row="2" Column="0"/>
    </CardLayouts>
</CUnit>
```
**Link 3 — the morph** (`InfoArray Unit="MercThor"`; the nested `SectionArray` timing re-stated
verbatim because it doesn't merge under a partial override):
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:514-529 -->
<CAbilMorph id="MercThorReborn" parent="ThorReborn">
    <InfoArray Score="1" Unit="MercThor">     <!-- rebuild a Jotun, not a base Thor -->
        <SectionArray index="Abils"><DurationArray index="Delay" value="12"/></SectionArray>
        ... <!-- Actor / Collide / Stats SectionArrays re-stated, AbilData.xml:519-527 -->
    </InfoArray>
</CAbilMorph>  <!-- NO <Cost> — the gas charge is on the rebuilt unit, zeroed below -->
```
**Wire it onto the merc** — OVERRIDE the inherited `BehaviorArray index 1` (not the old `removed=1`
tombstone) and zero the rebuild cost:
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:559, 564-565 -->
<BehaviorArray index="1" Link="MercThorDontDie"/>   <!-- replaces inherited ThorDontDie -->
<CostResource index="Minerals" value="0"/>          <!-- kills the "costs gas" tooltip + 2nd HP bar -->
<CostResource index="Vespene" value="0"/>
```
**The wreck actor** (else sphere — CHECK1), morph-birth events re-bound to the new id:
```xml
<!-- src/mod/Base.SC2Data/GameData/ActorData.xml:91-94 -->
<CActorUnit id="MercThorWreckage" parent="ThorWreckage" unitName="MercThorWreckage">
    <Model value="Thor"/>
    <On Terms="AbilMorph.*.Finish; MorphTo MercThorWreckage" Send="$Birth 0 1.0 1.0"/>
    <On Terms="UnitBirth.MercThorWreckage.Suppressed" Send="$Stand PlayForever,NonLooping"/>
</CActorUnit>
```
**Why it's a parallel chain, not a reuse:** the campaign Thor carries `ThorDontDie` at
`BehaviorArray index 1` (`[0]=ScavengingSystemsMechDeath, [1]=ThorDontDie`), and the vanilla chain
runs `ThorDontDie → ThorWreckage (Handled) → ThorReborn (InfoArray Unit="Thor")` — every link
points back at base-Thor ids (`mods/_reference/campaigns/liberty.sc2campaign/BehaviorData.xml:2117`,
`UnitData.xml:13682`, `AbilData.xml:2700`). Inheriting it = reviving as a Thor with Thor's gas.
The three `Merc*` clones re-point each link at the merc, and the `BehaviorArray index 1` override
swaps the whole chain in.

### Merc/hero reach
This is a fully **merc-exclusive** chain — every id (`MercThorDontDie`/`MercThorWreckage`/
`MercThorReborn`) is player-only, so no flag gate is needed. The wreck unit clone is safe under
"never clone unit TYPES" via the elite-merc carve-out (the id never appears in a WoL map).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: read the base chain (xmlq.py/Grep) — confirm <BASE>DontDie's Handled=,
     <BASE>Wreckage's AbilArray[0], and <BASE>Reborn's InfoArray Unit=, plus any caster-bound
     cost in the morph (cf. [11] effect-set trap). Re-state structs/nested arrays IN FULL. -->
<CBehaviorBuff id="<M>DontDie" parent="<BASE>DontDie">
  <DamageResponse><Chance value="1"/><Fatal value="1"/><Handled value="<M>Wreckage"/><ModifyFraction value="0"/></DamageResponse>
  <Requirements value="UseMechanicalRebirth"/>
</CBehaviorBuff>
<CUnit id="<M>Wreckage" parent="<BASE>Wreckage"><AbilArray index="0" Link="<M>Reborn"/></CUnit>
<CAbilMorph id="<M>Reborn" parent="<BASE>Reborn"><InfoArray Score="1" Unit="<M>">...</InfoArray></CAbilMorph>
<!-- On the merc unit: BehaviorArray index <i> Link="<M>DontDie"; CostResource Minerals/Vespene 0 -->
<!-- In ActorData: a CActorUnit id="<M>Wreckage" with explicit Model + re-bound MorphTo/UnitBirth events -->
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`parent=` inheritance revives as the BASE unit** — every chain link points at base ids; you
  must clone all THREE and re-point them, not just the behavior.
- **The gas cost is on the REBUILT UNIT's `CostResource`, not the morph** (the morphs have no
  `<Cost>`). Zero the merc unit's `CostResource` to kill the "costs gas" tooltip + the double HP
  bar.
- **The new wreck id needs its OWN `CActorUnit`** with re-bound morph-birth events, or it renders
  as a sphere (CHECK1).
- **Re-state structs/nested arrays in full** — a partial override of `DamageResponse` or the
  morph `InfoArray` `SectionArray` timing doesn't reliably merge.
- **OVERRIDE the inherited `BehaviorArray` index with a `Link`, don't tombstone it** —
  `removed="1"` just deletes the protocol (the v0.3.7 strip); a `Link` swaps in the merc chain.
- **Check the rebuild chain for a caster-bound cost** before cloning (the `ReplenishNanoConstructor`
  trap, [11](11-effect-set-caster-trap.md)) — here the morphs are cost-free, so it's clean.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (FAIL) proves every `parent=`/`Handled=`/
  `InfoArray Unit=`/`AbilArray Link=` id resolves; CHECK1 (FAIL) proves `MercThorWreckage` has an
  actor (no sphere). **The static gate CANNOT prove the death-response fires, the identity is
  right, the gas is gone, or the HP bar is single** — death-response is observable only in play.
  `[STATIC]` for structure only.
- **In-game (owner) — REQUIRED, this recipe is heavy [GAME]:** kill a Jotun; confirm it collapses
  to a wreck, rebuilds **as a Jotun**, charges **no gas**, and shows a **single** HP bar.
  `[GAME]` — add to queue.

## Parked for bunch-verify
- `[GAME]` Kill a Jotun: it morphs to a wreck and rebuilds AS A JOTUN (not a base Thor), no gas
  cost, single HP bar. (Death-response cannot be statically proven — owner playtest is the only
  gate.)
