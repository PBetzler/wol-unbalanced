# 24 — Keep visuals on clones (actors bind to ids)

> When you clone an ability / weapon / effect, keep its projectiles, beams, and impacts —
> because `ActorData` events are keyed to **ids**, and a clone with a new id matches none of them.

**Maps to (request):** every `*WoLU` clone that must still *look* right (Snipe, EMP, Yamato,
Magrail, Thor splash, Nano-Repair) — design rules 4/10 (heroes/mercs inherit abilities *and*
their look). **Status:** [STATIC] for the binding rule + which clones reuse which ids · every
asset *render* is [EDITOR]/[GAME] (Previewer / in-game) — see Verify.

---

## Result
A cloned ability/weapon/effect still fires its **projectile, beam, and impact**. Concretely:
`SnipeWoLU` keeps the snipe shot, `YamatoWoLU` keeps the Yamato beam, the Thor keeps its ground
attack animation + splash, the Magrail fires a real railgun beam — none of them render as a
silent damage tick.

## Mechanism
`ActorData` events key off ability / weapon / effect **ids** via event terms:
`Abil.Snipe.SourceCastStart`, `WeaponStart.ThorsHammer.AttackStart`, `Effect.<id>.Start`. **A
clone with a NEW id inherits NONE of these** — the actor never matches → no visual. (learnings.md
§"Visual actors bind to IDs"; [implementation-patterns.md §12](../implementation-patterns.md).)

Three rules of thumb keep the visuals:
1. **Reuse the vanilla EFFECT id** and you keep the **effect-bound** visuals (projectile, beam,
   impact — the ones that matter). Only **ability/weapon-bound caster animations** (cast poses,
   the stim puff) are lost — cosmetic. So `SnipeWoLU` sets `Effect=SnipeDamage`, `YamatoWoLU`
   sets `Effect=Yamato`, etc.
2. **Don't clone a WEAPON** if you can avoid it — weapon-bound animations break
   (`WeaponStart.<id>`). Instead **override the vanilla weapon's `Effect`** to a player-gated
   effect set; the weapon id stays, so the attack animation fires. This is exactly why the Thor
   keeps `ThorsHammer` and there is **no `ThorsHammerWoLU`**.
3. **Base-CASC `.m3`/`.dds`/portrait tokens are path-referenceable** from any mod (independent of
   data dependencies). To give a *new* effect a real model, define a `CModel` pointing at the
   `Assets\…\.m3` path and clone the original's actor, binding it to your effect's `Effect.<id>.*`
   event. The Magrail does this with the WarHound railgun model.

## Worked example (real, from this repo)

### Rule 2 — don't clone the weapon; override its Effect (Thor splash)
```xml
<!-- src/mod/Base.SC2Data/GameData/WeaponData.xml:11-12 -->
<CWeaponLegacy id="ThorsHammer">          <!-- vanilla weapon id KEPT -->
    <Effect value="ThorsHammerWoLUSet"/>  <!-- only the Effect is redirected -->
```
There is **no `id="ThorsHammerWoLU"` anywhere in GameData** (grep-confirmed). The comment above
(`WeaponData.xml:3-10`) records *why*: cloning the weapon broke the attack visual because the
Thor's animation actors bind to `WeaponStart.ThorsHammer` (the weapon id). Keeping the id means
the attack animation fires for everyone; the player-vs-vanilla split lives in the validator-gated
effect set (the Shaped Blast pattern — see [12](12-simultaneous-fire.md) / [13](13-flatten-attribute-bonus.md)).
The `MercThor` actor proves the binding it relies on:
```xml
<!-- src/mod/Base.SC2Data/GameData/ActorData.xml:66-69  (MercThor CActorUnit) -->
<On Terms="WeaponStart.ThorsHammer.AttackStart; ..." Send="AnimBracketStart Attack Attack,Superior"/>
<On Terms="WeaponStart.ThorsHammer.AttackStart; ..." Send="AnimBracketStart Attack Attack,Inferior"/>
<On Terms="WeaponStart.ThorsHammer.AttackStart" Send="AnimBracketStart Attack Attack"/>
```
Had we renamed the weapon, none of these would match → the Thor would attack with no animation.

### Rule 1 — clones that REUSE the vanilla effect id keep effect-bound visuals
Each of these is a `CAbilEffectTarget` clone that **explicitly pins** the vanilla effect id, so the
effect's projectile/beam still fires (and it dodges the [02](02-no-op-traps.md) clone-Effect
re-default trap):
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml -->
<CAbilEffectTarget id="SnipeWoLU">      <Effect index="0" value="SnipeDamage"/>      <!-- :63-65 -->
<CAbilEffectTarget id="EMPWoLU">        <Effect index="0" value="EMPLaunchMissile"/> <!-- :103-105 -->
<CAbilEffectTarget id="ObliterateWoLU"> <Effect index="0" value="Obliterate"/>       <!-- :123-125 -->
<CAbilEffectTarget id="YamatoWoLU" parent="Yamato"> <Effect index="0" value="Yamato"/> <!-- :159-163 -->
<CAbilEffectTarget id="NanoRepairWoLU"> <Effect index="0" value="NanoRepair"/>       <!-- :384-387 -->
<CAbilEffectTarget id="HealWoLU" parent="heal"> <Effect index="0" value="heal"/>     <!-- :553-557 -->
```
`SnipeWoLU` reuses `SnipeDamage` → the snipe shot still fires; `EMPWoLU` reuses `EMPLaunchMissile`
→ the EMP missile (whose actor uses `AmmoUnit="EMP2Weapon"`) still launches; `YamatoWoLU` reuses
`Yamato` → the Yamato beam still fires; `NanoRepairWoLU`/`HealWoLU` reuse `NanoRepair`/`heal` → the
heal beams still bind. Only the *caster-bound* animations (cast pose, the stim puff) are lost — a
cosmetic price, not a missing projectile.

### Rule 3 — a real model for a NEW effect (Magrail railgun)
The Magrail is a genuinely new effect (`MagrailDamageWoLU`), so its visual is **authored**: a
`CModel` pointing at the base-game WarHound railgun `.m3` (path-referenced — no bundling, no NCO
dependency), and a beam actor cloned from the railgun style, bound to the effect's `Start`:
```xml
<!-- src/mod/Base.SC2Data/GameData/ModelData.xml:9-12 -->
<CModel id="WoLUMagrailBeam" parent="PersistentSpellFX">
    <Model value="Assets\Effects\Terran\WarHoundRailGunMissile\WarHoundRailGunMissile.m3"/>
