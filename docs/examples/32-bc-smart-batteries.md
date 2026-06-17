# 32 — Battlecruiser "smart batteries": auto-cast spells + multi-target-no-overkill (design example)

> Make the BC / Jackson's Revenge **auto-cast** its spells, ignore armor, and fire on the move
> (SHIPPED) — and spread its fire to **avoid overkill** across many targets (DESIGN, deferred).
> **HONESTY:** the autocast/ignore-armor half ships; the multi-target-no-overkill half is
> blueprinted but **not** shipped.

**Maps to (request):** BACKLOG WP-D "BC smart-batteries: the fully-blueprinted rogue-kit
multi-target-no-overkill system (needs in-game iteration; pre-approved single-target fallback
already works)"; open-issues **#5** (Jackson's Revenge no attack upgrades / Yamato-only autocast),
**#6** (only Yamato autocasts), "Defensive Matrix never autocast" (RESOLVED v0.2.5). **Status:**
autocast + ignore-armor + fire-while-moving = [STATIC] done; multi-target-no-overkill = DESIGN.
implementation-patterns §10 (TargetSort) + §2 (autocast clone); learnings §"Abilities, autocast,
and targeting".

---

## What's shipped vs. what's only designed (read this first)

| Piece | Built? | Where |
|---|---|---|
| **Autocast** Yamato / Missile Pods / Defensive Matrix on the hero BC (Jackson's Revenge) | ✅ SHIPPED | `DukesRevenge{Yamato,MissilePods,DefensiveMatrix}WoLU` clones (`AbilData.xml:471-503`). |
| `State="Restricted"` → `"Normal"` fix (why only Yamato auto-cast before) | ✅ SHIPPED | `AbilData.xml:491,500` (open-issues #6). |
| **Defensive Matrix autocast** rewired to the self-buff pattern | ✅ SHIPPED | `AutoCastValidatorArray="CasterIsFiringWeapon"` (`AbilData.xml:499`; open-issues "Defensive Matrix never autocast", RESOLVED v0.2.5). |
| **Ignore armor** + **fire while moving** on the BC attack side | ✅ SHIPPED | genlib `ArmorReduction=0` + `AllowedMovement=Moving` ([17](17-ignore-armor-fire-moving.md)). |
| **Multi-target, no-overkill "smart batteries"** (spread fire so the BC doesn't pile onto one target) | ❌ **DESIGN / deferred** | The mechanism (an un-descended `TSTrackedByBattlecruiser` TargetSort) is understood ([10](10-autocast-priority-targetsort.md)) but **no such sort is wired onto the BC weapons in our XML** — the pre-approved single-target fallback works; the spread system "needs in-game iteration" (BACKLOG WP-D). |

## Result (as actually shipped)
The player's Jackson's Revenge **auto-fires** Yamato (on big targets), Missile Pods (at air), and
auto-shields with Defensive Matrix while its weapons are firing; its attacks **ignore armor** and
fire **on the move**. It does **not** yet intelligently spread shots to avoid overkill — that's the
deferred half.

## Mechanism

### Shipped: autocast clones (the `parent=` + State=Normal pattern)
Each active is a `parent=` clone that inherits the vanilla ability (cost/effect/range) and adds
only the autocast block + a re-pointed gated button ([08](08-autocast-ability.md)). The subtle bug
that made *only Yamato* autocast: `DukesRevengeMissilePods`/`DefensiveMatrix` ship their
`CmdButtonArray` with `State="Restricted"` (Yamato doesn't); a `parent=` clone **inherits** that
state and overriding the same `index="Execute"` **merges field-by-field**, so `State` stayed
Restricted. The fix is an explicit `State="Normal"`.

### Shipped: Defensive Matrix as a self-buff autocast
Defensive Matrix is a self-buff `CAbilEffectInstant`; the original autocast used **offensive**
`AutoCastFilters` that exclude Self/Ally → no valid target → never fired. Rewired to the verified
self-buff pattern `AutoCastValidatorArray="CasterIsFiringWeapon"` (same idiom as `StimpackWoLU`),
so it auto-shields whenever the BC is in combat.

### Deferred (design): multi-target-no-overkill
The overkill-avoid primitive is a **`CTargetSortValidator`** on "already targeted by a BC", used
**un-descended** so already-attacked units sort to the **back** → the BC spreads fire instead of
piling on ([10](10-autocast-priority-targetsort.md); learnings — the RaynorRogue kit's
`TSTrackedByBattlecruiser`, used un-descended). To ship it you'd add that sort to the BC weapons'
`<TargetSorts>`. **That wiring is not in our XML today** — the BC keeps single-target fallback.

## Worked example (real, from this repo)

### Yamato autocast clone (big-target-gated, structure-skipping)
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:471-480 -->
<CAbilEffectTarget id="DukesRevengeYamatoWoLU" parent="DukesRevengeYamato">
    <Flags index="AutoCast" value="1"/>
    <Flags index="AutoCastOn" value="1"/>
    <AutoCastRange value="10"/>
    <AutoCastFilters value="Visible;Self,Player,Ally,Neutral,Structure,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AutoCastValidatorArray value="WoLUYamatoBigTarget"/>     <!-- only worthwhile (big) targets -->
    <CmdButtonArray index="Execute" DefaultButtonFace="YamatoGun" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffectTarget>
```

### Missile Pods + Defensive Matrix — the State="Normal" fix
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:486-503 -->
<CAbilEffectTarget id="DukesRevengeMissilePodsWoLU" parent="DukesRevengeMissilePods">
    <Flags index="AutoCast" value="1"/><Flags index="AutoCastOn" value="1"/>
    <AutoCastRange value="7"/>
    <AutoCastFilters value="Air,Visible;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="MissilePods" State="Normal" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffectTarget>
<CAbilEffectInstant id="DukesRevengeDefensiveMatrixWoLU" parent="DukesRevengeDefensiveMatrix">
    <Flags index="AutoCast" value="1"/><Flags index="AutoCastOn" value="1"/>
    <AutoCastRange value="5"/>
    <AutoCastValidatorArray value="CasterIsFiringWeapon"/>     <!-- self-buff while fighting -->
    <CmdButtonArray index="Execute" DefaultButtonFace="DefensiveMatrix" State="Normal" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffectInstant>
```

### Wired onto the hero (append + re-point the 3 buttons)
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:268-275 -->
<CUnit id="DukesRevenge">
    <AbilArray index="6" Link="DukesRevengeYamatoWoLU"/>
    <AbilArray index="7" Link="DukesRevengeMissilePodsWoLU"/>
    <AbilArray index="8" Link="DukesRevengeDefensiveMatrixWoLU"/>
    <CardLayouts index="0">
        <LayoutButtons index="5" AbilCmd="DukesRevengeYamatoWoLU,Execute"/>      <!-- re-point existing buttons -->
        <LayoutButtons index="6" AbilCmd="DukesRevengeMissilePodsWoLU,Execute"/>
        <LayoutButtons index="7" AbilCmd="DukesRevengeDefensiveMatrixWoLU,Execute"/>
    </CardLayouts>
</CUnit>
```
The three clones are also `TechTreeAbilityAllow`-ed in the lib so nothing gates them
(`LibWoLUnbalanced.galaxy:153-155`). `DukesRevenge` is a player-exclusive hero → rule-9 safe with
no flag gate needed (the button `Requirements="WoLUHaveFlag"` is belt-and-suspenders).

### Merc/hero reach
`DukesRevenge` is the BC hero (its own unit id) — handled directly above. The base `Battlecruiser`
gets the parallel `YamatoWoLU`/`MissilePodsWoLU`/`DefensiveMatrixWoLU` clones (`UnitData.xml:239-246`).

## Reusable snippet (swap the ids)
```xml
<!-- Autocast a vanilla active without re-specifying its effect chain: -->
<CAbilEffect* id="<NAME>WoLU" parent="<VANILLA_ABIL>">
    <Flags index="AutoCast" value="1"/><Flags index="AutoCastOn" value="1"/>
    <AutoCastRange value="<r>"/>
    <!-- offensive: AutoCastFilters that EXCLUDE Self/Ally; self-buff: AutoCastValidatorArray="CasterIsFiringWeapon" -->
    <CmdButtonArray index="Execute" DefaultButtonFace="<FACE>" State="Normal" Requirements="WoLUHaveFlag">
        <Flags index="ToSelection" value="1"/>
    </CmdButtonArray>
</CAbilEffect*>
<!-- DESIGN (deferred) multi-target-no-overkill: add an un-descended sort to the BC weapon's <TargetSorts>:
     <CTargetSortValidator id="TSWoLUBCNotTracked"><Validator value="<is-already-bc-target>"/></CTargetSortValidator>
     (NO <Descending> → passers LAST → spread fire). NOT wired today; iterate in game. -->
```
> RESOLVE FIRST: the `parent=` vanilla ability exists; the `State="Restricted"`-inheritance trap is
> handled with an explicit `State="Normal"`; any TargetSort/validator id resolves (`xmlq.py`).

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **`State="Restricted"` inherited from `parent=`** → the autocast button stays restricted and
  never fires; override `State="Normal"` explicitly (open-issues #6 — this cost the "only Yamato
  autocasts" bug).
- **Self-buff with offensive `AutoCastFilters`** → never fires (filters exclude Self). Use
  `AutoCastValidatorArray="CasterIsFiringWeapon"`, not offensive filters.
- **Behavior-class abilities can't autocast at all** — these are effect-style abilities, which can
  ([08](08-autocast-ability.md)).
- **`TargetSorts` orders, it doesn't gate** — the overkill-avoid sort spreads fire but won't
  *exclude* anything; pair with `AutoCastValidatorArray` to skip junk targets
  ([10](10-autocast-priority-targetsort.md)).
- **Don't claim multi-target-no-overkill ships** — it's design only; the BC currently single-targets.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (`DukesRevenge*WoLU`, `WoLUYamatoBigTarget`,
  `CasterIsFiringWeapon` resolve), CHECK4 (parent clones inherit/override Effect), CHECK5 (the
  re-pointed buttons). **Does not prove** any autocast fires, nor that fire spreads. `[STATIC]`
- **In-game (Test Document / owner):** select Jackson's Revenge in a fight → Yamato auto-fires on a
  big target, Missile Pods auto-fire at air, Defensive Matrix auto-shields while attacking;
  attacks ignore armored targets and fire while moving. Observe whether shots **spread or
  overkill** (expected: overkill — the spread system is unbuilt). A late BC mission. `[GAME]`.
- **Editor (Previewer):** the 3 re-pointed buttons render on Jackson's Revenge; autocast/spread are
  runtime, not previewable. `[EDITOR]` limited.

## Parked for bunch-verify
- `[GAME]` — Jackson's Revenge auto-casts all three actives (Yamato on big targets, Missile Pods at
  air, Defensive Matrix while firing); attacks ignore armor + fire on the move.
- `[GAME]` / design — confirm the BC currently **overkills** (single-target); the
  multi-target-no-overkill "smart batteries" spread system is **not shipped** (an un-descended
  `TSTrackedByBattlecruiser`-style sort still needs wiring + in-game iteration).
