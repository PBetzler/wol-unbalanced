# Open Issues

The canonical bug tracker for WoL Unbalanced — confirmed in-game defects, not the test plan ([verification-checklist.md](verification-checklist.md) is the "what to test", this is the "what's broken"). Each entry is a concrete defect with the version it was seen in + root-cause notes.

Format: `- [ ]` open, `- [x]` resolved. Newest at the top of each section. When a fix ships, move the item to **Resolved** with the version + the actual fix.

Running gate: `python3 scripts/audit.py` catches the structural classes statically (missing/malformed actors, dead calldowns) before a build ships; the rest below need in-game observation.

## Clone metadata (the Merc* elite mercs)

- [ ] **Inspect panel armor/defense category** — shield armor was "unknown" (FIXED v0.2.2 via `ShieldArmorName`); re-verify the life-armor category reads correctly on all elite mercs. (In-game check.)

## Damage display + values

- [ ] **"X dmg + X vs light/armored" should flatten to "X dmg"** (Ghost, Thor AA, Spectre). v0.2.4: the effect/field paths are CONFIRMED correct (`C10CanisterRifle`/`SpecterU`/`JavelinMissileLaunchersDamage` `AttributeBonus[Light/Armored]`, same class as the working `CostResource[Minerals]`). The open question is whether a per-player *indexed-array* effect edit reflects on the card. Added **diag3** readback (`gAmt`/`gLgt`) — if `gLgt=0` it works; if `gLgt=10` the array edit is a no-op and the fix is the Shaped-Blast clone pattern (like ThorsHammer). VERIFY the diag, then act.
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
- [ ] **`Button.Requirements` per-player edit (Marauder Tech Lab + Hercules Fusion Core)** — v0.2.4 set both train buttons' `Requirements` to empty (rule-compliant attempt). This is a requirement-LINK field; per-player link edits are often no-ops. VERIFY: can the player build a Marauder with no Tech Lab / a Hercules with no Fusion Core? If not, the field is a no-op and the only working lever (`TechTreeRestrictionsEnable(p,false)`) is rejected because it also strips the Merc Compound requirement (rule 6).
- [ ] **Medic Adaptive Medpacks (heal mech + air)** — v0.2.4 CONFIRMED the only biological/ground gate is the `heal` ability `TargetFilters` (no effect/validator gate); the genlib edit drops it correctly. Open question: does a per-player *string-field* edit apply? VERIFY the Medic can heal a Marauder/Viking in game.
- [ ] **Risky field paths still to re-verify resolve + apply**: `Charge.*`/`Cooldown.TimeStart` on `SummonMercenaries` train infos; `Cost[0].Vital[Energy]` on cloak abils; `AttributeBonus[Light]` Add on `FirebatUFull` (same class as the damage-flatten question — diag3 will settle it).
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

## Resolved (most recent first)

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
