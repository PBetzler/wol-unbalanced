# VERIFIED implementation patterns — double-check against this before/after every change; update it when a pattern is found wrong.

The authoritative "how to implement X" reference for WoL Unbalanced. Built by reading
our XML (`src/mod/Base.SC2Data/GameData/`), `scripts/genlib.py`, and the reference
catalogs under `mods/_reference/`, citing `file:line`. It exists because the recurring
bug classes were (1) guessing a mechanism and (2) editing a base id that silently never
reaches the merc/hero. Compare a change against the relevant pattern before writing it,
and re-check side effects after.

**Confidence legend** used throughout:
- **[STATIC]** — proven from the catalogs/schema here; the mechanism is correct.
- **[GAME]** — needs the owner's in-game playthrough or the SC2 API harness to confirm
  the *effect* (a value reflected, a card shown, an autocast firing, an asset rendering).
- **[ASSUMPTION]** — a value or semantic taken on faith (e.g. AP's exact numbers); flagged
  where it lives.

Two cross-cutting facts that every pattern leans on (from `docs/learnings.md`, re-verified):
- `CatalogFieldValueModify(catalog, id, field, player, value, op)` edits ONE player's copy
  of an **existing scalar-ish field**. It **cannot create array entries**, and **runtime
  LINK edits** (`AbilArray[i].Link`, `WeaponArray[i].Link`, `LayoutButtons[j].AbilCmd`) +
  **indexed-array element edits** (`Options[]`, `AreaArray[]`, `AttributeBonus[...]` on some
  effects) are **silent no-ops**. [STATIC, confirmed in game per learnings]
- Static XML is **global** (reaches enemies). Safe there: pure definitions, and additions
  to **player-exclusive** units (heroes, mercs). Player-only changes to *shared* units go
  through per-player runtime edits OR validator-gated `*WoLU` clones gated by the
  `WoLUnbalancedFlag` upgrade (only our lib grants it, only to the human player).

---

## 0. THE CENTRAL QUESTION — does an edit reach mercs and heroes?

This is the root cause of several active bugs. The answer is **not uniform**; it depends on
the *kind of id you edit* and *how the merc/hero is defined*. There are TWO different kinds
of "merc", and they behave oppositely.

### 0.1 The two merc kinds (this distinction is everything)

**(A) Standard campaign mercs are STANDALONE units with their OWN ids — they share nothing
by inheritance.** Verified: `HammerSecurity` (the Marauder merc) is a fully-spelled-out
`<CUnit id="HammerSecurity">` with `LifeMax=125`, its own `<AbilArray Link="StimpackMarauder"/>`,
and **its own weapon** `<WeaponArray Link="HammerSecurity"/>` — NOT `parent="Marauder"`, NOT
`PunisherGrenades` (`mods/_reference/campaigns/liberty.sc2campaign/UnitData.xml:4178`, weapon
link at the `WeaponArray` line in that block). So:
- A per-unit edit on `Marauder` (e.g. `LifeArmor +2`) does **NOT** reach `HammerSecurity`.
- A weapon edit on `PunisherGrenades` (Marauder's weapon) does **NOT** reach the merc — its
  weapon is the distinct id `HammerSecurity`.
- An ability edit on `StimpackMarauder` (a shared ability id) **DOES** reach the merc,
  because the merc's `AbilArray` links the same `StimpackMarauder` id.
- This is exactly why genlib hand-mirrors every headline buff onto the merc's *own* ids:
  e.g. `("Weapon", "HammerSecurity", "Range", "1", "Add", ...)` and
  `("Unit", "HammerSecurity", "LifeArmor", "2", "Add", ...)` (`scripts/genlib.py:421-423`),
  and the Marine-merc range via `KelmorianMinerGaussRifle` (`genlib.py:325`), Swann via
  `DutchConcussiveGrenade` (`genlib.py:424`). The HERO heroes (`Raynor*`, `Swann`, `Nova`,
  `Tosh`, `Odin`, `DukesRevenge`) are the same story — distinct unit ids and usually distinct
  weapon ids — and are likewise listed explicitly in `HERO_MERC_UNITS` (`genlib.py:21-27`)
  and the parity sweep (`genlib.py:293-507`). [STATIC]

**(B) The 6 ELITE mercs ARE `parent=` clones of the base unit** (`MercMedic parent="Medic"`,
`MercThor parent="Thor"`, `MercWraith parent="Wraith"`, `MercHellion parent="Hellion"`,
`MercReaper parent="Reaper"`, `MercSeniorGhost parent="Ghost"` —
`src/mod/Base.SC2Data/GameData/UnitData.xml:486-587`). A `parent=` clone inherits the base's
**static** definition at load: its `WeaponArray`, `AbilArray`, `BehaviorArray`, etc. So:
- `MercThor` has **no** `WeaponArray` override → it inherits `Thor`'s `ThorsHammer` /
  `JavelinMissileLaunchers` weapon **ids** (verified: `MercThor parent="Thor"` block has no
  `WeaponArray` line, `UnitData.xml:526-550`).
- Therefore a **runtime per-player edit on the shared id `ThorsHammer`** (e.g. the windup cap,
  the range +1) **DOES** reach `MercThor` — because the clone fires the *same weapon id* the
  edit targets. Same for any shared `AbilArray`/`BehaviorArray` id it inherits.
- But a **per-unit edit on `Thor`** (e.g. `("Unit","Thor","Sight","2","Add")`) does **NOT**
  reach `MercThor` — `MercThor` is a different unit id; the engine applied the edit to `Thor`'s
  per-player unit record, not the clone's. (This is why elite-merc stats are set either on the
  clone directly in static XML — `MercThor LifeMax=500` — or on the `Merc*` id in genlib —
  `MercSeniorGhost` 1.5× via `genlib.py:501-505`.)

### 0.2 The definitive rule

> An edit reaches another unit **iff that unit links the exact id the edit targets** at the
> moment the edit applies.
> - **Shared WEAPON/EFFECT/ABILITY/BEHAVIOR id** edited per-player → reaches every unit
>   (base, merc, hero) that links that same id — UNLESS the edit is an indexed-array /
>   link no-op (then it reaches *no one*).
> - **Per-UNIT-id** edit (`LifeMax`/`armor`/`Sight`/`Speed` on "Thor") → reaches ONLY that
>   exact unit id. Mercs/heroes need their **own** unit id added to the edit list.
> - **Static `parent=` inheritance** gives a clone the base's *static* definition (and thus
>   makes it link the base's shared ids), but it does **NOT** carry our *runtime per-player*
>   per-unit modifications of the base id.

### 0.3 Checklist — "to make base-unit change X also affect merc/hero Y, do Z"

1. Identify what X edits:
   - a **shared sub-id** (weapon/effect/ability/behavior link) → go to 2.
   - a **per-unit field** (`LifeMax`, `Sight`, `Speed`, `LifeArmor`, `Food`, `Cost*`) → go to 3.
2. **Shared sub-id**: does Y link the SAME id?
   - Standard merc (kind A): usually **NO** (distinct weapon id; sometimes same ability id).
     Add an explicit edit on Y's own id (find it via `xmlq.py get <Y> .../UnitData.xml`).
   - Elite merc / hero clone (kind B, `parent=`): **YES** for inherited links → the existing
     per-player edit already reaches it; do nothing extra. (Confirm Y has no override of that
     `WeaponArray`/`AbilArray` index.)
   - And confirm X is not an **indexed-array/link no-op** (§0 cross-cutting facts) — if it is,
     it reaches no one and needs the clone pattern (§2.x).
3. **Per-unit field**: add Y's own unit id to the edit list (genlib `stat_edits` for runtime,
   or the clone's static XML if Y is player-exclusive). For the % advantage, recompute Y's
   value as **buffed-base × original-ratio**, not a flat copy (see the SpartanCompany lesson,
   §1.4).
4. Re-run `python3 scripts/audit.py` (CHECK3 catches a typo'd id; CHECK5 catches a card miss).
5. Mark the verification as [STATIC] (id resolves, field class matches a known-working one) vs
   [GAME] (value reflected / asset rendered) — never conflate them in the summary.

---

## 1. Per-player unit stat edits (LifeMax, armor, speed, cost, sight)

**What it changes:** a scalar field on one unit id, for the human player only.
**Mechanism:** `CatalogFieldValueModify(c_gameCatalogUnit, "<id>", "<Field>", p, "<v>", op)`
emitted from genlib `stat_edits` (`scripts/genlib.py:199-508`). Ops: `Set`/`Add`/`Subtract`/
`Multiply`. Indexed scalar fields like `CostResource[Vespene]`, `CostResource[Minerals]` work
(same class as the known-good cost cuts — `genlib.py:206-239`).
**Reference example (working):** Marine +20 HP — `Marine`/`LifeMax`/`LifeStart` Add 20
(`genlib.py:140-143`); enemy marines stay 45 (verified in game per plan §7 M2). Firebat ×2 HP
via `Multiply` then `+100` Kinetic Foam (`genlib.py:201-202`, `genlib.py:352-353`).
**Known no-op traps:**
- **`CargoSize` per-UNIT is a LOAD-time read** — the runtime per-player edit does NOT reach the
  bunker (Ghost still took 2 slots). [STATIC + GAME-confirmed] The working lever is the
  **transport ability's** scalar fields (`MaxCargoCount`/`MaxCargoSize`/`TotalCargoSpace` on
  `BunkerTransport`/`MedivacTransport`), which DO apply per player — `genlib.py:257-259`,
  `genlib.py:343-344`; learnings "Per-player `MaxCargoCount` …".
- A misspelled id is a silent no-op (`GuassRifle` is Blizzard's real typo — `genlib.py:318`).
  Verify every id with `xmlq.py` before writing.
**Merc/hero reach:** per §0.2 — per-unit fields reach ONLY that id. Heroes/standard-mercs are
listed explicitly (`HERO_MERC_UNITS`, `genlib.py:21-27`; parity sweep `genlib.py:293-507`).
Elite-merc per-unit stats are set on the `Merc*` id (static XML literals, or genlib Multiply
for SeniorGhost). [STATIC]
**Confidence:** scalar stat edits [STATIC] resolve + apply; the *displayed/observed* result is
[GAME] only where a load-time/indexed trap is suspected.

### 1.4 The % advantage recomputation (mercs)
A merc's "+X% over the counterpart" must be recomputed against the **buffed** base, or the merc
falls behind. Lesson: SpartanCompany base 165 / Goliath base 125 → ratio 1.32; buffed Goliath =
125 + 25 (Shaped Hull) = 150 → parity needs 150 × 1.32 ≈ 198, so the merc's flat add is **+33**
(165→198), not +25 (`genlib.py:452-458`; open-issues "Spartan Company HP"). [STATIC math; GAME
to confirm the merc reads ~198]

---

## 2. Clone + flag-gate architecture (the structural-change backbone)

When a change is structural (new array entry, autocast, new targeting, new splash) it can't be
a per-player runtime edit. Define a `*WoLU` clone in static XML and gate it so only the player
uses it. Two gating styles:

- **Abilities (have a button):** gate the **button** on the `WoLUHaveFlag` requirement —
  `<CmdButtonArray index="Execute" ... Requirements="WoLUHaveFlag">`. The ability exists for
  everyone but only the flagged player sees/uses the button. Reference: every clone in
  `AbilData.xml` (e.g. `StimpackWoLU` button `AbilData.xml:28`).
- **Weapons/effects (fire without a button):** can't gate a button, so keep the clone
  stat-identical to vanilla and split the BUFF into a validator-gated **effect set** — sibling
  effects, one `ValidatorArray="WoLUHasFlag"` (buffed) and one `WoLUNoFlag` (vanilla). The
  player hits the buffed branch, enemies hit the vanilla branch. This is the campaign's "Shaped
  Blast" pattern. Reference: `ThorsHammerWoLUSet` (`EffectData.xml:43-60`) and the validators
  `WoLUHasFlag`/`WoLUNoFlag` (`ValidatorData.xml:7-14`).
**Wiring the clone in:** XML **index-override** of the vanilla `AbilArray`/`LayoutButtons` slot
(never a runtime link swap — that's a no-op). Two sub-cases, both proven:
- **Override-in-place** when the vanilla ability was requirement-gated and the AI never gets it
  (the stim case): `<AbilArray index="3" Link="StimpackWoLU"/>` (`UnitData.xml:80`).
- **Append-don't-override** when enemy AI actively uses the vanilla ability (Snipe, Obliterate,
  Yamato): append the clone at the next free index and re-point only the card BUTTON's
  `AbilCmd` (cards are pure UI, AI never reads them). Reference: Ghost
  `AbilArray index 10/11` + button re-points (`UnitData.xml:197-207`); learnings
  "Append, don't override …".
**Append rule:** array appends MUST carry an explicit `index=` (= the unit's vanilla element
count); index-less appends are silently dropped in our dependency mod. [STATIC + GAME-proven
on Magrail] (`UnitData.xml:79-114` comment; learnings).
**Clone-Effect trap:** a `CAbilEffect*`/`CWeapon*` clone with **no `<Effect>`** re-defaults the
effect link to its OWN id (nonexistent) and does nothing. Always set `<Effect index="0"
value="..."/>` explicitly — even `parent=` clones (`YamatoWoLU` Effect=`Yamato`,
`AbilData.xml:163`; `HealWoLU` Effect=`heal`, `AbilData.xml:531`). `audit.py` CHECK4 fails on
this. [STATIC]
**Never clone unit TYPES** — mission scripts check unit types. (Elite mercs are the carve-out:
their ids never appear in WoL maps, so cloning is safe there.) [STATIC, learnings]

---

## 3. Ability clone + autocast — the Super Stim pattern (Bug 1: merc super stim)

**What it changes:** gives a unit an effect-style ability that the engine can **autocast**.
**Mechanism (verbatim from NCO `SuperStimpackMarine`/`Marauder`):** a `CAbilEffectInstant`
with `Effect index="0"` → a `CEffectSet` (apply buff + `CEffectModifyUnit` heal), autocast via
**ability-level** `<Flags index="AutoCast"/>` + `<Flags index="AutoCastOn"/>`,
`AutoCastValidatorArray="CasterIsFiringWeapon"` (perma-stim while fighting), 18 s cooldown.
Reference: `StimpackWoLU`/`StimpackMarauderWoLU` (`AbilData.xml:13-53`), effect chain
`WoLUStimSet`→`WoLUStimApply`(buff `WoLUSuperStim`)+`WoLUStimSetMU`(heal 30/60)
(`EffectData.xml:10-34`), buff `WoLUSuperStim` (`BehaviorData.xml:8-14`).
**Schema gotchas (cost two sessions, do not re-derive):** `Effect` needs `index="0"` or the
ability has no effect; `AutoCast`/`AutoCastOn` are **ability-level** flags, NOT `CmdButtonArray`
flags; effect chain heals use the attribute form `<VitalArray index="Life" Change="30"/>` and
target `Source`. **Behavior-class abilities (`CAbilBehavior`, e.g. cloaks) cannot autocast at
all** — that's why stim had to be rebuilt as `CAbilEffectInstant`. [STATIC + GAME-VERIFIED
(stim autocast confirmed in game, plan §7)]
**Cross-type one-button firing:** `<AbilSetId value="Stimpack"/>` (`AbilData.xml:17`) +
`<Flags index="ToSelection" value="1"/>` make one button stim every selected unit whose ability
shares the set. [STATIC]

### 3.1 Bug 1 — Hammer Securities (Marauder merc) has no super stim
**Root cause (per §0.1-A):** `HammerSecurity` is a STANDALONE unit, not a `parent="Marauder"`
clone. We added `StimpackMarauderWoLU` to the base Marauder by overriding its `AbilArray
index 3` (`UnitData.xml:122-123`). The merc's `AbilArray` links the **vanilla** `StimpackMarauder`
(`liberty.sc2campaign/UnitData.xml:4178` block), and we did add an index-3 override for the merc
— **but only on `HammerSecurity`'s ability**, at `UnitData.xml:144-146`:
`<CUnit id="HammerSecurity"><AbilArray index="3" Link="StimpackMarauderWoLU"/></CUnit>`. So the
*ability* is swapped, but there is **no card-button** override on `HammerSecurity` — its merged
card still shows the vanilla stim button (or none, if the campaign turned it passive), so the
super-stim autocast may be present without a working/visible button, OR (more likely from the
report) the campaign's `HammerSecurity` card has the stim button at an index we never re-pointed.
**Candidate fix direction (cite §3 + §2 append-rule):** compute `HammerSecurity`'s EFFECTIVE
merged card (card-merge simulator / `audit.py` CHECK5), find the stim button index, and either
re-point it to `StimpackMarauderWoLU,Execute` or APPEND a fresh `Type=AbilCmd` stim button at
the next free index in a free cell (the Marauder #3 fix pattern, `UnitData.xml:115-128`). Verify
the merc's `AbilArray index 3` is actually `StimpackMarauderWoLU` in the merged unit (it is, per
the override) — the gap is the **button**, not the ability. [STATIC root cause; GAME to confirm
the button appears + autocasts]
**Note:** because `StimpackMarauderWoLU`'s button is gated on `WoLUHaveFlag`, the merc is
player-exclusive so the gate is always satisfied — fine.

---

## 4. Ability TargetFilters / heal clone — Adaptive Medpacks (Bug 2: medic can't heal mech)

**What it changes:** broadens what an ability can target (heal mechanical + air).
**Mechanism:** `TargetFilters` is a **STRING field** → a per-player runtime edit is a **silent
no-op** (the genlib attempt at `genlib.py:371` never took — owner report). The fix is a `parent=`
clone of `heal` with a broadened `TargetFilters` + explicit `Effect=heal`. Reference:
`HealWoLU` (`AbilData.xml:527-534`). The vanilla gate is `Ground,Biological,...` on `heal`
(verified `liberty.sc2campaign/AbilData.xml` `heal` block: `TargetFilters value="Ground,
Biological,Visible;..."`); `HealWoLU` drops `Ground,Biological` to allow mech + air.
**Verification — the mechanism looks statically CORRECT (a surprise):** I traced every gate
that could still block mechanical and found NONE that survives the clone:
1. The working BUTTON is pointed at `HealWoLU`: the Medic's merged heal button is **index 6**
   (vanilla `heal,Execute` at cell 2,0); v0.3.7 #5 re-points it `<LayoutButtons index="6"
   AbilCmd="HealWoLU,Execute"/>` (`UnitData.xml:316`). [STATIC — confirm index 6 in the merged
   card; Stetmann re-points its `BonesHeal` button similarly at `UnitData.xml:336`.]
2. `HealWoLU` is on the `AbilArray` (`Medic AbilArray index 6`, `UnitData.xml:307`). [STATIC]
3. The clone heals via `Effect index="0" value="heal"` (`AbilData.xml:531`) → the real
   `CEffectCreateHealer "heal"`, whose `ValidatorArray` is `noMarkers, NotWarpingIn,
   HiddenCompareAB/BA, NotVortexd` (`liberty.sc2campaign/EffectData.xml` heal block) — **NONE
   gate Biological/Mechanical**. [STATIC, CHECK4-clean]
4. `HealWoLU`'s `TargetFilters` correctly drops `Ground,Biological`:
   `Visible;Self,Enemy,Structure,Missile,UnderConstruction,Dead,Hidden,Invulnerable`
   (`AbilData.xml:532`) — no bio/ground requirement remains. [STATIC]
5. The inherited autocast/smart filters do NOT gate by attribute either: vanilla `heal`'s
   `SmartValidatorArray` is `healSmartTargetFilters` = `CValidatorUnitFilters Filters="-;Enemy"`
   (just excludes enemies — `liberty.sc2mod/ValidatorData.xml:1318`) + `NotWarpingIn`; its
   `AutoCastFilters` is `Visible;Neutral,Enemy` (excludes neutral/enemy only). **No
   Biological/Mechanical gate anywhere.** [STATIC — this corrects an earlier draft hypothesis
   that the smart-validator blocked mechanical; it does not.]

**Conclusion:** statically, `HealWoLU` SHOULD heal mechanical + air, both manual AND autocast.
So the persistence of Bug 2 is **most likely a [GAME] observation/wiring issue, not a missing
filter override**. Candidate causes to check in game, in order:
- **The merged heal button index isn't actually 6** for the campaign Medic (the re-point landed
  on a different/passive cell) → run the card-merge simulator on `Medic` and confirm the cell
  carrying the visible heal button is the one re-pointed to `HealWoLU,Execute`. (Most likely.)
- The owner tested **autocast** and the heal *did* fire but slowly (`CEffectCreateHealer` heals
  over time) and wasn't noticed; or tested on a full-HP mech (no visible heal).
- A `parent=heal` field the clone needed to re-state didn't merge (re-`get` the *merged*
  `HealWoLU` in game via a diag line if needed).
[STATIC: mechanism correct; GAME: which of the above — start by confirming the button cell.]
**Merc/hero reach:** Skibi's Angels = `MercMedic parent="Medic"` inherits `HealWoLU` via the
`AbilArray` (kind B). Stetmann is a distinct unit and gets its own re-point (`UnitData.xml:336`).
[STATIC]

---

## 5. Weapon Options for simultaneous air+ground fire (Bug 4: Jotun can't fire both)

**What it changes:** lets a 2-weapon unit fire BOTH weapons at once instead of sharing one
cooldown.
**Mechanism (verified semantics, Goliath Multi-Lock pattern):** with **no `Options` block**,
`LinkedCooldown` defaults to **1** → the unit's weapons share one cooldown clock → only one
fires at a time. The independent-fire flags are three `Options[]` entries:
`LinkedCooldown=0`, `OnlyFireWhileInAttackOrder=0`, `OnlyFireAtAttackOrderTarget=0`. These live
on the Goliath's `*Upgraded` weapons (the Multi-Lock upgrade only un-hides those weapons; the
flags are on the weapon defs). Reference: our copy onto `ThorsHammer` +
`JavelinMissileLaunchers` + `Odin` + `OdinAntiAir` (`WeaponData.xml:11-50`).
**KEY no-op trap:** `Options[]` is an **INDEXED array** → a per-player `CatalogFieldValueModify`
on it is a **silent no-op**. So this MUST be **static XML** — which is **GLOBAL**: enemy Thors
also gain simultaneous fire. Accepted tradeoff (few/zero enemy Thors in WoL), documented at
`WeaponData.xml:22-27`. [STATIC; the simultaneous-fire EFFECT is GAME — owner confirms.]
**Merc/hero reach:** `MercThor` (kind B, `parent="Thor"`, no `WeaponArray` override) fires the
same `ThorsHammer`/`JavelinMissileLaunchers` ids → the static Options edit reaches it
automatically. Odin (hero) handled by the explicit `Odin`/`OdinAntiAir` edits. [STATIC]

---

## 6. Attack windup / "time to first shot" (Bug 4: Jotun windup >> 0.1s)

**What it changes:** the rule-7 cap on the pre-damage swing.
**The REAL field(s) — identified:**
- **`DamagePoint`** = the pre-damage swing ("windup"). This is the rule-7 field. Capped to 0.1
  per player on every player-unit weapon by the rule-7 pass (`genlib.py:152-165`), and on
  `ThorsHammer` specifically (it's in the player weapon list via `Thor`).
- **`Backswing`** = post-damage recovery (does NOT delay the first shot but reads as sluggish).
  Thor's was trimmed: `ThorsHammer`/`Odin` `Backswing=0.1` (`genlib.py:273-275`).
- **`Period`** = time between shots (attack rate). Thor's slow 1.93 s `Period` read as a long
  "windup" even with `DamagePoint` capped — the real culprit behind "Thor felt slow". Fixed via
  Rapid Reload: `ThorsHammer`/`Odin` `Period=1.0` (`genlib.py:272-274`; open-issues "Thor ground
  attack felt slow", RESOLVED v0.2.3). [STATIC + GAME-confirmed it was Period, not DamagePoint.]
- NOT a unit-actor animation field for our purposes — the timing is weapon-data, and the attack
  ANIMATION binds to the weapon id `WeaponStart.ThorsHammer` (why we never cloned the weapon).
**Where Thor's values live + reach:** all on the shared weapon ids `ThorsHammer` (AG) and
`JavelinMissileLaunchers` (AA). The per-player `DamagePoint`/`Period`/`Backswing` edits are on
those ids → reach `MercThor` (inherits them via `parent="Thor"`, kind B) and base Thor; Odin via
the explicit `Odin`/`OdinAntiAir` edits. **There is no `ThorsHammerWoLU` clone anymore** — the
weapon id is kept and only its `Effect` is overridden (`WeaponData.xml:11`), so the windup cap on
`ThorsHammer` is the live path. [STATIC; GAME to confirm the Jotun's first-shot delay is ≤ ~0.1
and the rate feels fast — if it still reads slow, check the AA `JavelinMissileLaunchers` Period
(NOT currently capped) and the unit-actor `PreswingZ`/attack-prep, which we have not edited.]
**Open uncertainty to flag:** the rule-7 pass caps `DamagePoint` but does NOT touch `Period` on
the AA weapon `JavelinMissileLaunchers` — if the owner's "windup" complaint is about the AA
missile cadence, that's a separate `Period` edit, not covered. [GAME to disambiguate.]

---

## 7. Death-response resurrect — Immortality Protocol (Bug 4: Jotun rebuilds wrong)

**What it changes:** a fatal hit morphs the unit into a wreck that rebuilds, instead of dying.
**Mechanism (verified chain):** `ThorDontDie` is a `CBehaviorBuff` with
`<DamageResponse><Fatal value="1"/><Handled value="ThorWreckage"/></DamageResponse>`, gated on
`Requirements="UseMechanicalRebirth"` (we auto-grant that upgrade). Verified verbatim:
`mods/_reference/campaigns/liberty.sc2campaign/BehaviorData.xml:2117`. The wreck →
`ThorReborn` rebuilds — and the morph's `InfoArray Unit="Thor"` rebuilds a **base `Thor`**, not
a `MercThor`, AND charges Thor's gas cost → the "costs gas" tooltip + a TWO-HP-bar rebuilt unit.
**Why it broke on the Jotun:** `MercThor parent="Thor"` inherits the Thor's `BehaviorArray`,
whose index 1 is `ThorDontDie` (verified order: `[0]=ScavengingSystemsMechDeath,
[1]=ThorDontDie` in `libertystory.sc2campaign/UnitData.xml` Thor block). So the merc auto-revives
*as a base Thor*. [STATIC]
**Current state (v0.3.7 #9):** STRIPPED from the Jotun via the tombstone
`<BehaviorArray index="1" removed="1"/>` (`UnitData.xml:549`) — it just dies (unlimited calldown
charges, drop another). [STATIC]
**Owner now wants it to WORK — the verified pattern to resurrect a `MercThor` AS ITSELF:**
The reborn unit id is determined by the **morph/rebuild chain off `ThorWreckage`** (the
`ThorReborn` ability's `InfoArray Unit="Thor"`), NOT by the death-response behavior. To make the
Jotun revive as itself you must give the merc a **parallel resurrect chain** pointing at
`MercThor`, not reuse the Thor one:
1. Keep a death-response on `MercThor` (don't tombstone it) → but point it at a NEW wreck id
   (e.g. `MercThorWreckage`, a `parent="ThorWreckage"` clone) so the merc's wreck is distinct.
2. Clone the rebuild ability (`MercThorReborn parent="ThorReborn"`) with `InfoArray Unit="MercThor"`
   and **zero resource cost** (drop the gas) — this is what fixes BOTH the wrong-identity rebuild
   and the gas-cost tooltip.
3. Clone the death-response behavior (`MercThorDontDie parent="ThorDontDie"`) with
   `Handled="MercThorWreckage"`, and replace the inherited `BehaviorArray index 1` with it
   (override, not tombstone).
All ids must resolve (`audit.py` CHECK3/CHECK4). Because `MercThor` is player-exclusive, no flag
gate is needed. [STATIC design; GAME to confirm it revives as a Jotun, no gas, single HP bar.]
**Flag:** the morph-chain field names (`InfoArray Unit=`, `Handled=`) are cited from the Thor
chain; the exact `ThorReborn`/`ThorWreckage` definitions should be re-read with `xmlq.py` before
implementing, as the rebuild ability may carry additional caster-bound costs (cf. the
`ReplenishNanoConstructor` trap, §11).

---

## 8. Armor display on shielded clones (Bug 3: shielded units need normal armor shown too)

**What it changes:** the inspect panel's defense category indicators on a unit that has BOTH
life-armor and a shield.
**Mechanism — TWO separate string-key fields, both required:**
- `LifeArmorName` = the normal life-armor sign. `ShieldArmorName` = the shield (Defensive
  Matrix) sign. Both must be a **string-table KEY**, not a literal — a raw value shows
  "unknown".
- A `parent=` clone does **NOT** reliably surface the base unit's `LifeArmorName` either, so it
  must be set **explicitly** on the clone (= the base unit's vanilla value).
Reference (our clones): each elite merc sets BOTH — e.g. `MercMedic`
`ShieldArmorName="Unit/ShieldArmorName/WoLUDefensiveMatrix"` +
`LifeArmorName="Unit/LifeArmorName/TerranInfantryArmor"` (`UnitData.xml:495-496`); vehicle mercs
use `TerranVehiclePlating`, ship mercs `TerranShipPlating` (`UnitData.xml:520,536,565`).
**Key resolution (verified):** `Unit/ShieldArmorName/WoLUDefensiveMatrix=Defensive Matrix` exists
in our `src/mod/enUS.SC2Data/LocalizedData/GameStrings.txt:54`; the vanilla `Terran*` keys
resolve in `mods/_reference/mods/liberty.sc2mod/UnitData.xml` (and the campaign catalog).
`audit.py` CHECK7 verifies every armor key we set resolves. [STATIC, CHECK7-clean]
**Why v0.3.8's `LifeArmorName` add may not be "sufficient" (Bug 3):** CHECK7 only proves the KEY
RESOLVES (no "unknown" text). It does NOT prove the engine renders BOTH the life-armor icon AND
the shield icon side-by-side in the inspect panel — that's a UI/preload behavior. The reported
"shielded units need the normal armor shown too" is about the **icon/indicator** appearing, which
is [GAME]-only. The static piece (both keys set + resolving) is done; the visible-both-indicators
piece awaits the owner. [STATIC done; GAME for the dual indicator + the heart-portrait piece is
separate, CHECK6 = portrait-ok but still GAME].
**Merc/hero reach:** elite mercs set these on their own `Merc*` id (player-exclusive static XML).
Base units already have vanilla `LifeArmorName`; shields are merc-only, so base units don't need
`ShieldArmorName`. [STATIC]

---

## 9. Append-don't-override card edits + merge-aware indices

**What it changes:** adds/repoints command-card buttons without breaking the merged vanilla card.
**Mechanism:** vanilla cards are built across base→campaign→story layers; campaigns *edit* the
arrays (`removed="1"` tombstones, index-less appends to the end). You must compute the
**EFFECTIVE merged card** before choosing an index — `audit.py` CHECK5 simulates the
base→campaign→story→our-mod merge (with `parent=` resolution + `removed`/index-less-append
semantics) and warns on passive-as-action / button-with-no-ability / cell collisions.
**Rules (all GAME-proven the hard way):**
- Appends need an **explicit `index=`** = the unit's vanilla element count (index-less dropped).
- To re-point a button the campaign turned **passive**, APPEND a fresh full `Type=AbilCmd`
  button — overriding only its `AbilCmd` leaves `Type=Passive`/old `Face` (the Marauder stim
  bug, fixed at `UnitData.xml:122-128`).
- `removed="1"` is a real tombstone; a later layer re-setting the same index with a `Link`
  re-occupies it.
- Hero rows are often fully occupied (RaynorCommando 2,1; Raynor 2,0-2,3; Tychus/Firebat 2,0/2,1)
  — pick a verified free cell (`UnitData.xml:8-13` comment block).
Reference: the whole Ghost/Spectre/Nova/Tosh card layout (`UnitData.xml:197-216`, `448-467`);
the CC single-MULE re-point (`UnitData.xml:357`); the merc root-card layout (`UnitData.xml:608-617`).
[STATIC via the simulator; GAME for the buttons actually appearing — a dependency-mod whole-new-
`CardLayouts`-page was the one structural thing flagged unverified, now avoided by using root.]
**`audit.py` checks here:** CHECK5 (WARN) + the #3-class check (WARN: a passive Face implying a
capability the unit lacks — Shaped Hull on a Medic).

---

## 10. SearchFilters on cloned/added area effects (friendly-fire safety)

**What it changes:** stops a new/cloned area-damage effect from hitting your own units.
**Mechanism:** cloned/added area-damage effects **friendly-fire by default**. Always set an
explicit `SearchFilters` — the Crucio enemy-only pattern:
`<plane>;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable`. Plane is `Ground`
for ground splash, `Air` for AA splash, `-` for both.
Reference: `ThorsHammerDamageWoLU` SearchFilters `Ground;...`
(`EffectData.xml:56`); the AA buffed branch uses `Air;...` (`EffectData.xml:93`); Viking
`TwinGatlingCannonsWoLU` `Ground;...` (`EffectData.xml:114`); EMP Shockwave `-;...`
(`EffectData.xml:181`). [STATIC; GAME to confirm no self-damage observed.]

---

## 11. Reusing a vanilla EFFECT SET — the caster-bound trap

**What it changes:** (a cautionary pattern, not a feature) — pointing a new ability/weapon at a
vanilla `CEffectSet`.
**Trap:** a vanilla set can include a **caster-specific** member that errors on a new caster and
aborts the WHOLE set. Verified: `SpawnSpiderMineSet = [SpawnSpiderMine,
ReplenishNanoConstructor]`; `ReplenishNanoConstructor` refunds a charge on the **Vulture-only**
`MakeVultureSpiderMines` ability → on a Siege Tank caster the missing-ability cost aborts the set
→ no mine (sieged fails hardest). Fix: point at the core effect alone (`SpawnSpiderMine`), not the
set. Reference: `SpiderMineWoLU` Effect=`SpawnSpiderMine` (`AbilData.xml:416-426`; open-issues
v0.3.7 #11). **Rule:** before pointing at a vanilla `CEffectSet`, expand its members and check
each for a caster-bound `Cost Abil=`/validator. [STATIC + GAME-flagged]
**Relevance to Bug 4 (§7):** apply this same check to the `ThorReborn`/`ThorWreckage` rebuild
chain before cloning it for the Jotun.

---

## 12. Visual actors bind to ids — clones lose visuals

**What it changes:** which animations/projectiles a clone keeps.
**Rule:** `ActorData` events key off ability/weapon/effect **ids** (`Abil.Snipe.SourceCastStart`,
`WeaponStart.ThorsHammer.AttackStart`, `Effect.Yamato.*`). A clone with a NEW id inherits NONE.
Mitigations (all in learnings, re-confirmed in our XML):
- A clone that **reuses the vanilla EFFECT id** keeps the effect-bound visuals (projectiles,
  beams, impacts) — only ability/weapon-bound caster animations (stim puff, cast poses) are lost
  (cosmetic). E.g. `SnipeWoLU` Effect=`SnipeDamage`, `YamatoWoLU` Effect=`Yamato`.
- **Don't clone a WEAPON if you can avoid it** — override the vanilla weapon's `Effect` instead,
  so `WeaponStart.<id>` animations still fire. This is exactly why `ThorsHammer` is kept and only
  its `Effect` is redirected (`WeaponData.xml:1-31`), and why there is no `ThorsHammerWoLU`.
- Base-CASC `.m3`/`.dds`/portrait tokens are path-referenceable from any mod but only resolve
  in-game → `audit.py` lists them `UNVERIFIED — confirm in game` (CHECK6 promotes portrait tokens
  to `portrait-ok` if a vanilla actor references the same `PortraitModel`, but it's still [GAME]).
[STATIC for the binding rule; GAME for every asset render.]

---

## 13. Free cloak + permanent-cloak buff + the toggle-order quirk (context for many units)

**What it changes:** rule-8 free cloak, and spawning units cloaked.
**Mechanism:** (a) zero the cloak ability's `Cost[0].Vital[Energy]` and the buff's
`Modification.VitalRegenArray[Energy]` per player (`genlib.py:146-149`, `CLOAK_ABILS`/
`CLOAK_BEHAVIORS` at `genlib.py:50-53`). (b) `PersonalCloakingFree`/`SpectreCloakingFree` are
permanent-cloak BUFFS (`StateFlags[Cloak]=1`, no drain) — `UnitBehaviorAdd` them to make a unit
spawn cloaked; generic across cloak-capable units. (c) The buff leaves the TOGGLE ability OFF, so
the card shows "Cloak On" — issue the On command from the lib:
`UnitIssueOrder(u, Order(AbilityCommand("GhostCloak",0)), c_orderQueueAddToFront)` (no-target
`Order(...)`, `AddToFront`, guarded to idle units). [STATIC + GAME-iterated, learnings.] Not tied
to a specific active bug but governs Ghost/Banshee/Wraith/Spectre/Nova/Tosh/DuskWing/MercWraith/
MercSeniorGhost behavior.

---

## ACTIVE BUGS — most-likely root cause + candidate fix (per the verified patterns above)

| Bug | Most likely root cause (verified pattern) | Candidate fix direction | Needs |
|-----|-------------------------------------------|-------------------------|-------|
| **1. Hammer Securities has no super stim** | §0.1-A + §3.1: `HammerSecurity` is a standalone unit; we swapped its `AbilArray index 3` → `StimpackMarauderWoLU` (`UnitData.xml:144-146`) but added **no card-button** override, so its merged card has no working/visible super-stim button. | Compute the merc's merged card (CHECK5); re-point its stim button to `StimpackMarauderWoLU,Execute` OR append a fresh `Type=AbilCmd` stim button (Marauder #3 pattern). | [STATIC root cause] → [GAME] button + autocast |
| **2. Medic still can't heal mechanical** | §4: traced every gate — the mechanism is statically **CORRECT** (TargetFilters drops bio/ground; the `heal` effect, smart-validator `-;Enemy`, and autocast filter don't gate by attribute). So the bug is most likely a **[GAME] wiring/observation** issue, not a missing filter override. | First confirm via the card-merge simulator that the Medic's **visible** heal button cell is the one re-pointed to `HealWoLU,Execute` (index may not be 6 in the merged card); if it is, in-game test a manual heal on a Marauder/Viking. | [STATIC: correct] → [GAME] confirm button cell + manual heal |
| **3. Jotun + all shielded units need normal armor shown too** | §8: both `LifeArmorName` + `ShieldArmorName` are set + resolve (CHECK7-clean). The *static* piece is done; the report is about the inspect-panel rendering BOTH indicators, which is engine/preload UI behavior. | Likely already correct statically; if the life-armor icon is still absent in game, re-check the exact `Unit/LifeArmorName/Terran*` value matches the merc's attribute class (Infantry/Vehicle/Ship) — a mismatch can hide the sign. | [STATIC done] → [GAME] dual-indicator render |
| **4. Jotun: air+ground / windup / resurrect / AA splash** | §5 (Options static→reaches MercThor via `parent=`), §6 (windup = `DamagePoint`/`Period`/`Backswing` on the shared `ThorsHammer` id → reaches MercThor; AA `Period` NOT capped), §7 (Immortality currently STRIPPED — owner wants it back, needs a `MercThor`-targeted resurrect chain). | §5: already wired statically (confirm in game). §6: if AA cadence is the complaint, add a `Period` cap on `JavelinMissileLaunchers`. §7: build the parallel `MercThor{Reborn,Wreckage,DontDie}` chain with `Unit="MercThor"` + zero cost (don't reuse Thor's). | [STATIC] → [GAME] for each sub-item |

---

## Contradictions / caveats vs `docs/open-issues.md` resolved items

1. **`heal` Adaptive Medpacks — "CONFIRMED the only biological/ground gate is `TargetFilters`"
   (open-issues "Medic Adaptive Medpacks", and v0.3.7 #5 marked `[x]`).** I VERIFIED this claim
   is **correct** — and stronger than the note states. I checked the two gates the
   `TargetFilters`-only claim could have missed: (a) the inherited
   `SmartValidatorArray="healSmartTargetFilters"` is `CValidatorUnitFilters Filters="-;Enemy"`
   (`liberty.sc2mod/ValidatorData.xml:1318`) — excludes enemies only, no attribute gate; (b) the
   `heal` effect (`CEffectCreateHealer`) has validators `noMarkers/NotWarpingIn/HiddenCompare*/
   NotVortexd` — no attribute gate. So `HealWoLU` is statically a complete fix for mechanical/air
   healing (manual AND autocast). **No contradiction** — but it means if Bug 2 persists in game,
   the cause is NOT the heal mechanism (don't add a `SmartValidatorArray` override — that would be
   chasing a non-bug); it's the **button wiring / observation** (§4 conclusion).

2. **Immortality Protocol (open-issues v0.3.7 #9, `[x]`).** Marked resolved by STRIPPING the
   behavior — correct for "no gas / no double HP bar", but the owner's NEW directive ("now wants
   it to WORK") makes the current state a *regression against intent*. Not a contradiction in the
   tracker (the `[x]` was for the old goal), but flagging that the resolved item must be reopened
   with the §7 resurrect-as-`MercThor` design.

3. **Damage-flatten (open-issues "X dmg + X vs light/armored", still `[ ]`).** Consistent with my
   read: the per-player `AttributeBonus[Light]=0` on `C10CanisterRifle`/`JavelinMissileLaunchersDamage`
   is an **indexed-array edit** → a no-op (same class as `Options[]`), so the flatten needs the
   Shaped-Blast clone pattern (already done for the Thor AA via `JavelinMissileLaunchersDamageBuffedWoLU`,
   `EffectData.xml:89-96`, but NOT for the Ghost/Spectre rifle, whose genlib `Set` on
   `C10CanisterRifle.AttributeBonus[Light]` (`genlib.py:262`) is still a no-op). **The Ghost/Spectre
   card will still read "+X vs light" until those get the clone treatment too.** No contradiction —
   the item is correctly still open — but naming the exact remaining no-op (`C10CanisterRifle`/
   `SpecterU` `AttributeBonus`) for whoever picks it up.

4. **`Button.Requirements` per-player edit (Marauder Tech Lab / Hercules Fusion Core, open-issues
   `[ ]`).** Consistent: `Button.Requirements` is a requirement-LINK field
   (`genlib.py:290-292`), and per §0 link edits are no-ops — so this is very likely dead, as the
   tracker already suspects. Confirms the open flag; no new contradiction.

---

## Result
- STATUS: success
- ARTIFACTS: created `docs/implementation-patterns.md` (this file). No mod files changed.
- RISKS: §7 (Jotun resurrect) cites the Thor morph-chain field names but the exact
  `ThorReborn`/`ThorWreckage` defs must be re-read with `xmlq.py` before implementing (possible
  caster-bound cost à la §11). Bug 2's leading cause is now "[GAME] button wiring", reasoned from
  the catalogs — the in-game card-cell + manual-heal test confirms it. All "[GAME]" items remain
  owner/harness-gated by design.
- LEARNINGS: none re-derived into `docs/learnings.md` (this doc consolidates existing learnings
  with new citations rather than adding a new gotcha). The genuinely-new finding this round —
  the `heal` mechanical-gate is ONLY `TargetFilters` (the inherited smart-validator is `-;Enemy`,
  the heal effect has no attribute gate), so `HealWoLU` is statically a complete fix — is captured
  in §4 + contradiction #1; not promoted to learnings until the in-game wiring cause of Bug 2 is
  pinned (it may turn out to be a button-index lesson worth recording).
- NEXT: (1) owner/harness verify the 4 bugs against the §"ACTIVE BUGS" table; (2) for Bug 2, run
  the card-merge simulator on `Medic`/`Stetmann` to confirm the visible heal button cell is the
  re-pointed one, then in-game test a manual heal on a mech unit (do NOT add a filter override —
  the mechanism is correct); (3) for Bug 4 resurrect, build the `MercThor`-targeted
  `{Reborn,Wreckage,DontDie}` chain (§7) after re-reading the Thor chain defs; (4) consider the
  Ghost/Spectre rifle flatten clone (contradiction #3); (5) for Bug 1, add the `HammerSecurity`
  stim CARD button (the ability is already swapped).
