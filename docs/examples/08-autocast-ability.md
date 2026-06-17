# 08 — Autocast ability (the Super Stim pattern)

> Give a unit an effect ability the engine **autocasts** — fires it itself in combat, no clicks.

**Maps to (request):** unit-table Barracks "super stim … should auto cast"; the Ghost/Spectre
"Snipe, EMP and super stim ability should be auto cast" kit. **Status:** [STATIC] proven **and
[GAME]-VERIFIED** — stim autocast is confirmed firing in game (plan §7; implementation-patterns
§3). The schema gotchas below each cost a real session; do not re-derive them.

---

## Result
A selected unit, while it is fighting, **automatically** uses an effect ability (Super Stim:
+50% move/attack speed for 15 s, plus a heal) with no manual cast — and only the player gets it
(button gated on `WoLUHaveFlag`, per [07](07-clone-flag-gate.md)).

## Mechanism
Autocast needs an **effect-style** ability: a `CAbilEffectInstant` (or `CAbilEffectTarget`) whose
`Effect` runs an effect chain. **Behavior-class abilities (`CAbilBehavior`, e.g. cloak toggles)
CANNOT autocast at all** — no Blizzard data does it — which is exactly why stim, even though
vanilla stim is already `CAbilEffectInstant`, had to be rebuilt as one here rather than reused as
a behavior ([02](02-no-op-traps.md)).

The autocast itself is **three ability-level fields**: `<Flags index="AutoCast" value="1"/>` +
`<Flags index="AutoCastOn" value="1"/>` turn it on by default, and
`AutoCastValidatorArray="CasterIsFiringWeapon"` makes it fire while the unit is attacking
(perma-stim in combat). The whole thing is a **verbatim clone of NCO's `SuperStimpackMarine`/
`Marauder`** (`mods/_reference/mods/novastoryassets.sc2mod`) with only ids, the button face, the
`WoLUHaveFlag` gate, and our effect-set ids changed — copy a working Blizzard chain, never
hand-write the schema. (learnings.md §"Per-player isolation…"; implementation-patterns §3.)

## Worked example (real, from this repo)

### The ability (autocast block + gated button)
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:13-34 -->
<CAbilEffectInstant id="StimpackWoLU">
    <AbilSetId value="Stimpack"/>                          <!-- one button stims all selected -->
    <Effect index="0" value="WoLUStimSet"/>                <!-- index="0" is MANDATORY (below) -->
    <Flags index="AutoCast" value="1"/>                    <!-- ABILITY-level autocast flags -->
    <Flags index="AutoCastOn" value="1"/>
    <AutoCastRange value="5"/>
    <AutoCastValidatorArray value="CasterIsFiringWeapon"/> <!-- fire while attacking -->
    <CmdButtonArray index="Execute" DefaultButtonFace="Stim" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
    <Cost><Cooldown TimeUse="18"/></Cost>
</CAbilEffectInstant>
```
(`StimpackMarauderWoLU` is the twin, `AbilData.xml:35-53`, pointing at `WoLUStimMarauderSet`.)

### The effect chain (`Effect index="0"` → set → buff + heal)
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:10-34 -->
<CEffectApplyBehavior id="WoLUStimApply">
    <Behavior value="WoLUSuperStim"/>
    <WhichUnit Value="Source"/>                            <!-- Source, not Caster -->
</CEffectApplyBehavior>
<CEffectSet id="WoLUStimSet">
    <EffectArray value="WoLUStimApply"/>                   <!-- apply the speed buff -->
    <EffectArray value="WoLUStimSetMU"/>                   <!-- + heal -->
</CEffectSet>
<CEffectModifyUnit id="WoLUStimSetMU">
    <VitalArray index="Life" Change="30"/>                 <!-- ATTRIBUTE form, target Source -->
    <ImpactUnit Value="Source"/>
</CEffectModifyUnit>
```
(`WoLUStimMarauderSetMU` heals 60 — `EffectData.xml:30-34` — the NCO 30/60 split.)

