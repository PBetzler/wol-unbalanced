# 07 — Clone + flag-gate backbone (the structural-change engine)

> Make a **structural** change (a new array entry, an autocast, new targeting, bigger splash)
> apply to the **player only** — via a `*WoLU` clone in static XML, gated by the
> `WoLUnbalancedFlag` upgrade.

**Maps to (request):** every player-only change that can't be a per-player scalar edit — Super
Stim ([08](08-autocast-ability.md)), broadened heal ([09](09-broaden-targeting.md)), smart-Snipe
([10](10-autocast-priority-targetsort.md)), Thor splash ([14](14-enlarge-splash.md)), flatten
([13](13-flatten-attribute-bonus.md)). **Status:** [STATIC] proven; the wiring is the same one
the shipped clones use, and the flag plumbing is [GAME]-confirmed (clones fire only for the
player). See implementation-patterns §2.

---

## Result
A clone ability/weapon/effect that is *structurally* different from vanilla (it has the new
array entry / autocast / filter you couldn't add per-player) — and it takes effect **only for the
human player**, while enemies keep the exact vanilla behavior. Rule 9 preserved.

## Mechanism
`CatalogFieldValueModify` edits one player's copy of a **scalar** field, but it **cannot create
array entries**, and **runtime link edits** (`AbilArray[i].Link`, `WeaponArray[i].Link`,
`LayoutButtons[j].AbilCmd`) are **silent no-ops** ([02](02-no-op-traps.md)). So a structural
change has to live in **static XML** — which is **global** (reaches enemies). The clone
architecture squares that circle: define a `*WoLU` clone with the structure baked in, then gate
it so only the player ever reaches it.

There are **two gating styles**, picked by whether the construct has a *button*:

- **Abilities (have a button) → gate the BUTTON on `WoLUHaveFlag`.** The clone exists for
  everyone, but its `CmdButtonArray` carries `Requirements="WoLUHaveFlag"` — a requirement only
  satisfied by players holding the `WoLUnbalancedFlag` upgrade, which only our library grants, to
  the human player. Enemies never see/use the button.
- **Weapons/effects (fire without a button) → split the BUFF into a validator-gated effect set.**
  You can't gate a button that doesn't exist, so keep the weapon/clone **stat-identical to
  vanilla** and route its `Effect` to a `CEffectSet` of **sibling effects**: one
  `ValidatorArray="WoLUHasFlag"` (the buffed branch) and one `WoLUNoFlag` (the vanilla branch).
  The player hits the buffed branch; everyone else hits vanilla. This is the campaign's
  "Shaped Blast" pattern.

(learnings.md §"Per-player isolation (rule 9) and the clone architecture"; implementation-patterns
§2.)

## Worked example (real, from this repo)

### The flag plumbing (define once, used by every clone)
The whole gate is four tiny entries. The upgrade is an empty marker; our library grants it
per-player at mission start:
```xml
<!-- src/mod/Base.SC2Data/GameData/UpgradeData.xml:5 -->
<CUpgrade id="WoLUnbalancedFlag">
    <EditorCategories value="Race:Terran"/>
</CUpgrade>
```
```xml
<!-- src/mod/Base.SC2Data/GameData/RequirementData.xml:5-12 -->
<CRequirement id="WoLUHaveFlag">       <!-- satisfied iff player holds the flag -->
    <NodeArray index="Use" Link="WoLUCountFlag"/>
</CRequirement>
<CRequirement id="WoLUNoFlagReq">      <!-- the negation, for the vanilla branch -->
    <NodeArray index="Use" Link="WoLUNotCountFlag"/>
</CRequirement>
```
```xml
<!-- src/mod/Base.SC2Data/GameData/ValidatorData.xml:7-14 -->
<CValidatorPlayerRequirement id="WoLUHasFlag"> <Find value="1"/> <Value value="WoLUHaveFlag"/>  </CValidatorPlayerRequirement>
<CValidatorPlayerRequirement id="WoLUNoFlag">  <Find value="1"/> <Value value="WoLUNoFlagReq"/> </CValidatorPlayerRequirement>
```
Note the split: the **`CRequirement`** gates BUTTONS (it's a card requirement); the
**`CValidatorPlayerRequirement`** gates EFFECTS (it's a validator). Same flag, two consumers.

### Style 1 — button-gated ability (Super Stim)
The clone is appended/overridden onto the unit, and only its button carries the flag requirement:
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:28 (inside StimpackWoLU) -->
<CmdButtonArray index="Execute" DefaultButtonFace="Stim" Requirements="WoLUHaveFlag">
    <Flags index="ToSelection" value="1"/>
</CmdButtonArray>
```
Wired into the Marine by an **XML index-override** of the vanilla stim slot (NOT a runtime link
swap — that's a no-op):
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:80,83 -->
<AbilArray index="3" Link="StimpackWoLU"/>          <!-- vanilla stim slot, overridden -->
<LayoutButtons index="5" AbilCmd="StimpackWoLU,Execute"/>
```
Full ability mechanism in [08](08-autocast-ability.md).

### Style 2 — validator-gated effect set (Thor's Hammer splash)
The vanilla weapon `ThorsHammer` is **kept** (so its attack animation still fires — see
[24](24-clone-visuals.md)); only its `Effect` is redirected to a set whose two branches are
flag-gated:
```xml
<!-- src/mod/Base.SC2Data/GameData/EffectData.xml:43-60 -->
<CEffectSet id="ThorsHammerWoLUSet">
    <EffectArray value="ThorsHammerDamageVanillaWoLU"/>   <!-- enemies -->
    <EffectArray value="ThorsHammerDamageWoLU"/>          <!-- player -->
</CEffectSet>
<CEffectDamage id="ThorsHammerDamageVanillaWoLU" parent="ThorsHammerDamage">
    <ValidatorArray value="WoLUNoFlag"/>                  <!-- vanilla branch -->
</CEffectDamage>
<CEffectDamage id="ThorsHammerDamageWoLU" parent="ThorsHammerDamage">
    <ValidatorArray value="WoLUHasFlag"/>                 <!-- buffed branch -->
    <Kind value="Splash"/> <KindSplash value="Splash"/>
    <SearchFilters value="Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
    <AreaArray Radius="1.6" Fraction="1"/>
    <AreaArray Radius="2.5" Fraction="0.5"/>
</CEffectDamage>
```
The buffed branch added splash, so it also sets explicit enemy-only `SearchFilters` — added
area-damage **friendly-fires by default** ([15](15-friendly-fire-safety.md)).

### Wiring: override-in-place vs append-don't-override (read [26](26-command-card-edits.md))
- **Override-in-place** — safe only when the vanilla ability was requirement-gated and the AI
  never gets it (the stim case above: `AbilArray index="3"` directly replaced). Overriding it
  for the player is the same as for the (gated-out) AI.
- **Append-don't-override** — required when enemy AI *actively uses* the vanilla ability (Snipe,
  Obliterate, Yamato). Replacing the slot would lock the requirement-gated clone for AI too and
  change enemy behavior. Instead **append** the clone at the next free `AbilArray` index and
  re-point only the **card button's** `AbilCmd` (cards are pure UI; the AI never reads them).
- **Appends MUST carry an explicit `index=`** (= the unit's vanilla element count). Index-less
  appends are silently **dropped** in our component-folder mod (Magrail was invisible until
  `index="4"`). See [02](02-no-op-traps.md), [26](26-command-card-edits.md).

### Merc/hero reach
The flag gate is **global on the clone**; reach is decided by which ids the merc/hero links
([01 §reach](01-per-player-scalar-stat-edit.md), [06](06-merc-hero-parity.md)). An elite merc
(`parent=` clone, e.g. `MercThor`) inherits the base's `AbilArray`/`WeaponArray` ids, so it
reaches the override automatically. A standalone merc (e.g. `HammerSecurity`) links its **own**
ids — it needs its **own** index-override + button ([18](18-elite-merc-clone.md)).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: confirm <VANILLA_ABIL>, its AbilArray index on <UNIT>, and the card cell
     (python scripts/xmlq.py get <UNIT> .../UnitData.xml ; scripts/audit.py CHECK5 for the merge).

  STYLE 1 — ability with a button: -->
<CAbilEffect... id="<ABIL>WoLU" parent="<VANILLA_ABIL>">
    <Effect index="0" value="<REAL_EFFECT>"/>      <!-- ALWAYS explicit (clone-Effect trap) -->
    <CmdButtonArray index="Execute" DefaultButtonFace="<Face>" Requirements="WoLUHaveFlag"/>
</CAbilEffect...>
<!-- wire on the unit (override-in-place if AI never gets it; else append + re-point button): -->
<AbilArray index="<vanilla-slot-or-next-free>" Link="<ABIL>WoLU"/>

  <!-- STYLE 2 — weapon/effect, no button: keep the weapon id, gate the effect: -->
<CEffectSet id="<WPN>WoLUSet">
    <EffectArray value="<WPN>DamageVanillaWoLU"/>   <!-- WoLUNoFlag branch -->
    <EffectArray value="<WPN>DamageWoLU"/>          <!-- WoLUHasFlag branch -->
</CEffectSet>
<CEffectDamage id="<WPN>DamageVanillaWoLU" parent="<VANILLA_DMG>"><ValidatorArray value="WoLUNoFlag"/></CEffectDamage>
<CEffectDamage id="<WPN>DamageWoLU" parent="<VANILLA_DMG>"><ValidatorArray value="WoLUHasFlag"/> <!-- + your buff + SearchFilters if area --> </CEffectDamage>
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **Runtime link swap is a no-op** — wire clones by **XML index-override**, never
  `CatalogFieldValueModify` on `AbilArray[i].Link`/`WeaponArray[i].AbilCmd`.
- **The clone-Effect re-default trap (CHECK4 FAIL)** — a `CAbil*`/`CWeapon*` clone with no
  `<Effect>` defaults the effect link to its **own (nonexistent) id** and does nothing. Always set
  `<Effect index="0" value="<real-effect>"/>` — even on a `parent=` clone.
- **Override-in-place on an AI-used ability** locks the gated clone for the AI too — use
  append-don't-override there.
- **Index-less append** is silently dropped — every append needs an explicit `index=`.
- **Area effect with no `SearchFilters`** friendly-fires ([15](15-friendly-fire-safety.md)).
- **Never clone a unit *type*** (mission scripts check them) — clone abilities/weapons/effects;
  the elite-merc carve-out is the only unit-clone exception ([18](18-elite-merc-clone.md)).

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (FAIL) catches a bad `parent=`/`Effect=`; CHECK4
  (FAIL) catches the missing-`<Effect>` re-default; CHECK5 (WARN) catches a passive-as-action /
  off-array / colliding button. `galaxy_lint.py` proves the apply lib compiles. **Does not prove**
  the gate actually isolates the player. `[STATIC]`
- **In-game (Test Document / owner):** trigger the clone on a player unit (button shows / weapon
  fires the buffed branch); confirm an **enemy** of the same type behaves **vanilla**. `[GAME]`
- **Editor (Previewer):** the gated button's presence on the merged card (it shows because the
  Previewer is the static catalog; this does not prove the runtime grant). `[EDITOR]`

## Parked for bunch-verify
- `[GAME]` — fire a flag-gated clone on a player unit and confirm the **enemy** copy stays
  vanilla (the isolation works end-to-end). One per newly-gated clone.
- `[EDITOR]` — the `WoLUHaveFlag`-gated button appears on the player unit's merged card.
