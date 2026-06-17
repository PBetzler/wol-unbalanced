# 14 — Enlarge splash radius (bigger AoE)

> Give a weapon a larger area-of-effect — **player-only** — when the splash radius lives in an
> indexed array that can't be edited per-player.

**Maps to (request):** Thor ground splash "doubled" (0.8/1.25 → 1.6/2.5) and the Jotun/Thor AA
splash matched to the ground radius — open-issues v0.3.7 #8 (`docs/open-issues.md:182` "#8 Jotun
AA splash too small"). Cross-refs [implementation-patterns.md §2 + §5](../implementation-patterns.md),
[13](13-flatten-attribute-bonus.md), [15](15-friendly-fire-safety.md). **Status:** [STATIC] done ·
[GAME] parked.

---

## Result
The player's Thor ground cannon throws a wider blast (full-damage radius 1.6, half-damage 2.5,
where vanilla single-target / small splash was far tighter), and the Thor AA rocket gains the same
1.6/2.5 splash. Enemies keep the vanilla footprint (rule 9).

## Mechanism
A damage effect's splash geometry is its `AreaArray[]` (each entry = `Radius` + `Fraction`).
`AreaArray` is an **indexed array** → a per-player `CatalogFieldValueModify` on it is a **silent
no-op** (same class as `Options[]` [12] and `AttributeBonus[...]` [13]; cross-ref
[02](02-no-op-traps.md)). You can't grow splash per-player at runtime.

The working path is the **Shaped-Blast clone**: override the weapon's `Effect` to a `CEffectSet`
with two validator-gated branches — a buffed branch (`WoLUHasFlag`) carrying the larger
`AreaArray` (as static-XML literals), and a vanilla branch (`WoLUNoFlag`) untouched for enemies.
This is the [07](07-clone-flag-gate.md) backbone applied to splash, exactly like [13]. Note the
Thor ground case **adds** splash where vanilla had none: vanilla `ThorsHammerDamage` is a plain
`Amount=45` single-target hit (`mods/_reference/mods/liberty.sc2mod/EffectData.xml:2253-2258`) —
the entire `Kind=Splash` + `AreaArray` lives in the clone.

## Worked example (real, from this repo)

### Thor GROUND splash — 1.6/2.5 in the buffed branch
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:43-60 -->
<CEffectSet id="ThorsHammerWoLUSet">                       <!-- weapon's Effect points here -->
    <EffectArray value="ThorsHammerDamageVanillaWoLU"/>     <!-- enemies: vanilla -->
    <EffectArray value="ThorsHammerDamageWoLU"/>            <!-- player: buffed -->
</CEffectSet>
<CEffectDamage id="ThorsHammerDamageVanillaWoLU" parent="ThorsHammerDamage">
    <ValidatorArray value="WoLUNoFlag"/>
</CEffectDamage>
<CEffectDamage id="ThorsHammerDamageWoLU" parent="ThorsHammerDamage">
    <ValidatorArray value="WoLUHasFlag"/>
    <Kind value="Splash"/>
    <KindSplash value="Splash"/>
    <SearchFilters value="Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AreaArray Radius="1.6" Fraction="1"/>      <!-- full damage out to 1.6 -->
    <AreaArray Radius="2.5" Fraction="0.5"/>    <!-- half damage out to 2.5 -->
