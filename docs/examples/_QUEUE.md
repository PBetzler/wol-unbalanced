# Bunch-verify queue — parked [EDITOR] / [GAME] checks

Everything in the example catalog (and the shipped mod) that is **statically complete** but
needs the **SC2 Editor** or an **in-game playtest** — i.e. needs the owner. Batch these.

**Update 2026-06-17:** the Editor grant was approved and the local toolchain is now built
(portable MinGW + CMake → `mpqpatch.exe` → full `build.py build` works). An **Editor Previewer
pass** ran and verified the highest-value Flow-A items (elite-merc model + portrait render, armor
signs — rows marked ✅ below), and surfaced one new flag (MercWraith). The mod + sample maps are
installed to `Documents\StarCraft II\{Mods,Maps\Campaign}`, so **Test Document (Ctrl+F9)** is now
set up for the remaining Flow-B items.

**Originally parked because:** the SC2-Editor computer-use grant needs the owner's in-person
approval, and the local map build needed `mpqpatch.exe` (no compiler was installed). Both are now
resolved; the remaining unchecked rows need a Test Document / in-game run.

Run these via the [README runbook](README.md#sc2-editor-verification-runbook). Tick each as it
passes. Two flows: **A = Previewer** (render/card/armor — no playtest, fastest), **B = Test
Document / playtest** (numbers/autocast/behavior). The catalog is **statically complete**; this
queue is the *only* remaining work, and all of it is owner/Editor-gated.

---

## Flow A — Editor Previewer (static render; fastest, no game)

| ☐ | Recipe | Check | Expected |
|---|--------|-------|----------|
| ☐ | [07](07-clone-flag-gate.md) | `WoLUHaveFlag`-gated button on a player unit's merged card | Button present on the player unit (the gate is satisfied for the player) |
| ☐ | [09](09-broaden-targeting.md) | Medic/Stetmann merged card | Exactly ONE heal button, pointing at `HealWoLU,Execute` |
| ✅ | [18](18-elite-merc-clone.md) | Previewer renders the elite mercs | **VERIFIED 2026-06-17 (Editor):** MercThor (Jotun) → body model **"Thor"** + portrait **"Portrait - Thor"** (real Thor portrait, NOT a heart; model renders in the Previewer, NOT a sphere). Condor (Hellion merc) renders as a Hellion. Mechanism proven; CHECK6 confirms all 6 tokens. ⚠ **MercWraith (Winged Nightmares) did NOT appear** in the standalone-mod Data editor (only 1 of 6 missing) — statically identical to siblings (UnitData.xml:586 + actor ActorData.xml:73), so likely a missing-campaign-dependency artifact of the standalone-mod view; **confirm in-game / with a map (full deps)**. |
| ☐ | [24](24-clone-visuals.md) | Previewer renders `WoLUMagrailBeam` / `WoLUMagrailImpact` | Railgun model resolves (not a missing-asset cube) |
| ✅ | [25](25-armor-display-shielded.md) | Each shielded merc's armor signs | **VERIFIED 2026-06-17 (Editor):** Jotun & Condor both show Shield Armor Name **"Defensive Matrix"** (not "unknown") AND Life Armor Name **"Terran Vehicle Plating"** — both string keys resolve in the merged catalog. (The dual-icon *render* side-by-side is still a [GAME] in-game observation.) |
| ☐ | [26](26-command-card-edits.md) | Appended/re-pointed buttons render | Marauder stim 2,0; Marine Magrail 2,1; Ghost/Spectre stim; single CC MULE — right icon, right cell |
| ☐ | [28](28-tactical-jump.md) | Tactical Jump button on Hercules/Predator/BC/SV | Button renders with the real jump icon (not blank) |
| ☐ | [30](30-spider-mines-siege.md) | Spider Mine button on SiegeTank/SiegeTankSieged/SiegeBreaker/SiegeBreakerSieged | Mine-icon button renders on all 4 forms |
| ☐ | [32](32-bc-smart-batteries.md) | 3 re-pointed actives on Jackson's Revenge | Yamato/MissilePods/DefensiveMatrix buttons render |

## Flow B — Test Document / owner playtest (runtime effect)

| ☐ | Recipe | Check | Expected |
|---|--------|-------|----------|
| ☐ | [03](03-attack-windup-cap.md) | Jotun (`MercThor`) ground attack | First shot ≤ ~0.1 s; cadence brisk (Period 1.0) |
| ☐ | [03](03-attack-windup-cap.md) | **Open suspect** — Thor/Jotun **AA** missile cadence | If sluggish, `JavelinMissileLaunchers.Period` (3.0 s) is NOT capped → needs a separate Period edit |
| ☐ | [04](04-build-time-cap.md) | Train Predator / Hercules | Build bar ≈ 10 s / 20 s |
| ☐ | [04](04-build-time-cap.md) | Optimized-Logistics units `[ASSUMPTION]` | Marine 19 / Hellion 22 / Goliath 30 s (−25% factor unverified) |
| ☐ | [05](05-cost-supply-armor.md) | Predator / Hercules / Medic / Ghost tooltips | Predator 0 gas + 1 supply; Hercules +2 armor; Medic/Ghost cost+supply cuts |
| ☐ | [05](05-cost-supply-armor.md) | RE sweep numbers `[ASSUMPTION]` | −25/−25/−1 on Firebat/Reaper/Goliath/Diamondback/SiegeTank/Raven/Medivac (only Medic+Ghost documented) |
| ☐ | [06](06-merc-hero-parity.md) | Spartan Company HP next to a buffed Goliath | ≈ 198 (merc) vs 150 (Goliath) |
| ☐ | [06](06-merc-hero-parity.md) | Marine-line heroes/mercs (Raynor, War Pigs) | HP ×1.4444 over own base; range/sight parity on own weapon ids |
| ☐ | [07](07-clone-flag-gate.md) | Fire a flag-gated `*WoLU` clone on a player unit | Buffed behavior for player; **enemy copy stays vanilla** (rule 9 end-to-end) |
| ☐ | [08](08-autocast-ability.md) | Super-stim already [GAME]-confirmed; any NEW autocast ability | Unit auto-fires it while attacking; effect applies; enemy copy does not |
| ☐ | [09](09-broaden-targeting.md) | Medic heals a damaged **mechanical** unit (Viking/Hellion) | Manual heal works; autocasts onto it when idle nearby |
| ☐ | [10](10-autocast-priority-targetsort.md) | Ghost smart-Snipe autocast in a mixed group | Prioritizes healers → clean-kill → tankiest → nearest; no overkill |
| ☐ | [11](11-effect-set-caster-trap.md) | A SIEGED Siege Tank (and a Breaker) deploys a Spider Mine | Mine spawns (the `ReplenishNanoConstructor` abort no longer occurs) |
| ☐ | [12](12-simultaneous-fire.md) | Thor/Jotun/Odin between an air and a ground enemy | Both weapons fire simultaneously (not alternating) |
| ☐ | [13](13-flatten-attribute-bonus.md) | Thor AA vs a Light and a non-Light target | Both take 35 (no light bonus) |
| ☐ | [13](13-flatten-attribute-bonus.md) | Ghost/Spectre rifle card | **STILL reads "+X vs light/armored"** (confirms the `AttributeBonus` edit is a dead no-op; clone fix unbuilt — open-issues:15) |
| ☐ | [14](14-enlarge-splash.md) | Thor ground / AA shot on clumped units | Wider splash (full ≤1.6, half ≤2.5); enemy Thor splash unchanged |
| ☐ | [15](15-friendly-fire-safety.md) | Thor ground/AA, Viking ground, SV EMP in radius | Enemies hit/drained; **own units inside the blast unharmed** |
| ☐ | [16](16-stacking-on-attack-buff.md) | Player Wraith + MercWraith sustained attacking | Fire rate ramps, caps ~2.6×, decays after a lull; enemy Wraith unaffected |
| ☐ | [17](17-ignore-armor-fire-moving.md) | Player BC + Jackson's Revenge vs high-armor target | Full un-reduced damage; enemy BC still reduced (player-only) |
| ☐ | [17](17-ignore-armor-fire-moving.md) | Player BC / Jackson's Revenge / Vulture | Fire while moving (no stop-to-shoot) |
| ☐ | [18](18-elite-merc-clone.md) | Summon each elite merc in a mission | Model/portrait/name correct; buffed stats present |
| ☐ | [19](19-unlock-units-merc-calldowns.md) | All 8 standard + 6 elite mercs from mission start | Unlimited charges, no cooldown; **no Marauder/Firebat/Factory leak** |
| ☐ | [20](20-auto-unlock-upgrades.md) | In a unit's unlock mission | The unit + its hero already carry every relevant armory upgrade (no armory visit) |
| ☐ | [21](21-bunker-transport-capacity.md) | Player bunker / Medivac | 32-space bar fully usable (32 marines OR 4 Thors); size-8 Thor admitted; air rejected; Medivac holds 12 |
| ☐ | [21](21-bunker-transport-capacity.md) | Known no-op (documents the trap) | Infantry still cost their real `CargoSize` (the per-unit `CargoSize=1` edit is a load-time no-op) |
| ☐ | [22](22-death-response-resurrect.md) | Kill a Jotun | Morphs to wreck, rebuilds **AS A JOTUN** (not base Thor), no gas, single HP bar |
| ☐ | [23](23-free-cloak.md) | Spawn a player Ghost/Banshee | Invisible on spawn; energy static while cloaked; card shows working "Cloak Off"; enemy still pays/drains (#11, #7) |
| ☐ | [24](24-clone-visuals.md) | Cloned abilities keep visuals | Magrail beam+impact (`ActorData.xml:8` FLAG); Snipe/EMP/Yamato projectile/beam; Thor attack anim + splash |
| ☐ | [25](25-armor-display-shielded.md) | Merc inspect panel | BOTH life-armor and Defensive Matrix indicators render side by side (Bug 3 / #8) |
| ☐ | [26](26-command-card-edits.md) | Buttons fire; hotkey | Stim autocasts; single MULE calls down; Spider Mine on **Y**, Enter Siege stays **E** (#3/#1/#5/#10) |
| ☐ | [27](27-galaxy-per-player-effects.md) | Canary subtitle | "WoL Unbalanced: data applied…" ~10 s in (absent ⇒ black-map compile fail) |
| ☐ | [27](27-galaxy-per-player-effects.md) | Predator Vespene Synthesis | Gas rises +5 per living player Predator / 3 s; enemy Predators give none |
| ☐ | [27](27-galaxy-per-player-effects.md) | Graduating siege range | Sieged range +1/3 s up to +5; resets on unsiege |
| ☐ | [28](28-tactical-jump.md) | Tactical Jump warp | Click + point warps the unit; cooldown applies; enemy same-type has no button |
| ☐ | [29](29-permanent-summons-free-kit.md) | Permanent + free Raven kit | PDD/turret persist (3600 s) + cast at 0 energy; enemy Ravens unchanged |
| ☐ | [30](30-spider-mines-siege.md) | Sieged mine deploy + hotkey | Sieged tank deploys mine (no "Can't turn"); hotkey Y ≠ Enter Siege (E) |
| ☐ | [31](31-engineering-bay-upgrade.md) | 30 s + cascade to vehicle/ship | Infantry weapon/armor research ~30 s; completing grants vehicle + ship levels |
| ☐ | [31](31-engineering-bay-upgrade.md) | Combined attack+defense upgrade — **DESIGN, NOT shipped** | Decide with owner: are separate weapon/armor researches acceptable, or build the merged `CUpgrade`? |
| ☐ | [32](32-bc-smart-batteries.md) | BC autocast + ignore-armor + fire-moving | All 3 actives autocast; attacks ignore armor; fires on the move |
| ☐ | [32](32-bc-smart-batteries.md) | Multi-target no-overkill — **DESIGN, NOT shipped** | BC currently overkills (single-target); the spread system needs wiring (owner call) |

---

## Owner decisions surfaced by the catalog (not just verification)

Two recipes documented a **gap between the request and what's built** — these need an owner
*decision*, not just a playtest:
- **[31] Engineering-Bay "one combined attack+defense upgrade"** — only the 30 s time cut +
  galaxy cascade ship; the single merged upgrade the unit-table asked for is **not built**.
- **[32] BC multi-target no-overkill ("smart batteries")** — the autocast/ignore-armor/
  fire-moving half ships; the overkill-avoiding spread (TargetSort) is **design-only**.

## Cross-reference
The pre-existing v0.3.9 `[GAME]` batch in [HANDOFF.md](../HANDOFF.md) §"Pending [GAME]
verification" and [open-issues.md](../open-issues.md) (the `⚠`/`[~]` items) overlaps this queue —
verify them together. This catalog queue adds the **example-driven** checks; the open-issues
items are the **bug-driven** ones. Same Editor session settles both.
</content>
