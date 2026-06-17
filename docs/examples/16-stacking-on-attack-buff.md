# 16 — Stacking on-attack buff (+X% per attack up to a cap) — data-only, no galaxy

> "Every time this unit attacks, it gets +X% attack speed, stacking up to N" — the long-blocked
> "on each attack" trigger, solved entirely in data (no galaxy script).

**Maps to (request):** Wraith "Trigger Override" (AP upgrade) — BACKLOG WP-C
(`docs/BACKLOG.md:19` "Wraith: Advanced Laser Technology + Trigger Override — SHIPPED v0.3.1").
Cross-refs [07](07-clone-flag-gate.md) (flag gate), [08](08-autocast-ability.md) (effect-apply
shape), learnings §"Damage reduction" (DamageResponse/Modification schema). **Status:** [STATIC]
done · [GAME] parked (owner confirms the stack builds + caps).

---

## Result
Each shot the player's Wraith fires applies a hidden buff stack that raises its attack speed by
10%, stacking to 10 (≈2.6× fire rate at cap — funnily overpowered). The stack decays after 4 s of
not attacking. Enemy Wraiths are unaffected (rule 9). No galaxy/trigger code — it's all data.

## Mechanism
The "fire a trigger on every attack" problem is solved by hanging an **apply-behavior effect off
the weapon's own fire**: redirect the weapon's `Effect` to a `CEffectSet` that runs the original
damage delivery **plus** a `CEffectApplyBehavior` that adds one stack of a stacking buff to the
firing unit. Because the weapon fires the set on every shot, the buff is applied on every shot —
no galaxy needed.

The buff is a `CBehaviorBuff` with `MaxStackCount` (the cap), a short `Duration` (the decay
window, refreshed each application), and a per-stack `Modification` (here `AttackSpeedMultiplier`).
This is the **Moebius BarrelAccelerator pattern** — verified reference:
`mods/_reference/moebius/Base.SC2Data/GameData/BehaviorData.xml:169-176` (a stacking
`AttackSpeedMultiplier=1.1`, `MaxStackCount=5`, `Duration=3` buff). Player isolation is at the
effect level: the apply-effect carries `ValidatorArray="WoLUHasFlag"`, so enemy Wraiths fire the
same weapon set but the apply **no-ops** for them ([07](07-clone-flag-gate.md) gating; cross-ref
[15](15-friendly-fire-safety.md) for the sibling-validator idea, here used as a single gate rather
than a vanilla/buffed split).

## Worked example (real, from this repo)

### 1. The stacking buff (the "+10% per attack, cap 10, decay 4 s")
```xml
<!-- src/mod/Base.SC2Data/GameData/BehaviorData.xml:93-100 -->
<CBehaviorBuff id="WoLUWraithTriggerOverride">
    <Alignment value="Positive"/>
    <InfoFlags index="Hidden" value="1"/>
    <EditorCategories value="Race:Terran,AbilityorEffectType:Units"/>
    <MaxStackCount value="10"/>                         <!-- cap = 10 stacks -->
    <Duration value="4"/>                               <!-- decays 4 s after the last attack -->
    <Modification AttackSpeedMultiplier="1.1"/>         <!-- +10% attack speed per stack -->
</CBehaviorBuff>
```
`AttackSpeedMultiplier > 1` = faster (confirmed against vanilla Stimpack). Stacks multiply, so 10
stacks ≈ 1.1^10 ≈ 2.6×. `Duration=4` is refreshed on each new application, so it only decays after
a 4 s lull. `InfoFlags Hidden` keeps the stack icon off the unit panel.

### 2. The on-fire apply effect (gated to the player)
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:187-192 -->
<CEffectApplyBehavior id="WoLUWraithTriggerOverrideApply">
    <EditorCategories value="Race:Terran"/>
    <Behavior value="WoLUWraithTriggerOverride"/>
    <WhichUnit Value="Source"/>                  <!-- apply to the FIRING unit (self-buff) -->
    <ValidatorArray value="WoLUHasFlag"/>        <!-- player-only; no-ops for enemy Wraiths -->
</CEffectApplyBehavior>
```
`WhichUnit=Source` is the project's self-apply convention (the firing Wraith buffs itself, not the
target).

### 3. Weapon Effect → a set that runs {original delivery + the apply}
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:194-204 -->
<CEffectSet id="WraithATriggerOverrideSet">       <!-- AA weapon -->
    <EffectArray value="WraithAPersistent"/>       <!-- original missile-pair delivery -->
    <EffectArray value="WoLUWraithTriggerOverrideApply"/>
</CEffectSet>
<CEffectSet id="WraithGTriggerOverrideSet">       <!-- AG weapon -->
    <EffectArray value="WraithGLaunchMissile"/>     <!-- original missile launch -->
    <EffectArray value="WoLUWraithTriggerOverrideApply"/>
</CEffectSet>
```
`WraithAPersistent` and `WraithGLaunchMissile` are the **real vanilla delivery effects** (verified:
`mods/_reference/campaigns/liberty.sc2campaign/EffectData.xml:4583` and `:4604`). Reusing them
verbatim keeps the original damage/visuals intact (cross-ref [11](11-effect-set-caster-trap.md):
check a reused set for caster-bound members — these two are plain delivery, no trap).

