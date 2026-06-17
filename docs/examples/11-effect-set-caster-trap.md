# 11 — Reusing a vanilla effect set (the caster-bound member trap)

> A cautionary pattern: pointing a new ability/weapon at a vanilla `CEffectSet` can drag in a
> **caster-specific** member that errors on the new caster and **aborts the whole set** — so
> nothing happens.

**Maps to (request):** Siege Tank "deploy Spider Mines" / open-issues v0.3.7 #11. **Status:**
[STATIC] root cause + [GAME]-flagged. implementation-patterns §11; learnings §"Reusing a vanilla
EFFECT SET…".

---

## Result (the bug this avoids)
You give a non-Vulture unit (Siege Tank / Breaker) an ability that reuses the vanilla
`SpawnSpiderMineSet`, expecting it to drop a mine. It drops **nothing** — and a *sieged*
(immobile) caster fails hardest. The fix points the ability at the **core effect alone**, so the
mine spawns.

## Mechanism
A `CEffectSet` runs **every** member effect. If a member carries a **caster-bound cost or
validator** that only the original caster can satisfy, firing the set from a new caster makes that
member error — and the error **aborts the entire set** (the mine spawn included).

`SpawnSpiderMineSet` has two members:
- `SpawnSpiderMine` — the actual mine (what you want).
- `ReplenishNanoConstructor` — a `CEffectModifyUnit` that **refunds a charge** on the
  **Vulture-only** ability `MakeVultureSpiderMines`. On a Siege Tank, that ability doesn't exist →
  the `Cost Abil=` fails → the whole set aborts.

**Fix:** point your ability's `Effect` at the **core effect** (`SpawnSpiderMine`), not the set.
(learnings.md; implementation-patterns §11.)

## Worked example (real, from this repo)

### The trap (reference catalog — verbatim)
```xml
<!-- mods/_reference/campaigns/liberty.sc2campaign/EffectData.xml:1482 -->
<CEffectSet id="SpawnSpiderMineSet">
    <EffectArray value="SpawnSpiderMine"/>          <!-- the mine (wanted) -->
    <EffectArray value="ReplenishNanoConstructor"/> <!-- the caster-bound trap -->
    <TargetLocationType value="UnitOrPoint"/>
</CEffectSet>
```
```xml
<!-- mods/_reference/campaigns/liberty.sc2campaign/EffectData.xml:504 -->
<CEffectModifyUnit id="ReplenishNanoConstructor">
    <ImpactUnit Value="Source"/>
    <Cost Abil="MakeVultureSpiderMines,Specialize1" ChargeCountUse="-1"/>  <!-- Vulture-only -->
</CEffectModifyUnit>
```

### The fix (our clone — points at the core effect, not the set)
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:416-426 -->
<CAbilEffectTarget id="SpiderMineWoLU">
    <Effect index="0" value="SpawnSpiderMine"/>   <!-- the core effect ALONE, not SpawnSpiderMineSet -->
    <Placeholder value="SpiderMine"/>
    <Range value="4"/>
    <Flags index="IgnoreFacing" value="1"/>
    <Cost><Cooldown TimeUse="1"/></Cost>
    <CmdButtonArray index="Execute" DefaultButtonFace="SpiderMineWoLU" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
```
The `WoLUHaveFlag`-gated button makes it player-only ([07](07-clone-flag-gate.md)); the explicit
`Effect index="0"` avoids the clone-Effect re-default ([07](07-clone-flag-gate.md), CHECK4). The
Tank loses only the (irrelevant) Vulture charge-refund — the mine spawns reliably.

### The general rule
> **Before pointing a new ability/weapon at a vanilla `CEffectSet`, expand its members and check
> each for a caster-bound `Cost Abil=` / validator.** If any member is bound to the original
> caster's ability/state, point at the core effect directly (or build a trimmed set without the
> caster-bound member).

This same check applies to the Thor resurrect chain ([22](22-death-response-resurrect.md)) — the
`ThorReborn`/`ThorWreckage` morphs must be expanded for caster-bound costs before being cloned for
the Jotun (implementation-patterns §7 flag, §11).

## Reusable snippet (swap the ids)
```sh
# RESOLVE FIRST — expand the set and inspect EACH member for a caster-bound cost/validator:
python scripts/xmlq.py get <SOME>Set      mods/_reference/.../EffectData.xml   # list its EffectArray
python scripts/xmlq.py get <eachMember>   mods/_reference/.../EffectData.xml   # look for Cost Abil= / a caster validator
```
```xml
<!-- If a member is caster-bound, target the CORE effect instead of the set: -->
<CAbilEffectTarget id="<ABIL>WoLU">
    <Effect index="0" value="<CORE_EFFECT, not the SET>"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="<Face>" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **A caster-bound `Cost Abil=` aborts the whole set** on a caster that lacks that ability — the
  failure is silent (no mine, no error dialog). Immobile/sieged casters fail hardest.
- **The static gate does NOT catch this** — every id resolves (CHECK3 passes), the set is
  well-formed. It only surfaces in game (or by reading each member by hand). That's why this page
  exists: read the members *before* you wire the set.
- **Don't assume "reuse the vanilla set" is free** — sets are convenient but inherit every
  member's caster assumptions. Targeting the core effect is often the safer call.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3/CHECK4 prove the ids resolve and the clone has a
  real `<Effect>`. **It does NOT prove the set won't abort** — that's the whole point of the trap.
  `[STATIC]` for structure only.
- **In-game (owner / Test Document):** order the non-Vulture caster (Siege Tank, **sieged**) to
  deploy a mine — a mine actually spawns. Mission with Siege Tanks. `[GAME]`
- **Editor (Previewer):** n/a (this is runtime effect resolution, not a render). `[GAME]` only.

## Parked for bunch-verify
- `[GAME]` — a **sieged** Siege Tank (and a Breaker) deploys a Spider Mine via `SpiderMineWoLU`;
  the mine spawns (the `ReplenishNanoConstructor` abort no longer occurs).
