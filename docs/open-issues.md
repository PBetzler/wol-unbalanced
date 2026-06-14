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

- [ ] **The elite-merc submenu collapses after buying a merc** (can't buy a second without re-opening). v0.2.4 INVESTIGATED to ground truth: SC2 returns the command card to its root after *any* issued command — there is **no data flag** to keep a native submenu open (the full flag list has no such option). The only fix is a trigger-built dialog that re-implements the card, which `plan.md` explicitly rules out (loses native autocast circles/hotkeys). **Accepted SC2 limitation** unless the owner wants the dialog route. (Mitigation available if desired: make the elite-merc page the *root* card so it persists, demoting the vanilla 8 to a submenu.)

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

- [ ] **Raven self-Point-Defense (PDD-as-unit)** — making the Raven itself auto-intercept missiles needs the `PointDefenseLaser` weapon on the Raven. It can't be added per-player (runtime `WeaponArray` append = no-op), and a static add is GLOBAL → enemy Ravens would also intercept your Hunter-Seeker missiles (rule 9). The only route is a **cloned, WoLUHasFlag-effect-gated** `PointDefenseLaser` added globally to the Raven id (hidden weapon; effect no-ops for non-flag holders) — but that still gives enemy Ravens a (no-op) weapon they didn't have. **DECISION:** accept that minor rule-9 bend (hidden, no-op-for-enemies weapon) and ship the gated clone? Or leave the Raven's self-PDD out? The permanent-summons half of the Raven kit already ships.
- [ ] **Reaper literal flight** (Jet Pack Overdrive) — anti-air shipped (v0.3.0); literal flight needs a Viking-style morph to a *new flying unit type*, which collides with the "never clone unit types" Hard Rule. **DECISION:** waive that rule for a player-exclusive Reaper-flight morph, or leave Reaper grounded-but-shoots-air (current)?
- [ ] **Marauder Tech Lab / Hercules Fusion Core drop** — if the per-player `Button.Requirements=""` edit proves a no-op in game (verify), the only working lever is `TechTreeRestrictionsEnable(p,false)`, which also strips the Merc Compound requirement (rule 6). **DECISION:** accept losing the Compound gate to drop build prereqs, or leave the prereqs in place?

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
