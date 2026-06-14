# In-Game Verification Checklist — WoL Unbalanced

Working doc for the **verify-then-fix pass**. Almost everything below ships in `main` but is *unverified in game* (the engine can't be run from the dev box). Play the missions in order, tick what passes, and for anything that fails report it back in the format at the bottom — I'll fix from there.

Legend: `[ ]` untested · `[~]` partly verified earlier · `[RISK]` flagged mechanism (most likely to be wrong) · numbers in **bold** are the exact expected values from `genlib.py`.

---

## Part A — Every-mission canary (do this once, on Mission 1)

The mod proves it ran via three subtitle lines (bottom-centre) that fire together right after the campaign-tech grant — at **~1 s and again ~10 s** into the mission. Skip the intro cinematic so you reach the 10 s burst; watch the subtitle area for ~12 s.

- [ ] **Canary** — line reads exactly: `WoL Unbalanced: data applied, upgrades & mercs granted.`
  - Absent ⇒ our library never ran on this map (dependency/MapScript injection problem). Black map with no error ⇒ Galaxy compile failure. Either way, nothing below will be in effect — stop and report.
- [ ] **Diag line** — healthy value: `WoLU diag: clone=5 fx=WoLUStimSet flag=1 m3=StimpackWoLU t1=ThorsHammer`
  - `clone=5` = stim clone XML loaded · `fx=WoLUStimSet` = stim effect wired (this was the old autocast-killer) · `flag=1` = player-only gate granted · `m3=StimpackWoLU` = Marine slot-3 override applied · `t1=ThorsHammer` = Thor weapon kept (splash via effect-override).
- [ ] **Diag2 line** — healthy value: `WoLU diag2: acount=5 m4=MagrailWoLU bcount=<N>`
  - `acount=5` + `m4=MagrailWoLU` = static-XML ability appends are applying. If `acount=4` / `m4` empty ⇒ appends dropped (every new ability/icon would be silently missing — high-impact failure).

If any of these three is wrong, note the **literal text you saw** — it tells me exactly which layer broke.

---

## Part B — Priority test missions (≈9 missions cover the whole risky surface)

### M1 · Liberation Day — Marine + Raynor foundation
Infantry only, no production, enemy Dominion present → perfect for the foundation + rule-9 check.

- [~] Visible upgrade icons on the Marine command card (passive row) — *verified earlier ("worked great"), just confirm still present*
- [ ] Marine HP ≈ **65** (45 base **+20**) — or **75** if the Combat Shield armory grant also landed (+10). Just confirm it's clearly above the enemy's 45.
- [ ] Marine out-ranges enemy marines (Gauss rifle range **6**, was 5) and fires with **no windup** (near-instant)
- [ ] [RISK] **Super Stim autocast + heal**: an engaged Marine auto-stims and *gains* green **+30** HP instead of losing health; manual Stim button still works
- [~] [RISK] **Magrail autocast**: Marine periodically fires the extra railgun shot (authentic WarHound beam + impact) — *visual verified; confirm it still auto-fires*
- [ ] **Raynor (hero = Marine)**: HP ≈ **+44 %** over a buffed Marine, **+1** range, **+2** sight, has the Stim button and Magrail
- [ ] [RISK] **ENEMY-VANILLA (rule 9)**: enemy marines are unchanged — **45** HP, no stim-heal, no extra range, no passive icons. *This is the single most important correctness check; verify on every mission with enemy Terrans.*

### M2 · The Outlaws — Medic (flagged string-field edits)
- [ ] Medic cost **−25 / −25** and **−1** supply vs vanilla (75/50→50/25, 2→1)
- [ ] Medic heal **range 4** (was 2)
- [ ] [RISK] **Adaptive Medpacks** (string-field edit on `heal.TargetFilters`): Medic can heal **mechanical and air** units (try healing an SCV / a Viking). If it can't, the filter-string edit is wrong — report.
- [ ] Tychus (hero = Firebat) present here too — see Firebat values under M4

### M3 · Zero Hour — mercs-from-start + bunker
- [ ] [RISK] **ALL 8 mercs available from the start** (rule-3 override): in *any* mission where you have a Merc Compound, every merc calldown — War Pigs, Devil Dogs, Hammer Securities, Spartan Company, Siege Breakers, Hel's Angels, Dusk Wings, Jackson's Revenge — is present and usable immediately, **regardless of which unit counterparts have unlocked**. Each has effectively unlimited charges and is ready at mission start; never "Not enough charges" (Merc Compound still required to exist).
- [ ] Each merc also carries **its counterpart's upgrades** (parity) even in early missions where that counterpart isn't unlocked yet.
- [ ] **Bunker**: all infantry cost **1 slot** — load 4× Firebat/Marauder (normally 2 each) into one bunker
- [ ] **War Pigs parity** (= buffed Marine + merc %): clearly tankier than your Marines, **+1** range, **+2** sight
- [ ] ENEMY-VANILLA recheck (enemy Terrans everywhere here)

### M3b · Extra elite mercs (NEW — AP "Terran Mercenaries" extras)
Five new merc calldowns added to the Merc Compound, named per the Archipelago roster. All are player-exclusive clones of WoL base units. Test in any mission with a Merc Compound.

The 5 extra mercs now live on a **second card page (submenu)** so the vanilla card stays intact.

| Submenu button | AP merc | Cloned from | Stats |
|---|---|---|---|
| Skibi's Angels | Mercenary Medics | Medic | +50 sh, 150 HP, drops 2 |
| Death Heads | Mercenary Reapers | Reaper | +50 sh, 150 HP, drops 2 |
| Condor* | (non-AP bonus) | Hellion | +50 sh, 200 HP, drops 2 |
| Jotun | Mercenary Thor | Thor | +100 sh, 500 HP, +2 armor, drops 1 |
| Winged Nightmares | Mercenary Wraiths | Wraith (cloaked) | +50 sh, 200 HP, drops 2 |
| Midnight Riders | Mercenary Liberators | Viking + **Liberator/LiberatorAG models** | +75 sh, 250 HP, +4 range, **transforms (both forms airborne)**, drops 2 |
| Senior Ghost | (special) | Ghost + **Ghost model** | 1.5× life/energy/regen/dmg, +3 armor, +75 sh, drops 1 |

- [ ] [RISK] **Midnight Riders transforms and STAYS AIRBORNE** — summons as a flying Liberator (VikingFighter clone, `Liberator` model, mobile). The morph button (R2C2) deploys it to **Defender Mode** (now a stationary *flying* VikingFighter clone with `LiberatorAG` model + an anti-ground gun — it should hover, NOT drop to the ground), and a button reverts it. *High-risk item — the redirected morph, both model tokens, the Speed=0 hover, and the ground-weapon swap are all unverified. If it lands on the ground, looks like a Viking, or the morph fails, report which.*
- [ ] [RISK] **Senior Ghost renders as a standard Ghost** (`Model="Ghost"`, NOT Nova) with **1.5× stats** — bigger life/energy bar, hits ~50% harder, +3 armor; keeps Snipe/EMP/cloak. If damage looks unchanged, the `DamageDealtFraction=0.5` behavior didn't read as +50%.

- [ ] [RISK] **The Merc Compound's main card has an "Elite Mercenaries" submenu button** (top-right, R0C4). The vanilla 8 merc buttons + Rally/SelectBuilder/Halt/Cancel are all **back/intact**.
- [ ] [RISK] **Clicking it opens a second page** listing the 5 elite mercs (row 0) + a Cancel button (bottom-right) that returns to the main card. *This is the #1 risk — a dependency mod adding a whole new `CardLayouts` page (index 1, CardId `EMrc`) is unverified. If the submenu button does nothing or the page is empty, that's the thing to debug.*
- [ ] [RISK] **Each calldown drops its units**, usable immediately, unlimited charges, no cooldown.
- [ ] [RISK] **Units render** as their base unit (Medic/Reaper/Hellion/Thor/Wraith). **If a unit is invisible**, its `CActorUnit` Model token is wrong.
- [ ] Button icons show the unit card icon (cosmetic — blank still works).

> Provenance (corrected): the AP **Terran Mercenaries** group has the 8 standard + 6 extras — Skibi's Angels (Medics), Death Heads (Reapers), **Winged Nightmares (Wraiths)**, Midnight Riders (Liberators), Brynhilds (Valkyries), **Jotun (Thor)**. Confirmed from `archipelago-sc2/content-docs` `item_data.json`. *Condor (Hellion) is a Moebius bonus, not AP.* **Deferred:** Midnight Riders (Liberator = LotV unit, not loaded in WoL maps) and Brynhilds (Valkyrie = custom BW asset AP bundles, no base unit) — both need cross-expansion unit access / asset transplant.

### M7 · The Devil's Playground — Reaper + Vulture (perma-cloak)
- [ ] [RISK] **Reaper permanent free cloak** (periodic behavior-apply): Reapers are cloaked at all times, no energy drain
- [ ] Reaper HP **+10** (Ballistic Flightsuit), out-of-combat regen, cost **−25/−25/−1**, **+1** range, **+2** sight
- [ ] Vulture: faster move (**×1.25**), regen, **fire while moving** (Auto-Launchers), faster attack
- [ ] ENEMY-VANILLA: enemy Reapers/Vultures unchanged

### M (Ghost of a Chance) · Ghost — autocast caster kit
- [ ] Ghost cost **−100 / −50 / −1** (Bargain Bin), **+1** range (7), **+2** sight, **free cloak** (no energy cost/drain)
- [ ] [RISK] Ghost rifle damage **20 flat** (was 10 +10 vs light) — same vs everything
- [ ] [RISK] **Snipe autocast** fires automatically on valid targets; **EMP autocast** fires on energy/shield targets; **Super Stim** autocasts (heal 30). All three appended without removing the AI's vanilla copies, so enemy ghosts are unaffected.
- [ ] [RISK] ENEMY-VANILLA: enemy Ghosts do **not** auto-snipe/EMP

### M (Breakout) · Spectre — Ghost mirror
- [ ] Spectre cost **−100/−50/−1**, **+1** range (7), **+2** sight, **free cloak**
- [ ] [RISK] Spectre rifle **20 flat** (was 15 +5 vs armored)
- [ ] [RISK] **Psionic Lash + Super Stim autocast**
- [ ] Tosh (hero = Spectre) parity if he appears

### M (The Dig) · Siege Tank — graduating range + no friendly fire
- [ ] **Siege Tank no friendly fire**: sieged splash does **0** damage to your own units (fire near your own army)
- [ ] [RISK] **Graduating Range**: sieged range grows **+1 every 3 s up to +5** (watch the range ring extend after sieging; resets on unsiege). *Confirm it caps at +5, not runaway.*
- [ ] Sieged tank **+3 armor** (Advanced Siege Tech), **+1** range both modes, **+2** sight
- [ ] **Siege Breakers** merc parity (range/sight/+3 sieged armor)

### M (Media Blitz) · Thor + Odin — splash & AA
- [ ] [RISK] **Thor ground attack splashes like a sieged Siege Tank** (player only) — hits clusters; does **not** splash-damage your own units
- [ ] Thor AA: **35 per rocket** (was 8 +4 vs light), AA **range 12**, ground **+1** range, **+2** sight
- [ ] [RISK] **Odin (hero = Thor)** mirrors all of it: AA **range 12 / 35** dmg, ground range +1, sight +2, ground splash
- [ ] ENEMY-VANILLA: enemy Thors (if any) unchanged

### M (Maw of the Void) · Battlecruiser — the BC kit (highest mechanism risk)
- [ ] BC **+2 armor**, **×1.25** speed
- [ ] [RISK] **Fire while moving** (ATX-style) — BC attacks without stopping
- [ ] [RISK] **Missile Pods + Defensive Matrix autocast** (Defensive Matrix self-buff autocast has no clean blueprint — most likely to misbehave)
- [ ] [RISK] **Yamato autocast** on beefy targets only — skips structures; fires on high-HP units
- [ ] [RISK] **Ignore armor** (`ArmorReduction=500`) — BC damage unaffected by target armor. *Semantics unconfirmed; verify the number actually lands.*
- [ ] Jackson's Revenge merc: fire while moving parity

### M (Engine of Destruction) · Wraith — perma-cloak
- [ ] [RISK] **Wraith permanent free cloak** (periodic behavior-apply)
- [ ] Note: Wraith **Trigger Override** (stacking attack speed) and **Advanced Laser Tech** are **not yet implemented** — don't expect them.

---

## Part C — Lower-risk stat spot-checks (test opportunistically as units unlock)

These are plain scalar edits the automated audit already confirmed resolve against the catalogs; quick to eyeball, unlikely to be wrong.

- [ ] **The Evacuation** — Firebat HP ≈ **300** (100 ×2 +100 Kinetic Foam), +4 vs light, flame **range 4**; Super Stim heals **60**. Devil Dogs merc: ×2 HP +100, flamer +2 range.
- [ ] **Outbreak** — Hellion **+2 armor**; Super Stim heals 60
- [ ] **Smash and Grab** — Marauder **+2 armor**, **+1** range (7), **+2** sight; Hammer Securities + Swann parity (range/sight/+2 armor)
- [ ] **Welcome to the Jungle** — Goliath AA **+3** range, cannon **+1** range, HP **+25** (Shaped Hull), cost −25/−25/−1; Spartan Company parity (Ares +3/+1, Shaped Hull +25 — note: the old double-count bug was removed, should be **+25 once**)
- [ ] **The Great Train Robbery** — Diamondback **+3** range, faster attack (×0.75 period), **×1.25** speed, cost −25/−25/−1
- [ ] **The Moebius Factor** — Medivac **+100 shields**, **12 cargo** (was 8), perma-cloak [RISK], cost −25/−25/−1
- [ ] **Safe Haven / Haven's Fall** — Viking **×1.55** speed; Hel's Angels parity
- [ ] **Supernova** — Banshee **+2** range (folded), **+25 %** dmg (folded), **×1.25** speed, **+2** sight; Dusk Wings parity
- [ ] **SCV** (anywhere) — **+15** HP, faster attack (`FusionCutter` period 0.7)
- [ ] **Predator / Hercules / Raven / Science Vessel** (lab-research units) — Predator: 1 supply, 0 gas, **10 s** build; Hercules: **+2 armor**, **20 s** build, no Fusion Core; Raven: permanent Auto-Turrets / Point-Defense Drones (3600 s)
- [ ] **Build times** — nothing trains slower than **60 s** (BC 110→60, Banshee 60, Hercules 20)
- [ ] **Engineering Bay** — combined Atk/Def upgrades research in **30 s** each and apply to infantry+vehicle+ship together; Armory researches disabled

---

## Part D — High-risk mechanism index (where to look if something's off)

| Mechanism | Test in | If it fails, likely cause |
|---|---|---|
| Clone-architecture autocast (Stim) | M1 | `StimpackWoLU` Effect/AutoCast wiring; diag `fx=` value |
| Static-XML ability appends | M1 diag2 | missing explicit index ⇒ append dropped (learnings) |
| Append caster kit (Snipe/EMP/Lash) | Ghost/Spectre | button re-point vs append; AbilArray index |
| Periodic perma-cloak | Reaper/Medivac/Wraith | 2 s behavior-apply trigger; `Cost[0].Vital[Energy]` |
| Thor/Odin ground splash | Media Blitz | `ThorsHammer` Effect override + Shaped-Blast validator branches |
| BC Yamato/Matrix/Pods autocast | Maw of the Void | autocast on append clones; structure-discrimination validator |
| BC ignore-armor | Maw of the Void | `ArmorReduction=500` semantics (unconfirmed) |
| Graduating Range cap | The Dig | `libWoLU_GraduateSiegeRange` stack count (cap 5) |
| Medic heal mech/air | The Outlaws | `heal.TargetFilters` string edit |
| Enemy-vanilla (rule 9) | every mission | any change leaking to non-player units = the worst class of bug |

---

## Report-back format

For each failure, give me:
1. **Mission** + which checklist item.
2. **What you saw** vs expected (e.g. "Marine stim still *hurt* the marine" / "diag showed `acount=4 m4=`").
3. The **diag/diag2 line text** if the foundation looked off.

That's enough to localize the fix — most failures map to one row in Part D.
