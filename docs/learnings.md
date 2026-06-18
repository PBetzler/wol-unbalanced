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
- Campaign upgrades already list **merc** units in their `EffectArray`s (e.g.
  `CombatShield` covers `WarPig`) but never heroes — extend via XML `CUpgrade`
  appends (`MarauderLifeBoost` = Kinetic Foam).
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