</CModel>
```
```xml
<!-- src/mod/Base.SC2Data/GameData/ActorData.xml:11-17 -->
<CActorBeamSimple id="WoLUMagrailBeam" parent="BeamSimpleAnimationStyleOneShot">
    <On Terms="Effect.MagrailDamageWoLU.Start; At Caster" Send="Create"/>   <!-- bound to the EFFECT id -->
    <Model value="WoLUMagrailBeam"/>
    <HostLaunchSiteOps Ops="SOpAttachWeapon" HoldPosition="1"/>
    <HostImpactSiteOps Ops="SOpTargetPoint"/>
</CActorBeamSimple>
```
The effect it's bound to (`EffectData.xml:133`) and the ability that fires it
(`AbilData.xml:205-211`, `<Effect index="0" value="MagrailDamageWoLU"/>`) close the loop. There's
also a matching impact actor at `ActorData.xml:19-23` (`Effect.MagrailDamageWoLU.Start` →
`WoLUMagrailImpact`, the railgun-impact `.m3` at `ModelData.xml:13-16`).

### Merc/hero reach
Visual binding follows the **shared id**, so mercs/heroes that link the same effect/weapon id
inherit the visual automatically — `MercThor parent="Thor"` fires `ThorsHammer` → its attack
animation + the overridden splash both fire; the heroes' Snipe/EMP/Yamato clones reuse the same
effect ids. No per-merc actor work is needed for the *visual* (a new wreck unit id is a separate
story — see [22](22-death-response-resurrect.md) / CHECK1). [STATIC]

## Reusable snippet (swap the ids)
```xml
<!-- A clone that keeps its visual: REUSE the vanilla effect id. -->
<CAbilEffectTarget id="<Abil>WoLU">
    <Effect index="0" value="<VANILLA_EFFECT_ID>"/>   <!-- RESOLVE: this effect must exist + own the visual -->
</CAbilEffectTarget>

<!-- A weapon buff WITHOUT cloning: keep the weapon id, redirect its Effect. -->
<CWeaponLegacy id="<VANILLA_WEAPON_ID>">
    <Effect value="<PlayerGatedEffectSet>"/>
</CWeaponLegacy>

<!-- A real model for a NEW effect: path-reference the base .m3 + clone the actor. -->
<CModel id="<MyModel>"><Model value="Assets\Effects\...\X.m3"/></CModel>
<CActorBeamSimple id="<MyBeam>" parent="<RailgunStyleParent>">
    <On Terms="Effect.<MyEffect>.Start; At Caster" Send="Create"/>
    <Model value="<MyModel>"/>
</CActorBeamSimple>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **A clone with no `<Effect>` re-defaults the link to its OWN (nonexistent) id** → fires nothing
  (the `HealWoLU`/`YamatoWoLU` trap). Always pin `<Effect index="0" value="…"/>`. `audit.py`
  CHECK4 **fails** on this.
- **Renaming a weapon kills `WeaponStart.<id>` animations** — prefer overriding the vanilla
  weapon's `Effect` (rule 2). A weapon clone is a last resort.
- **A new unit id (e.g. a wreck) needs its OWN `CActorUnit`** or it renders as a sphere (`audit.py`
  CHECK1). Reusing an effect id is *not* the same as reusing a unit id.
- **Reusing the effect id keeps effect visuals, NOT caster animations.** If a missing *caster*
  animation matters, you must also clone/bind the caster's actor — usually not worth it.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 fails if a `parent=`/`Effect=` resolves to no
  real id; CHECK4 fails on the clone-Effect re-default; CHECK1 fails on a sphere unit. CHECK6 lists
  `.m3`/portrait tokens as `UNVERIFIED — confirm in game`. **Proves** the ids/actors are wired;
  **does not prove** any model actually renders. `[STATIC]`
- **Editor (Previewer):** open the actor → **Preview Object**; confirm the model/beam shows.
  Answers "is the railgun model real?" without a playtest. `[EDITOR]` — add to queue.
- **In-game (Test Document / owner):** fire each cloned ability and watch for the projectile/beam/
  impact: `SnipeWoLU` shot, `YamatoWoLU` beam, Thor attack animation + ground splash, the Magrail
  railgun beam. The Magrail beam is explicitly flagged in-source as authored without in-game
  iteration (`ActorData.xml:8`). `[GAME]` — add to queue.

## Parked for bunch-verify
- `[EDITOR]` — Previewer renders the `WoLUMagrailBeam` / `WoLUMagrailImpact` models (railgun
  model resolves, not a missing-asset cube).
- `[GAME]` — In-game: the Magrail fires a visible railgun beam + impact (`ActorData.xml:8` FLAG);
  `SnipeWoLU`/`EMPWoLU`/`YamatoWoLU` keep their projectile/beam; the Thor's ground attack plays its
  animation + splash with the weapon id kept.