</CEffectDamage>
```
Wired via the weapon: `<CWeaponLegacy id="ThorsHammer"><Effect value="ThorsHammerWoLUSet"/></CWeaponLegacy>`
(`src/mod/Base.SC2Data/GameData/WeaponData.xml:11-12`). The weapon id is kept (not cloned) so the
attack animation `WeaponStart.ThorsHammer` still fires ([24](24-clone-visuals.md)).

### Thor AA splash — matched 1.6/2.5 (open-issues #8)
The AA rocket impacts `JavelinMissileLaunchersDamage`, whose vanilla `AreaArray Radius="0.5"`
(`mods/_reference/mods/liberty.sc2mod/EffectData.xml:2280`) was too small. Same clone pattern, off
the AA missile's `ImpactEffect`:
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:89-96 (buffed AA branch) -->
<CEffectDamage id="JavelinMissileLaunchersDamageBuffedWoLU" parent="JavelinMissileLaunchersDamage">
    <ValidatorArray value="WoLUHasFlag"/>
    <Amount value="35"/>
    <AttributeBonus index="Light" value="0"/>
    <SearchFilters value="Air;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AreaArray Radius="1.6" Fraction="1"/>
    <AreaArray Radius="2.5" Fraction="0.5"/>
</CEffectDamage>
```
Reached because we override `<CEffectLaunchMissile id="JavelinMissileLaunchersLM"><ImpactEffect
value="JavelinMissileLaunchersDamageWoLUSet"/></CEffectLaunchMissile>` (`EffectData.xml:74-76`).
(This branch also flattens the light bonus — that's [13]. The two recipes share the same clone.)

### Merc/hero reach
Both fixes are at the **shared effect-set level** off the shared weapon ids, so `MercThor`
(`parent="Thor"`, no weapon override) inherits them automatically
([implementation-patterns.md §5](../implementation-patterns.md)). Odin (hero) ground splash is
wired separately; see the genlib/XML Odin handling.

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: the vanilla damage effect <DMG_ID> the weapon impacts (xmlq.py get ...).
     Override the weapon's Effect (or the missile's ImpactEffect) to <DMG_ID>WoLUSet. -->
<CEffectSet id="<DMG_ID>WoLUSet">
    <EffectArray value="<DMG_ID>VanillaWoLU"/>
    <EffectArray value="<DMG_ID>WoLU"/>
</CEffectSet>
<CEffectDamage id="<DMG_ID>VanillaWoLU" parent="<DMG_ID>"><ValidatorArray value="WoLUNoFlag"/></CEffectDamage>
<CEffectDamage id="<DMG_ID>WoLU" parent="<DMG_ID>">
    <ValidatorArray value="WoLUHasFlag"/>
    <Kind value="Splash"/>
    <KindSplash value="Splash"/>
    <SearchFilters value="<Ground|Air|->;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AreaArray Radius="<R1>" Fraction="1"/>
    <AreaArray Radius="<R2>" Fraction="0.5"/>
</CEffectDamage>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`AreaArray[]` per-player edit = silent no-op** (indexed array). Must go in a static clone.
- **New splash friendly-fires by default** — set `SearchFilters` (the Crucio enemy-only pattern)
  or your bigger blast hits your own army. See [15](15-friendly-fire-safety.md) for the exact
  plane semantics (`Ground` / `Air` / `-`).
- **Don't clone the weapon** — keep the vanilla weapon id and override only its `Effect`, or you
  lose `WeaponStart.<id>` animations ([24](24-clone-visuals.md)).
- **Forgetting the `WoLUNoFlag` vanilla branch** leaks the bigger splash to enemies (static XML is
  global).

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (ids/parents resolve), CHECK4 (clones have a real
  effect). **Does not prove** the splash radius is visibly larger or lands on multiple units.
  `[STATIC]`
- **In-game (Test Document / owner):** clump several ground units; one Thor ground shot should
  damage a wider ring (full to ~1.6, half to ~2.5). For AA, clump air units and confirm the rocket
  splashes them. Mission: any with a Thor/Jotun. `[GAME]` — parked.
- **Editor (Previewer):** static catalog shows the clone exists/merges; it can't render the blast.
  `[EDITOR]` only for confirming the clone is in the merged data.

## Parked for bunch-verify
- `[GAME]` — Thor ground shot splashes a wider ring (full ≤1.6, half ≤2.5) onto clumped ground
  units; enemy Thor splash unchanged.
- `[GAME]` — Thor/Jotun AA rocket splashes clumped air units at the matched 1.6/2.5 radius
  (open-issues #8, `docs/open-issues.md:182`).
</content>
