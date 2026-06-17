# 28 — Tactical Jump (point-target warp anywhere)

> Give a unit a button that **teleports it to any clicked point** on the map (the Hercules
> Tactical Jump, generalized), player-only.

**Maps to (request):** BACKLOG Cross-cutting "**Tactical Jump** (Hercules / Science Vessel / BC /
Predator) — **SHIPPED v0.3.0**". **Status:** [STATIC] done (ids resolve, clone+gate correct);
the warp landing + button visibility are [GAME]. implementation-patterns §2 (clone+flag-gate).

---

## Result
The player's Hercules, Science Vessel, Battlecruiser, and Predator each get a **Tactical Jump**
button (real Hercules jump icon, hotkey-free). Click it, click anywhere on the map → the unit
warps there instantly (10 s cooldown). Enemies of those types never see the button (gated).

## Mechanism
Teleport-to-point is the engine effect **`CEffectTeleport`** with
`TargetLocation Value="TargetPoint"` — fed by a **point-target ability** `CAbilEffectTarget` whose
`<Effect index="0">` points at the teleport effect. This is a pure structural addition (a new
ability + effect + a card button on existing units), so it goes through the **clone + flag-gate
backbone** ([07](07-clone-flag-gate.md)): define the `*WoLU` ability/effect/button in static XML,
gate the **button** on `WoLUHaveFlag` so only the flagged player uses it, and wire it in by
**XML index-override** of each unit's `AbilArray` + a card button append (never a runtime link
edit — that's a no-op, [02](02-no-op-traps.md)).

The ability sets `Range value="500"` (effectively map-wide) and `Arc value="360"` so it can target
any direction without turning. The button carries `<Flags index="ToSelection" value="1"/>` so one
click jumps every selected unit that shares the ability.

## Worked example (real, from this repo)

### The effect — teleport the caster to the clicked point
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:144-148 -->
<CEffectTeleport id="TacticalJumpWoLU">
    <EditorCategories value="Race:Terran"/>
    <WhichUnit Value="Caster"/>
    <TargetLocation Value="TargetPoint"/>
</CEffectTeleport>
```

### The ability — point-target, map-wide range, gated button
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:336-348 -->
<CAbilEffectTarget id="TacticalJumpWoLU">
    <EditorCategories value="Race:Terran,AbilityorEffectType:Units"/>
    <Effect index="0" value="TacticalJumpWoLU"/>        <!-- explicit Effect — see Gotchas -->
    <Range value="500"/>
    <Arc value="360"/>
    <Flags index="RequireTargetVision" value="0"/>      <!-- jump to fogged points too -->
    <Cost><Cooldown TimeUse="10"/></Cost>
    <CmdButtonArray index="Execute" DefaultButtonFace="TacticalJumpWoLU" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffectTarget>
```
Note the ability id and the effect id are the **same string** (`TacticalJumpWoLU`) — that's fine,
they live in different catalogs (Abil vs Effect); but the `<Effect index="0">` is still set
**explicitly** so the ability doesn't re-default its effect link to a nonexistent id
([02](02-no-op-traps.md) clone-Effect trap; `audit.py` CHECK4).

### The button (real Hercules jump icon, base-CASC path)
```xml
<!-- src/mod/Base.SC2Data/GameData/ButtonData.xml:63-65 -->
<CButton id="TacticalJumpWoLU">
    <Icon value="Assets\Textures\btn-ability-terran-hercules-tacticaljump.dds"/>
</CButton>
```

### Wired onto 4 units (index-override AbilArray + card append, all `WoLUHaveFlag`-gated)
| Unit | AbilArray | Card button (cell) | cite |
|---|---|---|---|
| Battlecruiser | `index="8"` | `index="11"` R1C2 | `UnitData.xml:242,247` |
| ScienceVessel | `index="5"` | `index="10"` R1C0 | `UnitData.xml:286,291` |
| Hercules | `index="3"` | `index="8"` R2C2 | `UnitData.xml:301,303` |
| Predator | `index="3"` | `index="7"` R2C1 | `UnitData.xml:307,309` |

Each append carries an **explicit `index=`** = that unit's vanilla element count (Hercules
AbilArray 3 / buttons 8; Predator AbilArray 3 / buttons 7 — `UnitData.xml:297-299` comment) —
index-less appends are dropped in our component-folder mod ([26](26-command-card-edits.md)).

### Merc/hero reach
Tactical Jump is added per-unit (4 base units). Mercs/heroes that are `parent=` clones of these
would inherit it, but none of these four has an elite-merc clone, so no extra wiring is needed.
(If you add it to a unit with an elite merc, the `parent=` clone inherits the `AbilArray` override
automatically — kind B, [18](18-elite-merc-clone.md).)

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: WoLUHaveFlag requirement exists; the icon path is real (or pending [GAME]). -->
<!-- EffectData.xml -->
<CEffectTeleport id="<NAME>WoLU"><WhichUnit Value="Caster"/><TargetLocation Value="TargetPoint"/></CEffectTeleport>
<!-- AbilData.xml -->
<CAbilEffectTarget id="<NAME>WoLU">
    <Effect index="0" value="<NAME>WoLU"/><Range value="500"/><Arc value="360"/>
    <Cost><Cooldown TimeUse="<N>"/></Cost>
    <CmdButtonArray index="Execute" DefaultButtonFace="<NAME>WoLU" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffectTarget>
<!-- UnitData.xml, on each target unit (indices = that unit's vanilla element counts): -->
<AbilArray index="<count>" Link="<NAME>WoLU"/>
<LayoutButtons index="<count>" Face="<NAME>WoLU" Type="AbilCmd" AbilCmd="<NAME>WoLU,Execute"
              Requirements="WoLUHaveFlag" Row="<r>" Column="<c>"/>
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **No explicit `<Effect>` on the ability** → re-defaults to its own (here harmless because the
  ids match, but always set it; `audit.py` CHECK4 enforces it).
- **Index-less `AbilArray`/`LayoutButtons` append** → silently dropped. Always set `index=`.
- **Runtime `AbilArray[i].Link` / `LayoutButtons[j].AbilCmd` edit** → no-op; must be XML
  index-override.
- **Card-cell collision** — pick a free cell on the *merged* card; `audit.py` CHECK5 warns.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (`TacticalJumpWoLU` ability/effect/button ids
  resolve), CHECK4 (effect set), CHECK5 (card cells don't collide). **Does not prove** the warp
  happens or the icon draws. `[STATIC]`
- **Editor (Previewer):** open Hercules/Predator/BC/SV — the Tactical Jump button shows with the
  jump icon (not a blank/colored box). `[EDITOR]` — add to queue.
- **In-game (Test Document / owner):** select a player Hercules, click Tactical Jump, click a far
  point → it warps there; 10 s cooldown; an enemy unit of the same type has **no** button. Any
  mission with these units. `[GAME]`.

## Parked for bunch-verify
- `[EDITOR]` — Tactical Jump button renders with the real jump icon on all 4 units.
- `[GAME]` — clicking it warps the selected unit(s) to the clicked point; 10 s cooldown; enemy
  units of the same type never show the button (gate holds).
