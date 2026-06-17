# Open Issues

The canonical bug tracker for WoL Unbalanced — confirmed in-game defects, not the test plan ([verification-checklist.md](verification-checklist.md) is the "what to test", this is the "what's broken"). Each entry is a concrete defect with the version it was seen in + root-cause notes.

Format: `- [ ]` open, `- [x]` resolved. Newest at the top of each section. When a fix ships, move the item to **Resolved** with the version + the actual fix.

Running gate: `python3 scripts/audit.py` catches the structural classes statically (missing/malformed actors, dead calldowns) before a build ships; the rest below need in-game observation.

## Editor verification pass (2026-06-17) — SC2 Editor Previewer, local build working

The Windows local build now works end-to-end (portable MinGW+CMake → `mpqpatch.exe` →
`build.py build` patched 30 maps; see [SETUP.md §3](SETUP.md)). The mod was loaded into the SC2
**Editor** (Data module + Previewer / Data Navigator) and these were confirmed:

- [x] **Elite-merc PORTRAITS render (the long-standing "heart placeholder" question) — CONFIRMED
  for the representative case.** `MercThor` (Jotun) resolves to body model **"Thor"** and portrait
  model **"Portrait - Thor"** (the real Thor portrait, NOT a heart; the model renders in the
  Previewer, NOT a sphere). `Condor` (Hellion merc) renders as a Hellion. The merc-clone
  model/portrait mechanism is therefore proven in the Editor; combined with audit CHECK6 (all 6
  `*Portrait` tokens are valid base-CASC tokens) this settles the heart-portrait item for the
  loaded mercs. (Death Heads / Skibi's Angels / Senior Ghost are structurally identical and were
  not individually previewed.)
- [x] **Shielded-merc armor signs — CONFIRMED resolve (not "unknown").** Jotun & Condor both show
  `ShieldArmorName` = **"Defensive Matrix"** and `LifeArmorName` = **"Terran Vehicle Plating"** in
  the merged catalog. (The dual-icon *side-by-side render* remains a [GAME] in-game observation.)
- [x] **MercThor resurrect cost zeroed — CONFIRMED.** Jotun `CostResource` reads 0/0/0 in the
  Editor (the Immortality-Protocol "no gas" piece; the death-response *firing* is still [GAME]).
- [x] **`MercWraith` (Winged Nightmares) standalone-view absence — RESOLVED (was a
  missing-dependency artifact, not a bug).** It was absent only when the mod was opened **standalone**
  (Liberty-Mod dep only). **Re-checked with the full dependency stack** (opened the built
  `traynor01.SC2Map` in the Editor): **Winged Nightmares appears and resolves correctly** — Wraith
  weapons (Gemini Missiles + Burst Lasers), Wraith Cloaking Field, flying/air, Life 200 / Shields 50 /
  Life Armor 1 (exactly the static XML values, `UnitData.xml:586-597`), Shield Armor Name =
  "Defensive Matrix". All 6 elite mercs load + resolve with full deps. Lesson: **verify clones in a
  loaded MAP (full deps), not the standalone-mod Editor view** — the latter lacks the campaign layer
  and drops campaign-dependent entries.
- [x] **Our edits ARE the top merged layer + clone families resolve — CONFIRMED across recipe
  families.** In the full-deps map the units we modify show **Source = `WoLUnbalanced.SC2Mod`**
  (Medic, Marauder, …) i.e. our layer wins the merge. Spot-checks: the **Marauder's** merged ability
  list includes **"Super Stimpack"** (`StimpackMarauderWoLU` — recipe 08 / the Bug-1 ability side is
  wired in); the **Medic's** merged abilities include **Optical Flare + Restoration** (the AP-port
  clones — recipes 09/20 resolve). So the unit-clone, added-ability and autocast-ability recipe
  families are confirmed present + resolved in the real merged catalog.
- **[STATIC-vs-RUNTIME framing — what the Editor can and cannot confirm.]** The Editor shows the
  **merged STATIC catalog**, so it confirms: clones resolve, models/portraits render, armor/name
  strings resolve, cards merge, and our layer wins. It does **NOT** show **per-player runtime
  `CatalogFieldValueModify` edits** (the buffs) — by design (rule 9): e.g. the Marauder's `CargoSize`
  reads the un-modified **2** in the Editor (our per-player `=1` only applies when the lib runs
  in-game), and Medic Life reads the base **60** (not the +HP buffs). So the recipes' **[STATIC]/
  [EDITOR]** claims are Editor-verified here; the **[GAME]** claims (runtime numbers, autocast
  firing, death-response, splash, simultaneous fire) are inherently NOT Editor-observable and remain
  for the owner's in-game / CCM playtest. This is the correct, expected split — not a gap.

## Preview lens + CHECK8 cleanup (2026-06-17) — dead runtime edits removed, gaps surfaced

Built `scripts/preview.py` (the buff manifest + **CHECK8**, now in the pre-commit gate + CI — see
[verification-ledger.md](verification-ledger.md)). It parses the generated lib's 332 per-player
edits and classifies each: **GOOD 326 / NOOP 0 / UNCERTAIN 6 / UNRESOLVED 0** after cleanup. CHECK8
**fails** if any runtime edit ever lands on a known no-op field class again.

- [x] **Removed 11 dead no-op runtime edits + 1 dead id (behavior-neutral — they did nothing).**
  From `genlib.py`: per-unit `CargoSize=1` ×4 (load-time read), `AttributeBonus[Light/Armored]=0`
  ×3 on the rifles (indexed-array element), `Button.Requirements=""` ×2 (link field), `FirebatUFull
  AttributeBonus[Light]+4` (indexed-array), `heal TargetFilters` (string field), and the bogus
  `SpectreCloak` id in `CLOAK_ABILS` (Spectres cloak via `RogueGhostCloak`, already listed). Each was
  a silent no-op, so removal changes no in-game behavior — it just shrinks the dead surface and makes
  CHECK8 green. The gen lib dropped 364 → 352 lines.
