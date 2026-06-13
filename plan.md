# Implementation Plan — WoL Unbalanced (CCM mod)

Working title: **WoL Unbalanced** (rename anytime). Source of truth for *what* changes: [unit-table.md](unit-table.md) (Comments column) plus the 8 project rules. This file covers *how*.

## 1. Architecture (confirmed from the Perpetual Randomizer files)

A CCM custom campaign is a folder with:

- the 29 WoL `.SC2Map` files — **vanilla content**, except their `DocumentInfo` gets one extra dependency line: `file:Mods\WoLUnbalanced.SC2Mod` (this is how the Randomizer does it; maps keep `Liberty (Mod)`, `Liberty (Campaign)`, `LibertyStory (Campaign)`),
- our `WoLUnbalanced.SC2Mod` (an MPQ archive), containing:
  - `Base.SC2Data/GameData/*.xml` — static data-catalog patches (UnitData, WeaponData, AbilData, EffectData, BehaviorData, UpgradeData, RequirementData, ButtonData, ActorData, ValidatorData, …). Patches are by-id deltas on top of Liberty data, affect all missions.
  - `Base.SC2Data/Lib*.galaxy` + `Triggers` — a trigger library run at map init for everything dynamic/per-player (the EZupgrade mod shows the pattern: `CatalogFieldValueModify(...)` per player, auto-granting upgrades, % adjustments).
  - `enUS.SC2Data/LocalizedData/GameStrings.txt` — names/tooltips for new buttons/upgrades.
  - `ComponentList.SC2Components`, `DocumentInfo`, `DocumentHeader`.
- `metadata.txt` for the CCM launcher.

Two mechanisms, used deliberately — **revised for rule 9 (player-only changes; enemies stay vanilla)**:
- **Static XML** only for *definitions* that are inert until granted: new abilities/effects/buttons/upgrades, requirement changes. Direct CUnit/CWeapon stat edits are GLOBAL (the 1000-HP test affected enemy marines) — so stat changes must NOT be applied via plain catalog XML.
- **Galaxy trigger lib** (EZupgrade-style) as the main application layer: at map init, apply all stat changes per player via `CatalogFieldValueModify(..., player1, ...)` and grant upgrades/tech to player 1 only. Heroes/mercs inherit by applying the same modifications to their unit types.
- Consequence for maps: a dependency's trigger library only runs if the map script includes it. We do NOT re-save maps in the editor; instead the build pipeline text-patches each map's `MapScript.galaxy` (inject `include "LibWoLUnbalanced"` + init call via mpqpatch). Prototype this FIRST in M2 — it's the new risk.

## 2. Repo layout & build tooling

```
src/mod/Base.SC2Data/GameData/*.xml      ← hand-written catalog patches
src/mod/Base.SC2Data/*.galaxy            ← trigger library
src/mod/enUS.SC2Data/...                 ← strings
src/maps/dependency-patch.py             ← rewrites DocumentInfo in each .SC2Map
scripts/build.py                         ← packs src/mod → build/WoLUnbalanced.SC2Mod (MPQ)
build/                                   ← output campaign folder (gitignored)
mods/                                    ← reference mods, gitignored
```

Open tooling question (M1): **MPQ writing on macOS**. mpyq is read-only. Options, in preference order:
1. `stormlib` (build via Homebrew/cmake) + a ~50-line C or Python-cffi packer.
2. The SC2 Editor on the gaming machine does the final "save as .SC2Mod" (works, but manual every build).
3. Check whether SC2/CCM accepts *component-folder* mods (directory instead of MPQ) — if yes, no packer needed at all.

