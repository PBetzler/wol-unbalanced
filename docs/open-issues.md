# Open Issues

The canonical bug tracker for WoL Unbalanced — confirmed in-game defects, not the test plan ([verification-checklist.md](verification-checklist.md) is the "what to test", this is the "what's broken"). Each entry is a concrete defect with the version it was seen in + root-cause notes.

Format: `- [ ]` open, `- [x]` resolved. Newest at the top of each section. When a fix ships, move the item to **Resolved** with the version + the actual fix.

Running gate: `python3 scripts/audit.py` catches the structural classes statically (missing/malformed actors, dead calldowns) before a build ships; the rest below need in-game observation.

## v0.3.18 — ROOT CAUSE found (install path) + correcting the v0.3.15–v0.3.17 record (2026-06-20)

**The real bug behind the whole "nothing works" spiral was NOT in the mod — it was the install
TARGET.** `build.py install` wrote to `C:\Program Files (x86)\StarCraft II` instead of the SC2 USER
folder `C:\Users\<user>\Documents\StarCraft II` (regression commit a4ab52b), so the files landed where
the game never looks → `Documents\…\Maps\Campaign` stayed EMPTY → the owner played the VANILLA WoL
campaign with no mod attached. Fixed in `scripts/build.py` `_default_sc2_dir()` + reinstalled correctly;
guarded by a new CLAUDE.md Hard Rule ("verify the mod is LOADED before debugging the code") and the
SessionStart engram hook.