- [ ] **⚠ NEW (minor) — Firebat "Infernal Pre-Igniter" +4 vs light never applied.** The
  `FirebatUFull AttributeBonus[Light]+4` edit was an indexed-array no-op (now removed). To actually
  grant it, needs a Shaped-Blast effect clone (recipe [13](examples/13-flatten-attribute-bonus.md)).
  Low priority — the Firebat is already massively buffed (×2 HP +100). Decide: build the clone, or
  drop the upgrade.
- [x] **`heal TargetFilters` runtime edit was dead-redundant — confirmed.** The heal-mech/air feature
  ships via the `HealWoLU` clone on the Medic (`AbilArray index 6`) + Stetmann (`index 5`); the
  string-field runtime edit never did anything. Removed.
- **UNCERTAIN (kept, flagged):** the 6 free-cloak `Modification.VitalRegenArray[Energy]=0` edits are
  an indexed regen-array element (recipe-02 would call it a no-op) but free cloak is GAME-confirmed
  working — kept, re-verify only if cloak energy-drain ever returns.

> Cross-ref: the **rifle-flatten** item below (Ghost/Spectre still read +vs-light/armored) and the
> **Marauder Tech Lab / Hercules Fusion Core** blocked item are the two real gaps these no-op
> removals confirmed — both already tracked; the cleanup just stopped pretending the dead runtime
> edits implemented them.

## Yamato + Defensive Matrix autocast — verified + retuned (2026-06-17)

Owner asked to verify the Battlecruiser / Jackson's Revenge (`DukesRevenge`) kit.

- [x] **Yamato autocast — VERIFIED wired correctly.** `YamatoWoLU` (base BC) + `DukesRevengeYamatoWoLU`
  both: `AutoCast`+`AutoCastOn`, explicit `Effect=Yamato` (CHECK4-safe), `AutoCastValidatorArray=
  WoLUYamatoBigTarget` (only fires on `LifeMax≥300` targets, so the 125-energy blast isn't wasted on
  small units), structures skipped, button re-pointed (`WoLUHaveFlag`). Statically sound; in-game
  firing is the owner's [GAME] check.
- [x] **Defensive Matrix autocast — RETUNED to "on taking damage" (was "on firing").** Owner spec:
  the shield should auto-trigger **only when the unit takes any damage**. It was gated on
  `CasterIsFiringWeapon` (fires while *attacking*) — wrong. Changed both `DefensiveMatrixWoLU` (base
  BC + Science Vessel) and `DukesRevengeDefensiveMatrixWoLU` to a new `WoLUCasterDamaged` validator =
  caster **Life fraction < 1.0** (`CValidatorUnitCompareVital Type=Fraction`, the percent-of-max mode
  confirmed from vanilla `ShieldsFull`). So the shield now goes up only when the unit is below full
  HP (= has taken damage). [STATIC — audit confirms the validator resolves + is referenced; the stim
  autocasts correctly KEEP `CasterIsFiringWeapon`. GAME — owner confirms it auto-shields when hit; it
  reuses the same self-buff-autocast mechanism as the GAME-confirmed super-stim, just a different
  caster-state gate.]

## Elite-merc clone ANIMATION-EVENT audit (2026-06-17) — full sweep of all units/mercs/heroes

Owner asked: "check all the animations in the editor — are they all there for all units, mercs and
heroes?" Done as a **reference-catalog comparison** (our `CActorUnit` actors vs each base unit's
vanilla actor in `mods/_reference/liberty.sc2{mod,campaign}/ActorData.xml`) — more precise than GUI
playback, which can only show a model renders (already editor-confirmed, see the 2026-06-17 pass
above) but NOT which in-game anim EVENT fires. Findings:

