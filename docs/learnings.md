# Engineering learnings — SC2 WoL campaign modding

Hard-won, non-obvious facts this project had to discover the hard way. Read before
touching the matching area; **contribute back** when you re-derive something new
(also save it to engram — see CLAUDE.md §Session Memory). Each entry leads with the
gotcha; authoritative details live in the code/plan, not here.

## Maps are the only injection point

- The campaign UI prefers loose `Maps/Campaign/<name>.SC2Map` files over CASC — that's
  the entire mechanism. Loose-file shadowing of `Mods/Liberty.SC2Mod` does NOT work
  (tested: CASC wins over the legacy `file:` fallback), and extension mods don't apply
  to campaign.
- Every map needs THREE patches (all in `scripts/build.py`): the `DocumentInfo`
  dependency line, the **same dependency list duplicated in the binary
  `DocumentHeader`** (u32 count + null-terminated strings after the first `bnet:`
  byte sequence — missing this gives "map references content that no longer exists"),
  and a `MapScript.galaxy` include+init injection for the trigger library.
- Component-**folder** `.SC2Mod` directories work fine (no MPQ packing needed for the
  mod); maps are MPQs — patch them with StormLib (`tools/mpqpatch.c`).
- Map line endings vary per map (CRLF vs LF) — patchers must detect, not assume.

## Per-player isolation (rule 9) and the clone architecture

- `CatalogFieldValueModify(catalog, entry, field, player, value, op)` applies a change
  for ONE player — the backbone of "buff us, not them". But it can only **edit
  existing fields**; creating array entries (`AbilArray`, `LayoutButtons`,
  `AreaArray`, `EffectArray`) is a **silent no-op**.
- Behavior-class abilities (`CAbilBehavior` — cloaks; **not** stim, which is
  `CAbilEffectInstant` even in vanilla) **cannot autocast at all**; no Blizzard data
  does it. Autocast needs effect-style abilities (`CAbilEffectInstant`/`Target`).
- **Never hand-guess ability/effect schemas — copy a working Blizzard chain
  verbatim** and adapt ids (cost: two sessions). The killers found by diffing against
  NCO's Super Stimpack (`mods/novastoryassets.sc2mod` in the SC2GameData dump):
  `<Effect value=.../>` without `index="0"` on `CAbilEffectInstant` silently leaves
  the ability with **no effect** (manual cast does nothing); `AutoCast`/`AutoCastOn`
  are **ability-level** `<Flags>`, not `CmdButtonArray` flags; effect chains use
  `Value="Source"` (not Caster) and the attribute form
  (`<VitalArray index="Life" Change="30"/>`).
- Therefore: **clone architecture** — define `*WoLU` clones in static XML (arrays and
  autocast baked in) and wire them in by **XML index-overrides** of the vanilla slots
  (`<AbilArray index="3" Link="StimpackWoLU"/>`; indices verified against reference
  XML). Per-player runtime LINK edits (`AbilArray[i].Link`, `WeaponArray[i].Link`,
  `LayoutButtons[j].AbilCmd` via `CatalogFieldValueModify`) are **silent no-ops** —
  only scalar stat-like fields apply per player.
- **Append, don't override, abilities that enemies actively use** (Snipe, Obliterate):
  replacing the AbilArray slot would lock the requirement-gated clone for AI too and
  change enemy behavior. Append the clone as a NEW ability slot and index-override
  only the card BUTTON's `AbilCmd` — cards are pure UI, the AI never reads them.
  (Override-in-place is fine only when the vanilla ability was requirement-gated and
  never granted to AI — the stim case.)