### The buff (what the speed boost actually is)
```xml
<!-- src/mod/Base.SC2Data/GameData/BehaviorData.xml:8-14 -->
<CBehaviorBuff id="WoLUSuperStim">
    <Alignment value="Positive"/>
    <Duration value="15"/>
    <Modification MoveSpeedMultiplier="1.5" AttackSpeedMultiplier="1.5"/>
</CBehaviorBuff>
```

### The wiring (override the vanilla stim slot — [07](07-clone-flag-gate.md))
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:80,83 (Marine) -->
<AbilArray index="3" Link="StimpackWoLU"/>
<LayoutButtons index="5" AbilCmd="StimpackWoLU,Execute"/>
```
Override-in-place is safe here: vanilla stim is requirement-gated and the AI never gets it.
`<AbilSetId value="Stimpack"/>` + `<Flags index="ToSelection" value="1"/>` make ONE press stim
every selected unit whose ability shares the `Stimpack` set, across unit types.

### Merc/hero reach
Marine/Firebat heroes and standard mercs get their own `AbilArray index` overrides + buttons
(UnitData.xml:31,41,57,63,…). The **standalone Marauder merc `HammerSecurity`** gets the ability
swap (`AbilData.xml`/UnitData.xml) but is an open bug if its **card button** wasn't re-pointed —
the ability can autocast without a visible button (implementation-patterns §3.1; [26](26-command-card-edits.md)).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: copy a WORKING Blizzard autocast chain (NCO SuperStimpack*, etc.) and rename
     ids only. Confirm the vanilla ability's AbilArray index on the unit (xmlq.py get <UNIT>). -->
<CAbilEffectInstant id="<ABIL>WoLU">
    <Effect index="0" value="<SET>"/>                       <!-- index="0" or it has NO effect -->
    <Flags index="AutoCast" value="1"/>                     <!-- ability-level, NOT CmdButton -->
    <Flags index="AutoCastOn" value="1"/>
    <AutoCastValidatorArray value="<gate, e.g. CasterIsFiringWeapon>"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="<Face>" Requirements="WoLUHaveFlag"/>
    <Cost><Cooldown TimeUse="<n>"/></Cost>
</CAbilEffectInstant>
<CEffectSet id="<SET>"><EffectArray value="<applyBuff>"/><EffectArray value="<heal>"/></CEffectSet>
<CEffectModifyUnit id="<heal>"><VitalArray index="Life" Change="<n>"/><ImpactUnit Value="Source"/></CEffectModifyUnit>
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
These three each cost a session (learnings.md §"Per-player isolation…"):
- **`Effect` needs `index="0"`.** `<Effect value="..."/>` *without* `index="0"` on a
  `CAbilEffectInstant` silently leaves the ability with **no effect** — manual cast does nothing,
  autocast does nothing. (CHECK4 catches the *missing* effect; the missing-`index` is subtler.)
- **`AutoCast`/`AutoCastOn` are ABILITY-level `<Flags>`, NOT `CmdButtonArray` flags.** Putting them
  on the button does nothing.
- **Effect chain heals use the ATTRIBUTE form `<VitalArray index="Life" Change="30"/>` and target
  `Source`, not `Caster`.** A `<Vital>` child or `Caster` target won't heal the stimming unit.
- **Behavior-class abilities can't autocast** — if your ability is a `CAbilBehavior`, you must
  rebuild it as `CAbilEffectInstant`/`Target`.
- **Don't hand-write the schema** — clone a known-working Blizzard chain verbatim, then rename.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (the effect-set/buff ids resolve), CHECK4 (the
  ability has a real `<Effect>`). `galaxy_lint.py` for the apply lib. **Does not prove** the
  autocast fires or the flags are on the right level. `[STATIC]`
- **In-game (owner / Test Document):** select a player unit, attack — the stim icon/glow appears
  on its own; HP ticks up by the heal; the cooldown gates re-cast. **Already [GAME]-confirmed for
  stim** (plan §7). A **new** autocast ability still needs this. `[GAME]`
- **Editor (Previewer):** the gated button shows on the merged card (static only — does not show
  autocast firing). `[EDITOR]`

## Parked for bunch-verify
- `[GAME]` — stim autocast itself is **already confirmed**; no new line. For any **new** autocast
  ability built from this pattern: "`<unit>` auto-fires `<abil>` while attacking; effect applies;
  enemy `<unit>` does not."