Correcting the record — several v0.3.15/v0.3.16 "bugs" were the **not-loading symptom**, not real defects:
- [x] **Siege Breakers / mercs "still buyable"** was vanilla merc behaviour (mod not loaded). The
  all-mercs-from-start grant already works (engram #74). The v0.3.15 hub merc re-purchase + the
  `c_timeReal` hub timers are KEPT as low-risk belt-and-suspenders (UpdateMercStatus genuinely flips a
  newly-unlocked merc back to buyable; story-mode game-time is genuinely uncertain), but they were
  addressing a phantom at the time — re-validate in a real (loading) playtest.
- [x] **WoLUSmartServos "crashed the grant" — FALSE SUSPECT, RE-ENABLED (v0.3.18).** I disabled the
  `TechTreeUpgradeAddLevel(p,"WoLUSmartServos",1)` grant in v0.3.16 suspecting it halted GrantCampaignTech;
  the real cause was the install path. Its EffectArray references all resolve (AssaultMode/FighterMode +
  Hel's Angels WreckingCrew*Mode), so it's re-enabled. The standard "data applied" canary completing
  confirms it doesn't crash.
- [x] **Removed the temporary "pre-grant" diagnostic canary** (it was for a grant-crash hypothesis that
  was wrong). The `WoLU hub:` diag stays until the owner confirms the Skip-Prophecy button in-game.

**Now genuinely [GAME]-pending their FIRST real (loading) playtest:** the canary + buffs show; the
Skip-Prophecy button on the Hyperion (tstory01); Siege Breakers/elite mercs owned; faster Viking transform.

## v0.3.16 — owner playtest: the WHOLE mod stopped running in-mission (no canary, no mercs) (2026-06-20)

Owner on v0.3.15: **no canary subtitle at all in mission**, Siege Breakers + all elite mercs unbuyable, no Hyperion diag. The canary + the merc grants both come from `libWoLU_OnGrantTech` → `libWoLU_GrantCampaignTech` (canary prints AFTER the grant returns; the elite-merc `TechTreeUnitAllow` calls are LATE in that function), so "no canary AND elite mercs unbuyable" = **the grant is halting partway / the library isn't running**. Static investigation: the **released artifact is correct** — verified the released maps carry our injection (`include "LibWoLUnbalanced"` + `libWoLU_InitLib()`) and the released mod is the right galaxy version; `WoLUSmartServos`' EffectArray `Reference=` paths all resolve. Two changes shipped to localize + likely-fix:

- [ ] **[GAME-pending] Disabled the `WoLUSmartServos` grant (prime suspect).** It was the ONLY combat-path change since the mod last ran clean and sits immediately before the elite-merc allows + canary. Its references resolve statically, but applying a `Subtract` to a `CAbilMorph` `DurationArray` via a per-player upgrade is unverified in-game and could error at apply-time → halting `GrantCampaignTech`. Commented out the `TechTreeUpgradeAddLevel(p, "WoLUSmartServos", 1)` call (the fire-while-moving half of Smart Servos, a separate `Weapon.AllowedMovement` genlib edit, stays). If the owner now sees the canary + owns mercs, this was the culprit and we redesign/drop it.
- [ ] **[diagnostic] Early "pre-grant" canary.** `libWoLU_OnGrantTech` now prints `WoLU: lib running (pre-grant) — if you see this but not 'data applied', the grant is crashing.` BEFORE calling the grant. Owner reports which of the two lines appear: **pre-grant only** = grant still crashing (look past the disabled line); **neither** = library/timer not running at all (install/load issue — clean reinstall); **both** = grant completes, mercs should work.
- [x] **Release-pipeline parity fix (`repack.py`).** CI-repacked releases shipped the mod WITHOUT the `DocumentInfo/GameData/GameText.version` files that a local `build.py` build generates (the only structural difference between the known-good local build and the release zip). `repack.py` now emits them via the shared `build.version_file_blobs()`. (Auxiliary per ComponentList, so likely not the load-blocker, but eliminates the discrepancy.)

## v0.3.15 — owner playtest fixes: Siege Breakers stayed buyable + Skip-Prophecy button missing (2026-06-20)

Two bugs from the v0.3.14 playtest. Both point at the SAME suspected root cause — our per-mission grant runs on **game-time** timers (1 s/10 s) that may not advance on the **story-mode Hyperion hub** (`tstory01`), so neither the merc re-purchase nor the button creation reached the hub. Fixes are SHIPPED but the timer hypothesis is **not yet statically confirmed** (no SC2 MCP); a temporary diagnostic subtitle will confirm it in one playtest.

- [ ] **[GAME-pending] Siege Breakers (and any merc) shows a BUY button on the Hyperion after its unlock mission — FIX SHIPPED, confirm.** VERIFIED mechanism: when a counterpart-unlock mission completes (The Dig → Siege Tank), the campaign's own `libCamp_gf_TS_UpdateMercStatus` (CampaignLib.galaxy:3653-3656) flips that merc `Locked→New` = back to PURCHASABLE; it leaves an already-`Purchased` merc alone once the counterpart is enabled. Our auto-purchase grant didn't re-assert `Purchased` on the hub (game-time timer). **Fix:** a hub-scoped handler `libWoLU_OnStoryModeInit` re-runs `libWoLU_PurchaseAllMercs` (SetMercStatus Purchased for all mercs + re-apply merc tech) on the Hyperion, wired on REAL-time timers (2 s/6 s) so it fires even if game time is paused there. **Confirm:** after The Dig, Siege Breakers reads as owned (no buy button) on the Hyperion merc panel.
- [ ] **[GAME-pending] Skip-Prophecy button never appeared on the Hyperion — FIX SHIPPED, confirm + diagnostic.** Same suspected root cause (game-time creator timer didn't fire on the hub) PLUS a found gate bug: the gate tested `MissionStatusCheck(TZeratul01, Available)`, but `libCamp_gf_MissionStatus` (CampaignLib.galaxy:2767-2779) returns `Available` ONLY while a mission is unlocked-AND-not-completed — so completing TZeratul01 would have hidden the button even with 02-04 left. **Fixes:** (1) gate now tests `TZeratul01 != Locked` (unlocked = Available OR Completed); (2) the creator now also fires on REAL-time timers (2 s/6 s) on the hub. **Diagnostic (TEMP):** on the Hyperion the owner should now see a subtitle `WoLU hub: race=Terr z1=<0/1/2> z4=<0/1/2> offer=<0/1> dlg=<id>` (z1/z4 = TZeratul01/04 MissionStatus; offer = gate result; dlg = button dialog id). If it shows `offer=1 dlg=<nonzero>` but still no visible button, the remaining suspect is that raw `DialogCreate` overlays are suppressed in story mode → the button would move to the Zeratul mission maps. **Owner: report the `WoLU hub:` line text (or its absence) from the Hyperion.**

## v0.3.14 — passive-icon truth pass (3 features made real) + tooltip accuracy + Skip-Prophecy button (2026-06-20)

Made three advertised-but-empty passive upgrade FACES actually do something, corrected stale tooltip text so every card is honest, and added a one-time **Skip Prophecy (Zeratul) missions** convenience button. The features are STATICALLY proven (CHECK8-GOOD field classes / verified CUpgrade pattern / independent Opus review); the in-game feel + the campaign-progression flow are owner-confirmed at playtest.

- [ ] **[GAME-pending] Skip Prophecy (Zeratul) missions button — owner to confirm the full campaign-progression flow in-game.** New one-time on-screen button, implemented purely in `src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy` (no XML/strings). It appears ONLY on the `tstory01` Hyperion hub, once the Prophecy arc is unlocked (TZeratul01 `Available`, after Tychus 02) but not yet finished (TZeratul04 not `Completed`). On click it: marks all 4 Zeratul missions (`TZeratul01`–`04`, MapIDs 22–25) complete on every difficulty (`libCamp_gf_TS_SetMissionDifficultyCompleted` + `MarkMissionAsStatus`), grants their full 100%-clear research-point yield (writes `libCamp_gv_tSX_ResearchMissionProgress[m][cat]` = `StoryResearchMissionOpportunities`; the engine adds the per-mission reward on top once Completed — storing the sum would double-count, see [learnings.md](learnings.md)), re-runs `libCamp_gf_UpdateMissionFlow()` to propagate the unlock chain, persists via the campaign's own `libCamp_gf_PrepareForStoryModeTransitionalSave()`, then destroys itself. Gate green; independent Opus review found no blockers. **Statically unverifiable (no SC2 MCP); owner to confirm in-game:** (1) the button appears on the Hyperion once the arc is unlocked-but-unfinished, (2) one click marks all 4 Prophecy missions complete and the Lab research total jumps by their full yield, (3) the button disappears and stays gone after leaving and re-entering the hub, (4) the on-screen placement (top-center, +120 px) is acceptable — easy to relocate (`libWoLU_CreateSkipProphecyButton` `DialogCreate`/`DialogControlSetPosition` offsets).

- [ ] **[GAME-pending] Raven ability ENERGY-COST tooltip BODY text — owner to confirm in-game.** genlib zeroes the energy cost per-player for `PlacePointDefenseDrone` / `BuildAutoTurret` / `SeekerMissile` (`Cost[0].Vital[Energy]=0`, player-only — the free Point Defense Drone / Auto-Turret / Hunter-Seeker kit). The auto-rendered cost PANEL already shows 0 (it reads the live per-player field). What is **UNKNOWN statically** is whether the tooltip BODY prose still shows a hardcoded `100/50/125` — the vanilla strings for these three live in base CASC, are absent from our reference dump and not in our GameStrings.txt, so we cannot confirm whether they hardcode the literal number or use a `<d ref="Abil,...,Cost[0].Vital[Energy]"/>` autotext token (which would already read 0 after our edit). Per the Don't-guess discipline we did NOT blind-override these strings (a hand-written override risks REPLACING the whole vanilla ability description and could be wrong if vanilla already auto-updates). **Owner to confirm in-game:** do the Raven PDD/Auto-Turret/Hunter-Seeker tooltips read "0 energy" (or no energy line) in the body? If the body still hardcodes 100/50/125, the fix is to add our own `Button/Tooltip/<key>` entries using `<d ref="Abil,<id>,Cost[0].Vital[Energy]"/>` autotext (button faces: `PointDefenseDrone` / `AutoTurret` / `HunterSeekerMissile`). Until then this is **deferred, not fixed.**

## v0.3.13 — reroute-detach sweep + panel-truth gate (CHECK11) + flier scaling (2026-06-19)

Owner playtest surfaced two classes: rerouted weapons losing their effect-bound visuals (Viking "ground does nothing"), and rerouted weapons showing the wrong card number. Both are now CLASS-fixed and gated.

- [x] **Viking ground projectile/impact missing — RESOLVED (v0.3.13, [STATIC]; [GAME] confirm pending).** The `TwinGatlingCannon`→`TwinGatlingCannonsWoLUSet` weapon-`Effect` reroute detached the vanilla `CActorAction id="VikingAssaultAttack"`'s launch sound + impact sound + flesh blood-reaction (an `effectAttack` binds to the EXACT damage effect id, not its `parent=` children). Restored via 3 `CActorAction` clones — `VikingAssaultAttack{Vanilla,}WoLU` (enemy + player branch) + the Hel's Angels merc's single un-gated `WreckingCrewAssaultAttackWoLU` — each restating the vanilla `LaunchAttachQuery`/`ImpactMap`/`LaunchAssets` verbatim. Same class as the Thor ground-muzzle fix. The Viking ground attack is launch-sound + impact-sound + blood (no missile/beam actor), so "no projectile" was really "those assets stopped firing." `src/mod/Base.SC2Data/GameData/ActorData.xml`. **⚠ [GAME] confirm the Viking/Hel's Angels ground attack shows impact + blood again.**
- [x] **Thor/Jotun AA impact SOUND missing — RESOLVED (v0.3.13, [STATIC]; [GAME] confirm pending).** Found by a full sweep of all 6 weapon/effect reroutes (the only additional detachment). The `JavelinMissileLaunchersLM` `ImpactEffect` reroute (in `EffectData.xml`) detached `CActorAction id="ThorAAAttack"`'s `effectImpact="JavelinMissileLaunchersDamage"` → the AA impact sound (`Thor_AntiAirAttackImpact`) went silent for every Thor. The launch sound (`effectLaunch`, un-rerouted) + the rocket trail (`CActorMissile unitName="ThorAAWeapon"`, unit-name-bound) were preserved. Fixed with `ThorAAAttack{Vanilla,}WoLU` (`parent="ThorAAAttack"`, override only `effectImpact`, OMIT `LaunchAssets` so the launch sound isn't doubled). The other 4 reroutes are confirmed fine: Wraith air/ground SETs WRAP the unchanged vanilla delivery (detach nothing), SV EMP reuses `AmmoUnit="EMP2Weapon"` (unit-name-bound). `src/mod/Base.SC2Data/GameData/ActorData.xml`. **⚠ [GAME] confirm Thor/Jotun AA hits play their impact sound.**
- [x] **Rerouted-weapon damage panels showed the wrong number — RESOLVED + GATED (CHECK11, v0.3.13).** The unit-info damage panel reads a weapon's `<DisplayEffect>` (or `<Effect>` if absent), NOT the actually-fired effect — so rerouting `<Effect>`/`ImpactEffect` to a `*WoLU(Set)` clone leaves the panel pinned to the vanilla effect. Two real divergences fixed via static `DisplayEffect` repoints (`src/mod/Base.SC2Data/GameData/WeaponData.xml`; display-only → rule-9-safe):
  - **Thor/Jotun AA** — panel read `JavelinMissileLaunchersDamage` (per-player `Amount`=35 but `AttributeBonus[Light]`=4 → "+4 vs Light"), player fires the flat-35 `JavelinMissileLaunchersDamageBuffedWoLU` → repointed `DisplayEffect` to that clone (now flat 35, no phantom Light bonus).
  - **Viking/Hel's Angels ground** — panel read `TwinGatlingCannons` (14), player fires `TwinGatlingCannonsWoLU` (14 +`AttributeBonus[Mechanical]`=20) → repointed (now 14 "+20 vs Mechanical").
  `scripts/check_panel_damage.py` (**CHECK11**, wired into pre-commit + CI) now FAILs when a rerouted weapon's `DisplayEffect` number diverges from the player's fired number. Gate green. **⚠ [GAME] confirm the AA card reads flat 35 and the Viking ground card reads 14 +20 vs Mechanical.**
- [x] **Flier/vehicle units didn't scale with the combined Eng Bay upgrade — RESOLVED (v0.3.13, [STATIC]; [GAME] confirm pending).** WoL splits weapon/armor research into base `Terran{Ship,Vehicle}{Weapons,Armors}Level{N}` ids (which the sync grants — they carry the real effects) vs. icon-only `…UltraCapacitors/…VanadiumPlating` wrappers (the sync doesn't grant). Several player combat units (base Banshee/BC/Viking weapons + Banshee/BC/Viking/Medivac/Raven/Thor/SiegeTank/Hellion armor + elite mercs) had their scaling entries ONLY in the wrappers → they didn't scale. Mirrored the missing unit keys into the base-Level upgrades via index-less new-key `EffectArray` appends (`src/mod/Base.SC2Data/GameData/UpgradeData.xml`), omitting the wrappers' +5% HP `LifeMax/LifeStart` perk (separate from armor-level scaling). Also extended the 30 s research-time cap to the after-lab Research11–16 buttons. **⚠ [GAME] confirm a Banshee/BC/Viking gains weapon/armor levels from Eng Bay upgrades; one caveat — whether `Effect,TwinGatlingCannons,Amount` reaches the rerouted Viking-ground clone is the same class as the GAME-confirmed Thor case.**

- [x] **Senior Ghost +50% panel under-show — RESOLVED (v0.3.x, [STATIC]; [GAME] confirm pending).** `MercSeniorGhost` deals +50% rifle damage via the `WoLUSeniorGhostBoost` `DamageDealtFraction` behavior (panel-invisible), and its rifle `C10CanisterRifle` is SHARED with the base Ghost (can't per-player-edit just the merc). Owner approved a merc-only weapon clone for accuracy: added `C10CanisterRifleWoLU` (effect: `Amount=30`, `AttributeBonus[Light]=15` = the player's 20/+10 ×1.5 baked; weapon: `parent="C10CanisterRifle"`, both `<Effect>` and `<DisplayEffect>` → the clone), repointed `MercSeniorGhost`'s `WeaponArray index="0"` to it, and REMOVED the now-double-counting `DamageDealtFraction[Ranged]` from the boost behavior (kept `Spell` so Snipe `SnipeWoLU`→`SnipeDamage` Kind=Spell keeps its +50%). Player-exclusive merc → rule-9-safe; CHECK11 now lists the clone with panel==actual=30. **⚠ [GAME] confirm the Senior Ghost damage panel reads ~30 (+15 vs Light) and Snipe still hits boosted.**

> **Still OPEN (owner-decision-pending) — the remaining damage-display item in this family** (see §"Damage display + values" below): Ghost/Spectre rifle "+vs Light/Armored" flatten (a per-player `AttributeBonus` edit is a confirmed NOOP class → needs a Shaped-Blast effect clone, recipe 13). Not a reroute-detach or a CHECK11 case; awaits an owner call. (This is card-ACCURATE — the panel shows what the unit deals; only the flat-N *intent* is unmet — so it is NOT false info.)

## Merc/hero parity guard (CHECK10) + full audit (2026-06-18)

Owner's ask: "how do we stop this from happening?" — mercs/heroes/variants keep silently
MISSING per-player upgrades their BASE unit has (Spartan ← Goliath #12, Death Heads ← cloak/stim,
Hammer Securities ← stim, …). Built the PREVENTION mechanism + ran the full audit + fixed the gaps.

- [x] **CHECK10 — `scripts/check_merc_parity.py` (wired into the gate: pre-commit + CI + CLAUDE.md
  dev-loop).** For each base unit it enumerates the FUNCTIONAL per-player buffs it gets — (a) genlib
  `CatalogFieldValueModify` Unit fields keyed to the base id, and (b) `LibWoLUnbalanced.galaxy`
  per-unit-type loop memberships (cloak / def-matrix / graduate-range, by EFFECT CLASS so a
  legitimate id difference like `PersonalCloakingFree` vs `SpectreCloakingFree` or `BansheeCloak`
  vs `DuskWingBansheeCloakingField` isn't flagged) — then verifies each merc/hero counterpart has
  the SAME CLASS of buff present (rule 4: values legitimately differ; it checks PRESENCE). `parent=`
  elite mercs inherit static XML (abilities/cards/weapons) so they only need (a)+(b); standalone
  mercs + heroes inherit nothing. **FAILS** on any un-excepted gap, and on a STALE exception (so the
  allowlist can't rot). Self-test confirmed it catches a simulated regression (dropping MercThor's
  Sight edit → FAIL). **SCOPE (deliberate):** checks the two FUNCTIONAL dimensions where the real
  bugs lived; does NOT enforce the cosmetic WoLU passive-display *card faces* (`WoLUUpg*`/`ShapedHull`/
  …) — those grant nothing (AbilCmd=255, display-only), are noisy to diff (vanilla campaign faces look
  identical), and audit.py's #3-class check already guards face↔capability fit. Cost fields
  (`CostResource[*]`/`Food`) are excluded wholesale (mercs are free calldowns, heroes are map-placed →
  cost is never paid). **Exceptions allowlist: EMPTY** — after the cost-filter + class-collapse, every
  remaining gap was a REAL functional gap and got fixed (below), so no per-pair exception was needed.

- [x] **The 9 real gaps CHECK10 found, all FIXED in genlib (`scripts/genlib.py` → regenerated lib;
  [STATIC] proven via CHECK8-GOOD + the parity check; [GAME] owner confirms in playtest).** Each is a
  base-unit per-player Unit buff that never reached the counterpart (the recurring class):
  - **Death Heads (`MercReaper`, parent=Reaper)** — missing Reaper's `Sight +2` (LTS),
    `LifeRegenRate=2` (Combat Drugs), `LifeMax/LifeStart +10` (Ballistic Flightsuit). Added all four
    (flat Add on top of the merc's elite 150 base keeps it ahead of the buffed base Reaper, rule 4).
  - **Condor (`MercHellion`, parent=Hellion)** — missing Hellion's `LifeArmor +2` (Infernal Plating). Added.
  - **Jotun (`MercThor`, parent=Thor)** — missing Thor's `Sight +2` (LTS). Added. (AA/ground range +
    windup already reach it via inherited weapon ids; only the unit-keyed Sight was missing.)
  - **Senior Ghost (`MercSeniorGhost`, parent=Ghost)** — missing Ghost's `Sight +2` (LTS). Added.
    (Its 1.5× life/energy + the weapon-range LTS were already present; only Sight was missing.)
  - **Hel's Angels (`HelsAngelFighter` + `HelsAngelAssault`, standalone Viking mercs)** — missing the
    Viking's `Speed ×1.55` (Aesir Turbines). Added to both modes (Multiply preserves any % advantage).
  These are CHECK8-GOOD scalar fields (Sight/LifeArmor/LifeRegenRate/LifeMax/Speed), player-only (the
  ids are player-exclusive). **⚠ [GAME] owner confirms in playtest:** Death Heads regen + sight, Condor
  armor, Jotun + Senior Ghost sight, and Hel's Angels move speed now match their base unit's buffs.

- [x] **Confirmed NON-gaps (the audit's clean cases — no fix needed).** MercMedic/Stetmann: only
  cost/Food differed (excepted — free calldown / map-placed). MercWraith: Wraith's buffs are on the
  WraithA/G weapon ids (inherited via parent=) + cloak loops (already in the hand-lib) → no unit-field
  gap. DuskWing: cloaks via `DuskWingBansheeCloakingField` (already in hand-lib; the class-collapse
  recognizes it as `cloak-toggle`). DukesRevenge: uses its OWN `DukesRevenge*WoLU` ability clones +
  has the def-matrix loop; no unit-field gap. WarPig/Raynor*/Swann/Tychus*/SpartanCompany/SiegeBreaker*/
  Odin/Nova/Tosh: their functional field buffs were already present in genlib's parity sweep.

## v0.3.10 playtest bugs — reported, NOT yet fixed (→ v0.3.11)

Three defects from the owner's v0.3.10 playthrough. A first read-only diagnosis pass was run on each but came back **too uncertain to ship** — each lead below was found unreliable, so these need rigorous investigation before a fix lands (do NOT ship the first-pass guesses):

- [~] **Death Heads (`MercReaper`, the Reaper merc) had NO cloak and NO super-stim; normal Reapers have both.**
  Owner playtest 2026-06-18. Two SEPARATE root causes, both fixed (v0.3.11, [STATIC]; [GAME] confirm pending):
  - **CLOAK — confirmed gap, fixed.** `LibWoLUnbalanced.galaxy` applies permanent free cloak via
    `libWoLU_AddBehaviorToType(p, "<UnitType>", "PersonalCloakingFree")` on the 2 s periodic. The list
    targets BASE unit ids (`Reaper`, `Ghost`, …) plus the cloak-capable mercs (`DuskWing`, `MercWraith`,
    `MercSeniorGhost`) — but **`MercReaper` was missing**. `MercReaper` is a SEPARATE unit id from
    `Reaper`, so the base-`Reaper` cloak line never reached it (recurring merc-parity class: per-player
    loops keyed to the base id silently skip the elite mercs). **Fix:** added
    `libWoLU_AddBehaviorToType(libWoLU_Player, "MercReaper", "PersonalCloakingFree");` in the mercs
    block. Reaper has NO toggle cloak ability, so (like base Reaper/Medivac/Predator) it needs ONLY the
    permanent buff — no `ToggleCloakOn` entry. Player-only (rule-9-safe; `MercReaper` is a player-exclusive
    id). `src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy`.
  - **STIM — card-cell COLLISION, fixed.** The stim ABILITY and BUTTON were both [STATIC]-present on
    `MercReaper` (proven via the card-merge simulator: `MercReaper`'s merged AbilArray + card are
    byte-identical to base `Reaper` — both carry `StimpackMarauderWoLU` ability and the `Stim` button via
    `parent="Reaper"`). The defect was a **card-cell collision**: our `Reaper` override placed the Stim
    button at cell **R2,C1**, but the merged Reaper card ALREADY has the **JetPack passive display button**
    (libertystory index 5) at R2,C1 → two buttons at one cell, one silently hides (learnings: a colliding
    card button hides one of the two). **Fix:** moved the Reaper Stim button from R2,C1 → **R2,C2** (free;
    vanilla `U238Rounds` lived there before our index-6 override). `MercReaper parent="Reaper"` inherits the
    clean cell. The simulator now reports the stim button at R2,C2 with **zero collisions** on both Reaper
    AND MercReaper. `src/mod/Base.SC2Data/GameData/UnitData.xml` (`Reaper` card). NB: base Reaper apparently
    resolved the R2,C1 overlap in stim's favor in-game (owner said normal Reaper stim works), so the
    collision was a latent risk that surfaced on the merc — moving the cell eliminates it as a variable for
    both. **⚠ [GAME] owner confirms: Death Heads spawn cloaked (stay cloaked, free) AND show a working
    super-stim button like a normal Reaper.**
  - **Broader merc-parity audit (this pass).** Swept all 6 elite mercs for base-id-keyed per-player gaps:
    cloak (`PersonalCloakingFree`/`ToggleCloakOn`), inherited stim, and the behavior/order periodic loops.
    Only `MercReaper`'s cloak was a real gap (fixed). `MercWraith`/`MercSeniorGhost` cloak: correct.
    `MercMedic`/`MercHellion`/`MercThor`: correctly have no cloak (their base units don't). Stim parity:
    `MercHellion`/`MercSeniorGhost` inherit stim with no collision; the Ghost/MercSeniorGhost R2,C2 "overlap"
    is the cloak toggle's On/Off pair (mutually exclusive by toggle state — vanilla, not a real collision).
    No other clear gaps found.
- [ ] **(PARKED — known cosmetic limitation, owner decision 2026-06-18) Elite mercs show the "heart" placeholder portrait in-game.** Recurring (v0.2.4 / v0.3.7#4 / v0.3.8). It is a **PRELOAD** failure — the portrait model isn't loaded into memory for the merc *calldown* identity — **NOT a path/reference problem.** Verified via git that v0.2.4's local `Merc*Portrait` CModels used the EXACT correct `.m3` paths (`Assets\Portraits\Terran\<Unit>Portrait\<Unit>Portrait.m3`, identical to the moebius `SCVPortrait` pattern) **and still hearted**; the current base-token references also heart. So **both** the base-token AND correct-path-local-CModel approaches fail → the model reference is not the lever. The SC2 Editor only shows the portrait *resolving* (it always did), never the in-game preload, so it **cannot validate a candidate** — any test is owner-in-game-only. Remaining untried levers, both uncertain: (a) re-parent each merc actor to its base unit's actor (likely inherits the same no-explicit-preload behavior → probably still hearts); (b) a map-level model preload (touches the 30 campaign maps = map-affecting + fragile). Cosmetic; **parked** unless the owner wants to spend an in-game iteration on the re-parent shot.
- [x] **Medic / Skibi's Angels (`MercMedic`) can't heal mechanical units (Goliath / `SpartanCompany`). ✅ RESOLVED — owner-confirmed in game 2026-06-19.**
  **REAL ROOT CAUSE FOUND (v0.3.11, [STATIC]; [GAME] confirm pending) — the prior diagnosis below was
  WRONG.** Owner playtest 2026-06-18: the player's Medic heals NO mechanical unit, **neither manual NOR
  autocast.** The earlier note claimed "manual already works, only autocast was the gap" — that was an
  **UNVERIFIED ASSUMPTION and is FALSE.** The actual blocker is a `parent=`-clone merge trap, not the
  autocast.
  **THE BUG:** `HealWoLU` (`parent="heal"`) overrode `TargetFilters` with a **bare `value=`** (no
  `index=`). `TargetFilters` is an **INDEXED array** (`CFiltersParam[]`), not a scalar string — vanilla
  `heal` carries `Ground,Biological,Visible;…` at **index 0**. A bare `<TargetFilters value=…/>` on a
  `parent=` clone does **not replace** the inherited slot 0; it **appends** a second entry, and the
  engine **AND-combines** both → the clone STILL required `Biological` → it refused mechanical targets
  for **both** manual and autocast. (`CEffectCreateHealer` is NOT bio-only — `NanoRepair`/`Repair`/
  `MULERepair` are the same effect class and restore mechanical; the determinant is purely the
  ABILITY's `TargetFilters` require-bits. So the effect was never the problem — the inherited filter
  bit was.) Evidence: every reference layer that overrides an inherited heal `TargetFilters` uses
  explicit `index="0"` (`mods/_reference/rogue/GameData/AbilData.xml:603`; `index="0" removed="1"` at
  `:347` proves the array indexing).
  **THE FIX:** `<TargetFilters index="0" value="Visible;Self,Enemy,Structure,Missile,UnderConstruction,Dead,Hidden,Invulnerable"/>`
  — `index="0"` REPLACES the inherited `Ground,Biological` slot 0 so only the broad filter remains.
  Now heals any Visible friendly non-structure unit: biological, mechanical, ground, AND air, both
  manually and on autocast. `src/mod/Base.SC2Data/GameData/AbilData.xml` (`HealWoLU`); gate green
  (genlib/lint/audit/preview CHECK8/check_autocast CHECK9). **✅ [GAME] CONFIRMED (owner, 2026-06-19): a player Medic /
  Skibi's Angels can now MANUALLY heal AND auto-heals a damaged Goliath / Spartan Company / tank /
  Viking; enemy Medics still heal only biological.**

  <details><summary>Prior (WRONG) diagnosis — kept for the record; do not trust it</summary>

  The *manual* heal already works
  (HealWoLU's broadened `TargetFilters` has no Biological req, `SpartanCompany` IS `Mechanical,Armored`),
  but the user-visible "can't heal" was the **autocast**: the gap was *auto*-heal of mechanical allies.
  Trace: vanilla `heal` (`CAbilEffectTarget`, `mods/_reference/campaigns/liberty.sc2campaign/AbilData.xml`
  ~line 2485) carries `AutoCast=1`/`AutoCastOn=1` but its **autocast acquisition is gated by its own
  `TargetFilters` (`Ground,Biological,…`)** → vanilla auto-heal NEVER picks a mechanical/air ally; the
  player had to click the button. `HealWoLU` (`parent="heal"`) inherits the AutoCast flags AND drops
  `Ground,Biological`, so it CAN auto-acquire a damaged Spartan Company / Goliath / tank / Viking — and
  the heal effect (`CEffectCreateHealer`), `healSmartTargetFilters` (`-;Enemy`), and `AutoCastFilters`
  (`Visible;Neutral,Enemy`) gate NONE of them by attribute. **Contradiction resolved:** because
  `HealWoLU` inherited the autocast, it was *already* a latent rule-9 leak — ENEMY Medics (who carry
  `HealWoLU` on the global AbilArray) could auto-heal their mechanical allies too. **Fix:** make
  `HealWoLU` a **player-gated autocast** — explicit `<Flags AutoCast/AutoCastOn>` + an
  `<AutoCastValidatorArray value="WoLUHasFlag"/>` (the player-only `WoLUHaveFlag` upgrade). Net: the
  PLAYER's Medic auto-heals mechanical + air + bio via HealWoLU; ENEMY Medics FAIL the autocast
  validator (no flag) → keep ONLY vanilla biological `heal`. The inherited vanilla `heal` (idx 3) still
  autocasts on bio allies; HealWoLU supersets it on the player's Medic and the shared
  `Marker Link="Abil/MedivacHeal"` + the heal effect's `noMarkers` validator coordinate the two so the
  same target isn't double-healed/double-drained (verified two-autocast precedent: `heal` +
  `MedivacDoubleBeamHeal` both carry `Marker Link="Abil/MedivacHeal"`). `MercMedic` (parent `Medic`,
  no AbilArray override) inherits the whole thing.
  `src/mod/Base.SC2Data/GameData/AbilData.xml` (`HealWoLU`); `scripts/check_autocast.py` AUTOCAST_INTENT
  gained `HealWoLU` = `{WoLUHasFlag}`. Gate green (genlib/lint/audit/preview CHECK8/check_autocast CHECK9).
  ⚠ **[GAME]** owner confirms: the player's Medic/Skibi's Angels AUTO-heals a damaged Spartan
  Company / Goliath when idle nearby, and nothing enemy-side changed (enemy Medics don't auto-heal mech).
  **NCO biomechanical-drone cross-check (2026-06-18, owner-requested):** `HealWoLU` is ALREADY
  functionally equal to NCO's biomechanical repair drone (`HealingDroneHeal`, novastoryassets) — both
  are `CEffectCreateHealer` with NO Biological gate (heal bio + mech), and the smart `TargetSorts`
  (`TSAlliancePassive`/`TSDistance`/`TSLifeFraction` = heal the most-wounded ally first) are ALREADY
  inherited by `HealWoLU` from vanilla `heal`. The drone is drone-tuned (no energy cost) → a slight
  DOWNGRADE for a Medic. **No switch needed** — our heal is a complete biomechanical heal; the only
  missing piece was the autocast (fixed above).

  </details>

  > **Why the autocast gate (`AutoCastValidatorArray=WoLUHasFlag`) still stands:** the player-gated
  > autocast from the prior pass is correct and KEPT — it prevents enemy Medics auto-healing their
  > mechanical allies once the filter is broadened (a rule-9 leak). It just wasn't the bug the owner
  > reported. Both pieces ship: the `index="0"` filter fix (heals mechanical at all) + the WoLUHasFlag
  > autocast gate (only the player auto-heals mechanical). `MercMedic` (parent `Medic`) inherits both.
- [x] **Spartan Companies can't fire (at least their AA missiles) while loaded in a Bunker — ACCEPTED as an inherent SC2 limitation (v0.3.11).** Our mod lets mechanical/size-8 units load (open-issues #2/#3). The `Weapon.Arc=360` candidate was shipped then **REVERTED** — owner playtest (2026-06-18) confirmed a bunkered Spartan **STILL won't fire AA**, so widening the arc doesn't help: a stowed (bunkered) unit can't aim its turret at all, and the engine appears to block a turret-mounted unit's weapon acquisition from inside a bunker. No static fix exists. **Accepted:** load Spartans in a bunker for transport/ground, not for AA.
  **ROOT-CAUSED (2026-06-18) — it's a TURRET-AIM + narrow weapon-`Arc` limitation, NOT `CasterIsNotHidden`. No clean static fix proven; `Arc` is the one candidate lever but its in-bunker efficacy is unverifiable statically → owner-gated in-game test.**
  - **`CasterIsNotHidden` RULED OUT as the AA-specific cause.** It IS present on the SpartanCompany weapon effects, but on **BOTH** ground and air *identically* — `SpartanCompanyG` (`campaigns/liberty.sc2campaign/EffectData.xml:5278`) AND `SpartanCompanyA` (`:5267`) each carry `<ValidatorArray value="CasterIsNotHidden"/>`, same for the regular Goliath (`GoliathG :5252`, `GoliathA :5241`). A validator that gates both weapons equally cannot explain an **AA-only** failure. (Whether it gates *anything* in a bunker is also unproven — `CasterIsNotHidden` is undefined in the whole reference dump, so it's a core/built-in validator; in vanilla it appears only on burrow/baneline self-spawn effects. If it DID block on Hidden state it would silence the ground cannon too, contradicting the report.)
  - **The VERIFIED differentiator is the weapon `Arc` + turret.** Marine `GuassRifle` (`mods/liberty.sc2mod/WeaponData.xml:203`) sets **no `Arc`** (engine default 360°) and **no turret** → it fires omnidirectionally from a bunker regardless of the stowed body's frozen facing. Every SpartanCompany weapon sets **`Arc=29.9926`** (a ~30° firing wedge) AND is turret-mounted: `WeaponArray Turret="SpartanCompany"` (a `YawArc=135°` turret) for base `SpartanCompanyA`/`G`/`GUpgraded`, `Turret="FreeRotate"` (360°) for `SpartanCompanyAUpgraded` (`campaigns/liberty.sc2campaign/UnitData.xml:1850-1853`; turrets in `TurretData.xml:20` / `mods/.../TurretData.xml:22`). A 30° weapon arc only fires when the **turret** has swung to within 30° of the target — and a stowed (hidden) unit's model/turret cannot articulate to aim, so air targets (which approach from any bearing) fall outside the frozen wedge and the AA never fires. Ground targets often sit ahead of the bunker's frozen facing, which is why "at least the AA" fails while the ground cannon may sometimes connect.
  - **Which weapons are active depends on the Multi-Lock upgrade** (`MultilockTargetingSystems`, `campaigns/liberty.sc2campaign/BehaviorData.xml`): it disables base `SpartanCompanyA`/`G`, enables `*Upgraded`. We auto-grant armory upgrades (rule 2), so post-grant the active AA is `SpartanCompanyAUpgraded` (Turret=`FreeRotate` 360°) — but its weapon `Arc` is still 29.99°, so a 360° turret that can't articulate while stowed still can't satisfy the 30° arc. A full `Arc` fix must cover all four (`SpartanCompanyA`, `SpartanCompanyG`, `SpartanCompanyAUpgraded`, `SpartanCompanyGUpgraded`).
  - **No weapon `Options` flag bypasses facing/arc.** Enumerated all vanilla weapon `Options` (CanInitiateAttackOrder, ContinuousScan, Disabled, Hidden, KeepChanneling, LinkedCooldown, **LockTurretWhileFiring**, Melee, NoDeceleration, OnlyFireAtAttackOrderTarget, OnlyFireWhileInAttackOrder, Uninterruptible, …) — none is an "ignore facing / fire from cargo / bypass turret" flag. `LockTurretWhileFiring` is the *opposite* lever.
  - **The one candidate lever = per-player `Weapon.Arc → 360` on the four SpartanCompany weapons.** `Arc` is a plain weapon scalar (same GOOD class as `Range`/`Period`/`DamagePoint` in preview CHECK8) → per-player editable + **rule-9-safe** (player-only; enemy Goliaths keep 29.99°). It would make the weapon fire in any direction WITHOUT needing the turret to aim within a wedge — IF the engine still lets a stowed unit acquire/fire at all. **That last `IF` is the inherent engine question I cannot resolve statically**: there is NO vanilla precedent of a turret AA unit firing from a bunker to confirm it's even possible, and no actor/flag in the dump that re-enables a stowed unit's turret. So `Arc=360` is a **plausible-but-unproven** candidate, NOT a confirmed fix. **Owner-gated in-game test recommended** (add the 4 per-player `Arc=360` edits to genlib, build, and check whether a bunkered Spartan Company shoots air) before treating it as shipped. If even `Arc=360` doesn't fire air from a bunker, this is an inherent SC2 turret-from-bunker limitation with NO static fix — accept it (Spartans melee/ground only from a bunker, or don't bunker them for AA). [STATIC root-cause; [GAME] for any fix efficacy.]

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
- [x] **Firebat "+vs-light" replaced by a flat +5 damage buff (owner request).** The Firebat
  family now gets a clean flat **+5** attack damage via the CHECK8-GOOD `Effect.Amount` field
  (per-player, rule-9 safe): `FirebatUFull` 8→**13**, scaled to the merc/heroes per rules 4/10 —
  `DevilDogDamage` 10→**16.25** (+5 × the 10/8 = 1.25 ratio, preserving the merc's % advantage),
  `TychusCommandoAttackDamage` 5→**10** and `TychusChaingun` 16→**21** (Tychus = chaingun, +5 each).
  Statically proven (manifest); awaits in-game confirmation of the tooltip/damage numbers.
- [ ] **⚠ STOPPED AT GUARDRAIL — removing the Firebat's residual "+4 vs light" needs an effect clone.**
  There is **no Firebat "Infernal Pre-Igniter" upgrade** to drop — the +vs-light is **hardcoded**
  as `AttributeBonus[Light]=4` inside the `FirebatUFull` effect in static vanilla XML (Hellions, not
  Firebats, carry the real `HellionCampaignInfernalPreIgniter` armory upgrade). A per-player
  `AttributeBonus[Light]` edit is CHECK8-NOOP, so the **only** way to remove it for the player (and
  not enemy Firebats) is a Shaped-Blast effect clone (recipe
  [13](examples/13-flatten-attribute-bonus.md)) — the clone-avoidance guardrail. So today the player's
  Firebat reads **13 (+4 vs light)** = 17 vs light, 13 vs everything else; DevilDog **16.25 (+5 vs
  light)**; Tychus has no light bonus (chaingun) so already flat. **Owner decides:** accept the residual
  +vs-light (no clone) or authorize the `FirebatUFull`/`DevilDogDamage` Shaped-Blast clones to strip it.
- [x] **`heal TargetFilters` runtime edit was dead-redundant — confirmed.** The heal-mech/air feature
  ships via the `HealWoLU` clone on the Medic (`AbilArray index 6`) + Stetmann (`index 5`); the
  string-field runtime edit never did anything. Removed.
- **UNCERTAIN (kept, flagged):** the 6 free-cloak `Modification.VitalRegenArray[Energy]=0` edits are
  an indexed regen-array element (recipe-02 would call it a no-op) but free cloak is GAME-confirmed
  working — kept, re-verify only if cloak energy-drain ever returns.

> Cross-ref: the **rifle-flatten** item below (Ghost/Spectre still read +vs-light/armored) was one
> real gap these no-op removals confirmed. The **Hercules Fusion Core** drop (same no-op family — a
> card `Requirements` link can't be runtime-edited per player) is now RESOLVED via a static all-players
> `StarportTrain` Train6 requirement swap (see the Blocked section); the Marauder/Medic Tech Lab gate
> is left in place per owner decision.

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
  readback is now moot — the lens settles it without a playtest. **(v0.3.13 note: the Thor/Jotun AA
  member of this family is now fully DONE — flat-35 value + splash via the clone, and the card-number
  panel is correct via the CHECK11 `DisplayEffect` repoint. Only the Ghost/Spectre rifles remain,
  owner-decision-pending on the clone.)**
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
  [09](examples/09-broaden-targeting.md). **v0.3.11 made HealWoLU a PLAYER-GATED AUTOCAST** (explicit
  AutoCast flags + `AutoCastValidatorArray=WoLUHasFlag`) so the player's Medic now *auto*-heals
  mechanical/air (not just on a manual click) while enemy Medics keep vanilla biological auto-heal —
  see the v0.3.10-playtest "can't heal Spartan Companies" entry above. So nothing is missing; the only
  remaining check is the [GAME]/Layer-3 one: confirm the Medic actually auto-heals a Marauder/Viking/
  Goliath in game (the clone's autocast).
- [x] **Risky field paths — CLASSIFIED by the preview lens / CHECK8 (2026-06-17), no diag needed.**
  `SummonMercenaries` `Charge.*`/`Cooldown.*` and cloak `Cost[0].Vital[Energy]` are **GOOD** (nested
  per-player scalars that apply — CHECK8 confirms the class; the manifest shows their finals).
  `FirebatUFull AttributeBonus[Light]` was **NOOP** (indexed-array, removed — see the Pre-Igniter gap
  above). The only **UNCERTAIN** is the free-cloak `Modification.VitalRegenArray[Energy]` (indexed
  regen-array; cloak-free is GAME-confirmed working, so kept + flagged).
## Blocked — needs owner

These are investigated to ground truth but need an owner decision (a rule-9 tolerance call or a design choice), not more investigation.

- [x] **Hercules Fusion Core drop** — RESOLVED (owner-approved; static, all-players, rule-9-safe in effect). The earlier per-player `Button.Requirements=""` idea was a runtime no-op (a card `Requirements` link is a UI field, not a per-player-editable scalar). Owner guidance: "build requirements can be equal for all players." So instead of the upgrade-gate fallback, we re-pointed the Hercules train button's `Requirements` from `HaveAttachedStarportTechLabAndFusionCore` (Tech Lab AND Fusion Core) to **`HaveAttachedTechLab`** — the *same* requirement the Banshee/Raven/Wraith Starport trains already use, which is exactly the Tech-Lab-attached node with the Fusion-Core conjunct dropped (verified in RequirementData/RequirementNodeData). Done as a same-id merge override of `StarportTrain InfoArray index="Train6"` in `src/mod/Base.SC2Data/GameData/AbilData.xml` (full Button + Unit + Time re-stated; only Requirements changed). We did NOT edit `HaveAttachedStarportTechLabAndFusionCore` in place because it is NOT Hercules-exclusive — the **Battlecruiser** (Train4) also uses it, so editing it would have freed the BC from needing a Fusion Core too. Global, but no enemy Starport trains a Hercules in WoL → harmless. [GAME-pending: confirm the Hercules is buildable from a Starport+Tech-Lab with no Fusion Core.]
- **Marauder / Medic Tech Lab — LEFT AS-IS per owner decision.** The Marauder and Medic are trained via `BarracksTrain` gated on the shared `HaveAttachedTechLab` requirement; this is NOT a Marauder special case (it's the generic Tech-Lab gate every Tech-Lab Barracks unit uses). Owner decided to leave the Tech Lab prereq in place. Do not re-investigate.

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