**This Mac is the test machine** (since 2026-06-12): SC2 installing to `/Applications/StarCraft II` (EU), CCM v1.05r (portable .NET 4.7.2 WinForms app, `~/Downloads`) to be run via Wine (`brew install --cask wine-stable`, Rosetta 2 already active; point CCM's file picker at `Z:\Applications\StarCraft II`). CCM is just a file copier into `Maps/CustomCampaigns` / `Maps/Campaign` / `Mods` — the dev loop can copy builds there directly and use CCM only for end-user-parity checks.

## 3. Exact base values

Don't trust wiki numbers. Pull the real Liberty campaign catalogs:
- Primary: the **SC2GameData dump** on GitHub (SC2Mapster/SC2GameData — full XML dumps incl. `campaigns/liberty.sc2campaign`); download into `mods/_reference/` (gitignored).
- The AP mod repo (TheCondor07/Starcraft2ArchipelagoData) for ready-made implementations of every AP upgrade we port — clone into `mods/_reference/` and copy/adapt effect/behavior XML instead of re-inventing.
- Settle the flagged discrepancies (Ghost cost 150/150 vs 200/100, Diamondback supply, Wraith gas).

## 4. Work packages

### WP-A — Global rules (mostly static XML + small trigger lib)
1. **Armory/lab auto-unlock (rules 2 + both-sides decision):** map-init trigger grants every armory upgrade and both options of every lab research pair, gated on "unit already unlocked in story" for unit-bound upgrades. Reference: EZupgrade's lib + LibertyStory tech IDs.
2. **Build-time cap (rule 5):** train times >60 s → 60 s (BC 110→60); user-fixed values override (Predator 10 s, Hercules 20 s).
3. **Merc system (rules 3/6):** RequirementData — merc calldowns require only counterpart-unit-unlocked (not contract purchase); AbilData — remove charge maxima, zero initial cooldown; Merc Compound stays required.
4. **Hero parity (rule 10):** heroes get the same per-player modifications as their base unit — Raynor=Marine, Tychus=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost, Tosh=Spectre, Odin=Thor (last three inferred, user to veto). Protoss heroes (Zeratul etc.) out of scope — no Protoss base-unit changes.
5. **Merc % parity (rule 4):** WoL already applies armory upgrades to mercs; verify for our new effects and add merc units to every ported upgrade's affected-unit lists. Recompute merc HP/damage as counterpart-final-value × original multiplier (build-time, from the dumped XML; e.g. Devil Dogs = doubled Firebat HP × 1.6).
5. **Damage point cap (rule 7):** all player-faction Terran weapons → `DamagePoint ≤ 0.1`.
6. **Free cloak (rule 8):** all cloak abilities → zero energy cost/drain. Then **declutter**: do not implement Crius Suit, Nyx-Class Module, Cross-Spectrum Dampeners, Tomahawk Power Cells, Unregistered Cloaking Module; fold Shaped Blast into "no friendly splash".

### WP-B — Per-unit XML edits (cheap, from the table comments)
Stat lines: Firebat HP ×2; Predator 1 supply/no gas; Hercules +2 armor, no Fusion Core; Medic/Ghost/etc. cost reductions via the AP Resource-Efficiency values; damage flattening (Ghost, Spectre, Thor AA = old vs-light total, Thor AA per-rocket raised to HIP value if lower); Thor inherits the Goliath upgrade package + sieged-tank splash on ground attack; Siege Tank no friendly fire; Bunker: all infantry CargoSize 1; Engineering Bay: 6 new combined upgrades (Atk 1–3 / Def 1–3, infantry costs, 30 s each) replacing the per-class research, Armory building research removed.

### WP-C — Ported AP upgrades (copy/adapt from AP mod data)
Per unit exactly as the Comments column says (e.g. Marine: all; Marauder: listed subset; Reaper: armory + Super Stim + cloak; Hellion: all minus Jump Jets; Goliath: minus Jump Jets/ITM; Spectre: mirror Ghost incl. autocast Psionic Lash). Autocasts: Ghost Snipe/EMP/Super-Stim, Spectre Psionic Lash. Hellbat Aspect needs the HotS Hellbat assets — verify availability in Liberty dependencies, else pull via mod dependency (only named exception to rule 1, as a morph).

### WP-D — Custom features (highest risk, build last)
1. **Raven:** summons permanent (Durable Materials → infinite timed life); Raven itself = autocast point-defense (PDD weapon/behavior on the unit); Hunter-Seeker as manual ability.
2. **Ghost smart Snipe autocast** (likely mirrored on Spectre's Psionic Lash per the "mirror Ghost" decision): priority order — (1) healers, (2) clean-kill targets where snipe wastes ≤15 damage, (3) targets with HP+shields above snipe damage, (4) rest by remaining HP+shields. Implemented via TargetSorts/validators on the autocast; same risk class as the BC batteries.
3. **BC:** autocast Missile Pods + Defensive Matrix; add Yamato (copy from Jackson's Revenge/Loki data), autocast validator: max HP + max shields ≥ 300, where structures only qualify if they are attack-capable/defensive (Spine/Spore, Cannons, Turrets, Bunkers — not production/supply buildings); attacks ignore armor (WOLRE-style: spell/weapon flag or armor-reduction effect); **smart batteries** — multi-beam weapon with overkill-aware target finding (TargetFind/validators). Agreed fallback: if flaky → single-target with everything else kept.

### WP-E — Packaging, install, playtest
Build campaign folder (maps + mod + metadata), install via CCM, mission-by-mission test matrix (each feature has a natural test mission: Liberation Day = marines/windup; Zero Hour = bunkers/mercs-from-start; The Dig = tank no-FF; Maw of the Void = BC package; etc.). Tooltip/icon polish last.

## 5. Milestones

| # | Deliverable | Proves |
|---|---|---|
| M1 | Build pipeline + skeleton mod with one visible change (e.g. Marine HP) loads via CCM | packaging works end-to-end |
| M2 | WP-A global rules | trigger lib + requirement edits work |
| M3 | WP-B unit stats | catalog patching at scale |
| M4 | WP-C ported upgrades | AP ports + autocasts |
| M5 | WP-D Raven/BC customs | the two risky features |
| M6 | WP-E full playtest + polish | shippable |

## 6. Open questions

1. ~~Vanilla WoL maps~~ **Resolved**: Randomizer/Nightmare maps reference their own mod libraries → unusable; loose-file shadowing of `Mods/Liberty.SC2Mod` tested and dead (CASC wins). But the **Tactical Arsenal** campaign's 30 maps reference no custom libraries at all (its mod is purely data-driven) — effectively vanilla. `build.py` now uses them as map base, strips their mod dependency, inserts ours. Editor export remains a fallback if in-game testing reveals any non-vanilla behavior in these maps.
2. ~~MPQ packing route~~ Resolved: StormLib (vendored, built) + `tools/mpqpatch` (replace single file in MPQ, used for DocumentInfo); the mod itself ships as a **component folder** (`Mods/WoLUnbalanced.SC2Mod/`), no packing needed.
3. ~~Which machine runs SC2 + CCM for testing?~~ Resolved: this Mac. Wine 11 works; CCM still needs real .NET 4.8 (wine-mono crashes) — pending, but irrelevant for the dev loop (`scripts/build.py install` copies straight into the SC2 folder).

## 7. Status

**M1 complete (2026-06-12, verified in game):** pipeline `scripts/build.py` + `tools/mpqpatch` + component-folder mod, map base = Tactical Arsenal maps (effectively vanilla), patches: DocumentInfo + DocumentHeader (dependency swap) + MapScript.galaxy (library injection).

**M2 architecture validated (verified in game):** `LibWoLUnbalanced.galaxy` runs on map init and applies catalog changes per player — player marines 1000 HP, enemy marines 45 HP. Base-value ground truth downloaded to `mods/_reference/` from SC2Mapster/SC2GameData (liberty.sc2mod + liberty.sc2campaign + libertystory.sc2campaign catalogs; sanity-checked). Bonus: that dump also contains the vanilla campaign maps (`base.sc2maps`) as a map-base fallback.

**M2 complete:** genlib codegen (Marine +20, windup cap, free cloak, build caps) + campaign tech auto-grant (BuyAllTech/ApplyCampaignTech path, counterpart-gated mercs, research pairs, Ghost+Spectre).

**M3 batch shipped (2026-06-12):** rule 6 (merc charges unlimited via `SummonMercenaries InfoArray[TrainN].Charge.CountMax/CountStart=0`, `Cooldown.TimeStart=0`); per-unit stats (Firebat ×2, Predator gas0/supply1, Hercules +2 armor + `Button.Requirements=HaveAttachedTechLab`, Medic/Ghost/Spectre cost cuts via Subtract ops, infantry CargoSize 1); damage flattening (Ghost `C10CanisterRifle` 20 flat, Spectre `SpecterU` 20 flat, Thor AA `JavelinMissileLaunchersDamage` 35/rocket + range 12); Thor ground splash via `ThorsHammerDamage` AreaArray; tank no-FF via `CrucioShockCannonFriendly*Damage Amount=0`; EngBay 30 s researches + `libWoLU_SyncWeaponArmorLevels` periodic (vehicle/ship levels follow infantry) + Armory researches disabled.

**Hero/merc parity batch shipped (2026-06-12):** rules 4/10 — heroes/mercs in the windup-cap unit list; HP ratio scaling (Marine line ×1.4444: Raynor01/RaynorCommando/Raynor/WarPig; Firebat line ×2: TychusCommando/TychusChaingun/DevilDog; Spartan ×1.2; DukesRevenge/DuskWing get BC/Banshee buffs; Odin AA range 12); stim ability+button catalog-injected for Raynor/Tychus/Swann variants (EXPERIMENTAL — button at CardLayouts[0].LayoutButtons[13], Row2/Col1); Nova/Tosh permanent free cloak via runtime `UnitBehaviorAdd` of `PersonalCloakingFree`/`SpectreCloakingFree`. AP direct-field ports: Super Stimpack (stim heals 30, Cost.Vital[Life]=-30 — both path forms emitted), Marine +1 range, SCV +15, Reaper +10, Vulture speed/regen, Goliath +25, Banshee speed, BC +2 armor/speed, Medivac cargo 12.

**Clone architecture (2026-06-12, user-approved):** vanilla entries stay untouched for enemies; the player gets improved `*WoLU` CLONES defined in static XML (abilities/effects/weapons/validators), unlocked via the `WoLUnbalancedFlag` upgrade + `WoLUHaveFlag` requirement (only our lib grants the flag), and wired in by per-player swaps of EXISTING links (`AbilArray[i].Link`, `WeaponArray[i].Link`, `LayoutButtons[j].AbilCmd` — edits, which runtime catalog modify allows; data-driven indices in genlib `clone_swaps()`). First uses: `StimpackWoLU`/`StimpackMarauderWoLU` (instant-effect abilities with REAL engine autocast — behavior-class abilities can't autocast at all, which is why the circle was impossible before) and `ThorsHammerWoLU` (sieged-tank splash baked in). Do NOT clone unit types — mission scripts check unit types.

**Combined command card — researched (2026-06-13), answer:** the engine's CommandPanel only ever renders the LEADER subgroup's card; there is no native "merged card of all selected types". What mods (NCO, co-op commanders) actually do is make one button drive the whole mixed selection via three stackable mechanisms: (1) **`AbilSetId`** — abilities sharing a set id respond to one button press across unit types (vanilla stim variants share `Stimpack`, all cloaks share `Clok`); (2) **`CAbilRedirect*`** abilities (NCO SuperStimpack*Redirect pattern) to show a working button on a unit type whose own variant differs; (3) **`CmdButtonArray` `ToSelection` flag** (we set it everywhere) so same-id abilities fire for every selected unit, not just the leader subgroup. A literally merged visual card would need a trigger-built dialog UI that re-implements the command card (loses native autocast circles/hotkeys — not recommended). Applied: our stim clones now carry `AbilSetId=Stimpack` (they had lost vanilla's cross-type stim button); autocast-kit clones stay set-less deliberately — player ghosts carry BOTH vanilla Snipe (AI slot) and SnipeWoLU, and a shared set could double-fire.

**Stim rebuild + Thor gating (2026-06-12; stim autocast VERIFIED in game — clone architecture proven end to end; remaining checks below):** StimpackWoLU/StimpackMarauderWoLU rebuilt as **verbatim clones of NCO SuperStimpackMarine/Marauder** (novastoryassets.sc2mod, downloaded to `mods/_reference/`) — the first attempt's schema bugs: `Effect` needs `index="0"`, and AutoCast/AutoCastOn are ABILITY-level flags, not CmdButtonArray flags. New chain: CEffectSet → apply `WoLUSuperStim` buff (clone of NCO SuperStim) + CEffectModifyUnit heal (30 marine line / 60 marauder+firebat lines per unit-table), autocast via liberty's own `CasterIsFiringWeapon` validator, 18 s cooldown (NCO design: perma-stim while fighting). Firebat line (Firebat/DevilDog/Tychus heroes) moved to the 60-heal marauder variant. Thor: `WeaponArray[1]` XML index-override → `ThorsHammerWoLU` (stat-identical clone), splash isolated per player at the EFFECT level via the campaign's Shaped Blast pattern (`WoLUHasFlag`/`WoLUNoFlag` CValidatorPlayerRequirement on sibling damage branches in `ThorsHammerWoLUSet`); windup cap applied at runtime on the clone id (a baked `DamagePoint` would leak to enemy Thors). Dead runtime link-swap machinery removed from genlib. Diag line now also reports `fx=` (StimpackWoLU Effect[0]) — expected: `clone=5 fx=WoLUStimSet flag=1 m3=StimpackWoLU t1=ThorsHammerWoLU`.

**WP-C batch (2026-06-12 night session, commits ace87db/cb1df53, pending in-game test):** Super Stimpack rollout (Reaper/Ghost/Spectre 30-heal, Hellion 60-heal) + card-collision audit (4 hero/firebat stim buttons moved off occupied cells); Ghost/Spectre autocast kit (SnipeWoLU/EMPWoLU/ObliterateWoLU — **append-don't-override rule**: new abilities appended so enemy AI keeps vanilla, only card buttons re-pointed, which is AI-invisible); Magrail Munitions (Marine only per Comments); permanent cloak via 2 s periodic behavior-apply (Reaper/Medivac/Wraith); Odin AA 35/rocket (ground splash already vanilla-splashing — no change needed); stat batch (Marauder/Firebat/Ghost/Spectre/Hellion/Medivac/Viking/Diamondback/Tank/Banshee/SV documented values; OL = −25% train time and DB Hyperfluxor/Maglev ±25% are **flagged assumptions**); fixed silent no-op Marine +1 range (`GuassRifle` — Blizzard's typo'd id). Helper scripts `scripts/xmlq.py` (catalog queries) + `scripts/mpq_extract.py` (MPQ list/extract).

**WP-D/WP-C batch 2 (2026-06-13, commits 9afdfb9..5539edb, pending in-game test):** BC kit — autocast Yamato (big-target-gated, skips structures), Missile Pods, Defensive Matrix as append-don't-override `parent=` clones on the Battlecruiser; per-player `AllowedMovement=Moving` (fire while moving) + `ArmorReduction=500` (ignore armor) on the laser weapons/effects. Smart-Snipe: declarative approximation only (life-floor validator + TSLifeLargestFirst) — the full 4-tier priority is NOT expressible with the 6 built-in TargetSorts. Resource Efficiency cost cuts (canonical −25/−25/−1 assumption) for Firebat/Reaper/Goliath/Diamondback/Tank/Raven/Medivac. SV gets the Defensive Matrix clone.

**FLAGGED — implemented but unverified mechanism (check in game, may be guesses):** Defensive Matrix autocast (instant self-buff autocast has no clean blueprint — manual always works); BC ignore-armor via `ArmorReduction=500` (semantics unconfirmed); Yamato defensive-structure discrimination (skips ALL structures).

**Moebius mod surveyed (2026-06-13, found at mods/Moebius → MoebiusMod.SC2Mod, extracted to mods/_reference/moebius).** It's a Nightmare-difficulty pack: ~mostly galaxy-trigger-driven (251 KB lib), enemy-oriented, NOT player-only. Verdict: it does NOT provide clean data blueprints for most deferred customs — they live in its trigger framework, which would conflict with our per-player catalog architecture + rule 9. What it DID unblock (verified schemas): **`DamageResponse ModifyFraction`** for damage reduction (→ shipped Predator Adaptive Defenses, commit a49b7f6) and **`CEffectTeleport`** (would unblock Tactical Jump if wanted). Reaper Combat Drugs shipped as flat regen alongside.

**RaynorRogue kit surveyed (2026-06-13, mods/rogue → kit_liberty_story.SC2Mod, extracted to mods/_reference/rogue).** A comprehensive DATA-DRIVEN WoL upgrade kit (`Kit@` upgrades, ArmyUpgradeData, TargetSortData) — much better blueprint source than Moebius. Findings:
- **CORRECTED a wrong earlier claim:** custom `CTargetSort*` types ARE catalog-definable → **full smart-Snipe priority shipped** (healer→lethal→tanky→nearest, commit 05eff43). Sort direction confirmed from the kit (plain validator = passers-last; `Descending=1` = first).
- **BC smart-batteries: fully data-driven & blueprinted** — `BattlecruiserWeaponSwitch` weapon (Arc 360, IgnoreThreat/IgnorePriority, AllowedMovement=Moving) + `Marker→BattlecruiserAttackTrackerCP` (CEffectCreatePersistent→ApplyBehavior `BattlecruiserAttackTracker`→DestroyPersistent) + `AcquireTargetSorts` [TSTrackedBy, TSThreaten, TSPriorityDesc, TSTransient, GroundTarget] + validators (`AttackTrackedByBattlecruiser`=CValidatorUnitCompareBehaviorCount, `ThreatensBattlecruiser`=CValidatorUnitCompareAttackPriority). It's pure data (no galaxy), so transplantable — but a 10+-entry interconnected system that needs IN-GAME ITERATION; deliberately NOT shipped blind (our BC already works with the pre-approved single-target fallback). **This is the recommended next dedicated task.**
- **Graduating Range is NOT in the rogue kit** (its GameStrings have no "graduating" entry; the Google sheet the user linked documents a different mod). So BUILT FROM CONFIRMED PRIMITIVES instead (commit ab8456d): `WoLUGraduatingRange` buff (MaxStackCount=5, Modification WeaponRange=1 — field confirmed from liberty `BunkerWeaponRangeBonus`) stacked +1 every 3 s by `libWoLU_GraduateSiegeRange` on player SiegeTankSieged + SiegeBreakerSieged (UnitBehaviorAdd-with-count, dedicated 3 s trigger). Lives on the sieged form → resets on unsiege, regrows on re-siege. FLAG: confirm 5 stacks = +5 range in game.

**Still BLOCKED / deliberately NOT guessed:** Wraith Trigger Override (stacking attack-speed-on-attack — could now use the same galaxy-stacking approach as Graduating Range, but the "on each attack" trigger is the missing piece), Predator Charge/Vespene Synthesis, Viking Shredder *line* splash / Wild Missiles salvo, Hellbat Aspect morph (needs HotS assets), SV Magellan/EMP Shockwave, Medic Restoration/Optical Flare, BC smart-batteries (fully blueprinted from the rogue kit, needs in-game iteration). Next: the galaxy-stacking helper now exists (graduating range) — Wraith Trigger Override could reuse it if driven off an attack event; BC smart-batteries remain the big transplant.

**Open next:** in-game verification (see checklist in session summary — diag line, stim heals 30/60, autocast Snipe/EMP/Lash, Magrail, perma-cloaks, Thor/Odin splash+AA, enemy-vanilla checks); WP-C remaining (each a mini-project: Wraith laser tech + Trigger Override, Viking Shredder/AMM/Wild Missiles, Tank Graduating Range/Spider Mines/Transport Hook, Predator kit, SV Magellan/EMP/DefMatrix/TacJump, Medic Restoration/Optical Flare, Hellbat Aspect [needs HotS assets — named rule-1 exception], Reaper Jet Pack Overdrive); WP-D customs (Raven kit incl. permanent summons + PDD-as-unit-autocast, BC batteries/Yamato/ATX flags, smart-Snipe TargetSorts priorities); Ghost/Firebat/others "Resource Efficiency" exact values still unknown (only Medic's −25/−25/−1 and Ghost Bargain Bin documented). Risky/unverified field paths: `Charge.*`/`Cooldown.TimeStart` on train infos, `Button.Requirements` swap (Hercules — likely a no-op, link-field), `Cost[0].Vital[Energy]` on cloak abils, heal `TargetFilters` string edit, `AttributeBonus[Light]` Add on FirebatUFull, Medivac `TotalCargoSpace`.
