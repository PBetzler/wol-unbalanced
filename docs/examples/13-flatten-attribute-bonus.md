# 13 — Flatten "+X vs light/armored" into flat damage

> Turn a weapon's conditional "*N* damage (+*M* vs light)" into a flat "*N+M* damage" that hits
> everything equally — and know why the per-player edit that *looks* right does nothing.

**Maps to (request):** unit-table "X dmg + X vs light/armored" should read/deal flat "X dmg"
(Ghost, Spectre, Thor AA) — open-issues `docs/open-issues.md:15` (still `[ ]` for the rifles).
Cross-refs [implementation-patterns.md §2 + contradiction #3](../implementation-patterns.md).
**Status:** [STATIC] done for **Thor AA** (clone shipped) · [STATIC] **no-op, NOT fixed** for the
Ghost/Spectre rifles (the per-player edits are dead — see below) · [GAME] parked.

---

## Result
A unit's attack deals one flat number regardless of target attributes. Done correctly for the
**Thor AA** rocket: 35 flat per rocket, no residual light bonus (`JavelinMissileLaunchersDamageBuffedWoLU`).
**Not** done for the **Ghost/Spectre rifle** — the card still reads "+X vs light/armored" because
the attempt is a no-op (kept here as the cautionary half).

## Mechanism
`AttributeBonus[Light]` / `AttributeBonus[Armored]` on a `CEffectDamage` is an **indexed-array
element**. A per-player `CatalogFieldValueModify` on it is a **silent no-op** — same class as
`Options[]` ([12](12-simultaneous-fire.md)) and `AreaArray[]` ([14](14-enlarge-splash.md)). The
call compiles, runs, "succeeds", and the bonus stays. (Cross-ref [02](02-no-op-traps.md), row
"indexed array element"; [implementation-patterns.md §0 cross-cutting facts](../implementation-patterns.md).)

The **working** path is the **Shaped-Blast effect clone**: override the weapon's `Effect` to a
`CEffectSet` whose buffed branch (`ValidatorArray="WoLUHasFlag"`) is a `parent=` clone of the
vanilla damage effect that **re-states `Amount` and zeroes the bonus** — set in *static XML*
inside the clone, where the array element is a literal, not a runtime edit. The vanilla branch
(`WoLUNoFlag`) keeps the original numbers so enemies are unchanged (rule 9). This is the same
clone backbone as [07](07-clone-flag-gate.md) and [14](14-enlarge-splash.md).

## Worked example (real, from this repo)

### The NO-OP attempts (do NOT copy — kept as the anti-example)
```python
# scripts/genlib.py:261-267  — these AttributeBonus edits are SILENT NO-OPS
("Effect", "C10CanisterRifle", "Amount", "20", "Set", "Ghost rifle: 10(+10 light) -> 20 flat"),
("Effect", "C10CanisterRifle", "AttributeBonus[Light]", "0", "Set", ""),     # NO-OP (indexed array)
("Effect", "SpecterU", "Amount", "20", "Set", "Spectre rifle: 15(+5 armored) -> 20 flat"),
("Effect", "SpecterU", "AttributeBonus[Armored]", "0", "Set", ""),           # NO-OP (indexed array)
# Thor AA: same indexed-array trap — the Amount Set may take, but the bonus zero does NOT:
("Effect", "JavelinMissileLaunchersDamage", "Amount", "35", "Set", "Thor AA: HIP floor 35/rocket"),
("Effect", "JavelinMissileLaunchersDamage", "AttributeBonus[Light]", "0", "Set", ""),   # NO-OP
```
The `Amount` "Set" is a plain scalar and *does* apply, but the `AttributeBonus[...]` zero **does
not** — so the rifle still gets its conditional bonus vs light/armored. **The Ghost/Spectre rifle
card therefore still reads "+X vs light/armored"** until those weapons get the clone treatment.
Name this explicitly to whoever picks it up: the remaining live no-ops are
`C10CanisterRifle.AttributeBonus[Light]` and `SpecterU.AttributeBonus[Armored]`.

### The WORKING pattern (Thor AA — shipped)
The Thor AA weapon's impact is redirected to a set whose buffed branch zeroes the bonus in static
XML:
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:89-96 -->
<!-- Player branch: 35/rocket flat (HIP floor, NO light bonus) + splash. -->
<CEffectDamage id="JavelinMissileLaunchersDamageBuffedWoLU" parent="JavelinMissileLaunchersDamage">
    <ValidatorArray value="WoLUHasFlag"/>
    <Amount value="35"/>
    <AttributeBonus index="Light" value="0"/>     <!-- STATIC literal → actually overrides -->
    <SearchFilters value="Air;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AreaArray Radius="1.6" Fraction="1"/>
    <AreaArray Radius="2.5" Fraction="0.5"/>
</CEffectDamage>
```
The vanilla `JavelinMissileLaunchersDamage` is `Amount=8 / AttributeBonus[Light]=4` (verified
`mods/_reference/mods/liberty.sc2mod/EffectData.xml:2271-2280`). The clone sets `Amount=35` and
`AttributeBonus[Light]=0` **as static-XML literals**, so the override actually lands. It's wired
in via the weapon's launch-missile impact set (`JavelinMissileLaunchersDamageWoLUSet`,
`EffectData.xml:77-96`), reached because we override the AA missile's `ImpactEffect`
(`JavelinMissileLaunchersLM`, `EffectData.xml:74-76`). The vanilla branch
(`JavelinMissileLaunchersDamageVanillaWoLU`, `EffectData.xml:83-85`) keeps 8 +4-vs-light for
enemy Thors.

### Merc/hero reach
The Thor AA fix is at the **shared effect-set level** wired off the shared weapon id, so `MercThor`
(`parent="Thor"`, no weapon override) inherits it. The Ghost/Spectre rifle (`C10CanisterRifle`/
`SpecterU`) is shared by Nova/Tosh — but since the *edit* is a no-op, it reaches no one; the clone
fix, when built, would reach the heroes that link those effect ids.

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: vanilla damage effect <DMG_ID> (xmlq.py get <DMG_ID> ...EffectData.xml).
     Wire the weapon's Effect to a CEffectSet { vanilla branch (WoLUNoFlag), buffed (WoLUHasFlag) }. -->
<CEffectDamage id="<DMG_ID>BuffedWoLU" parent="<DMG_ID>">
    <ValidatorArray value="WoLUHasFlag"/>
    <Amount value="<FLAT_TOTAL>"/>                 <!-- old base + old bonus, as a literal -->
    <AttributeBonus index="<Light|Armored|...>" value="0"/>   <!-- STATIC literal kills the bonus -->
</CEffectDamage>
<CEffectDamage id="<DMG_ID>VanillaWoLU" parent="<DMG_ID>">
    <ValidatorArray value="WoLUNoFlag"/>           <!-- enemies keep vanilla -->
</CEffectDamage>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`AttributeBonus[...]` per-player edit = silent no-op** (indexed array). The plain `Amount` Set
  next to it *does* apply — so you get a half-applied result that looks deliberate but isn't.
- **Clone with no `<Effect>`/parent re-defaults** — here the buffed effect is a `parent=` clone of
  the real damage id, so it inherits everything and overrides only `Amount`/`AttributeBonus`.
  `audit.py` CHECK4 catches a missing-effect clone ([07](07-clone-flag-gate.md)).
- **Friendly-fire** — adding splash (here `AreaArray`) makes the area effect friendly-fire unless
  you set `SearchFilters` ([15](15-friendly-fire-safety.md)). The buffed branch sets `Air;...`.
- **Forgetting the vanilla branch** leaks the buff to enemies (static XML is global) — always pair
  `WoLUHasFlag` with a `WoLUNoFlag` sibling.

## Verify
- **Static:** `python scripts/audit.py` (CHECK3 confirms `parent=`/effect ids resolve; CHECK4
  confirms the clone has a real effect; CHECK5 unaffected). **Does not prove** the card text reads
  flat or the damage lands flat in game. `[STATIC]`
- **In-game (Test Document / owner):** attack a Light target and a non-Light target with the Thor
  AA; both should take 35. For the Ghost/Spectre rifle, the card **still shows "+X vs light"** —
  the diag readback (`gLgt`) confirms the array edit is a no-op (`docs/open-issues.md:15`). `[GAME]`
- **Editor (Previewer):** the static clone (Thor AA) shows in the merged catalog; the per-player
  rifle no-op does not (runtime). `[EDITOR]` for the Thor-AA tooltip only.

## Parked for bunch-verify
- `[GAME]` — Thor AA: hit a Light and a non-Light target, both take 35 (no light bonus).
- `[GAME]` — Ghost/Spectre rifle card **still reads "+X vs light/armored"** (confirms the
  `AttributeBonus` per-player edit is dead; the clone fix is unbuilt). Track as open-issue
  `docs/open-issues.md:15`.
</content>
