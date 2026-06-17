# 30 — Spider Mines from a sieged (immobile) unit + fix the hotkey collision

> Let a Siege Tank deploy spider mines **in either mode** — including while sieged and unable to
> turn — and give the button its own hotkey so it stops colliding with Enter Siege.

**Maps to (request):** BACKLOG WP-C "Siege Tank Spider Mines — **SHIPPED v0.3.1**"; open-issues
v0.3.7 **#4** (sieged "Can't turn towards target"), **#10** (hotkey shares E with Enter Siege),
**#11** (the caster-bound effect-set abort). **Status:** [STATIC] done; mine deploy + hotkey are
[GAME]. implementation-patterns §11 (effect-set caster trap) + §2 (clone+gate).

---

## Result
The player's Siege Tank (mobile **and** sieged), plus the Siege Breaker merc (both forms), gets a
**Spider Mine** button. Click it, target a point → a spider mine spawns and burrows. It works
while **sieged** (the tank can't turn but deploys anyway), and its hotkey is **Y** — no longer
fighting Enter Siege's **E**.

## Mechanism
Three problems, three fixes, all in the **clone + flag-gate** frame ([07](07-clone-flag-gate.md)):

1. **Sieged can't turn → deploy fails.** A point-target ability normally turns the caster to face
   the target; a **sieged** tank is immobile, so it errors `"Can't turn towards target"`. Fix:
   `<Flags index="IgnoreFacing" value="1"/>` on the ability — deploy without facing.

2. **The vanilla effect *set* aborts on a non-Vulture caster.** The obvious `Effect` to reuse is
   `SpawnSpiderMineSet`, but that's `[SpawnSpiderMine, ReplenishNanoConstructor]`, and
   `ReplenishNanoConstructor` refunds a charge on the **Vulture-only** `MakeVultureSpiderMines`
   ability. On a Siege Tank/Breaker that missing ability aborts the **whole set** → no mine (the
   sieged form fails hardest). Fix: point `Effect` at the **raw create alone**, `SpawnSpiderMine`
   — the mine still spawns + burrows (`CEffectCreateUnit` makes the `SpiderMine` unit, whose own AI
   burrows on idle). This is the canonical caster-bound-set trap ([11](11-effect-set-caster-trap.md)).

3. **Hotkey collision.** The vanilla `SpiderMine` button has no `Hotkey` field, so it inherits the
   base-CASC `Button/Hotkey/SpiderMine = E` — the **same** key as SiegeMode's "Enter Siege". Fix:
   a dedicated `CButton SpiderMineWoLU` (same icon) with its **own** hotkey
   `Button/Hotkey/SpiderMineWoLU=Y`; every spider-mine card button + the ability's
   `DefaultButtonFace` use that face ([26](26-command-card-edits.md)). Enter Siege keeps E.

## Worked example (real, from this repo)

### The ability — IgnoreFacing + the raw create (not the set)
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:416-426 -->
<CAbilEffectTarget id="SpiderMineWoLU">
    <EditorCategories value="Race:Terran,AbilityorEffectType:Units"/>
    <Effect index="0" value="SpawnSpiderMine"/>     <!-- #11: raw create, NOT SpawnSpiderMineSet -->
    <Placeholder value="SpiderMine"/>
    <Range value="4"/>
    <Flags index="IgnoreFacing" value="1"/>          <!-- #4: a SIEGED tank cannot turn -->
    <Cost><Cooldown TimeUse="1"/></Cost>             <!-- 1 s cd; not the Vulture charge system -->
    <CmdButtonArray index="Execute" DefaultButtonFace="SpiderMineWoLU" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
```
The `1 s Cooldown` (not a charge system) is *why* the replenish member is unnecessary — dropping
it loses nothing (`AbilData.xml:406-415` comment).

### The button — its own hotkey (Y), same icon
```xml
<!-- src/mod/Base.SC2Data/GameData/ButtonData.xml:18-21 -->
<CButton id="SpiderMineWoLU">
    <Icon value="Assets\Textures\btn-ability-terran-spidermine.dds"/>
    <AlertIcon value="Assets\Textures\btn-ability-terran-spidermine.dds"/>
</CButton>
```
```text
# src/mod/enUS.SC2Data/LocalizedData/GameHotkeys.txt:2
Button/Hotkey/SpiderMineWoLU=Y
```

### Wired onto all 4 forms (index-override AbilArray + card append)
| Unit | AbilArray | Card button (cell) | cite |
|---|---|---|---|
| SiegeTank (mobile) | `index="4"` | `index="9"` R2C1 | `UnitData.xml:399,404` |
| SiegeTankSieged | `index="3"` | `index="8"` R2C0 | `UnitData.xml:412,414` |
| SiegeBreaker (merc, mobile) | `index="4"` | `index="8"` R2C1 | `UnitData.xml:418,420` |
| SiegeBreakerSieged (merc) | `index="3"` | `index="8"` R2C0 | `UnitData.xml:424,426` |
Each append carries the explicit `index=` = the form's vanilla element count
(`UnitData.xml:407-410` comment). Every card button uses `Face="SpiderMineWoLU"` so they all carry
the Y hotkey.

### Merc/hero reach
The Siege Breaker is a **standard merc** (kind A — its own unit ids `SiegeBreaker` /
`SiegeBreakerSieged`), so it does **not** inherit the base SiegeTank's `AbilArray` override — each
form is wired **explicitly** above (rule 4 parity). This is exactly the standalone-merc reach rule
([06](06-merc-hero-parity.md), implementation-patterns §0.1-A).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: the core create effect (NOT a set with a caster-bound member — expand it!),
     and WoLUHaveFlag. -->
<CAbilEffectTarget id="<NAME>WoLU">
    <Effect index="0" value="<CORE_CREATE_EFFECT>"/>      <!-- not <...>Set if it has a Vulture-only member -->
    <Range value="<r>"/>
    <Flags index="IgnoreFacing" value="1"/>               <!-- only if a sieged/immobile caster uses it -->
    <Cost><Cooldown TimeUse="<n>"/></Cost>
    <CmdButtonArray index="Execute" DefaultButtonFace="<NAME>WoLU" Requirements="WoLUHaveFlag"/>
</CAbilEffectTarget>
<!-- ButtonData.xml: own face so you can give it an own hotkey -->
<CButton id="<NAME>WoLU"><Icon value="<icon.dds>"/></CButton>
<!-- GameHotkeys.txt: Button/Hotkey/<NAME>WoLU=<KEY>   (avoid the inherited base-CASC collision) -->
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **Reusing a vanilla `CEffectSet` with a caster-bound member** aborts on a new caster — expand
  the set and point at the core effect ([11](11-effect-set-caster-trap.md)). The single highest-value
  lesson here.
- **No `IgnoreFacing` on an immobile caster** → "Can't turn towards target", deploy fails.
- **A button with no `Hotkey` field inherits the base-CASC hotkey** → silent collisions (E here).
  Give it its own face + `Button/Hotkey/<id>=<KEY>`.
- **Index-less `AbilArray`/`LayoutButtons` appends** are dropped — set `index=`. Standalone mercs
  need their **own** wiring (no `parent=` inheritance).

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (`SpawnSpiderMine`, `SpiderMineWoLU` ids resolve),
  CHECK4 (effect set), CHECK5 (card cells). **Does not prove** the mine spawns from a sieged tank
  or that Y fires it. `[STATIC]`
- **Editor (Previewer):** the Spider Mine button shows on all 4 forms with the mine icon.
  `[EDITOR]` — add to queue.
- **In-game (Test Document / owner):** select a **sieged** player Siege Tank, press Y (or click
  the button), target a point → a mine spawns and burrows (no "can't turn" error); confirm Enter
  Siege still works on E. Repeat on the Siege Breaker. A mission with Siege Tanks. `[GAME]`.

## Parked for bunch-verify
- `[EDITOR]` — Spider Mine button renders on SiegeTank/SiegeTankSieged/SiegeBreaker/SiegeBreakerSieged.
- `[GAME]` — a **sieged** tank deploys a mine that burrows (no "Can't turn" error); the hotkey is
  Y and does **not** trigger Enter Siege; the mobile form and Siege Breaker both deploy too.
