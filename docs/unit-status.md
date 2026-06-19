# WoL Unbalanced — Unit Status (living view)

> **This is a LIVING document — update it whenever a decision or change alters the mod's effect.**
> **Last updated: 2026-06-16 (v0.3.8 bug batch).**
>
> Companion docs: [`unit-table.md`](../unit-table.md) is the **intent / spec** (the owner's Comments column is authoritative — never contradict it); [`docs/open-issues.md`](open-issues.md) is the **bug tracker** (confirmed defects + root-cause notes). This file is the **status cartography**: per unit, what the mod changes and whether it's proven, awaiting in-game, or broken.

## How to read the Status column

| Mark | Meaning |
| --- | --- |
| ✅ | Implemented **and statically proven** — the field/clone/edit resolves against reference catalogs and is the same class as a known-working edit. Static proof ≠ "looks perfect in game", but the mechanism is verified. |
| 🟡 | Implemented, **awaiting in-game confirmation** — the edit ships, but its *runtime* effect (per-player indexed-array edit, string-field edit, portrait/model asset, card-button appearance) can only be observed in game. Honest default when we can't prove it statically. |
| 🐞 | **Known bug / partial** — open defect, or a piece that works while another piece doesn't. |
| ⛔ | **Not implemented / dropped** — with the reason (owner decision, missing asset, engine limit). |

The owner verifies in game — there is no SC2 MCP. `galaxy_lint.py` + `audit.py` green is *necessary, not sufficient*: they catch structure (resolvable ids, card-merge collisions, sphere-no-model), not balance or visuals.

---

## Design rules — one line each (current state)

| # | Rule | State |
| --- | --- | --- |
| 1 | No new units (heroes/mercs are reskins of base units, not new types) | ✅ holds — even the elite mercs are `parent=` clones, never new unit *types* |
| 2 | All armory upgrades auto-unlocked when the unit is unlocked | ✅ `libWoLU_GrantCampaignTech` grants every campaign upgrade + both sides of each lab pair |
| 3 | Mercs unlock with their counterpart | ✅ — **owner override in effect: all 8 standard mercs available from mission start** (speeds testing), via direct `TechTreeUnitAllow` |
| 4 | Mercs keep their % advantage + inherit counterpart upgrades | ✅ mostly (parity sweep mirrors buffs onto distinct merc weapon ids); ⚠ Spartan Company parity just re-tuned (165→198), 🟡 in game |
| 5 | Build time ≤ 60 s | ✅ generated cap (BC 110→60) + overrides (Predator 10, Hercules 20, OL units −25%) |
| 6 | Merc calldowns: unlimited charges, ready at start (Compound still required) | ✅ `SummonMercenaries` Train1-15 Charge/Cooldown zeroed; Compound requirement kept |
| 7 | Attack windup (damage point) ≤ 0.1 s, player Terran units | ✅ generated per-weapon `DamagePoint` cap across all player+hero+merc weapons |
| 8 | Cloak always free (no cost / drain / regen hindrance) | ✅ cloak abil `Cost.Vital[Energy]=0` + buff `VitalRegenArray[Energy]=0`; permanent-cloak-on-spawn 🟡 (#7 below) |
| 9 | All changes player-only; enemies stay vanilla | ✅ the architecture's whole point — per-player `CatalogFieldValueModify` + `WoLUHasFlag`-gated clones. A few GLOBAL exceptions are documented + accepted (see Global Systems) |
| 10 | Heroes inherit base-unit changes & abilities | ✅ Raynor=Marine, Tychus=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost, Tosh=Spectre, Odin=Thor — all in the parity sweep |

**Every either/or choice grants both sides** (lab research pairs, branch units like Ghost/Spectre and Predator/Hercules/Raven/Science Vessel).

## Global systems (apply across many units)

| System | What it does | Status |
| --- | --- | --- |
| **Armory auto-unlock** | All campaign-armory upgrades + both sides of every lab pair granted at map init | ✅ |
| **Build-time cap (60 s)** | Generated from train infos; explicit overrides for Predator/Hercules/OL units | ✅ |
| **Free cloak** | Energy cost + drain zeroed on all cloak abilities/buffs (player-only) | ✅ |
| **Permanent cloak on spawn** | `PersonalCloakingFree`/`SpectreCloakingFree` applied periodically to ALL cloak-capable player units. **0.3.12 (owner): the Cloak On/Off toggle buttons are REMOVED** (tombstoned on Ghost/Banshee/Wraith/Spectre/Dusk Wings/Winged Nightmares/Senior Ghost; Nova/Tosh already had none) — units are simply always cloaked, no buttons. The `ToggleCloakOn` machinery was deleted. **Raven + Science Vessel newly cloaked (0.3.12).** Base units keep their cloak ability (rule 9 — enemies still cloak) | ✅ statically (CHECK5 merge sim: 0 cloak buttons remain, ability retained); 🟡 confirm in game |
| **Windup cap (0.1 s)** | `DamagePoint` capped on every player/hero/merc weapon | ✅ |
| **Merc system** | Unlimited charges, ready at start; Compound still required; % advantage + inherited upgrades | ✅ (Spartan Company parity 🟡) |
| **Engineering Bay combined upgrades** | One Atk + one Def upgrade per tier, infantry cost, 30 s each; applies to infantry/vehicles/ships (vehicle/ship levels follow infantry via periodic sync) | **0.3.12 FIX:** the sync detected the base `TerranInfantryWeaponsLevel{N}` ids, but the campaign's EngBay grants `…UltraCapacitorsLevel{N}` / `…VanadiumPlatingLevel{N}` → the condition never matched → vehicles/fliers never upgraded. Sync now OR-detects the wrapper ids. ✅ statically; 🟡 owner confirms via `diagUpg` (gap: base Banshee/BC/Viking-air aren't in the vanilla ship-weapon list — pending owner decision) |
| **Damage flattening** ("X +Y vs light/armored" → "X flat") | `Amount`/`AttributeBonus` edits on Ghost/Spectre/Thor-AA damage effects | 🐞 the *displayed* number may not update — per-player **indexed-array** effect edits are suspected no-ops; the AA splash uses the proven Shaped-Blast clone, but the card text is unconfirmed (see Open damage items) |
| **Accepted GLOBAL (non-player-only) edits** | A few edits leak to enemies by necessity and are accepted tradeoffs: Thor/Odin weapon `Options` (`LinkedCooldown=0`) for simultaneous air+ground fire (indexed array = per-player no-op → set globally); static bunker `TargetFilters` (drop Biological) | ✅ documented + accepted |

---

# Infantry (Barracks)

Baselines are WoL **campaign** values (from `unit-table.md`, cross-checked vs. `mods/_reference/` during implementation).

| Unit | Base baseline | What the mod changes | Status |
| --- | --- | --- | --- |
| **SCV** | 50/0, 1 supply, ~46 HP | +15 life (Hostile Env Adaptation); faster attack (`FusionCutter` Period 0.7) | ✅ |
| **Marine** | 50/0, 1 supply, 45 HP | **+20 base HP**; Super Stim (heals 30, autocast via `StimpackWoLU` clone); Combat Shield; Magrail Munitions; Laser Targeting (+1 range via `GuassRifle` typo-id, +2 sight) | ✅ (autocast stim **verified in game**); 🟡 Magrail visual verified, other passives display 🟡 |
| **Medic** | 75/50, 2 supply | Resource Efficiency (−25/−25/−1); heal range +2 (Nano Projector); **Adaptive Medpacks** (heal mech+air) via `HealWoLU` clone (re-pointed single button, index 6); Restoration + Optical Flare | ✅ Adaptive Medpacks CONFIRMED in game (owner 2026-06-19) — heals mechanical + air, manual + autocast (`HealWoLU` `TargetFilters index="0"` fix) |
| **Firebat** | 100/25, 2 supply, 50 HP | **HP ×2 then +100** (Kinetic Foam) → 200 HP; +40% flame area (Incinerator Gauntlets); **+5 flat attack damage** (`FirebatUFull` 8→13, owner request replacing the +vs-light framing); +2 range (Nano Projectors); +2 armor (Juggernaut); Super Stim (60-heal); Resource Efficiency | ✅ stats + flat +5 (statically proven, CHECK8-GOOD); ⚠ residual **+4 vs light** stays hardcoded in `FirebatUFull` (removing per-player needs an effect clone — see open-issues) |
| **Marauder** | 100/25, 2 supply | **Stim re-added** (campaign removed it; index-3 override + real stim button at index 10); Concussive Shells; Kinetic Foam (+25 HP); +2 armor (Juggernaut); Laser Targeting (+1 range, +2 sight); Internal Tech Module (no Tech Lab) | ✅ stim re-add statically fixed; 🟡 stim button appears; 🐞 **Internal Tech Module no-Tech-Lab** is a `Button.Requirements=""` link edit — suspected no-op, verify you can build with no Tech Lab |
| **Reaper** | 50/50, 1 supply | Super Stim (60-heal); free permanent cloak; +10 life (Ballistic Flightsuit); out-of-combat regen (approx flat regen); Laser Targeting; keeps vanilla armory (U-238, G-4) | ✅ stats; 🟡 cloak-on-spawn; ⛔ literal flight / anti-air (owner: Reaper stays ground-only, flight needs forbidden unit-type morph) |
| **Ghost** | 150/150, 2 supply | **Always unlocked**; Ocular Implants; **free cloak** (Crius folded in); EMP Rounds; Bargain Bin (−100/−50/−1); Laser Targeting; Super Stim; **autocast Snipe/EMP/Stim** (`SnipeWoLU`/`EMPWoLU` clones); damage flattened to 20 flat (`C10CanisterRifle`); smart-Snipe priority (healer→lethal→tanky→nearest via custom TargetSorts) | ✅ autocast kit + smart-Snipe shipped; 🐞 **+50% dealt damage** (`DamageDealtFraction` indexed) — card shows base 20, confirm *dealt* ~30 in game; 🐞 damage-flatten display (#10 "two stim buttons" not statically reproducible) |
| **Spectre** | 150/150, 2 supply | Mirrors Ghost: Psionic Lash (autocast `ObliterateWoLU`); free cloak (Nyx folded in); Impaler Rounds; Resource Efficiency; Bargain Bin; +1 range, +2 sight; damage flattened to 20 flat (`SpecterU`) | ✅ kit shipped; 🐞 same damage-flatten-display + dealt-damage caveats as Ghost |

---

# Vehicles (Factory)

| Unit | Base baseline | What the mod changes | Status |
| --- | --- | --- | --- |
| **Hellion** | 100/0, 2 supply | All AP except Jump Jets; Twin-Linked Flamethrower; Thermite Filaments; +2 armor (Infernal Plating); Smart Servos; Super Stim (60-heal); OL build-time −25% (30→22 s) | ✅ |
| **Vulture** | 75/0, 2 supply | All AP; Cerberus + Replenishable Magazine (free); Ion Thrusters (+25% speed); Auto Launchers (fire while moving); Jerry-Rigged regen | ✅ |
| **Goliath** | 150/50, 3 supply, 125 HP | Multi-Lock (attack ground+air at once); Ares-Class (+3 AA, +1 cannon range); **Shaped Hull (+25 HP → 150)**; Resource Efficiency; OL (40→30 s); **no** Jump Jets / Internal Tech Module | ✅ |
| **Diamondback** | 150/150, 4 supply | All AP; Tri-Lithium (+3 range); Shaped Hull; Hyperfluxor (−25% attack period, **assumption**); Maglev (+25% speed, **assumption**); Burst Capacitors; Resource Efficiency | ✅ (two values flagged assumptions) |
| **Siege Tank** | 150/125, 3 supply | All AP except Jump Jets / Internal Tech / move-while-sieged; Maelstrom Rounds; **Shaped Blast → no friendly splash** (`CrucioShockCannonFriendly*Damage=0`); Graduating Range (+1/3 s, 5 stacks); +3 armor sieged; Spider Mines; Laser Targeting; Resource Efficiency | ✅ no-FF + LTS proven; 🟡 Graduating Range (confirm 5 stacks = +5 range); 🟡 Spider Mine fixes (own hotkey Y; sieged deploy via raw `SpawnSpiderMine`) |
| **Thor** | 300/200, 6 supply | Goliath upgrade package + AP minus nuke/field-construction/HIP-mode; **ground splash = sieged-tank** (`ThorsHammerWoLU` effect-override); **AA = 35/rocket flat** (HIP floor, no light bonus), AA range 12 (HIP+1); Rapid Reload (Period 1.93→1.0); Laser Targeting; simultaneous air+ground fire (`LinkedCooldown=0`) | ✅ ground splash + Rapid Reload proven; 🟡 AA splash (Shaped-Blast clone — confirm radius); 🟡 simultaneous fire (global `Options` edit — accepted enemy leak); **ground muzzle/impact restored 0.3.11** (the `ThorsHammer`→`ThorsHammerWoLUSet` Effect reroute had silently unbound the muzzle `CActorAction`; rebound per validator branch — 🟡 [GAME] confirm) |
| **Predator** | 100/100, 3 supply | **1 supply, no gas, 10 s build**; Charge (behavior-add); Cloak; Adaptive Defenses (`DamageResponse ModifyFraction`, halves ranged/splash); Vespene Synthesis (galaxy timer); Resource Efficiency | ✅ stats + Charge + Adaptive Defenses shipped; 🟡 Vespene Synthesis timer in game |

---

# Air (Starport)

| Unit | Base baseline | What the mod changes | Status |
| --- | --- | --- | --- |
| **Medivac** | 100/100, 2 supply | All AP; +100 shields (Scatter Veil); +4 cargo (`MedivacTransport` 8→12); Afterburners; permanent cloak; Rapid Deployment; Advanced Healing AI; Resource Efficiency | ✅ stats (cargo=12 is the proven class); 🟡 cloak-on-spawn (no toggle — periodic buff only) |
| **Wraith** | 150/150, 2 supply | All upgrades; free permanent cloak; **Advanced Laser Tech** (air dmg ×2, ground dmg ×2, faster fire); **Trigger Override** (stacking +10%/attack up to +100%, data-only via Moebius BarrelAccelerator pattern); Displacement Field | ✅ Adv-Laser + Trigger Override shipped; 🟡 cloak-on-spawn |
| **Viking** | 150/75, 2 supply | All AP; Ripwave; Phobos (+range); **Shredder line-splash** + Anti-Mech (Assault mode); +55% speed (Aesir Turbines); Smart Servos; **free permanent cloak (0.3.11, owner request — both modes)** | ✅ ground splash + anti-mech; 🟡 cloak-on-spawn (0.3.11 — not normally cloak-capable; `PersonalCloakingFree` on both modes, no toggle/decloak button, like Reaper/Medivac); ⛔ Wild Missiles (deferred — swaps the air primary attack, owner-deferred) |
| **Banshee** | 150/100, 3 supply | All upgrades; +2 range / +25% dmg while cloaked (folded flat since perma-cloaked); Rocket Barrage; Shockwave Battery; Hyperflight (+25% speed); Laser Targeting; free permanent cloak | ✅ stats; 🟡 cloak-on-spawn |
| **Battlecruiser** | 400/300, 6 supply, 110 s build | **Build 110→60 s**; all AP; **fire while moving** (`AllowedMovement=Moving`); **ignore armor** (`ArmorReduction=0` — was backwards at 500, fixed); autocast Missile Pods + Defensive Matrix + **Yamato** (big-target-gated, skips structures); +2 armor; +25% speed; Tactical Jump | ✅ ignore-armor + autocasts shipped (kit clones `parent=`); 🟡 Yamato structure-discrimination (skips ALL structures — refinement deferred); ⛔ smart-batteries (rogue-kit blueprint exists, single-target fallback works — not shipped blind) |
| **Raven** | 100/200, 2 supply | All AP except Hunter-Seeker-as-attack; **summons permanent** (PDD/Auto-Turret Duration 3600); **free kit** (PDD/Turret/Seeker energy → 0, player-only); Interference Matrix; Anti-Armor Missile; **free permanent cloak (0.3.12)** | ✅ free-kit + permanent summons (owner's rule-9-safe design); ⛔ Raven-itself-as-autocast-PDD (owner rejected a hidden always-on weapon) |
| **Science Vessel** | 100/200, 2 supply | All AP; Improved Nano-Repair (free heal); Magellan (heal 2 at once); **EMP Shockwave**; Defensive Matrix (clone, autocast); Tactical Jump; **free permanent cloak (0.3.12)** | ✅ |
| **Hercules** | 300/200, 6 supply, 70 s build | **+2 armor, 20 s build, no Fusion Core**; Tactical Jump | ✅ armor + build time; 🐞 **no-Fusion-Core** is a `Button.Requirements=""` link edit — suspected no-op, verify you can build with no Fusion Core (owner-blocked: the only working lever strips the Merc Compound gate, rule 6) |

---

# Heroes (inherit base-unit changes + abilities, rule 10)

All hero HP/damage/range/sight parity is mirrored onto the hero's **distinct** weapon/unit ids (base-unit edits don't reach them automatically).

| Hero | = Base unit | Inherited / added | Status |
| --- | --- | --- | --- |
| **Raynor** (Raynor01 / RaynorCommando / Raynor) | Marine | HP ×1.4444 (Marine-line ratio); +1 range (own `RaynorGaussRifle`/`CommandoRifle`/`RaynorWeapon`); +2 sight; stim button catalog-injected | ✅ stats; 🟡 injected stim button (experimental index 13) |
| **Tychus** (TychusCommando / TychusChaingun) | Firebat | HP ×2 then +100 (Kinetic Foam); windup cap; **+5 flat chaingun damage** (rule-10 base parity: `TychusCommandoAttackDamage` 5→10, `TychusChaingun` 16→21 — chaingun, no light bonus) | ✅ stats + flat +5 (statically proven) |
| **Swann** | Marauder | +2 armor (Juggernaut); +1 range (`DutchConcussiveGrenade`); +2 sight | ✅ |
| **Stetmann** | Medic | Adaptive Medpacks via `HealWoLU` (its heal is `BonesHeal`, button re-pointed) | 🟡 confirm Stetmann's single heal button + mech/air heal |
| **Nova** | Ghost | Stim/Snipe/EMP kit; +1 range, +2 sight; permanent free cloak | ✅ kit; 🟡 cloak-on-spawn |
| **Tosh** | Spectre | Stim/Psi-Lash kit; +1 range, +2 sight; permanent free cloak | ✅ kit; 🟡 cloak-on-spawn |
| **Odin** | Thor | AA 35/rocket + range 12; ground range +1, sight +2; Rapid Reload (Period 1.0); simultaneous fire | ✅ (mirrors Thor; global `Options` edit accepted) |

> Protoss heroes (Zeratul etc.) are out of scope — no Protoss base-unit changes (rule 10 covers Terran heroes only).

---

# Mercenaries

## Standard mercs (Merc Compound calldowns — keep % advantage, inherit counterpart upgrades)

All 8 are on the Merc Compound **root** card (the submenu was dropped in v0.3.6 — root buttons never collapse). Available from mission start (owner override). They inherit their counterpart's buffs via the parity sweep onto their distinct weapon ids.

> **Calldown cost parity (0.3.11).** A merc's summon cost is the `SummonMercenaries InfoArray[TrainN].Resource[*]` value, NOT the merc unit's (inert) `CostResource`. Each merc whose base unit gets a cost cut now has its calldown reduced by the same amount, floored at 0 (per-player Set): **Devil Dogs** 100/75→75/50 (Firebat −25/−25), **Spartan Company** 25→0 gas (Goliath −25/−25), **Skibi's Angels** 100→75 min (Medic −25), **Death Heads** 100→75 min (Reaper −25), **Senior Ghost** 175→75 min (Ghost −100). Mercs whose base unit got no cut (War Pigs, Hammer Securities, Siege Breakers [already free], Hel's Angels, Dusk Wings, Jackson's Revenge, Condor, Jotun, Winged Nightmares) are unchanged. 🟡 [GAME] confirm one reduced cost in-mission (Resource per-player edit is same field-family as the confirmed rule-6 Charge/Cooldown edits).

| Merc | Counterpart | Bonus vs regular | Parity status |
| --- | --- | --- | --- |
| **War Pigs** | Marine | +65% HP, +35% dmg | ✅ HP ×1.4444; LTS range + sight mirrored (`KelmorianMinerGaussRifle`) |
| **Devil Dogs** | Firebat | +60% HP, +25% dmg | ✅ HP ×2 + Kinetic Foam +100; flamer +2 range; **Firebat +5 scaled by the 1.25 ratio = +6.25** (`DevilDogDamage` 10→16.25, preserves the merc's % advantage) |
| **Hammer Securities** | Marauder | +25% HP, +20% dmg | ✅ +2 armor; range + sight; **super-stim button added v0.3.9** (standalone unit, so the base Marauder's stim card button didn't reach it — appended a `Type=AbilCmd` stim button at idx 7 cell 2,2; 🟡 confirm it shows + autocasts) |
| **Spartan Company** | Goliath | +33% HP, +33% dmg | 🟡 **HP re-tuned 165→198** (Shaped Hull parity: buffed Goliath 150 × 1.32) — confirm ~198 HP in game; Ares-Class range mirrored |
| **Siege Breakers** | Siege Tank | +33% HP, +66% dmg | ✅ range/sight; +3 sieged armor; 🟡 spider-mine fixes (sieged deploy, own hotkey) |
| **Hel's Angels** | Viking | +45% HP, +40% dmg | ✅ SEPARATE ids `HelsAngel{Fighter,Assault}` → explicit parity edits (+55% speed; **free permanent cloak, both modes, 0.3.11**). Calldown cost unchanged — base Viking has no cost cut |
| **Dusk Wings** | Banshee | +25% HP, +50% dmg | ✅ range + sight mirrored (`DuskWingBanshee`); +25% speed |
| **Jackson's Revenge** | Battlecruiser | +30% HP, +30% dmg | ✅ +2 armor, +25% speed; fire-while-moving; **ignore armor on DR effects** (the missing "attack side", fixed); autocast Yamato/Missile-Pods/Defensive-Matrix clones (`State=Normal` fix); 🟡 simultaneous fire / no-rebuild Immortality Protocol stripped; **passive upgrade icons aligned to base BC (Internal Tech + Opt Logistics) 0.3.11** (was a stray Smart Servos icon) |

## Elite mercs (player-only `parent=` clones; AP "Terran Mercenaries" extras + 2 specials)

5 calldowns wired via `SummonMercenaries` Train9-13 + Senior Ghost; on the Merc Compound root card. **v0.3.8 fix:** the blanket decorative passive cards were **removed** — each elite merc now shows **only its base unit's real upgrade cards** (via `parent=`), never a hull/weapon card the unit can't justify. Shields shown via the armor sign, not a redundant passive card. **0.3.11:** the elite-merc calldowns gained keyboard hotkeys (`GameHotkeys.txt`: M/R/N/T/W/S — picked outside the standard-merc AP set D/J/I/H/A/P/G/C; 🟡 owner confirm no collision on the compound card).

| Elite merc | Clone of | Identity / buffs | Card / armor status | Portrait |
| --- | --- | --- | --- | --- |
| **Skibi's Angels** (`MercMedic`) | Medic | Medic merc; +shields; inherits Medic upgrades | ✅ shows **only** Medic's real cards (no hull/weapon face — it's a healer); `LifeArmorName=TerranInfantryArmor` + `ShieldArmorName` both resolve (audit CHECK7) | 🟡 `MedicPortrait` |
| **Death Heads** (`MercReaper`) | Reaper | Reaper merc; +HP/shields/armor | ✅ Reaper cards only; Infantry life-armor + shield signs resolve | 🟡 `ReaperPortrait` |
| **Condor** (`MercHellion`) | Hellion | Hellion merc (non-AP, owner-added); +armor/shields | ✅ Hellion cards only; Vehicle life-armor + shield signs resolve | 🟡 `HellionPortrait`-class token |
| **Jotun** (`MercThor`) | Thor | Thor merc; inherits Thor (Laser Targeting + Shaped Hull at idx 10/11) | ✅ shows inherited Thor cards; Vehicle life-armor + shield signs resolve; ✅ windup capped (both weapons' `DamagePoint`≤0.1 inherited) + simultaneous-fire `Options[]` (inherited) — both [STATIC], 🟡 [GAME] confirm; **Immortality Protocol now WORKS v0.3.9** — parallel `MercThor{DontDie,Wreckage,Reborn}` chain revives AS A JOTUN, no gas, single HP bar (own wreck actor); 🟡 [GAME] confirm rebuild identity/no-gas; 🟡 AA splash; **ground muzzle/impact restored 0.3.11** (🟡 [GAME] confirm) | 🟡 `ThorPortrait` |
| **Winged Nightmares** (`MercWraith`) | Wraith | Wraith merc; inherits Wraith Adv-Laser/Trigger-Override; +shields | ✅ Wraith cards only; Ship life-armor + shield signs resolve | 🟡 `WraithPortrait` |
| **Senior Ghost** (`MercSeniorGhost`) | Ghost | Ghost clone on the **Ghost** model (not Nova); **1.5× life/energy/regen**; +50% dmg (`DamageDealtFraction`); flat armor | ✅ shows inherited Ghost card (Laser Targeting); Infantry life-armor + shield signs resolve; 🐞 #10 "two stim buttons" not statically reproducible (one stim button in merge sim) | 🟡 `GhostAlternate` model / `GhostPortrait` |

> **Portrait heart — still 🟡 unverified for all 6.** The `PortraitModel` tokens are cross-confirmed valid base-CASC tokens by `audit.py` CHECK6 (each is referenced as a `PortraitModel` by a real vanilla actor in the ref dump → the engine loads it). That's strong evidence they render, but the actual portrait is preload-dependent and not locally observable — **the owner confirms the heart is gone in game.**

> **Removed elite mercs (⛔):** Midnight Riders (Liberator) + Brynhilds (Valkyrie) — their intended models don't exist cleanly in WoL deps, so they only ever reskinned to Viking/Wraith. Fully deleted (units, actors, portraits, morphs, calldowns, buttons, strings) per owner decision in the v0.3.5 batch.

---

# Buildings & defensive structures

| Target | Base baseline | What the mod changes | Status |
| --- | --- | --- | --- |
| **Bunker** | 8 cargo space, 4-unit cap, Biological-only, no Air | **BIG bunker (v0.3.8): `TotalCargoSpace=32`, `MaxCargoCount=32`, `MaxCargoSize=8`** — 32 marines OR 4 Thors OR any mix by space; **Thors allowed**; ground-only gate moved to **static** `TargetFilters` (drop Biological, exclude Air); Projectile Accelerator (+1 garrison range); Shrike Turret + Fortified Bunker | 🟡 v0.3.8 just refixed the regression (v0.3.7's `MaxCargoCount=4` bound before the 32-bar → only 4 loaded). Confirm: 32-bar fully usable; a Goliath/Hellion/Thor loads and consumes its real size. `MaxCargoCount` is the proven-editable class (same as Medivac Expanded Hull) |
| **Missile Turret** | — | Titanium Housing (+75 HP); Hellstorm Batteries; Resource Efficiency | ✅ (auto-unlocked) |
| **Terran buildings** | — | Fire-Suppression; Orbital Command (Scanner + MULE); CC gets free unlimited **MULE + Extra Supplies** kit (`CalldownMULEWoLU`/`SupplyDropWoLU`, no Orbital requirement) — single MULE button (re-pointed index 1, duplicate removed) | 🟡 confirm one MULE button + Extra Supplies appear on the CC |
| **Engineering Bay / Armory levels** | per-class 3-tier research | Replaced by **one combined Atk + one combined Def upgrade per tier**, infantry cost, 30 s each; applies to infantry/vehicles/ships (vehicle/ship levels follow infantry via periodic sync) | ✅ EngBay 30 s researches; 🟡 cross-class sync in game |
| **Lab research pairs** | choose one side | **Both sides auto-granted** (Shrike/Fortified, Planetary/Perdition, Predator/Hercules, Cellular/Bio-Steel, Ultra-Cap/Vanadium, etc.) | ✅ |
| **Regenerative Bio-Steel** (mechanical life regen) | vanilla 0.6015/sec | **20/sec** (NCO design 10 ×2) on all covered mechanical units — done by overriding the `RegenerativeBioSteel` CUpgrade's `EffectArray` `LifeRegenRate` Values in static XML (player-only grant path → rule-9-safe); reach: also covers **Odin / MercThor (Jotun) / MercWraith / MercHellion (Condor)**, which the vanilla list omits; 3 s out-of-combat delay kept | 🟡 [GAME] confirm a damaged Thor/Goliath regens ≈20/s after a 3 s pause |

---

# Open damage-display items (cross-cutting, still 🐞 / 🟡)

These are the unresolved questions whose root cause is the **per-player indexed-array edit** (suspected no-op on the *displayed* card number, even when the *value* is correct):

- **"X dmg + Y vs light/armored" → "X flat"** (Ghost `C10CanisterRifle`, Spectre `SpecterU`, Thor/Jotun AA `JavelinMissileLaunchersDamage`). The effect/field paths are CONFIRMED correct; the open question is whether a per-player indexed-array edit reflects on the card. **diag3** (`gAmt`/`gLgt` readback) settles it: `gLgt=0` ⇒ works; `gLgt=10` ⇒ no-op, needs the Shaped-Blast clone pattern (already used for the Jotun AA splash). The AA *value* (35) and *splash* are correct via the clone; only the card *text* is unconfirmed.
- **Senior / regular Ghost +50% dealt damage** — `DamageDealtFraction` rewritten to the correct indexed-per-Kind form. The card still shows weapon base (20) — a damage-*dealt* buff never changes the displayed weapon number. Confirm the *dealt* damage is ~30 in game.
- **Firebat damage** — now a flat **+5** on `FirebatUFull.Amount` (CHECK8-GOOD, applies per player; 8→13). The vanilla `FirebatUFull AttributeBonus[Light]=4` is hardcoded in static XML and stays (per-player AttributeBonus edit is NOOP); stripping it for the player needs a Shaped-Blast effect clone (see open-issues).

---

## Contradictions found (intent vs. implementation) — for the PM

These are places where `unit-table.md` intent and the actual `genlib.py`/XML implementation diverge. None are necessarily *wrong* — most are deliberate, owner-approved deviations — but they're flagged here because the spec and the code disagree on their face:

1. **Rule 3 (mercs unlock with counterpart) — intentionally overridden.** `unit-table.md` rule 3 says mercs unlock in their counterpart's mission; the implementation grants **all 8 standard mercs from mission start** (`libWoLU_GrantCampaignTech` purchases every campaign merc unconditionally) to speed testing. Documented as an owner override, but it contradicts the literal spec.

2. **Ghost autocast scope — Snipe damage parity not implemented as written.** `unit-table.md` says "The normal damage should always be equal to what was the overall damage to light units" and lays out a 4-tier Snipe autocast priority. Implementation: damage is flattened to **20 flat** (10+10-vs-light → 20), and the 4-tier priority shipped as a custom-TargetSort approximation (healer→lethal→tanky→nearest). The "20 flat" matches "overall damage to light" intent, but whether the *displayed/dealt* values match is still 🐞 (the indexed-array-display question).

3. **Marauder Internal Tech Module + Hercules Fusion Core drop — implemented as a suspected no-op.** The spec wants these build prerequisites gone. Implementation sets `Button.Requirements=""` (a requirement-LINK field) per player — flagged in the code itself as likely a runtime no-op. The only known working lever (`TechTreeRestrictionsEnable(p,false)`) is rejected because it also strips the Merc Compound gate (rule 6). **Owner-blocked decision pending** — so the spec says "no prereq" but the unit may still require the building.

4. **Resource Efficiency exact numbers — assumption, not spec.** `unit-table.md` lists "Resource Efficiency" on many units without exact numbers; genlib applies a **canonical −25 M / −25 G / −1 supply** to all of them (Firebat/Reaper/Goliath/Diamondback/Tank/Raven/Medivac), explicitly marked an assumption (only Medic's value is documented). Real AP per-unit values are unknown.

5. **Diamondback Hyperfluxor / Maglev — assumption values.** Spec lists the upgrades; genlib applies **−25% attack period / +25% speed** as flagged assumptions (AP gives no exact numbers).

6. **Optimized Logistics train-time — assumption.** Spec lists OL on Marine/Hellion/Goliath; genlib applies a **−25% build time** (25→19, 30→22, 40→30) as a documented assumption.

7. **BC "ignore armor" semantics — corrected away from a literal reading.** Early implementation set `ArmorReduction=500` (a naive "lots of armor reduction"); it's actually a **multiplier** (0 = ignore armor). Now `0`. The current code matches intent; flagged because the history shows the spec phrasing ("ignore armor") was implemented backwards once.

8. **Wild Missiles (Viking), Raven-self-PDD, Reaper flight/anti-air, Hellbat Aspect, BC smart-batteries — spec/AP-listed but deliberately not shipped (⛔).** Owner decisions or asset/engine limits. The AP/spec columns list these; the mod intentionally omits them.

---

*Skim target: this file should let a human understand the whole mod's state in ~2 minutes. For the authoritative per-unit intent see [`unit-table.md`](../unit-table.md); for confirmed defects + root causes see [`docs/open-issues.md`](open-issues.md).*