- **Heroes, base units, the 8 standard mercs (War Pigs … Jackson's Revenge): all animations intact.**
  They use **vanilla actors** (untouched by the mod) → every Stand/Walk/Attack/Spell/Death animation
  is present by definition. No clone risk.
- **The 6 elite-merc clones bind MINIMAL `GenericUnitBase` actors** (only `<Model>`+`<PortraitModel>`),
  because the vanilla actor binds to the base unit (`unitName="Thor"`), not the merc. So they get the
  generic move/idle/death/**basic-attack** bracket — those work for all 6 — but the base unit's
  **unit-specific** anim events were copied into **`MercThor` only** (the v0.2.4 Jotun fix). The other
  5 lack theirs. **None are BROKEN** (unlike the Jotun was); all are **cosmetic pose/cast gaps** —
  the models contain every animation, only the event wiring is absent:
  - [x] **Winged Nightmares (`MercWraith`)** — dual-weapon: vanilla splits `WraithA→Attack,Superior`
    (air) vs `WraithG→Attack` (ground). Ours plays the base ground pose for air too → **no upward-aim
    variant on air attacks.** Same CLASS as the fixed Jotun bug, much milder (still fires + animates).
    **FIXED (2026-06-17):** copied the vanilla Wraith actor's 5 weapon-anim events verbatim into
    `CActorUnit id="MercWraith"` (WraithA→Superior / WraithG→base, Ready apply/remove, AttackStop).
    [STATIC — pose fires in-game only; owner to confirm air units aim upward.]
  - [x] **Skibi's Angels (`MercMedic`)** — no `Abil.heal` channel pose (vanilla Medic also parents the
    richer `GenericUnitStandard`). **Medic stands still while healing** (beam/effect still shows).
    NB: the player merc casts **`HealWoLU`**, not `heal` — a fix must key the event on the clone id.
    **FIXED (2026-06-17):** added the `$Spell PlayForever` / `AnimClear Spell` channel pose keyed on
    **`Abil.HealWoLU.SourceChannelStart/Stop`** (verified: Medic AbilArray[6]=HealWoLU + card button 6
    re-pointed → the player merc casts HealWoLU; HealWoLU is `CAbilEffectTarget parent="heal"` so it
    fires the same channel events). Also keyed on vanilla `Abil.heal.*` as a belt-and-braces autocast
    fallback (harmless — the actor is worn only by the player-only merc). [STATIC — owner to confirm.]
  - [x] **Senior Ghost (`MercSeniorGhost`)** — no Snipe/EMP/nuke **cast poses**, no elevation-aim
    variants, no hold-fire cover. Effects fire; no animation. NB: it autocasts `SnipeWoLU`/`EMPWoLU`,
    not vanilla `Snipe`/`EMP` — fix must key on the clone ids.
    **FIXED (2026-06-17):** copied the `GhostAlternate` actor's combat + spell-cast events (the worn
    model) into `CActorUnit id="MercSeniorGhost"`, RE-KEYED `Snipe`→`SnipeWoLU` (3 phases:
    CastStart/Stop, ChannelStart/Stop, FinishStart + SpellC walk-cancel) and `EMP`→`EMPWoLU`
    (`Abil.EMPWoLU.SourceCastStart`); kept `Abil.TacNukeStrike.*` and `Behavior.GhostHoldFireB.On/Off`
    on their UNCHANGED vanilla ids (verified both inherited via parent="Ghost", not re-pointed); copied
    the rifle WeaponStart Attack bracket with Superior/Inferior elevation variants verbatim. Skipped the
    Ghost→GhostAlternate morph Destroy event (the merc is not a morphing unit). [STATIC — owner to
    confirm cast poses + upward/downward aim.]
  - [x] **Condor (`MercHellion`)** — no flame-beam **cleanup** timers → the `HellionAttackBeam` may
    linger when the unit moves. Minor visual.
    **FIXED (2026-06-17):** copied the vanilla Hellion actor's 3 `KillBeam` cleanup events verbatim
    (Walk + ReadyStop → `TimerSet 0.25 KillBeam`; TimerExpired → `Destroy HellionAttackBeam`); ids
    inherited unchanged. [STATIC — owner to confirm the flame beam no longer lingers on move.]
  - [x] **Death Heads (`MercReaper`)** — Reaper's vanilla actor is a **core** unit (not in our ref
    dump), so it couldn't be diffed; Reaper is single-weapon, so the generic bracket likely covers it.
    Lowest risk; flagged as unconfirmed.
    **LEFT AS-IS (2026-06-17), confirmed correct disposition:** searched all reference sources
    (`mods/_reference/*`, `mods/*`) — there is **NO `CActorUnit id="Reaper"`** anywhere (only a
    `CActorMissile id="Reaper"` and a `CActorUnit id="ReaperPlaceholder"`), confirming the Reaper unit
    actor is a core unit absent from the dump. The Reaper's combat weapon is single (the pistols; the
    `D8Charge` building-attack is a separate ability), so the generic `GenericUnitBase`
    `WeaponStart.*.AttackStart` bracket already covers its basic attack. No events fabricated. No change
    needed.

  **All 5 implemented (2026-06-17).** 4 mercs got their vanilla actor's `<On Terms=…>` events copied
  in (verbatim weapon-anim events; re-keyed to `HealWoLU`/`SnipeWoLU`/`EMPWoLU` where the mod re-points
  the ability), following the proven MercThor pattern; Reaper left as-is (no vanilla unit actor exists
  to copy and the generic bracket covers its single weapon). Every added event is in-game-only-
  verifiable — gate (genlib/lint/audit/preview/check_autocast) green, owner to confirm the poses.

## Clone metadata (the Merc* elite mercs)

- [x] **Inspect panel armor/defense category** — shield armor was "unknown" (FIXED v0.2.2 via `ShieldArmorName`). **v0.3.8: the NORMAL life-armor sign was missing** — added an explicit `LifeArmorName` (= each merc's base-unit vanilla value, verified against `mods/_reference/`) so the life-armor category resolves on a shielded clone. Statically proven (audit CHECK7 confirms the keys resolve); the heart-portrait piece is the only remaining in-game item (see v0.3.7 #4 below).

## Damage display + values

- [ ] **"X dmg + X vs light/armored" should flatten to "X dmg"** (Ghost, Thor AA, Spectre).
  **DIAG QUESTION ANSWERED (2026-06-17, statically, by the preview lens / CHECK8 — no in-game diag
  needed):** a per-player `CatalogFieldValueModify` on an effect's `AttributeBonus[Light/Armored]`
  is an **indexed-array element → confirmed no-op** (CHECK8 classifies it NOOP; the dead edits were
  removed from genlib). So the `Amount` raise applied but the `+vs-light/armored` bonus **remains**:
  **Ghost rifle ships 20 (+10 vs light), Spectre 20 (+5 vs armored)** — not flat 20. (Thor AA's flat
  35 IS delivered, via the `JavelinMissileLaunchersDamageBuffedWoLU` effect clone — that one's done.)
  **FIX for the rifles = the Shaped-Blast effect clone** (recipe [13](examples/13-flatten-attribute-bonus.md)),
  same pattern as Thor AA. Owner decides: build the clone (flat 20) or accept the +bonus. The diag3
  readback is now moot — the lens settles it without a playtest.
- [ ] **Senior Ghost should hit ~30 dmg** (base ghost 20 × +50%). v0.2.5 FIXED the likely no-op: `DamageDealtFraction` is an additive, per-damage-Kind INDEXED array (confirmed: liberty `DoubleDamage` = `DamageDealtFraction index="Ranged" value="1"` → ×2). The old scalar `DamageDealtFraction="0.5"` had no Kind index; rewritten to indexed form (Ranged/Spell/Melee/Splash = 0.5 → +50%). The card still shows weapon base (20) — a damage-dealt buff never changes the displayed weapon number; confirm the *dealt* damage is ~30 in game.

## Units / mechanics

- [ ] **All 8 standard mercs available from start** — logic CONFIRMED correct v0.2.4 (direct `TechTreeUnitAllow` of all 8 merc unit types; no counterpart-subgroup leakage). In-game re-test only: do all 8 appear with no Marauder/Firebat/Factory leakage?

## UX

- [x] **The elite-merc submenu collapses after buying a merc** — RESOLVED v0.3.6: dropped the submenu and put ALL 14 mercs (8 vanilla + 6 elite) on the Merc Compound **root** card, which never collapses (the card returns to root after every command, so root-card buttons persist — that's why the vanilla 8 always worked). Reclaimed 3 low-value buttons (SelectBuilder, Rally, Halt — a calldown building needs none; Cancel stays) to fit the 6 elite mercs. Verified with the card-merge simulator: 14 merc buttons on one persistent card, no real collisions.

## Flagged mechanisms — implemented but unverified (harden by static investigation)

These shipped and *probably* work, but the field/semantics were assumptions. Verify each against the reference catalogs (`mods/_reference`, `scripts/xmlq.py`) and fix if wrong — don't wait for in-game testing to find out.

- [ ] **Yamato structure discrimination** — autocast currently skips ALL structures (safe energy policy; manual works on anything). Refinement (auto-fire on *defensive* structures only) is now possible — the attack-capable primitive is `CValidatorUnitCompareAttackPriority parent="Threatens"` (e.g. `ThreatensPhoenix`/`ThreatensBattlecruiser`) — but DEFERRED: an untested autocast tweak risks draining the BC's 125-energy Yamato on the wrong targets. Owner call on whether the auto-fire-on-enemy-defenses is wanted.
- [ ] **Graduating Range** — confirm 5 stacks = +5 sieged range (`WoLUGraduatingRange` MaxStackCount). Structure CONFIRMED correct v0.2.4 (MaxStackCount=5, `Modification WeaponRange=1` per stack); in-game count check only.
- [ ] **Assumption values** — Optimized Logistics = −25% train time; Diamondback Hyperfluxor/Maglev ±25%. Settle against AP data if findable.
- [ ] **`Button.Requirements` per-player edit (Marauder Tech Lab + Hercules Fusion Core)** — v0.2.4 set both train buttons' `Requirements` to empty (rule-compliant attempt). This is a requirement-LINK field; per-player link edits are often no-ops. VERIFY: can the player build a Marauder with no Tech Lab / a Hercules with no Fusion Core? If not, the field is a no-op and the only working lever (`TechTreeRestrictionsEnable(p,false)`) is rejected because it also strips the Merc Compound requirement (rule 6). **Lens (2026-06-17): `Button.Requirements` is statically CONFIRMED a no-op class (CHECK8 NOOP — a requirement-LINK field); the two dead edits were removed from genlib.** So the feature genuinely does not work as a runtime edit — the in-game "can you build without the building?" verify is moot (confirmed no). Stays OWNER-BLOCKED (accept the prereqs, or accept losing the Compound gate).
- [~] **Medic Adaptive Medpacks (heal mech + air)** — the "does a per-player string-field edit apply?"
  question is **ANSWERED: NO** (the preview lens classifies `heal TargetFilters` as a NOOP string
  field; the dead edit was removed). But the feature **ships via the `HealWoLU` clone** (broadened
  `TargetFilters` baked in) on the Medic `AbilArray index 6` + Stetmann `index 5` — recipe
  [09](examples/09-broaden-targeting.md). So nothing is missing; the only remaining check is the
  [GAME]/Layer-3 one: confirm the Medic actually heals a Marauder/Viking in game (the clone's effect).
- [x] **Risky field paths — CLASSIFIED by the preview lens / CHECK8 (2026-06-17), no diag needed.**
  `SummonMercenaries` `Charge.*`/`Cooldown.*` and cloak `Cost[0].Vital[Energy]` are **GOOD** (nested
  per-player scalars that apply — CHECK8 confirms the class; the manifest shows their finals).
  `FirebatUFull AttributeBonus[Light]` was **NOOP** (indexed-array, removed — see the Pre-Igniter gap
  above). The only **UNCERTAIN** is the free-cloak `Modification.VitalRegenArray[Energy]` (indexed
  regen-array; cloak-free is GAME-confirmed working, so kept + flagged).
## Blocked — needs owner

These are investigated to ground truth but need an owner decision (a rule-9 tolerance call or a design choice), not more investigation.

- [ ] **Marauder Tech Lab / Hercules Fusion Core drop** — if the per-player `Button.Requirements=""` edit proves a no-op in game (verify), the only working lever is `TechTreeRestrictionsEnable(p,false)`, which also strips the Merc Compound requirement (rule 6). **DECISION:** accept losing the Compound gate to drop build prereqs, or leave the prereqs in place?

### Owner-resolved (v0.3.3)
- [x] **Raven self-Point-Defense** — owner rejected a hidden always-on intercept weapon (would be active on enemy Ravens). RESOLVED with the owner's energy-cost design: the player's Raven kit is made free to activate (`PlacePointDefenseDrone`/`BuildAutoTurret`/`SeekerMissile` energy → 0 per-player) so it spams free permanent PDDs/turrets; enemies keep vanilla costs (rule 9 clean).
- [x] **Reaper literal flight / anti-air** — owner is fine with the Reaper not shooting air; the flight morph is forbidden. Reverted the interim anti-air edit; Reaper keeps vanilla ground-only targeting.
- [x] **Hellbat Aspect** — owner: not pulling in HotS assets. Dropped from the backlog.

## In-game playtest batch (2026-06-15, fixed in v0.3.5 — pending re-test)

13 issues reported from a fresh playthrough. Root causes traced statically (catalog-merge
simulator + reference catalogs); fixes below. Items marked ⚠ are best-effort / not locally
verifiable.

- [x] **#3 Marauder has no stim** — the campaign REMOVES the Marauder's stim ability
  (`AbilArray index=3 removed=1`) and our old button override only set `AbilCmd` on the
  *AblativeScales passive* button (index 6) → stayed Type=Passive, never worked. Re-added the
  ability (index-3 override) and APPEND a real stim button at index 10 (cell 2,0). Devil Dog
  was already structurally correct (identical to Firebat) — re-verify it shows.
- [x] **#4 Siege Breaker spider mine "Can't turn towards target"** — a SIEGED tank can't turn;
  the ability needed `Flags IgnoreFacing=1`. Also switched the effect to the vanilla
  `SpawnSpiderMineSet` (the raw create skipped the burrow set) + added `Placeholder`.
- [x] **#5 Jackson's Revenge: Yamato not autocast / no attack upgrades** — added autocast
  clones `DukesRevenge{Yamato,MissilePods,DefensiveMatrix}WoLU` (re-pointed its 3 buttons),
  added ignore-armor (`ArmorReduction=0`) on its DR damage effects (the missing "attack side"),
  and a fire-while-moving passive display.
- [x] **#6 Brynhilds = Wraith look/upgrades** & **#9 Midnight Riders = Viking** — REMOVED both
  (owner decision). Their intended Valkyrie/Liberator models don't exist in WoL, so they only
  ever reskinned to Wraith/Viking. Units, actors, portraits, morphs, calldowns, buttons,
  strings all deleted.
- [x] **#11 cloaking units don't spawn cloaked** — `PersonalCloakingFree` is a permanent-cloak
  buff (StateFlags Cloak=1); it was only applied to ~6 unit types. Expanded the periodic
  apply to ALL cloak-capable player units (Ghost, Spectre, Banshee, Wraith, Reaper, Medivac,
  Predator, Nova, Tosh, Dusk Wings, Winged Nightmares, Senior Ghost). Cloaked ≤2 s after spawn.
- [x] **#12 Spartan Company missing upgrades** — it's a separate Goliath *merc*, not a clone, so
  it never inherited Goliath's WoL upgrade displays. Added Shaped Hull + Optimized Logistics
  passives (stat parity was already applied in genlib on `SpartanCompany*`).
- [x] **#2 bunker "full but slots empty"** — `TotalCargoSpace=8` but `MaxCargoCount=4`: size-1
  marines hit the 4-unit cap while the 8-space bar showed room. Set `MaxCargoCount=8` to match.
- [x] **#7 Jotun (Thor merc) upgrade panel** — the base-Thor passive display was at index 7,
  clobbering the 250mm Cancel button + colliding at cell 1,0. Appended at 10/11 (Laser
  Targeting + Shaped Hull); MercThor inherits them via `parent="Thor"`. ⚠ AA still reads
  35 (+ residual "vs light"): the per-player `AttributeBonus[Light]=0` array-edit is a no-op
  (see damage-display item); the *value* (35) is correct — full flatten needs an effect clone.
- [x] **#13 Medic doesn't heal mechanical** — the per-player `heal.TargetFilters` string edit
  is a no-op. Added a `HealWoLU` clone (parent `heal`, broad TargetFilters incl. Mechanical+Air,
  explicit `Effect=heal` so it doesn't re-default to a nonexistent id), autocast + gated button,
  on Medic (Skibi's Angels inherit) + Stetmann.
- [x] **#1 Command Center: no MULE** — our mod never touched the CC. Per owner, added a free,
  unlimited Calldown: MULE + Extra Supplies kit (`CalldownMULEWoLU`/`SupplyDropWoLU`, no Orbital
  requirement, WoLUHaveFlag-gated). ⚠ buttons appended at index 14/15 assuming the campaign CC
  has 14 card buttons (3-layer merge) — verify they appear.
- [x] **#8 elite mercs: heart portrait + "unknown" shield** — shield: `ShieldArmorName` was a raw
  string "Defensive Matrix"; the engine wants a string-table KEY (vanilla uses
  `Unit/ShieldArmorName/...`) → added `Unit/ShieldArmorName/WoLUDefensiveMatrix`. ⚠ portrait:
  the old custom `Merc*Portrait` CModels pointed at GUESSED `.m3` paths (→ heart); switched the
  actors to reference the base portrait CModel ids (`MedicPortrait`, `ReaperPortrait`, …) which
  must exist (the real units resolve them via `##unitName##Portrait`). Not locally verifiable.
- [ ] **⚠ #10 Senior Ghost "two stim buttons"** — NOT statically reproducible. The merged
  Senior Ghost card has EXACTLY ONE stim button (index 13), identical to the regular Ghost which
  works fine; no second source exists in any catalog layer (merge simulator confirmed). If it
  persists after v0.3.5, need a screenshot — possibly a multi-select / AbilSetId UI artifact.

## In-game playtest batch (v0.3.9 — implemented against docs/implementation-patterns.md)

4 bugs from a playthrough, implemented against the VERIFIED `docs/implementation-patterns.md`
(its root-cause analysis was independently double-checked). "[STATIC]" = statically settled here;
"[GAME]" = the mechanism is statically correct/complete and the *effect* awaits the owner's
in-game playthrough (no SC2 MCP). The verified-vs-needs-in-game split is deliberate.

- [~] **Bug 1 — Hammer Securities (Marauder merc) has no super stim** — [STATIC fix]. Root cause
  (ref §3.1): `HammerSecurity` is a STANDALONE unit (not a `parent="Marauder"` clone), so the base
  Marauder's stim CARD button doesn't reach it. The ability was already swapped (`AbilArray index 3`
  = `StimpackMarauderWoLU`) but the merged card had NO stim button at all (confirmed via the
  card-merge simulator: buttons 0-4 = move/stop/attack row, 5 = JackhammerConcussionGrenade passive
  @2,0, 6 = AblativeScales passive @2,1; max index 6, no AbilCmd stim). FIX: APPENDED a fresh
  `Type=AbilCmd` stim button at the next free index (7) in a verified-free action cell (2,2),
  `Face="Stim" AbilCmd="StimpackMarauderWoLU,Execute"` (Marauder #3 pattern). Button is
  `WoLUHaveFlag`-gated; the merc is player-exclusive so the gate is always satisfied. ⚠ [GAME]
  owner confirms the stim button shows on Hammer Securities and autocasts in combat.
- [~] **Bug 4a — Jotun Immortality Protocol now WORKS** — see the REOPENED v0.3.7 #9 item above
  (parallel `MercThor{DontDie,Wreckage,Reborn}` chain; [STATIC] design, [GAME] death-response).
- [x] **Bug 4b — Jotun "time to first shot" windup** — STATICALLY SETTLED, no change needed. The
  rule-7 `DamagePoint`≤0.1 cap is applied per-player to BOTH Thor weapons: `ThorsHammer` (AG,
  was 0.831) AND `JavelinMissileLaunchers` (AA, was default 0.167) — confirmed in the generated
  `LibWoLUnbalancedGen.galaxy` rule-7 block. `MercThor` (parent="Thor", no `WeaponArray` override)
  inherits both. ⚠ [GAME]: if a "windup"/sluggishness complaint persists after DamagePoint is
  confirmed capped, the remaining suspect is the AA weapon's `Period` (3.0 s, NOT capped — a
  cadence, not a first-shot delay) or acquisition/turn-to-face — read `MercThor`'s
  `ThorsHammer`/`JavelinMissileLaunchers` `DamagePoint`+`Period` to disambiguate (ref §6).
- [x] **Bug 4c — Jotun simultaneous air+ground fire** — STATICALLY SETTLED, no change needed. The
  three independent-fire `Options[]` flags (`LinkedCooldown=0`, `OnlyFireWhileInAttackOrder=0`,
  `OnlyFireAtAttackOrderTarget=0`) are present + correct in STATIC `WeaponData.xml` on `ThorsHammer`
  AND `JavelinMissileLaunchers` (Goliath Multi-Lock pattern); `MercThor` reaches them via
  `parent="Thor"`. ⚠ [GAME]: the static checker can't observe "fires both at once" — owner confirms.
- [x] **Bug 2 — Medic/Stetmann heal mechanical** — STATICALLY SETTLED, no change (ref §4 — do NOT
  add a filter; the heal mechanism is verified complete). Card simulator confirms BOTH units show
  exactly ONE visible heal button at the correct cell pointing at the mechanical-capable clone:
  Medic button[6] cell (2,0) `Type=AbilCmd AbilCmd=HealWoLU,Execute`; Stetmann button[6] cell (2,0)
  re-pointed `BonesHeal` → `HealWoLU,Execute`. The button index/cell is the visible action cell.
  ⚠ [GAME]: owner manually heals a Marauder/Viking (or harness `RequestQueryAvailableAbilities` on
  Medic/MercMedic with a mechanical target).
- [x] **Bug 3 — shielded-unit normal armor sign** — STATICALLY SETTLED, no change. Each of the 6
  elite mercs' `LifeArmorName` exactly matches its base unit's vanilla value (verified against the
  reference catalogs): MercMedic/MercReaper/MercSeniorGhost = `TerranInfantryArmor` (Medic/Reaper/
  Ghost), MercHellion/MercThor = `TerranVehiclePlating` (Hellion/Thor), MercWraith =
  `TerranShipPlating` (Wraith). `ShieldArmorName` (`WoLUDefensiveMatrix`) is kept on all. CHECK7
  confirms every key resolves. ⚠ [GAME]: owner confirms the inspect panel renders BOTH the
  life-armor icon AND the shield icon side-by-side (a UI/preload behavior, not statically provable).

## In-game playtest batch (v0.3.7 — root-caused statically, pending re-test)

11 issues from a playthrough. Root causes traced against `mods/_reference` (xmlq + the
card-merge simulator). Items marked ⚠ are best-effort / owner-verify-in-game only.

- [x] **#1 Command Center has two MULE buttons** — the merged CC card already carries the
  campaign's `CalldownMULE` button at index 1 (cell 1,2, from libertystory); our added
  `CalldownMULEWoLU` button sat at index 14 = a duplicate. Re-pointed index 1's `AbilCmd` to
  the free `CalldownMULEWoLU` and removed index 14. One free MULE button; Extra Supplies stays.
- [x] **#5 Medic / Stetmann have two heals** — Medic's merged heal button is index 6
  (`heal,Execute`); our `HealWoLU` (Adaptive Medpacks) was a 2nd button at index 11. Re-pointed
  index 6 → `HealWoLU,Execute`, removed index 11 (vanilla `heal` ability stays for enemy
  autocast). Stetmann differs (its heal is `BonesHeal`, not a heal/heal-L1 dup) — mirrored the
  same single-button result by re-pointing its BonesHeal button → HealWoLU. ⚠ verify Stetmann.
- [x] **#6 Jackson's Revenge: only Yamato autocasts** — `DukesRevengeMissilePods` +
  `DukesRevengeDefensiveMatrix` ship `CmdButtonArray State="Restricted"` (Yamato doesn't); the
  `parent=` clones inherited it. Added `State="Normal"` to both clones' `CmdButtonArray` +
  `TechTreeAbilityAllow` for all three DR clones in the lib.
- [x] **#10 Spider Mine shares hotkey E with Enter Siege** — the vanilla `SpiderMine` button
  has no Hotkey field → inherits base-CASC `Button/Hotkey/SpiderMine=E` = SiegeMode's E. Added
  a `CButton SpiderMineWoLU` (same icon) with `Button/Hotkey/SpiderMineWoLU=Y`; every
  spider-mine card button + the ability's DefaultButtonFace now use it. Enter Siege keeps E.
- [x] **#11 ⚠ Spider mines fail when SIEGED** — `SpawnSpiderMineSet` includes
  `ReplenishNanoConstructor`, which refunds a charge on the **Vulture-only**
  `MakeVultureSpiderMines` ability → aborts the set on a tank caster (sieged fails hardest).
  Pointed `SpiderMineWoLU.Effect` at the raw `SpawnSpiderMine` create (we use a cooldown, not
  the Vulture charge system). ⚠ verify a SIEGED Siege Breaker/Tank deploys + mobile still works.
- [x] **#2 ⚠ Jotun/Thor doesn't fire air + ground at once** — base Thor weapons have no
  `Options` block → `LinkedCooldown` defaults to 1 (weapons share one cooldown). The Goliath
  Multi-Lock upgrade swaps to *Upgraded weapons with `LinkedCooldown=0` +
  `OnlyFireWhileInAttackOrder=0` + `OnlyFireAtAttackOrderTarget=0`. Set those three Options on
  Thor's two weapons + Odin's (static WeaponData — `Options[]` is indexed = per-player no-op;
  GLOBAL, so enemy Thors also fire both: accepted tradeoff). ⚠ owner confirms simultaneous fire.
- [x] **#8 ⚠ Jotun AA splash too small** — `JavelinMissileLaunchersDamage` AreaArray radius 0.5
  < ground 1.6/2.5; AreaArray is indexed (per-player no-op). Used the Shaped-Blast clone pattern
  (like `ThorsHammerWoLUSet`): the AA missile's `ImpactEffect` → a `CEffectSet` with vanilla
  (`WoLUNoFlag`) + player-only buffed (`WoLUHasFlag`) branches; the buffed branch = 35 flat, no
  light bonus, AreaArray 1.6/2.5, air enemy-only SearchFilters. ⚠ owner confirms splash radius.
- [~] **#9 Jotun Immortality Protocol — REOPENED v0.3.9 under a NEW design (owner reversed the
  v0.3.7 strip): make it WORK, resurrecting AS A JOTUN with no gas + a single HP bar.** The Thor
  death-response `ThorDontDie` (DamageResponse Fatal=1 → morph into the `ThorWreckage` UNIT, gated
  on the auto-granted `MechanicalRebirth` upgrade) was inherited by MercThor; the wreck's
  `ThorReborn` morph rebuilds a *base Thor* (its `InfoArray Unit="Thor"`) and charges/shows the base
  Thor's 200 gas → wrong identity + "costs gas" tooltip + a double HP bar. v0.3.7 STRIPPED it
  (`<BehaviorArray index="1" removed="1"/>`). **v0.3.9 builds a PARALLEL merc-exclusive chain so the
  Jotun revives as itself** (statically proven; the death-response EFFECT is [GAME]):
  `MercThorDontDie` (parent `ThorDontDie`, `Handled="MercThorWreckage"`, full DamageResponse re-stated,
  `Requirements="UseMechanicalRebirth"`) → `MercThorWreckage` (parent `ThorWreckage` CUnit;
  elite-merc unit-type carve-out — id never appears in any WoL map; `AbilArray index 0` overridden to
  `MercThorReborn`, ImmortalityProtocol card button re-pointed) → `MercThorReborn` (parent `ThorReborn`
  CAbilMorph, `InfoArray Unit="MercThor"`, 12 s rebuild re-stated verbatim). `MercThor`'s inherited
  `BehaviorArray index 1` is now an OVERRIDE (`Link="MercThorDontDie"`, not the old tombstone), and
  `MercThor`'s `CostResource` Minerals+Vespene are zeroed so the rebuild charges/shows nothing. Added a
  `MercThorWreckage` CActorUnit (parent `ThorWreckage`, `unitName="MercThorWreckage"`, Thor model,
  morph-birth events re-bound to our id) so the wreck isn't a sphere (audit CHECK1). All ids resolve
  (audit CHECK3 green; CHECK1 green for the new wreck actor). **⚠ [GAME] — owner confirms in game: a
  fatal hit drops the Jotun to a wreck, it rebuilds AS A JOTUN (merc actor/name), no gas in the
  tooltip, and a single HP bar.** Death-response chains can't be fully statically proven.
- [x] **#3 Bunkers reject mechanical / size>1** — `BunkerTransport.TargetFilters` requires
  `Biological` (string = per-player no-op) → edited in STATIC XML (drop Biological, keep
  ground-only, exclude Air). Per-player (genlib): `MaxCargoSize=8` (admit the size-8 Thor),
  `TotalCargoSpace=32`. **REGRESSION + REFIX v0.3.8** (owner decision: "Big — 32 space, Thors
  allowed"): v0.3.7's `MaxCargoCount=4` was the UNIT-COUNT cap that bound BEFORE the 32-space bar
  → the bar showed 32 but only 4 units loaded. Raised `MaxCargoCount` 4→32 so `TotalCargoSpace`
  (32) is the binding limit: displayed slots == real capacity (32 marines, or 4 Thors, or any mix
  by space; a Thor legitimately takes 8/32). Per-player `MaxCargoCount` IS runtime-editable here
  (same class+ability-kind as the working `MedivacTransport.MaxCargoCount=12` Expanded Hull edit)
  — no static fallback needed. ⚠ verify in game: the 32-bar is fully usable; a Goliath/Hellion/Thor
  loads, each consumes its real size.
- [x] **#7 ⚠ Cloaked-on-spawn units don't show the decloak button** — we cloak via
  `PersonalCloakingFree`, so the toggle cloak ability stays OFF → shows CloakOn. The lib now
  issues each toggle's On command on the periodic (`Order(AbilityCommand(cloak,0))` +
  `AddToFront`, guarded to idle units — the liberty AI pattern) for Ghost/Banshee/Wraith/Spectre
  + Nova/Tosh/DuskWing/MercWraith/MercSeniorGhost. Reaper/Medivac/Predator (no toggle) unchanged.
  ⚠ confirm CloakOff shows and units stay cloaked + commandable.
- [~] **#4 Elite mercs: heart portrait + WRONG upgrade cards** — REFIXED v0.3.8 (was the
  recurring blanket-decorative-card bug). (a) **Upgrade cards — REGRESSION FIXED (statically
  proven):** v0.3.7 BLANKET-added decorative `DefensiveMatrix` / `ShapedHull` /
  `WoLUUpgLaserTargeting` passive faces to ALL six mercs regardless of fit → vehicle/weapon faces
  on units that lack a hull/weapon (Shaped Hull + Laser Targeting on the healer `MercMedic` = the
  owner's bug #3 report). **Removed all blanket faces**; each merc now shows ONLY its base unit's
  real upgrade cards via `parent=` (verified with the card-merge simulator: MercThor still shows
  Laser Targeting + Shaped Hull via the inherited Thor card; MercSeniorGhost still shows Laser
  Targeting via the inherited Ghost card; MercMedic/Reaper/Hellion/Wraith are clean of any face
  they can't justify — the Medic has zero vehicle/weapon faces). Shields are shown via the armor
  sign, not a redundant passive card. New `audit.py` **#3-class check** WARNs if a passive face
  implies a missing capability (hull-on-non-vehicle / weapon-on-weaponless / decorative-shield),
  so this class can't silently return. (b) **Inspect-panel armor signs — DONE (statically proven):**
  added an explicit `LifeArmorName` to each merc (= its base unit's vanilla value: Infantry for
  Medic/Reaper/SeniorGhost, Vehicle for Hellion/Thor, Ship for Wraith) so the normal life-armor
  category resolves on a shielded clone; the `ShieldArmorName` sign was already correct. New audit
  **CHECK7** verifies every armor key resolves (WoLU* in our GameStrings, vanilla via the ref dump).
  (c) **Portrait — awaiting in-game/API confirmation:** the six `PortraitModel` tokens
  (`MedicPortrait`/`ThorPortrait`/…) are now cross-confirmed by new audit **CHECK6** as valid
  base-CASC portrait tokens (each is referenced as a `PortraitModel` by a real vanilla actor in the
  ref dump → the engine loads it). This is strong evidence they should render, but the actual
  portrait is still preload-dependent and not locally observable — **owner confirms the heart is
  gone in game.** `audit.py` CHECK1 still FAILs if a clone body model can't resolve (sphere guard).

## Resolved (most recent first)

- [x] **Spartan Company HP didn't rise enough (parity)** — RESOLVED v0.3.8 (statically proven via
  reference catalogs). The genlib added a flat `LifeMax/LifeStart +25` to `SpartanCompany`
  (165→190), but that broke the merc's % advantage: SpartanCompany base 165, Goliath base 125
  (libertystory wins) → pre-buff ratio 165/125 = 1.32; buffed Goliath = 125 + 25 (Shaped Hull) =
  150, so parity needs 150 × 1.32 ≈ 198, not 190. Changed the Add 25→**33** (165 + 33 = 198). The
  per-player edit was already applying (190 was visible in game), so +33 → 198 will take. ⚠ confirm
  the merc reads ~198 HP in game.

- [x] **BC "ignore armor" was BACKWARDS** — RESOLVED v0.2.5: `ArmorReduction` is a MULTIPLIER on how much the target's armor applies (reference values are only 0 / 0.334 / 1; `SnipeDamage` ignores armor via `ArmorReduction=0`). The shipped `ArmorReduction=500` would have made armor reduce BC damage 500× (≈0 damage to any armored target). Corrected to `0` on `ATSLaserBatteryU`/`ATALaserBatteryU`.
- [x] **Defensive Matrix never autocast** — RESOLVED v0.2.5: it's a SELF-buff `CAbilEffectInstant`, but the autocast was configured with offensive `AutoCastFilters` that EXCLUDE Self/Ally → no valid target → never fired. Rewired to the verified self-buff pattern (`AutoCastValidatorArray=CasterIsFiringWeapon`, like StimpackWoLU) so the BC/SV auto-shields in combat.
- [x] **Senior Ghost +50% damage was a no-op form** — RESOLVED v0.2.5: scalar `DamageDealtFraction="0.5"` → indexed per-Kind form (the only shape the engine uses). See damage-display section.
- [x] **Stat discrepancies settled** — v0.2.5: campaign ground truth confirms Ghost **150/150** (the "200/100" was a wiki/campaign mix-up), Diamondback **4 supply** (Food −4), Wraith **150 gas**. The genlib assumptions already match; no change needed.

- [x] **Cloned merc units show the PARENT's name** (Jotun→"Thor" etc.) — RESOLVED v0.2.4: added an explicit `<Name value="Unit/Name/Merc*"/>` field to each Merc* CUnit. A `parent=` clone with no Name field inherits the parent's; the explicit field (used by 74 vanilla units) pins it.
- [x] **Cloned merc portraits show the "heart" placeholder** — RESOLVED v0.2.4: a base-CASC portrait token referenced from a dependency mod for a non-base unit identity isn't preloaded. Defined local `Merc*Portrait` CModels pointing at the real portrait `.m3` by CASC path (the Moebius SCVPortrait2 pattern), so the `##unitName##Portrait` token resolves to a loaded model. (FLAG: per-unit `.m3` folder follows the SCV-confirmed convention; verify each renders.)
- [x] **Jotun (Thor merc) plays AA animation vs ground + no muzzle** — RESOLVED v0.2.4: Thor's attack animations bind to its specific weapon ids (`ThorsHammer`/`JavelinMissileLaunchers`); a bare `GenericUnitBase` actor only had the generic bracket. Copied Thor's weapon-anim `<On>` events into the MercThor actor.
- [x] **Liberator merc (Midnight Riders) has no transform button** — RESOLVED v0.2.4: the button was appended at index 20 (VikingFighter's next-free is 6), leaving a gap that dropped it. Now overrides the inherited AssaultMode button at index 5 to drive the morph.
- [x] **Advanced-stim units with > Marine HP heal only 30** — RESOLVED v0.2.4: reassigned Reaper/Ghost/Spectre (+ hero parity Nova/Tosh) to the 60-heal `StimpackMarauderWoLU`; Hellion was already on it. Marine + Raynor stay on the 30-heal set.
- [x] **Ghost takes 2 bunker slots despite `CargoSize=1`** — RESOLVED v0.2.4: `CargoSize` per-player is read at bunker load and the runtime edit doesn't reach it. Instead bumped `BunkerTransport.TotalCargoSpace` to 8 (= MaxCargoCount 4 × MaxCargoSize 2) per player, so a bunker holds 4 of any infantry, incl. the size-2 Ghost/Marauder.

- [x] **Thor ground attack felt slow / "windup didn't reflect"** — RESOLVED v0.2.3: the `DamagePoint` cap (0.831→0.1) was already applied; the real cause was the slow `Period` (1.93s). Added the unit-table's Rapid Reload (`ThorsHammer`/`Odin` Period→1.0, backswing→0.1).
- [x] **Merc-unlock regression: Marauder/Firebat/Factory/Armory/Starport buildable in early missions** — RESOLVED v0.2.2: v0.2.1's `EnableCampaignTechUnit` on merc tech-subgroups mapped to the *counterpart* units; replaced with direct `TechTreeUnitAllow` of the merc unit types.
- [x] **Thor splash too small** — RESOLVED v0.2.2: ground-splash radius doubled (0.8/1.25 → 1.6/2.5).
- [x] **Elite-merc shield defense reads "unknown"** — RESOLVED v0.2.2: all shielded clones got `ShieldArmorName`.
- [x] **All elite mercs render as a sphere / no model / no attack visuals** — RESOLVED v0.2.1: the `CActorUnit` entries lacked `parent="GenericUnitBase"` + `unitName=`. `scripts/audit.py` now guards this class.
- [x] **Senior Ghost on Nova's character model instead of a ghost** — RESOLVED v0.2.1→GhostAlternate model.