### 4. Redirect both Wraith weapons' Effect (keep the weapon ids)
```xml
<!-- src/mod/Base.SC2Data/GameData/WeaponData.xml:72-77 -->
<CWeaponLegacy id="WraithA"><Effect value="WraithATriggerOverrideSet"/></CWeaponLegacy>
<CWeaponLegacy id="WraithG"><Effect value="WraithGTriggerOverrideSet"/></CWeaponLegacy>
```
The weapon ids `WraithA`/`WraithG` are kept (not cloned), so `WeaponStart.Wraith*` attack
animations still bind ([24](24-clone-visuals.md)).

### Merc/hero reach
`MercWraith` (Winged Nightmares) is `parent="Wraith"` with no `WeaponArray` override, so it shares
`WraithA`/`WraithG` and inherits the whole stacking mechanism automatically
(`docs/BACKLOG.md:19`; [implementation-patterns.md §0.1-B](../implementation-patterns.md)).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: the vanilla delivery effect(s) <DELIVERY> the weapon currently fires
     (xmlq.py get <WEAPON_ID> ...WeaponData.xml → its <Effect>; then expand that effect). -->
<CBehaviorBuff id="<NAME>Stack">
    <Alignment value="Positive"/><InfoFlags index="Hidden" value="1"/>
    <MaxStackCount value="<CAP>"/><Duration value="<DECAY_SECONDS>"/>
    <Modification AttackSpeedMultiplier="<1.1 etc>"/>   <!-- or any per-stack Modification field -->
</CBehaviorBuff>
<CEffectApplyBehavior id="<NAME>Apply">
    <Behavior value="<NAME>Stack"/><WhichUnit Value="Source"/>
    <ValidatorArray value="WoLUHasFlag"/>              <!-- player-only -->
</CEffectApplyBehavior>
<CEffectSet id="<NAME>Set">
    <EffectArray value="<DELIVERY>"/>                  <!-- keep the original delivery -->
    <EffectArray value="<NAME>Apply"/>
</CEffectSet>
<CWeaponLegacy id="<WEAPON_ID>"><Effect value="<NAME>Set"/></CWeaponLegacy>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`WhichUnit` must be `Source`** for a self-buff — `Target` would buff what you shot.
- **Forgetting `MaxStackCount`** makes it stack unbounded; forgetting `Duration` makes it
  permanent (never decays).
- **Reusing a vanilla `CEffectSet` blindly can drag in a caster-bound member** that aborts the set
  on a new caster ([11](11-effect-set-caster-trap.md)). Here we reuse single *delivery* effects
  (`WraithAPersistent`/`WraithGLaunchMissile`), not a set — confirmed clean.
- **Cloning the weapon would lose `WeaponStart.<id>` animations** — keep the weapon id, override
  only its `Effect` ([24](24-clone-visuals.md)).
- **The `WoLUHasFlag` gate is on the apply-effect, not the weapon** — enemy Wraiths fire the same
  set but the apply no-ops; the damage delivery (first set member) still runs for everyone.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 confirms `WoLUWraithTriggerOverride`,
  `WoLUWraithTriggerOverrideApply`, the sets, `WraithAPersistent`/`WraithGLaunchMissile`, and the
  weapon ids all resolve; CHECK4 unaffected (sets aren't `CAbil*`/`CWeapon*` Effect-default clones).
  **Does not prove** the stack visibly builds or caps. `[STATIC]`
- **In-game (Test Document / owner):** have a Wraith attack continuously; its fire rate should
  visibly ramp over ~10 shots and plateau (≈2.6×), then decay after a 4 s pause. Confirm an enemy
  Wraith does **not** speed up (gate works). `[GAME]` — parked.
- **Editor (Previewer):** static catalog shows the buff/effects exist; can't show stacking. n/a.

## Parked for bunch-verify
- `[GAME]` — Player Wraith (and MercWraith) fire rate ramps up over sustained attacking, caps at
  ~2.6×, decays after a 4 s lull; enemy Wraith unaffected.

> **Resolution note:** all ids in this recipe were resolved against our XML + `mods/_reference/`
> (Wraith delivery effects, Moebius BarrelAccelerator reference, our buff/effect/weapon defs) — no
> unresolved/guessed ids remain.
</content>