- **Appends MUST carry an explicit index** — `<AbilArray Link="X"/>` and
  `<LayoutButtons Face="X" .../>` WITHOUT an index are silently dropped in our
  dependency mod (confirmed in game: Magrail invisible until given `index="4"`; works
  after). Use the next free slot = the unit's vanilla element count (e.g. Marine has
  AbilArray 0-3 → Magrail at `index="4"`, LayoutButtons 0-5 → button at `index="6"`).
  Vanilla cards are contiguous, so count = next free index. (TA-style index-less
  appends may work in a fully editor-saved mod, but NOT in our hand-rolled component
  folder — don't trust them.)
- A `CAbilEffectTarget`/`CWeaponLegacy` with **no `Effect` element defaults the link
  to its own id** (vanilla `Obliterate` ability → `Obliterate` damage effect). Clones
  must set `Effect` explicitly or they point at a nonexistent `<clone-id>` effect.
- **`TargetFilters` is an INDEXED array (`CFiltersParam[]`), not a scalar string — on a
  `parent=` clone a bare `<TargetFilters value=…/>` does NOT replace the inherited filter;
  it APPENDS, and the engine AND-combines the entries.** This silently kept a require-bit we
  meant to drop: `HealWoLU parent="heal"` set a broad bare-`value=` filter to heal mechanical,
  but the inherited slot 0 (`Ground,Biological,…` from vanilla `heal`) survived and AND'd in →
  the Medic refused mechanical targets for **both** manual and autocast (owner playtest, not
  catchable statically by our gate). The require-list before the `;` is an AND of all entries.
  **Fix: override the inherited slot EXPLICITLY with `index="0"`** —
  `<TargetFilters index="0" value="Visible;…"/>` replaces `Ground,Biological,…` so only the broad
  filter remains. Every reference layer that edits an inherited `heal` filter uses `index="0"`
  (`mods/_reference/rogue/GameData/AbilData.xml:603`; the `index="0" removed="1"` tombstone at
  `:347` proves the indexing). General rule: **any time a `parent=` clone overrides an inherited
  indexed-array field (`TargetFilters`, `Effect`, `AbilArray`, …), carry the explicit `index=`** —
  bare `value=` only safely replaces on a SAME-ID override (e.g. our `BunkerTransport` filter edit),
  not on a clone. (Aside, unrelated to this bug: `CEffectCreateHealer` is NOT biological-only — the
  Medic `heal`, SCV `Repair`/`NanoRepair`, and `MULERepair` are all the same effect class; bio-vs-mech
  is decided ENTIRELY by the casting ABILITY's `TargetFilters`, never the healer effect.)
- **Verify Blizzard ids letter-by-letter** — the Marine rifle is `GuassRifle`
  (Blizzard's typo). A runtime edit on a misspelled id is a silent no-op; our Marine
  +1 range was dead for a whole batch. Same for card cells: audit the unit's vanilla
  card before placing buttons (hero rows 2,0–2,3 are often fully occupied; a
  colliding button silently hides one of the two).
- XML index-overrides are GLOBAL, so the player gate lives inside the clone:
  **abilities** gate their button on the `WoLUHaveFlag` requirement (flag upgrade
  only our library grants); **weapons** fire without buttons, so the clone must stay
  stat-identical to vanilla and the buff lives in a player-gated effect branch — the
  campaign's Shaped Blast pattern: weapon → `CEffectSet` → sibling effects with
  `CValidatorPlayerRequirement` gates (HasFlag = buffed, NoFlag via `CRequirementNot`
  = vanilla). Per-player stat buffs (e.g. windup cap) go on the **clone id** at
  runtime — neither runtime edits on the vanilla id nor parent inheritance propagate
  to a clone after load.
- **The merc/hero PARITY trap (recurring class — now gated by CHECK10).** Per-player buffs live
  keyed to BASE unit ids in two places: (a) genlib `CatalogFieldValueModify` edits (keyed to the base
  `id`) and (b) per-unit-type loops in the hand-written `LibWoLUnbalanced.galaxy`
  (`libWoLU_AddBehaviorToType`/`ToggleCloakOn`/`GraduateSiegeRange` — keyed to a `unitType` string).
  **NEITHER reaches a counterpart automatically:** a `parent=` elite merc (`Merc*`) inherits the base's
  STATIC XML (AbilArray/CardLayouts/weapons/armor) but NOT the per-player (a) edits or (b) loops;
  standalone mercs (`WarPig`/`DevilDog`/`HammerSecurity`/`SpartanCompany`/`SiegeBreaker`/`HelsAngel*`/
  `DuskWing`/`DukesRevenge`) and heroes (`Raynor*`/`Tychus*`/`Swann`/`Stetmann`/`Nova`/`Tosh`/`Odin`) are
  separate ids that inherit NOTHING. So a base-keyed buff silently SKIPS the merc/hero (Spartan ←
  Goliath upgrades #12, Death Heads ← cloak + super-stim, Hammer Securities ← stim). When you add ANY
  per-player Unit edit or galaxy per-type loop to a base unit, you MUST mirror it onto every
  counterpart (genlib edit on the merc/hero id; a `libWoLU_*ToType(p, "<MercId>", …)` line in the
  hand-lib), scaled per rule 4 (keep the merc's % advantage) / rule 10 (mirror for heroes). `scripts/
  check_merc_parity.py` (**CHECK10**, in the gate) now enumerates each base's functional buffs and
  FAILS if a counterpart is missing the same buff CLASS — so a future omission can't ship silently.
  It checks PRESENCE not value (mercs keep a % advantage), excludes cost/Food (free calldowns / map-
  placed heroes never pay), collapses same-effect ids to a class (`PersonalCloakingFree`≈
  `SpectreCloakingFree`; any cloak toggle ⇒ `cloak-toggle`), and does NOT police cosmetic passive-
  display card faces (display-only; audit.py's #3-class check already guards face↔capability). Genuine
  N/A cases go in the script's `EXCEPTIONS` allowlist with a reason; a STALE exception also FAILs.
- **Never clone unit types** — mission scripts check unit types ("all your Marines
  are dead", drop pods spawning `Marine`, …).
- Static XML is global. Safe there: pure definitions, and additions to
  player-exclusive units (heroes, mercs).
- Cloned/added **area-damage effects friendly-fire by default** — set explicit
  `SearchFilters` (campaign's Crucio pattern:
  `Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable`).

## Abilities, autocast, and targeting

- **`parent=` on a `CAbil*` clone** inherits the whole vanilla ability (cost, effect,
  range); override only the autocast block + the gated button. Cheapest way to add an
  autocast variant without re-specifying the effect chain (used by the BC kit:
  `YamatoWoLU parent="Yamato"`, etc.). Works for weapons too (`ThorsHammerWoLU`).
- **TargetSorts are catalog-definable** via `CTargetSortValidator` / `CTargetSortField`
  / `CTargetSortMarker` / `CTargetSortPriority` entries in `TargetSortData.xml` — NOT a
  fixed enum (the built-in `TS*` names are just the stock ones). So nuanced autocast
  priority IS expressible: `CTargetSortValidator` orders targets by a validator,
  `CTargetSortField` by any unit field. **Direction**: a plain `CTargetSortValidator`
  sorts passers LAST; add `<Descending value="1"/>` to put passers FIRST (confirmed
  from the RaynorRogue kit's `TSTrackedByBattlecruiser`, used un-descended to push
  already-attacked targets to the back for overkill avoidance). The `gada` component
  auto-discovers `TargetSortData.xml` — no ComponentList entry needed.
  (Smart-Snipe uses this: healer → lethal → tanky → nearest.)
- **Damage reduction** is a `CBehaviorBuff` with a `<DamageResponse ModifyFraction="0.5"
  ModifyMinimumDamage="1">` block (schema confirmed against the Moebius pack's
  `AdvancedShielding`; 0.5 = take half damage). `<Kind index="Ranged" value="1"/>`
  entries are meant to filter by damage kind, but the reference sets them all to 0 with
  no obvious effect — treat Kind-filtering as unverified and prefer halving all damage.
- **An ON-DAMAGE auto-trigger ("cast a thing whenever the unit gets hit") is a
  `DamageResponse Handled` behavior, NOT an autocast on a low-HP validator.** Autocasting
  an ability on a `Life < 100%` (state) validator re-casts every cooldown for as long as
  the unit merely *sits* below full HP — that's a STATE gate, not an EVENT. To fire once
  per hit, put a hidden permanent `CBehaviorBuff` on the unit whose
  `<DamageResponse Chance="1" Handled="<effect>"><Cost><Cooldown TimeUse="N"/></Cost></DamageResponse>`
  fires `<effect>` on every NON-fatal hit, rate-limited by the cooldown (schema confirmed
  verbatim from liberty's `RetributionField`). No `Fatal` needed (that's the death-response
  variant, cf. `MercThorDontDie`); no `ModifyFraction` needed unless you want the *response*
  to absorb — omit it when you want a real effect (e.g. raise a shield) to do the absorbing.
  Throttle `TimeUse` to the effect's own duration so it doesn't re-fire while still active.
  (Used for Defensive Matrix auto-raise on BC/SV/Jackson's Revenge — `WoLUDefMatrixOnDamage`.)
- **In a `DamageResponse` `Handled` chain, pin every child effect's unit to `Caster`
  EXPLICITLY — and the selector field name differs by effect class.** "Caster" in this
  context = the unit carrying the DamageResponse behavior = the DAMAGED unit. Bare campaign
  effects with no selector default ambiguously when re-fired from a damage response. The
  selector element is class-specific: `CEffectApplyBehavior` uses `<WhichUnit Value="Caster"/>`,
  but `CEffectModifyUnit` uses `<ImpactUnit Value="Caster"/>` (NOT `WhichUnit` — confirmed
  against liberty's own `CEffectModifyUnit` entries; `<WhichUnit>` on a `CEffectModifyUnit`
  is wrong). When cloning a vanilla cast's effects for a damage-response target, clone each
  member and add the right selector — don't reuse the bare originals.
- `CValidatorUnitCompareField` reads any unit field (e.g. `LifeMax`); default WhichUnit
  is the validated/target unit. `CValidatorUnitCompareVital` reads current Life/Energy/
  Shields with an explicit `<WhichUnit Value="Target"/>`. Both compose under
  `CValidatorCombine` (Or/And) — the toolkit for autocast gates.
- **Attack-while-moving** is the weapon's `AllowedMovement` enum (`Slowing` default,
  `Moving` = fire on the move) — a vanilla field, no custom work.
- **Faster TRANSFORM / morph DURATION is a nested indexed-array field → a per-player runtime
  `CatalogFieldValueModify` on it is a NOOP; the rule-9-safe lever is a player-only CUpgrade
  `EffectArray Operation="Subtract"` (the verified rogue `Kit@AISmartServos` pattern).** A
  `CAbilMorph`'s timings live at `Abil,<morph>,InfoArray[0].SectionArray[<Section>].DurationArray[<Field>]`
  (Section ∈ Actor/Mover/Collide/Stats; Field ∈ Delay/Duration) — an indexed array, the same no-op
  class as `AbilArray`/`AttributeBonus[…]` for runtime edits. So speed-up of the Viking transform can't
  go through genlib. Instead create a `CUpgrade` whose `EffectArray Operation="Subtract"` cuts each
  duration (copy the rogue kit `mods/_reference/rogue/GameData/UpgradeData.xml` `Kit@AISmartServos`) and
  grant it ONLY to the human player in `libWoLU_GrantCampaignTech` (next to the `WoLUnbalancedFlag`
  grant) → the global static EffectArray edit is effectively player-only, rule-9-safe (same class as
  `CombatShield`/`RegenerativeBioSteel`). The **gameplay-relevant** field is `Stats.Duration` (when the
  unit becomes the new form); `Actor.Duration` is cosmetic; `Mover.*` is the physics glide. **VERIFY each
  `Reference=` path against the ACTUAL morph def before subtracting** — the SectionArray indices differ
  by morph (base `AssaultMode` has NO Collide section; `FighterMode` does) and you must not subtract a
  field below ~0. Cite the durations: base Viking `AssaultMode` Stats/Actor.Duration=2.34 and
  `FighterMode`=2.333 (`liberty.sc2mod/AbilData.xml`) → Subtract 1.34/1.333 leaves ~1.0 s. **The Hel's
  Angels merc uses SEPARATE morph ability ids `WreckingCrewAssaultMode`/`WreckingCrewFighterMode`
  (`liberty.sc2campaign/AbilData.xml`, standalone — inherit NOTHING from the base Viking morphs), so they
  need their OWN EffectArray entries** (their Stats/Actor.Duration are also 2.333/2.334 → same 1.333 cut).
  (Done v0.3.14: `WoLUSmartServos` CUpgrade. The ATTACK-WHILE-MOVING half of the same passive face is the
  independent `Weapon.AllowedMovement=Moving` per-player edit above — two unrelated levers, one card.)
  [STATIC field-class + verified rogue pattern; the in-game transform-feel is GAME-confirmed at playtest.]
- **`PersonalCloakingFree` / `SpectreCloakingFree` are permanent-cloak BUFFS**, not
  cost-reducers: `CBehaviorBuff` with `Modification > StateFlags[Cloak]=1` and no energy
  drain. `UnitBehaviorAdd`-ing one makes the unit cloaked from that instant and stay cloaked
  for free — the way to make any cloak-capable unit "spawn cloaked." (It's generic; works on
  Ghost/Banshee/Wraith/Reaper/etc., not just the spectre/personal originals.)
- **Cloaking via the buff leaves the TOGGLE ability OFF → the card shows "Cloak On" not
  "Cloak Off".** The unit IS cloaked (by the buff) but its `CAbilBehavior` cloak toggle
  (`GhostCloak`/`BansheeCloak`/`WraithCloak`/`RogueGhostCloak`/
  `DuskWingBansheeCloakingField`; On = command index 0, Off = index 1) stays off, so the UI
  offers the decloak button only after you flip the toggle. Issue the On command from the
  trigger lib: **`UnitIssueOrder(u, Order(AbilityCommand("GhostCloak", 0)),
  c_orderQueueAddToFront)`** — `Order(...)` (no-target form, NOT `OrderTargetingNone`),
  and `AddToFront` (NOT `Replace`, which clobbers the unit's move/attack queue and freezes
  it). Pattern lifted verbatim from liberty's own AI cloak triggers. Guard with
  `if UnitOrderCount(u) == 0` so the periodic only toggles idle units (never interrupts a
  busy one; freshly-spawned units get it the first idle tick). Units with no toggle ability
  (Reaper/Medivac/Predator) just keep the permanent buff. Map: Ghost=GhostCloak,
  Banshee=BansheeCloak, Wraith=WraithCloak, Spectre=RogueGhostCloak,
  DuskWing=DuskWingBansheeCloakingField; heroes/mercs inherit the base's id.
- **The SIMPLER way to handle a permanently-cloaked unit's UI is to TOMBSTONE both Cloak
  On/Off card buttons, not to sync the toggle ON** (owner preference, v0.3.11): with
  PersonalCloakingFree/SpectreCloakingFree the unit is already cloaked for free, so a toggle
  pair is just clutter. Tombstone via a `CUnit` override `<CardLayouts index="0"><LayoutButtons
  index="N" removed="1"/>…`. **Rule 9 is preserved by tombstoning the BUTTONS only, never the
  ABILITY:** cards are player-UI-only (enemies render no command card and keep their cloak via
  AI), so removing the `GhostCloak`/etc ability would break enemy cloaking — keep it on the
  AbilArray. When all cloaked units lose their buttons, the whole `libWoLU_ToggleCloakOn`
  trigger becomes dead and goes away. **Merged cloak-button indices (verified via the audit.py
  `merge_unit_card` sim — DON'T eyeball):** Ghost On=9/Off=10, Banshee On=5/Off=6, Wraith
  On=5/Off=6, Spectre On=4/Off=5, MercWraith On=5/Off=6, MercSeniorGhost On=9/Off=10.
  **Two non-obvious findings:** (1) **Nova and Tosh have NO Cloak On/Off button pair at all** —
  the heroes show a *passive* `PermanentlyCloakedNova`/`…Tosh` display face (Type=Passive, no
  AbilCmd) and never carry `GhostCloak`/`RogueGhostCloak` as a unit ability, so there is nothing
  to tombstone for them (and they're player-exclusive, so rule 9 is moot regardless). (2) **A
  `parent=`-merc's card still shows the base unit's cloak buttons on the merc's OWN merged card**
  — `MercWraith parent="Wraith"` and `MercSeniorGhost parent="Ghost"` resolve the parent's
  vanilla card, so the buttons reappear; tombstone them EXPLICITLY on the merc's own `CUnit`
  (don't assume the base-unit tombstone propagates — re-state the indices on the merc to be
  unambiguous). Same indices as the base because the card is inherited 1:1.
- **`ShieldArmorName` (and `LifeArmorName`) must be a string-table KEY, not a literal** —
  vanilla uses `Unit/ShieldArmorName/ProtossPlasmaShields`. A raw value like
  `"Defensive Matrix"` shows **"unknown"** in the inspect panel. Add a `Unit/ShieldArmorName/<id>`
  GameStrings entry and reference that key. (Terran units have no vanilla shields, so added-shield
  clones must supply this themselves.) **A `parent=` clone does NOT reliably surface the base
  unit's `LifeArmorName` either** — make it explicit on the clone (= the base unit's vanilla value,
  e.g. `Unit/LifeArmorName/TerranInfantryArmor` for infantry mercs) or the *normal* life-armor sign
  can read "unknown" on a shielded clone. `audit.py` CHECK7 now verifies every armor key we set
  resolves (WoLU* keys in our GameStrings, vanilla `Terran*` keys via the reference dump).
- **Don't BLANKET-add decorative passive cards to clones — match the FACE to the unit's real
  capability.** An elite-merc (`parent=<base unit>`) already INHERITS its base unit's correct
  upgrade cards via `parent=`; adding the same decorative `Type=Passive` faces to *all* clones
  regardless of fit puts a vehicle-hull face (`ShapedHull`) or a weapon-range face
  (`WoLUUpgLaserTargeting`) on a unit that has neither — e.g. Shaped Hull + Laser Targeting on the
  **Medic** (a weaponless, hull-less healer). The owner sees nonsense cards. Rule: a clone shows
  ONLY its base unit's real cards (inherited); merc-exclusive **shields** go in the
  `ShieldArmorName` sign, NOT a redundant passive card. `audit.py` **#3-class check** now WARNs on
  a passive face whose capability the unit lacks (hull-on-non-vehicle, weapon-on-weaponless,
  decorative-shield-card) — verify against the card-merge simulator before adding any passive face.
- **Per-player `MaxCargoCount` on a `CAbilTransport` DOES apply at runtime** (unlike `CargoSize`,
  which is read at bunker LOAD time and the runtime edit doesn't reach — see the Ghost-2-slots
  note). Evidence: the per-player `MedivacTransport.MaxCargoCount=12` (Expanded Hull) edit works,
  and the bunker's `TotalCargoSpace`/`MaxCargoSize` per-player edits visibly took (the slot bar
  changed). So when a bunker shows N open slots but only loads fewer, the binding limit is the
  **unit-count cap `MaxCargoCount`**, not the space bar — raise `MaxCargoCount` to ≥ `TotalCargoSpace`
  so the space bar (and per-unit `CargoSize`) is what binds. Both `MaxCargoCount` and
  `TotalCargoSpace`/`MaxCargoSize` are scalar `CAbilTransport` fields editable per player; only
  the per-UNIT `CargoSize` is the load-time no-op.
- **A weapon's `DisplayAttackCount` and a `CEffectCreatePersistent`'s `PeriodCount` are plain scalar
  `value=` children → both apply per player** (added to the CHECK8 GOOD tables, v0.3.x). They are NOT
  the indexed-array no-op class: `PeriodCount` is the COUNT of periodic ticks (e.g. AA missiles a single
  attack fires), distinct from the sibling `PeriodicPeriodArray` (the per-tick delay list), which IS an
  indexed array and so a per-player edit on it WOULD no-op. So to multiply a multi-missile barrage
  per-player, edit `PeriodCount` (real count) — leave the period array alone. **When `PeriodCount` overruns
  the period array, SC2 repeats the LAST array entry for the extra ticks** (e.g. Thor AA `PeriodCount` 4→8
  over `[0,0.125,0.25,0.125]` → missiles 5-8 each at +0.125 s, barrage spans ~1.0 s). Keep the doubled
  barrage shorter than the weapon's `Period` so attacks don't overlap. `DisplayAttackCount` is DISPLAY-ONLY
  (drives the unit-info panel's "Nx" total, not the real fire count) and is a constant multiplier on BOTH
  sides of CHECK11's panel↔actual compare, so editing it never breaks panel truth — but you must scale it
  with `PeriodCount` to keep the panel honest (Thor/Jotun + Odin AA: ×2 both). Reaches a `parent=` merc
  (MercThor/Jotun) for free via the shared weapon/effect ids; the hero (Odin) uses a SEPARATE chain
  (`OdinAntiAir`/`OdinAA`) → edit it explicitly (rule 10). [STATIC field-class; barrage feel is GAME-only.]
- **A TURRET-mounted weapon with a narrow `Arc` cannot fire from a bunker; an omni weapon (no
  turret, default 360° `Arc`) can.** The engine fires a bunkered passenger's OWN weapons from the
  bunker (the passenger stays the caster — `BunkerTransport.LoadCargoBehavior=BunkerWeaponRangeBonus`
  even *adds* +1 range), but the stowed unit's model/turret can't articulate to aim. So a weapon
  whose firing is gated by turret aim never connects. The verified diagnostic: a **Marine fires fine
  from a bunker** because `GuassRifle` sets **no `Arc`** (engine default 360°) and has **no turret** →
  omnidirectional. A **Goliath/Spartan Company AA does NOT fire** because each weapon sets
  **`Arc=29.9926`** (a ~30° wedge) AND is turret-mounted (`Turret="SpartanCompany"` 135° yaw, or
  `"FreeRotate"` 360° on the Multi-Lock-upgraded variant) — the 30° arc needs the turret to swing to
  the target, which a stowed unit can't do; air targets (any bearing) fall outside the frozen wedge.
  Ground targets often sit ahead of the bunker's frozen facing, so "at least the AA" fails first.
  **NOT `CasterIsNotHidden`** — that validator sits on BOTH the ground and air effects identically
  (and is undefined in the reference dump = a core validator used in vanilla only on burrow/baneling
  self-spawns), so it can't explain an AA-*only* failure. **No weapon `Options` flag bypasses
  facing** (`LockTurretWhileFiring` is the opposite lever; there's no ignore-facing/fire-from-cargo
  flag). The ONLY candidate lever is per-player **`Weapon.Arc → 360`** (a GOOD scalar class, rule-9
  safe — enemy Goliaths keep 29.99°), which would let the weapon fire any direction without the
  turret aiming — **but only IF the engine lets a stowed unit acquire/fire at all, which is UNPROVEN
  statically** (no vanilla precedent of a turret AA unit firing from a bunker). Treat `Arc=360` as an
  owner-gated in-game candidate, not a confirmed fix; if it still doesn't fire air from a bunker, it's
  an inherent SC2 turret-from-bunker limitation with no static fix. [STATIC root-cause; [GAME] for any
  fix.]
- **`removed="1"` on an array index is a tombstone the campaign uses to delete inherited
  entries** (e.g. libertystory strips the Marauder's `StimpackMarauder` via
  `<AbilArray index="3" removed="1"/>`). A later layer that sets the same index with a real
  `Link` re-occupies the slot (verified by merge). To re-point a button the campaign turned
  into a *passive*, you must APPEND a fresh full button — overriding only its `AbilCmd` leaves
  `Type=Passive`/the old `Face`, so it never works as the action. **Same tombstone works on
  any inherited array on a `parent=` clone**: to drop an inherited BEHAVIOR from a clone, set
  its index `removed="1"` (e.g. one could strip the Thor's `ThorDontDie` reconstruction from the
  Jotun with `<BehaviorArray index="1" removed="1"/>` — the campaign Thor's behaviors are
  `[0]=ScavengingSystemsMechDeath, [1]=ThorDontDie`, index-less appends in libertystory). To
  re-point it to a different behavior, OVERRIDE the same index with a `Link` instead of the
  tombstone (`<BehaviorArray index="1" Link="MercThorDontDie"/>`).
- **To change ONE build-button's prereq, re-point it to an EXISTING requirement of a
  sibling that already lacks the unwanted node — don't edit a shared requirement, and a
  card `Requirements` link can't be edited per player anyway.** A train button's prereq lives in
  `CAbilTrain.InfoArray[TrainN].Button.Requirements` (a `CRequirement` id). That id is a UI/card
  field → a per-player `CatalogFieldValueModify` on it is a **runtime no-op** (only scalar stat-like
  fields apply per player; this is a *link*). So the prereq must change in **static XML**, which is
  global — fine when the same-named structure trains no enemy units in the campaign (e.g. no WoL
  enemy Starport trains a Hercules), making the global edit rule-9-safe *in effect* (owner-approved
  for build prereqs: "build requirements can be equal for all players"). The clean way to drop part
  of an AND-requirement: requirements decompose into `CRequirementAnd` over `CRequirementCountUnit`
  nodes (`RequirementData.xml` → `RequirementNodeData.xml`); find a **sibling button that already
  uses the sub-requirement you want** and re-point to *its* id, rather than editing the AND
  requirement in place. Concretely, the Hercules (`StarportTrain InfoArray Train6`) gated on
  `HaveAttachedStarportTechLabAndFusionCore` (= Tech-Lab-attached AND Fusion-Core) was freed of the
  Fusion Core by re-pointing its `Requirements` to **`HaveAttachedTechLab`** — the exact same prereq
  the Banshee/Raven/Wraith Starport trains use (just the Tech-Lab node, no Fusion-Core conjunct).
  **Never edit the AND requirement in place unless it's exclusive to the one button** — grep every
  reference layer first: `HaveAttachedStarportTechLabAndFusionCore` is *also* the Battlecruiser's
  prereq, so editing it would have freed the BC too. Merge-safety: do it as a same-id
  `<CAbilTrain>` override of just the one `InfoArray index="TrainN"`, re-stating the FULL `<Button>`
  (copy `DefaultButtonFace`/`State` verbatim, change only `Requirements`) + `<Unit>` + the element's
  `Time` so no sibling fields are blanked, and touch no other TrainN. (Done for the Hercules,
  v0.3.x — `src/mod/Base.SC2Data/GameData/AbilData.xml`.)
- **EITHER/OR STORY-BRANCH train buttons COLLIDE on one production-building cell once you grant BOTH
  sides — because the campaign APPENDS the second branch unit's train button index-less onto the SAME
  Row/Column as the first.** In vanilla only one branch ever unlocks (Ghost xor Spectre, Raven xor
  Science Vessel, Predator xor Hercules), so the base layer (`liberty.sc2mod`) and the story layer
  (`libertystory`) deliberately place the two branch units' train buttons in the SAME cell — harmless
  when only one renders. This mod grants BOTH sides ("every either/or grants both"), so the two
  index-less-appended buttons land in one cell on the merged card and **only one renders** (owner
  symptom: after Tosh's mission only the Spectre was buildable, the Ghost button hidden). Confirmed
  collisions: **Barracks** Ghost `BarracksTrain,Train3` (base) + Spectre `BarracksTrain,Train7` (story)
  both at R0C3; **Starport** Raven `StarportTrain,Train3` (base) + Science Vessel `StarportTrain,Train7`
  (story) both at R0C2. **Predator/Hercules do NOT collide** — that pair lives on TWO DIFFERENT
  buildings (Predator = `FactoryTrain,Train10` R0C3, Hercules = `StarportTrain,Train6` R1C1), each alone
  in its cell; always resolve which building trains each branch unit before assuming a collision. **Fix
  = a same-id `<CUnit>` override re-pointing ONE of the two buttons to a FREE cell, overriding ONLY
  Row/Column** (the inherited `AbilCmd`/`Face`/`Type` survive by field-merge — same one-field-override
  technique as the Medic heal-button `<LayoutButtons index="6" AbilCmd="HealWoLU,Execute"/>`). Two
  merge-mechanics traps: (1) **these production cards are built ENTIRELY from index-less appends across
  layers**, so a button's effective index = its position in the concatenated base→campaign→story stream
  — Spectre is Barracks merged idx **15** (13 base buttons 0-12, then the 3rd story append), Science
  Vessel is Starport merged idx **18** (14 base 0-13, then the 5th/last story append). DO NOT eyeball —
  dump the merged card via `audit.py`'s `merge_unit_card(uid)` (CHECK5's oracle) and read the index off
  it. (2) An explicit `index="N"` override DOES target the Nth slot of an index-less-built array (the
  engine numbers index-less appends sequentially; the campaign itself targets them this way, cf. the
  `<AbilArray index="3" removed="1"/>` tombstone) — so the override is reliable even though no source
  layer wrote an explicit index. **Rule-9-safe**: command cards are player-UI-only (enemies render no
  card), and the train tech for BOTH branch units is already granted in `libWoLU_GrantCampaignTech`
  (Ghost+Spectre groups enabled + `TechTreeUnitAllow`; the lab-research loop grants both sides of every
  Raven/SV + Predator/Hercules pair), so the now-visible button actually trains. Free-cell picks:
  Barracks Spectre → R0C4 (beside Ghost on the train row); Starport Science Vessel → R1C2 (row 0 full,
  R1C2 sits among Wraith R1C0 / Hercules R1C1). (Done v0.3.x —
  `src/mod/Base.SC2Data/GameData/UnitData.xml` `CUnit id="Barracks"`/`"Starport"`.)
- **A death-response RESURRECT chain has THREE links to clone for a merc clone to revive AS
  ITSELF, and the rebuild's gas cost lives on the REBUILT UNIT, not the morph ability.** The Thor
  Immortality Protocol is: `ThorDontDie` (`CBehaviorBuff`, `DamageResponse Fatal=1
  Handled="ThorWreckage"`) → morphs the dying unit into the **`ThorWreckage` UNIT** (a
  `CUnit parent="Thor"`, immobile wreck) whose `AbilArray[0]` = the `ThorReborn` **morph**
  (`CAbilMorph`, `InfoArray Unit="Thor"`) which rebuilds a *base Thor*. So `Handled=` points at a
  **unit id** (the wreck to become), and the reborn identity is set by the morph's
  `InfoArray Unit=`. A `parent="Thor"` merc inherits the whole chain and revives as a *base Thor*.
  To revive as the merc, clone all three with merc-targeted links: `MercThorDontDie`
  (`Handled="MercThorWreckage"`, re-state the full `DamageResponse` struct — a partial override on
  a struct field doesn't reliably merge) → `MercThorWreckage` (`parent="ThorWreckage"`,
  `AbilArray[0]` overridden to the merc morph + ImmortalityProtocol card button re-pointed) →
  `MercThorReborn` (`parent="ThorReborn"`, `InfoArray Unit="MercThor"`, re-state the InfoArray
  verbatim — the nested `SectionArray` timing children don't merge under a partial override). The
  "**costs gas**" tooltip + double-HP-bar came NOT from the morph (both `ThorReborn`/`ThorWreckage`
  morphs have **no `<Cost>`**; `RefundFraction`=0) but from the **rebuilt unit's `CostResource`**
  being displayed/charged during the `ShowProgress` rebuild — base Thor is 300/200. Fix: zero the
  merc unit's `CostResource` (a calldown unit should be free anyway). And: the **wreck is a NEW
  unit id → it needs its OWN `CActorUnit`** (clone the vanilla wreck actor, set
  `unitName="MercThorWreckage"`, re-bind the `MorphTo`/`UnitBirth` morph-birth `On` terms to the
  new id, explicit `<Model>`) or it renders as a sphere (audit CHECK1). The wreck-unit clone is
  safe under "never clone unit TYPES" via the elite-merc carve-out (the id never appears in a WoL
  map). [STATIC chain; death-response EFFECT is GAME-only.]
- **Reusing a vanilla EFFECT SET can drag in a CASTER-SPECIFIC effect that errors on a new
  caster.** `SpawnSpiderMineSet` = `[SpawnSpiderMine, ReplenishNanoConstructor]`;
  `ReplenishNanoConstructor` is a `CEffectModifyUnit` with
  `Cost Abil="MakeVultureSpiderMines,Specialize1" ChargeCountUse="-1"` — it refunds a charge
  on the **Vulture-only** `MakeVultureSpiderMines` ability. Fire that set from a non-Vulture
  caster (Siege Tank/Breaker) and the missing-ability cost aborts the whole set → nothing
  spawns (and an immobile/sieged caster fails hardest). Lesson: before pointing a new
  ability/weapon at a vanilla `CEffectSet`, expand its members and check each for a
  caster-bound `Cost Abil=`/validator; if present, point at just the core effect
  (`SpawnSpiderMine`) instead of the set.
- **Mid-mission saves do NOT survive mod changes — and `.version` files do NOT fix
  this** (two attempts proved it: constant counter, then monotonic counter; the error
  recurred both times). A `.SC2Save` serializes live game state *against the mod's
  exact catalog structure* — `save.ioSync` stores upgrade names (`WoLUnbalancedFlag`),
  ability IDs, and array indices. Any data change (a new ability, a shifted
  `AbilArray` index, a new behavior) makes those references no longer line up →
  "the game does not match the version of the saved game." Confirmed empirically: our
  `DocumentHeader` is byte-identical across builds, yet saves still break, so the
  binding is to content/structure, not a version number. **Dev workflow: after each
  reinstall, START THE MISSION FRESH** — don't reload a mid-mission save made on a
  previous build. Within a single unchanged build, saves work fine (make all changes →
  build+install once → then save/reload freely). Campaign-progress saves (between
  missions) are coarse and survive updates — that's the "other mods update fine" case.
  The `.version` files we still emit are harmless release hygiene, not a dev-save fix.

## Visual actors bind to IDs — clones with new IDs lose visuals

- Visuals live in `ActorData`, keyed to specific **ability / weapon / effect IDs** via
  event terms (`Abil.Snipe.SourceCastStart`, `WeaponStart.ThorsHammer.AttackStart`,
  `Effect.Yamato.*`, and `CActorMissile unitName="EMP2Weapon"`). A clone with a NEW id
  inherits NONE of these — the actor never matches → no visual.
- **Rule of thumb that mostly saves you:** if a clone **reuses the vanilla EFFECT id**
  (`SnipeWoLU` Effect=`SnipeDamage`, `EMPWoLU` Effect=`EMPLaunchMissile`, `YamatoWoLU`
  `parent="Yamato"` inheriting Effect=`Yamato`), the effect-bound visuals (projectiles,
  beams, impacts — the ones that matter) fire. Only **ability/weapon-bound caster
  animations** (cast poses, charge glows, the stim puff) are lost, which is cosmetic.
- **Projectiles need a launch effect + a missile unit with an actor**, or a beam
  actor. A raw `CEffectDamage` has no visual.
- **Raw assets (`.m3`/textures/sounds) under `Assets\...` are base-game CASC files,
  referenceable BY PATH from any mod — independent of DATA (catalog) dependencies.**
  So to use another campaign's visual you do NOT need to bundle the `.m3` or depend on
  that mod's data: define a `CModel` pointing at the `Assets\...\.m3` path and clone
  the original's actor. Bundling is only for assets not in the base install. The
  Magrail uses the real WarHound railgun model this way
  (`Assets\Effects\Terran\WarHoundRailGunMissile\WarHoundRailGunMissile.m3`) + a
  `CActorBeamSimple` cloned from NCO's `RailGunTurretAttackBeamPoint`, bound to
  `Effect.MagrailDamageWoLU.Start`. **General rule for ability visuals: reference the
  original's `Assets\` `.m3` by path and clone the original's actor.**
- **Faction-swap mods (Tychus Edition, War of Mengsk — examples in `mods/`) confirm the
  technique tiers:** (1) for whole cross-campaign UNITS they add the source mods as
  *dependencies* (`DocumentInfo`: Tychus adds `Void` + `file:Mods\alliedcommanders.sc2mod`);
  (2) they *bundle* only the binary assets NOT in the base CASC — premium/co-op SKIN
  textures (`Warhound_Sirius_*.dds`) — into an `Assets/Textures/` folder in the mod;
  (3) they do NOT bundle base-game EFFECT models (the railgun `.m3` is absent from both),
  proving effect models are base-CASC and path-referenceable. So: path-reference for a
  single base-game effect (what we do); bundle only truly-absent binaries; add a
  dependency when importing whole units. If a path-referenced effect ever fails to
  render in-game, the proven fallback is adding `file:Mods\alliedcommanders.sc2mod` (co-op
  has the magrail) as a dependency and referencing the real ability/actor directly.
- **Don't clone a WEAPON if you can avoid it** — weapon-bound animations
  (`WeaponStart.<id>`) break. Prefer overriding the **vanilla weapon's `Effect`** to a
  player-gated effect set (Thor does this): the weapon id stays, so the attack
  animation fires, and per-player isolation lives in the validator-gated effect set.
- **…BUT rerouting a weapon's `Effect` to a clone `CEffectSet` silently kills the
  effect-bound muzzle/impact actors, because a `CActorAction` binds `effectAttack`/
  `effectImpact` to the EXACT damage effect id, not its parent-chain descendants.** The
  Thor ground attack's muzzle+impact live on `CActorAction id="ThorAttack"`
  `effectAttack="ThorsHammerDamage"` (LaunchAssets `ThorHandGunAttackLaunch` + ImpactMap
  `ThorHandGunAttackImpact`). When WeaponData reroutes weapon `ThorsHammer`'s `Effect` to
  `ThorsHammerWoLUSet` (a `CEffectSet` firing two validator-gated CHILDREN
  `ThorsHammerDamageVanillaWoLU`/`…WoLU`, both `parent="ThorsHammerDamage"`), NOBODY fires
  the bare `ThorsHammerDamage` id anymore → the action never matches → the ground muzzle
  AND impact vanish for EVERY Thor (player AND enemy). The *air* attack survived because
  its launch effect id (`JavelinMissileLaunchersLM`) was preserved, so `ThorAAAttack`'s
  `effectLaunch` still matched. **Fix: re-bind a (cloned) action to the actually-fired
  child effect id(s) — one `CActorAction parent="<vanilla action>"` per validator-gated
  branch, overriding only `effectAttack`/`effectImpact`** (e.g. `ThorAttackVanillaWoLU`
  → `ThorsHammerDamageVanillaWoLU` restores the ENEMY muzzle, `ThorAttackWoLU` →
  `ThorsHammerDamageWoLU` restores the PLAYER muzzle). Each unit fires exactly ONE child
  (validator-gated) → one action per child = exactly one muzzle per shot per audience, NO
  double-firing. This is rule-9-NEUTRAL (restoring the enemy's vanilla appearance is
  desired, not a buff) and cosmetic-only (no damage change). **Restate the
  `LaunchAttachQuery`/`LaunchAssets`/`ImpactMap` verbatim on the clone** rather than
  relying solely on `parent=` attribute-merge, so the muzzle is unambiguous. CHECK3/4 SKIP
  actors (their parents are base-CASC `GenericUnit*`/vanilla actor ids the ref dump lacks),
  so audit will NOT catch a typo'd effect id here — resolve each `effectAttack`/`effectImpact`
  id against our `EffectData.xml` by hand. **Watch for a hero that fires a DIFFERENT
  weapon/effect:** Odin (the Thor hero) attacks with weapon `Odin` → effect `OdinDamage`
  (actors `OdinLeftAttack`/`OdinRightAttack`), NOT `ThorsHammer`/`ThorsHammerDamage` — we
  never rerouted the `Odin` weapon, so Odin's ground muzzle was never broken and needs no
  action clone. Always check the hero's actual weapon id before assuming the base-unit fix
  covers it. [STATIC root-cause + fix; muzzle render is GAME-confirmed by the owner.]
- **The SAME reroute-detaches-the-action trap bit the VIKING ground gatling and the Hel's
  Angels merc — fixed identically.** The vanilla `CActorAction id="VikingAssaultAttack"`
  `effectAttack="TwinGatlingCannons"` carries the ground launch sound (`VikingAssault_AttackLaunch`),
  impact sound (`Viking_AssaultAttackImpact`) and flesh blood-reaction (`BloodTargetImpact`).
  Rerouting weapon `TwinGatlingCannon`'s `Effect` to `TwinGatlingCannonsWoLUSet` (children
  `TwinGatlingCannonsVanillaWoLU`/`…WoLU`, both `parent="TwinGatlingCannons"`) meant nobody fires the
  bare `TwinGatlingCannons` id → those assets detached for EVERY Viking (player AND enemy). NB the
  Viking ground gatling is NOT a missile/beam (no `CActorMissile`/`CActorBeam` keyed to
  `TwinGatlingCannons` in the dump) — the visual is purely launch-sound + impact-sound + blood, so
  "no projectile" really meant "those assets stopped firing." Fix = the Thor pattern: two
  `CActorAction parent="VikingAssaultAttack"` clones (`VikingAssaultAttackVanillaWoLU` → enemy child,
  `VikingAssaultAttackWoLU` → player child), each restating the vanilla `LaunchAttachQuery`/both
  `ImpactMap` entries/`LaunchAssets` verbatim. The merc weapon `WreckingCrewAssault` is rerouted to a
  SINGLE un-gated clone `WreckingCrewAssaultWoLU` (player-exclusive, no flag gate), so its
  `CActorAction id="WreckingCrewAssaultAttack"` (vanilla body identical to VikingAssaultAttack) needs
  only ONE clone `WreckingCrewAssaultAttackWoLU`. (v0.3.x — `ActorData.xml`.)
- **And it bit the THOR/JOTUN ANTI-AIR impact — the third instance, found by a full reroute-universe
  sweep.** An `ImpactEffect` reroute on a `CEffectLaunchMissile` detaches the same way a weapon-`Effect`
  reroute does, but ONLY the `effectImpact`-bound asset: our `EffectData.xml` reroutes
  `CEffectLaunchMissile id="JavelinMissileLaunchersLM"`'s `ImpactEffect` to `JavelinMissileLaunchersDamageWoLUSet`
  (children `JavelinMissileLaunchersDamageVanillaWoLU` WoLUNoFlag / `…BuffedWoLU` WoLUHasFlag, both
  `parent="JavelinMissileLaunchersDamage"`), so the vanilla `CActorAction id="ThorAAAttack"`'s
  `effectImpact="JavelinMissileLaunchersDamage"` stopped matching → the AA impact sound
  (`Thor_AntiAirAttackImpact`) went silent for EVERY Thor. The `effectLaunch="JavelinMissileLaunchersLM"`
  binding (launch sound `Thor_AntiAirAttackLaunch`) and the `CActorMissile unitName="ThorAAWeapon"` rocket
  trail were PRESERVED — the launch-missile id + `AmmoUnit` are unchanged. Fix = the two-clone pattern
  (`ThorAAAttackVanillaWoLU`/`ThorAAAttackWoLU`, `parent="ThorAAAttack"`, override ONLY `effectImpact`,
  restate `LaunchAttachQuery`+`ImpactMap` verbatim) but **OMIT `LaunchAssets`** — the launch sound rides
  `effectLaunch` (un-rerouted), so it still fires once via the unmodified parent; restating it would
  double the launch sound. (Contrast the Viking case, which restates `LaunchAssets` because the Viking
  launch sound rides the *rerouted* `effectAttack`.) Note the player child carries a **`Buffed` infix**
  (`…DamageBuffedWoLU`, unlike the ground `ThorsHammerDamageWoLU`) — a copy-paste from the ground template
  drops it and silently re-detaches; resolve the exact child ids by hand. (v0.3.x — `ActorData.xml`.)
- **THE COMPLETE REROUTE UNIVERSE (audited v0.3.x — check this list before adding any new reroute).** Every
  place our static XML reroutes a weapon `<Effect>` / missile `ImpactEffect` to a `*WoLU(Set)` clone, and
  whether an effect-bound actor detached:
  | Reroute (id → target) | File | Clone children | Actor DETACHED? | Fix |
  |---|---|---|---|---|
  | `ThorsHammer.Effect` → `ThorsHammerWoLUSet` | WeaponData | `…DamageVanillaWoLU`/`…DamageWoLU` (parent=`ThorsHammerDamage`) | YES — `ThorAttack effectAttack` (ground muzzle+impact) | `ThorAttack{Vanilla,}WoLU` |
  | `TwinGatlingCannon.Effect` → `TwinGatlingCannonsWoLUSet` | WeaponData | `…VanillaWoLU`/`…WoLU` (parent=`TwinGatlingCannons`) | YES — `VikingAssaultAttack effectAttack` (ground launch+impact sound+blood) | `VikingAssaultAttack{Vanilla,}WoLU` |
  | `WreckingCrewAssault.Effect` → `WreckingCrewAssaultWoLU` | WeaponData | single un-gated (parent=`WreckingCrewAssault`) | YES — `WreckingCrewAssaultAttack effectAttack` (merc, player-only) | `WreckingCrewAssaultAttackWoLU` (one clone) |
  | `JavelinMissileLaunchersLM.ImpactEffect` → `JavelinMissileLaunchersDamageWoLUSet` | EffectData | `…DamageVanillaWoLU`/`…DamageBuffedWoLU` (parent=`JavelinMissileLaunchersDamage`) | YES — `ThorAAAttack effectImpact` (AA impact sound only; launch sound+trail preserved) | `ThorAAAttack{Vanilla,}WoLU` |
  | `WraithA.Effect` → `WraithATriggerOverrideSet` | WeaponData | set = `[WraithAPersistent, WoLUWraithTriggerOverrideApply]` | **NO** — set WRAPS the vanilla `WraithAPersistent` (kept as element 0); the whole sub-chain (`WraithA{Left,Right}LaunchMissile`→`WraithAU`, missiles `WraithAirWeapon{Left,Right}`) is unchanged → all actors (`WraithAirAttack{Left,Right}`, the two missiles) fire | none needed |
  | `WraithG.Effect` → `WraithGTriggerOverrideSet` | WeaponData | set = `[WraithGLaunchMissile, WoLUWraithTriggerOverrideApply]` | **NO** — set WRAPS the vanilla `WraithGLaunchMissile` (kept as element 0); sub-chain (`→WraithGU`, missile `WraithGroundWeapon`) unchanged → `WraithGroundAttack`+missile fire | none needed |
  | `EMPShockwaveLaunchWoLU`/`…SearchWoLU` (SV BW EMP) | EffectData | new player-only ability, NOT a vanilla reroute | **NO** — reuses `AmmoUnit="EMP2Weapon"` so `CActorMissile id="GhostEMPAttackMissile" unitName="EMP2Weapon"` (bound by unit-name, not effect id) fires | none needed |
  **The decisive distinction:** a reroute SET that includes the original delivery effect as a member
  (`WraithAPersistent`/`WraithGLaunchMissile` — the Wraith "trigger-override" pattern, which only ADDS an
  on-fire buff alongside the unchanged delivery) does NOT detach anything — every actor below that id still
  fires. A reroute SET whose members are `parent=`-CLONES of the damage/impact id (the Thor/Viking "Shaped-
  Blast" pattern, which REPLACES the fired id) DOES detach the `effectAttack`/`effectImpact`-bound actor.
  And a `CActorMissile`'s `unitName=` binds to the spawned `AmmoUnit`, NEVER to the impact/launch effect id —
  so rerouting an `ImpactEffect` never detaches the rocket trail, only the `effectImpact`-bound `CActorAction`.
  **Before adding any new `*WoLU(Set)` reroute, ask: does the player end up firing a clone of the id an actor
  binds to? If yes, add the per-validator-branch action/actor clone(s) restating the vanilla assets verbatim.**
- **The unit-info DAMAGE PANEL reads a weapon's `<DisplayEffect>` (or `<Effect>` if `DisplayEffect` is
  absent), NOT the actually-fired effect — so rerouting `<Effect>`/`ImpactEffect` to a clone leaves the panel
  showing the WRONG number, and you must REPOINT `DisplayEffect` to the player's fired clone to make it
  honest. CHECK11 (`scripts/check_panel_damage.py`) now gates this.** The panel computes
  `DisplayEffect.Amount + Σ AttributeBonus[...]` (× `DisplayAttackCount`), resolved PER PLAYER for a
  player-owned unit. Our clone architecture reroutes the weapon's `<Effect>` (or a missile's `ImpactEffect`)
  to a `*WoLU(Set)` clone but leaves `DisplayEffect` pinned to the vanilla effect — so the panel is
  display-NEUTRAL to the reroute and DIVERGES exactly when the player's fired `WoLUHasFlag`-gated clone child
  carries an `Amount`/`AttributeBonus` the vanilla `DisplayEffect` id does not. Two real divergences this
  caught: **Thor/Jotun AA** panel read `JavelinMissileLaunchersDamage` (per-player `Amount`=35 via genlib,
  but `AttributeBonus[Light]`=4 unchanged → "+4 vs Light"), player fired
  `JavelinMissileLaunchersDamageBuffedWoLU` = flat 35 no light → panel OVER-showed +4 Light; **Viking/Hel's
  Angels ground** panel read `TwinGatlingCannons` (14), player fired `TwinGatlingCannonsWoLU` (14
  +`AttributeBonus[Mechanical]`=20) → panel UNDER-showed +20. **Fix = a STATIC `<DisplayEffect>` repoint to
  the player's fired clone** (`JavelinMissileLaunchersDamageBuffedWoLU` / `TwinGatlingCannonsWoLU`). This is
  **rule-9-safe** because `DisplayEffect` is DISPLAY-ONLY (it never changes damage dealt): enemy ACTUAL damage
  is untouched, and enemy command cards / damage panels are never rendered to the player, so showing the
  buffed number globally harms nothing. (A per-player `DisplayEffect` LINK edit would NOT work — weapon/effect
  link edits are the known no-op class; the static repoint is the only mechanism.) **Non-divergent cases the
  check correctly leaves alone:** (a) a reroute where the weapon has NO `DisplayEffect` → the panel falls back
  to `<Effect>`, which we already rerouted to the clone, so it reads the player's value directly (Hel's Angels
  `WreckingCrewAssault`); (b) the Thor GROUND clone adds only splash, no `Amount`/`AttributeBonus` delta →
  panel 45 == actual 45; (c) the Wraith trigger-override sets WRAP the unchanged vanilla delivery effect (no
  damage clone) → the real damage stays the vanilla `WraithAU`/`WraithGU` the panel already shows. `DisplayAttackCount`
  is a constant multiplier applied identically to old and new `DisplayEffect`, so a per-hit repoint keeps the
  ×N total correct — the check compares the per-hit `Amount`+`AttributeBonus` tuple. **OUT of scope (panel
  already == actual, or no per-unit fix exists):** Ghost/Spectre rifle "+vs Light/Armored" (display already
  equals actual — both show the bonus). **The Senior Ghost +50% panel under-show — RESOLVED via the
  SHARED-weapon clone pattern below** (the "surface as a decision" item; owner approved it for accuracy).
  [STATIC mechanism; panel render is GAME-confirmed by the owner.]
- **A panel-INVISIBLE damage multiplier (`DamageDealtFraction` behavior) on a unit that SHARES its weapon
  with a base unit is made panel-honest by a per-unit WEAPON-EFFECT clone — NOT a `DisplayEffect` repoint.**
  `MercSeniorGhost` (`parent="Ghost"`, player-exclusive) deals +50% via `WoLUSeniorGhostBoost`
  (`DamageDealtFraction[Ranged/Spell/Melee/Splash]=0.5`), which touches no displayed field, so the unit-info
  panel under-showed (~20 vs ~30 real). Its rifle `C10CanisterRifle` is SHARED with the base Ghost, so you
  CAN'T per-player-edit just the merc's number, and there's no reroute → CHECK11 never saw it. **Fix pattern
  (the "bake-the-multiplier-into-a-merc-only-weapon-clone" recipe):** (1) clone the damage effect
  `C10CanisterRifleWoLU parent="C10CanisterRifle"` with the boosted numbers HARDCODED (`Amount=30`,
  `AttributeBonus[Light]=15` = the player's post-genlib `20`/`+10` × 1.5); (2) clone the weapon
  `C10CanisterRifleWoLU parent="C10CanisterRifle"` setting BOTH `<Effect>` and `<DisplayEffect>` to the clone
  (fires==displays → can't diverge); (3) repoint ONLY the merc's `WeaponArray index="0"` to the clone so the
  base Ghost keeps the vanilla weapon (rule-9-safe — grep the new ids to confirm no other referrer); (4)
  REMOVE the now-double-counting `DamageDealtFraction` kind that the clone bakes (`Ranged` here), and KEEP the
  other kinds whose abilities aren't weapon-cloned (`Spell` → Snipe `SnipeWoLU`→`SnipeDamage` Kind=Spell keeps
  its +50%; verify the ability's damage `Kind` before dropping its fraction, or you silently de-buff it).
  **Three gotchas:** (a) the per-player genlib edit keyed to the PARENT weapon (`C10CanisterRifle.Range=7`
  LTS) reaches the `parent=` clone via read-time inheritance (the Thor-precedent) — do NOT add a genlib edit
  for the clone id, and do NOT override `Range` on the clone, or you detach it from the LTS scaling. (b) The
  clone HARDCODES the ×1.5 result, so a future change to the genlib base (`20`) won't auto-track — acceptable
  because the +50% is a fixed design intent, but note it inline. (c) A single-shot hitscan rifle is NOT area
  damage → do NOT add `SearchFilters`/`AreaArray` (those are only for the cloned-splash class). This is the
  general remedy whenever an accuracy fix needs the panel to reflect a multiplier the engine applies
  invisibly AND the weapon is shared. [STATIC; panel render GAME-pending owner confirm.]
- **Card/tooltip ACCURACY is a distinct bug class from card STRUCTURE — sweep the NUMBERS, not just the
  ids.** audit.py (face↔capability, merge indices) and CHECK11 (panel==fired) guard STRUCTURE; neither reads
  the literal NUMBERS in our `GameStrings.txt` tooltips. A full accuracy pass (2026-06) found these false
  numeric claims, all in strings we OWN (cheap to fix): a merc "+armor"/"+N armor" tooltip whose merc
  `LifeArmor` equals (or is only +1 over) the base unit's vanilla armor (Skibi's/`MercMedic` = base Medic 1 →
  "+armor" was false; Jotun/`MercThor` = 2 vs base Thor 1 → "+2 armor" was really +1) — **always compute the
  delta against the BASE unit's vanilla `LifeArmor` (resolve it in the reference dump), the tooltip's
  parenthetical reads as a delta**; and a "1.5x … armor" claim where the armor is actually a FLAT clone value
  (base Ghost has 0 armor → ×1.5 is meaningless; Senior Ghost is a flat `LifeArmor=3`). **Surface-don't-fix
  class:** a SHARED tooltip string (`Button/Tooltip/WoLUUpgLaserTargeting` = "+1 weapon range") that's true
  for most units but wrong for one (Banshee `BacklashRockets` is genlib-Set to +2 range) — fixing needs
  either a per-unit string or a genlib value change (a design call), so report it, don't unilaterally rewrite
  a shared string. **Out of scope (a known design convention, NOT false info):** the decorative
  `WoLUUpg*`/`ShapedHull` passive faces (`AbilCmd=255`, display-only) advertising an armory-upgrade THEME on a
  unit that gets the stat differently or not at all — these are deliberate flavor cards (open-issues §"the
  cosmetic … card faces"), and rebalancing/removing them is owner-gated, not an accuracy fix. **A future
  tooltip-number gate is tractable but bounded:** you'd regex each numeric token out of our owned strings and
  cross-check the few that map cleanly to a single resolvable field (merc `LifeArmor`/`ShieldsMax`, a
  cooldown `TimeUse`, a heal `Change`) — but most tooltip prose (multi-unit "+1 range", "faster training",
  "1.5x damage") has no single field to bind to, so such a gate would cover only the merc-stat subset; treat
  it as a nice-to-have, not a CHECK11-grade invariant.
- **PROVEN: an upgrade `EffectArray Reference="Effect,<vanilla-parent>,Amount"` modification DOES
  propagate to a `parent=`-inheriting CHILD clone that does NOT override `<Amount>`.** This was the
  open "unverified statically" caveat on the rerouted weapons (see the CampaignLib §"Extending a
  weapon/armor LEVEL upgrade" note's in-game caveat). The proof is the SHIPPED Thor case treated as a
  natural experiment: the vanilla `TerranVehicleWeaponsLevel{1,2,3}` upgrade modifies
  `Effect,ThorsHammerDamage,Amount` (+2/level); our mod fires the player child `ThorsHammerDamageWoLU`
  (`parent="ThorsHammerDamage"`, splash only, no `<Amount>` → inherits the parent's 45); the owner
  confirms Thor GROUND damage scales with the upgrade. Because catalog-field inheritance resolves the
  child's `Amount` THROUGH the parent at read time (distinct from the runtime-`CatalogFieldValueModify`
  clone-detachment, which can't reach an already-loaded clone), the upgrade's parent-`Amount` modify
  reaches the child. **Implication:** the Viking ground case is identical — `TerranShipWeaponsLevel{N}`
  modifies `Effect,TwinGatlingCannons,Amount` (+1/level), the player fires `TwinGatlingCannonsWoLU`
  (`parent="TwinGatlingCannons"`, no `<Amount>`), so the player's ground gatling ALREADY scales; keep
  the upgrade targeting the PARENT (retargeting to the child, or adding a child `Amount` entry, would
  double-count). The owner's "Viking ground doesn't scale" report was a PERCEPTION artifact of the
  detached launch/impact above (no visible ground hits to read), not a real scaling gap. **Merc reach
  via the VANILLA layer:** the Hel's Angels merc (standalone `HelsAngelAssault`/`HelsAngelFighter`,
  inherits nothing from the base Viking) does NOT need a parity entry because the VANILLA libertystory
  `TerranShipWeaponsLevel{N}` already lists `Effect,WreckingCrewAssault,Amount` (ground) +
  `Effect,WreckingCrewFighterU,Amount` (air, un-rerouted) in its own EffectArray — and our genlib
  grants that base-Level upgrade per-player, so the merc scales through the vanilla definition. Lesson:
  before adding a "missing" merc-weapon parity entry, grep the MERGED vanilla upgrade (libertystory +
  liberty.sc2mod) — a grep of only OUR `UpgradeData.xml` will miss vanilla coverage and tempt a
  double-counting duplicate. [STATIC mechanism proof via the GAME-confirmed Thor precedent.]
- **An elite-merc clone (`parent=<base unit>`) wears a bare `GenericUnitBase` actor that has
  ONLY the generic move/idle/death/basic-attack bracket — it carries NONE of the base unit's
  unit-specific anim events** (dual-weapon elevation poses, spell-cast poses, heal channel,
  beam-cleanup timers), because the vanilla actor binds to the base unit via `unitName="<base>"`,
  not to the merc. The merc's effects/projectiles still fire (effect-bound visuals), but the
  *caster* pose is missing. Fix = copy the vanilla actor's `<On Terms=…>` events into the merc's
  own `CActorUnit` (the MercThor/Jotun pattern). Two re-keying rules when you do:
  - **Weapon-anim events copy VERBATIM** — the weapon ids (`WraithA`/`WraithG`, `ThorsHammer`,
    the Ghost rifle, `HellionAttackBeam`/`KillBeam`) are inherited UNCHANGED via `parent=`, so the
    `WeaponStart.<id>`/timer terms match as-is.
  - **Cast-pose events for a re-pointed ability must key on the CLONE id, NOT the vanilla id.**
    Where the mod re-points an enemy-used ability via append-not-override (vanilla slot kept,
    only the card BUTTON re-pointed to the `*WoLU` clone — the Snipe/EMP/heal pattern), the
    PLAYER only ever issues the clone, so `Abil.Snipe.*` never fires on the player's merc — use
    `Abil.SnipeWoLU.*` / `Abil.EMPWoLU.*` / `Abil.HealWoLU.SourceChannelStart`. A `*WoLU` clone
    with `parent="<vanilla abil>"` (or a same-class `CAbilEffectTarget`) inherits the same cast
    phases, so the vanilla actor's `SourceCastStart/Stop`→`SourceChannelStart/Stop`→
    `SourceFinishStart` structure copies 1:1 under the new id. Abilities the mod does NOT re-point
    (TacNukeStrike, the `GhostHoldFireB` hold-fire behavior) keep their vanilla ids — key on those
    directly. Keying the merc actor on BOTH the vanilla and clone id is harmless (the actor is worn
    only by the player-only merc, never an enemy) and covers the case where the inherited vanilla
    ability also autocasts. These are STATIC actor events, unit-bound via `unitName` → player-only
    (rule-9 safe). Done for MercWraith/MercMedic/MercSeniorGhost/MercHellion (v0.3.10); MercReaper
    needs none (single-weapon, and no `CActorUnit id="Reaper"` exists in the dump to copy — the
    Reaper unit actor is a CORE unit; the generic bracket already covers its one weapon).

## Galaxy script

- Galaxy is **single-pass** like C: use-before-definition is a compile error, and a
  MapScript compile failure kills every trigger → mission loads as a **black map with
  no error message** (campaign suppresses the script-error dialog).
  `scripts/galaxy_lint.py` (CI + local) catches brace and declaration-order bugs.
- Diagnostic canary: the subtitle line at ~1 s/10 s game time. Absent ⇒ library
  didn't run. Map-init messages are useless — intro cinematics swallow them.
- Our injected init registers before mission triggers, so anything depending on the
  mission's own setup (tech application) runs on timers (1 s + 10 s re-run).

## CampaignLib (libertystory) internals

- Missions apply story tech via `libCamp_gf_ApplyCampaignTech(player)`.
  `libCamp_gf_TS_BuyAllTech()` marks all 44 armory techs purchased, BUT
  `TS_UpdateTechStates()` reverts techs whose **tech group** (unit category) the
  story hasn't introduced — in a unit's own unlock mission nothing applies. Bypass:
  loop `libCamp_gv_tS_TechID[]` and grant rewards directly
  (`libCamp_gf_StoryTechAbilityCommand/StoryTechUpgrade` →
  `TechTreeAbilityAllow` / `libNtve_gf_SetUpgradeLevelForPlayer`).
- Mercs: `libCamp_gf_SetMercStatus(id, Purchased)`; Locked derives from the
  counterpart's tech group — skip Locked mercs and rule 3 gating is preserved.
- Lab research lives in `libCamp_gv_tSX_ResearchState[1..20]` as adjacent pairs
  (Raven/SV = 7/8, Predator/Hercules = 15/16); Ghost/Spectre are tech groups 20/21.
- **In WoL the player-facing weapon/armor RESEARCHES are NOT the base `Terran*Weapons/ArmorsLevelN`
  ids — they are the icon-only wrappers `Terran*WeaponsUltraCapacitorsLevelN` /
  `Terran*ArmorsVanadiumPlatingLevelN`.** The campaign (libertystory) overrides
  `EngineeringBayResearch` (and `ArmoryResearch`) to grant the UltraCapacitors/VanadiumPlating
  ids (`libertystory.sc2campaign/AbilData.xml`; the wrapper upgrades are defined
  `parent=`-chained off `…UltraCapacitors`/`…VanadiumPlating` in
  `liberty.sc2campaign/UpgradeData.xml`). Those wrappers are display-only — the real
  +damage/+level/+armor `EffectArray`s live on the **base** `Terran*Weapons/ArmorsLevelN` ids
  (`libertystory.sc2campaign/UpgradeData.xml`: e.g. `TerranVehicleWeaponsLevel1` → `ThorsHammerDamage.Amount`,
  `TerranShipWeaponsLevel1` → `WraithGU.Amount`, `TerranVehicle/ShipArmorsLevelN` → Diamondback/Hercules armor).
  **…BUT the family the player actually researches depends on the LAB STATE, and BOTH must be
  detected.** The Eng Bay button differs by whether the lab's `UltraCapacitors`/`VanadiumPlating`
  ROOT research is complete: BEFORE-lab (the default at every mission start — these ROOT upgrades
  are NOT force-granted, so the player always begins before-lab) the Eng Bay shows Research3/4/5
  (weapons) + Research7/8/9 (armors), which grant the **base** `TerranInfantryWeapons/ArmorsLevelN`
  ids (`liberty.sc2mod/AbilData.xml:1699-1734`); completing the lab ROOT HIDES those (their
  `.Show`) and reveals Research11/12/13 + Research14/15/16, which grant the **wrapper**
  `…UltraCapacitorsLevelN`/`…VanadiumPlatingLevelN` ids
  (`libertystory.sc2campaign/AbilData.xml:172-201`). **The two families are INDEPENDENT tech-tree
  entries** (`…UltraCapacitorsLevel1 parent="…UltraCapacitors"`, NOT `parent="…Level1"` —
  `liberty.sc2campaign/UpgradeData.xml:1591`): researching one leaves the other's
  `TechTreeUpgradeCount` at 0. So a trigger keying off "did the player research weapons/armor?"
  must **OR-detect BOTH families per level** — checking only one misses the other lab state. This
  bit the Eng Bay "combined upgrade" sync (`libWoLU_SyncWeaponArmorLevels`): detecting only the
  base ids worked before-lab but missed after-lab; a later fix detecting only the wrapper ids did
  the reverse (and made the diag read `infW=0` before-lab, falsely implying the sync hadn't fired
  — the diag now prints `base/uc` so the owner reads the effective state in EITHER scenario).
  **Robust rule: per level n in 1..3, detect `…WeaponsLevel{n}` OR `…WeaponsUltraCapacitorsLevel{n}`
  (armor likewise with `…ArmorsLevel{n}` OR `…ArmorsVanadiumPlatingLevel{n}`); on a hit, grant ONLY
  the base vehicle/ship `TerranVehicle/ShipWeapons/ArmorsLevel{n}` ids** (those carry the real
  effects; the vehicle/ship UltraCapacitors/VanadiumPlating variants are icon-only — granting them
  adds no damage and any duplicate-effect grant would double-apply) **guarded by a per-target
  `TechTreeUpgradeCount(... ) == 0` check so the periodic re-run is idempotent.** An absent id just
  returns 0, so OR-ing the extra id is harmless.
- Campaign upgrades already list **merc** units in their `EffectArray`s (e.g.
  `CombatShield` covers `WarPig`) but never heroes — extend via XML `CUpgrade`
  appends (`MarauderLifeBoost` = Kinetic Foam).
- **Extending a weapon/armor LEVEL upgrade's affected-unit list — and the two-family trap.**
  The weapon/armor upgrade tree splits into TWO families per level: the **base**
  `Terran{Ship,Vehicle}{Weapons,Armors}LevelN` ids (which our Eng Bay sync grants — they
  carry the REAL `Level`/`Amount`/`LifeArmor` effects) vs. the **wrapper**
  `…UltraCapacitorsLevelN`/`…VanadiumPlatingLevelN` ids (icon-only display variants the sync
  does NOT grant). **Gotcha:** the base-Level `EffectArray`s do NOT cover every player combat
  unit — several base fliers (Banshee, Battlecruiser, Viking) + base Thor/SiegeTank/Hellion
  armor + Medivac/Raven armor have their scaling entries ONLY in the bare **wrapper**
  `…UltraCapacitors`/`…VanadiumPlating` upgrades (the `default="1"` ids at
  `liberty.sc2campaign/UpgradeData.xml`: `TerranShipWeaponsUltraCapacitors` :394,
  `TerranVehicleArmorsVanadiumPlating` :318, `TerranShipArmorsVanadiumPlating` :467). In the
  base-Level upgrades those same units appear ONLY as cosmetic `Actor,<id>,LifeArmorIcon` /
  `Weapon,<id>,Icon` Set entries — NOT real scaling. So if you grant only the base-Level ids
  (as our sync does), those units don't scale. **Fix = mirror the missing units into the
  base-Level upgrades** via same-id `<CUpgrade>` overrides with **index-less new-key
  `EffectArray` APPENDS** (the CombatShield pattern — no explicit `index=` for NEW keys; that
  discipline is only for OVERRIDING an existing slot's Value). Resolve the mirror values
  against the wrapper, and re-state each LevelN identically (the per-level deltas are all `1`).
  **Two reach rules:** (1) **armor is a per-unit-id `Unit` field** → it does NOT propagate to a
  `parent=` merc, so `MercThor`/`MercHellion`/`MercWraith` need EXPLICIT armor entries; **weapons
  reach `parent=` mercs via shared effect ids** (the merc inherits the base weapon's `Effect`),
  so no merc-weapon entry is needed. (2) **Omit the wrapper's `LifeMax`/`LifeStart` `Operation=
  "Multiply" Value="1.05"` entries** — that +5% HP is a separate perk; the base-Level armor
  upgrades intentionally carry only `LifeArmor`+`LifeArmorLevel`. Before adding any unit, grep the
  base-Level upgrade's MERGED contents (libertystory + liberty.sc2mod layers) — standalone
  mercs/heroes (Wraith/Hercules/Odin/Predator/SpartanCompany/SiegeBreaker*/HelsAngel*/DukesRevenge/
  DuskWing/ScienceVessel) usually ALREADY have base-Level entries; don't duplicate. (Done v0.3.x:
  added the base fliers + Thor/SiegeTank/Hellion armor + Medivac/Raven armor + MercThor/MercHellion/
  MercWraith to `TerranShip{Weapons,Armors}LevelN` + `TerranVehicleArmorsLevelN` —
  `src/mod/Base.SC2Data/GameData/UpgradeData.xml`.) **One in-game caveat:** an upgrade entry
  modifying a weapon `Effect`'s `Amount` (e.g. `Effect,TwinGatlingCannons,Amount`) when our mod has
  rerouted that weapon's `Effect` to a `*WoLUSet` whose children are `parent="<that effect>"` —
  whether the bump reaches the already-loaded child clones is unverified statically, but it's the
  SAME class as the shipped Thor case (`Effect,ThorsHammerDamage,Amount` vs. the rerouted
  `ThorsHammerWoLUSet`), which works per owner. Flag it for playtest, don't block on it. Rule-9:
  these are global EffectArray edits but the player gets the upgrades per-player via the sync, and
  WoL never grants these exact base-Level ids to enemies → effectively player-only.
- **You can also CHANGE a vanilla CUpgrade's existing `EffectArray` *Value* (not just
  append new keys), and the safe way is by EXPLICIT `index=`.** A same-id `<CUpgrade>` in
  our static XML merges onto the vanilla definition. New `Reference=` keys append (the
  `CombatShield` hero pattern). To override an *existing* entry's Value, re-state it with
  its vanilla `index=` — an indexed `EffectArray` entry overrides the same array slot
  in place (proven: libertystory's `TwinLinkedFlameThrowers` does
  `<EffectArray index="0" Operation="Set" Reference="..." Value="0.5"/>` to set an entry).
  Index-less re-statements of an existing key are ambiguous (may append a duplicate
  "fighting" entry), so for a Value change prefer **re-stating the COMPLETE EffectArray
  with explicit indices 0..N in vanilla order** — duplicates are then impossible and your
  value wins unambiguously. Done for `RegenerativeBioSteel` (life regen 0.6015 → 20).
- **Ordering: an upgrade's `EffectArray Operation="Set"` is the LAST writer of the field
  it sets, beating a genlib per-player edit.** Our genlib `CatalogFieldValueModify` runs
  at MapInit; upgrades we auto-grant (e.g. `RegenerativeBioSteel`) are Set on the 1 s/10 s
  `libWoLU_OnGrantTech` timers, *after* MapInit → the upgrade Set overwrites whatever
  genlib wrote for the same field. So to buff a field that a granted upgrade also Sets,
  edit the **upgrade's EffectArray** (above), not the per-player field — a genlib edit
  there is silently overwritten (e.g. the genlib `Vulture LifeRegenRate=1` is overwritten
  by bio-steel). Upgrades like `RegenerativeBioSteel` are granted ONLY to the human player
  (the lab-research path our lib drives, never to AI), so editing the upgrade's Value in
  static XML is effectively player-only → rule-9-safe.
- State persists via ConversationState values and mission banks.
- **Granting a mission's research yield by hand: write ONLY the OPPORTUNITY points into
  `libCamp_gv_tSX_ResearchMissionProgress[mission][cat]` — the REWARD points are added by the
  engine automatically once the mission is `Completed`, so adding them to the array double-counts.**
  The Lab total (`libCamp_gf_StoryResearchPoints`, CampaignLib.galaxy:4853-4855) sums, per COMPLETED
  mission, `array[mission][cat] + libCamp_gf_TS_MissionRewardResearchPoints(mission,cat)`; the battle
  report (:4202-4207) splits the same way. The array (`CampaignLib_h.galaxy:784`, shape `[36][3]`,
  category 1=Protoss/2=Zerg) holds the per-mission OPPORTUNITY value only (= `libCamp_gf_TS_StoryResearch
  MissionOpportunities(mission,cat)`, :5000), NOT opportunities+reward. So a "100%-clear" hand-grant is:
  set the four difficulties complete (`libCamp_gf_TS_SetMissionDifficultyCompleted`, :3097) → mark
  `Completed` (`libCamp_gf_TS_MarkMissionAsStatus`, :3059) → store ONLY Opportunities in the array
  (guarded `if existing < new` so a partial clear isn't lowered) → `libCamp_gf_UpdateMissionFlow()`
  (:2967, re-propagates the unlock chain) → `libCamp_gf_PrepareForStoryModeTransitionalSave()` (:8474,
  the supported persistence path: opens bank, SaveTransitionVars Normal, BankSave, SaveMissionBanks —
  do NOT hand-roll BankSave). Used by the "Skip Prophecy missions" tstory01 button (v0.3.14,
  `LibWoLUnbalanced.galaxy`). Note the brief's literal `Opportunities+Reward` into the array would have
  double-counted the reward — the engine's add-on-completion is the gotcha. [STATIC mechanism; in-game
  Lab-total render GAME-pending owner confirm.]

## Data sources

- [SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData): full dumps —
  `mods/liberty.sc2mod`, `campaigns/liberty.sc2campaign` (catalogs; campaign stats
  differ from wikis — Ghost is 150/150), `campaigns/libertystory.sc2campaign`
  (CampaignLib sources), `campaigns/liberty.sc2campaign/base.sc2maps` (vanilla map
  fallback), `mods/missionpacks/novacampaign.sc2mod` (Nova Covert Ops — origin of
  many Archipelago upgrade designs, e.g. healing stim), `mods/starcoop` (co-op).
- Hero ↔ base map: Raynor01/RaynorCommando/Raynor=Marine,
  TychusCommando/TychusChaingun=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost,
  Tosh=Spectre, Odin=Thor. Ready-made free-cloak behaviors exist:
  `PersonalCloakingFree`, `SpectreCloakingFree`.
- Merc calldown: `SummonMercenaries` `InfoArray[Train1..8]` with `Charge.CountMax/
  CountStart` and `Cooldown.TimeStart` (vanilla 300 = 5 min wait at mission start).
- **A merc's RESOURCE cost is the CALLDOWN's, not the unit's — and IS per-player-editable.**
  The merc UNIT's own `CostResource[Minerals]/[Vespene]` is INERT: mercs are SUMMONED via
  `SummonMercenaries`, never trained, so the unit's train cost is never read (a per-player edit
  on it is a no-op; heroes are likewise map-placed → moot). The cost the player actually pays is
  the calldown's **`SummonMercenaries InfoArray[TrainN].Resource[Minerals]`** (and `[Vespene]`)
  — an indexed SCALAR nested under the InfoArray entry (verified path; same applies-per-player
  class as `InfoArray[TrainN].Charge.*`/`Cooldown.*` and the unit's own `CostResource[*]`), so
  `CatalogFieldValueModify` on it DOES apply per player (preview CHECK8-GOOD once the classifier
  knows the shape — see `scripts/preview.py classify()`). So **cost parity for a merc goes
  through the calldown, keyed to `SummonMercenaries` + the merc's Train index — NOT the merc
  unit id.** v0.3.11 reduces each merc's summon cost by the same amount its base unit's
  per-player cost cut, floored at 0 (genlib's "merc calldown cost parity" block; computes the
  final at build time as `max(0, current − cut)` and emits a `Set`). Train-index ↔ merc map:
  Train2=Devil Dogs, Train3=Spartan Company, Train4=Hammer Securities, Train5=Siege Breakers (no
  Resource = free), Train9=Skibi's/MercMedic, Train10=Death Heads/MercReaper, Train11=Condor,
  Train12=Jotun, Train13=Winged Nightmares, Train15=Senior Ghost/MercSeniorGhost. (This is also
  why CHECK10 correctly EXCLUDES the merc/hero UNIT cost field from unit-field parity — that
  field is inert; the real cost lives on the calldown and is handled separately in genlib.)
- **Firebat damage chain (and "Infernal Pre-Igniter" is NOT a Firebat upgrade).** The Firebat's
  attack damage is the `FirebatUFull` `CEffectDamage` (`Amount=8`, `AttributeBonus[Light]=4`) — fired
  both directly (`FirebatSet`=[`Firebat` persistent, `FirebatUFull`]) AND repeatedly by the persistent
  flame (`Firebat`→`FirebatE` ×4→`FlameThrowerDamageSet`=[`FirebatUFull`, `FlameThrowerApplyDoTBehavior`]).
  So a flat attack-damage buff goes on `FirebatUFull.Amount` (CHECK8-GOOD). The merc mirror is
  `DevilDogDamage` (`Amount=10`, `+5` Light) via `DevilDogSet`; ratio 10/8 = 1.25 sets the rule-4 merc
  scale. Tychus (=Firebat hero, rule 10) uses **chainguns**, not the flamethrower: `TychusCommando`→
  `TychusCommandoChaingun`→`TychusCommandoAttackDamage` (`Amount=5`); `TychusChaingun`→`TychusChaingun`
  weapon (its `Effect`/`DisplayEffect` are commented out → defaults link to the same-id
  `TychusChaingun` effect, `Amount=16`); neither has a Light bonus. **The +vs-light is intrinsic, not
  an upgrade:** "Infernal Pre-Igniter" (`HellionCampaignInfernalPreIgniter`) is a **Hellion** armory
  upgrade; the Firebat/DevilDog `AttributeBonus[Light]` is hardcoded in the static effect and applies
  to enemies too. Removing it for the player only = a Shaped-Blast effect clone (recipe 13), since a
  per-player `AttributeBonus[Light]` edit is CHECK8-NOOP — there's no grant-list to exclude.

## Verification tooling

- **SC2 client API live reads are a HARD BLOCK on retail 5.x** (this Mac). `scripts/verify_api.py`
  can `RequestPing` + `RequestCreateGame` (campaign map loads, mod deps resolve — a "mod loads via
  the engine" sanity check), but `RequestJoinGame` ALWAYS fails `"Unable to validate game license"`.
  NOT bypassable by Battle.net SSO/`-sso`, reaching the main menu, `Play Offline`, `--attach` to a
  BNet-launched instance, or timing — confirmed against Blizzard's `s2client-proto` repo + community.
  The only API binary for live reads is the Linux headless **4.10** (no 5.x). So live HP/armor/cargo
  reads are impossible here; verification = static analysis (`audit.py` + merge sim +
  `implementation-patterns.md`) + the owner's in-game playtest. **Don't re-attempt the API for live
  verification on this Mac.**
- **Account ban risk — SAFE for our workflow (sourced).** Galaxy Editor + CCM offline-campaign mods
  carry ZERO ban risk (official Blizzard tools/file formats, no process injection, no multiplayer).
  The s2client-proto API is covered by Blizzard's OWN "AI and Machine Learning License" which
  explicitly overrides the EULA's anti-automation + matchmaking clauses (a Battle.net account is
  "not required"); no documented ban exists for local/offline API use. Launching `-listen` idle (never
  joining a game) = indistinguishable from launching SC2 and not playing. Real ban triggers are ONLY:
  online/ladder maphacks/cheats, memory-injecting trainers, botting multiplayer, account sharing.
  RULES: only official tooling; never automate ONLINE play; keep any API use localhost-only & never
  enter an online game; never inject into the SC2 process.
- **The SC2 Editor is a sanctioned VALIDATION path** the API/`audit.py` can't match. Its Previewer
  (`ObjectViewInPreviewer` → portrait aspect) RENDERS a unit's model + portrait → answers the
  heart-portrait / sphere questions locally. It shows the merged STATIC catalog (cards, armor-name
  resolution, `parent=` wiring, a field-diff of our layer) but NOT per-player runtime
  `CatalogFieldValueModify` numbers (those need the lib to run in a game). Its **Test Document**
  (Ctrl+F9) launches via Battle.net's own mechanism → gets the SSO license token → should BYPASS the
  API's `JoinGame` license block and run the mod in-game (lib applies per-player edits; canary + diag
  lines show). Worth a 2-min trial on `build/maps/Campaign/traynor01.SC2Map` (a campaign-license guard
  `EDSTR_ERROR_TESTDOC_NOCAMPAIGNLICENSE` may or may not fire).
