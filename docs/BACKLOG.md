# Backlog

Forward-looking work for WoL Unbalanced — the *features* still to build, separate from architecture ([plan.md](../plan.md)), the spec ([unit-table.md](../unit-table.md)), confirmed bugs ([open-issues.md](docs/open-issues.md)), and the test plan ([verification-checklist.md](verification-checklist.md)).

Maintain: newest decisions at the top of each section; when an item ships, move it to **Recently done** with the version.

## Active / next (prioritized)

1. **Clear the open-issues bug list** ([open-issues.md](open-issues.md)) — the elite-merc clone metadata (name/portrait), damage-display flatten, and the functional fixes (stim-60, transform button, bunker slot, Marauder tech-lab) are ahead of new features while the owner is actively playtesting.
2. ~~**Brynhilds — Valkyrie merc**~~ — **SHIPPED v0.3.2**. No third-party transplant needed after all: a `Valkyrie` CActorUnit exists in base liberty data, so the **"Valkyrie" model is in base CASC** and path-referenceable. Built as a standard elite-merc clone — `MercValkyrie` (parent="Wraith", wears the Valkyrie model, +shields/HP/armor), SummonMercenaries Train16, submenu button at the free R1C2 slot. As a Wraith clone it also inherits the player's Wraith Adv-Laser + Trigger-Override. This completes the AP "Terran Mercenaries" roster. (FLAG: Valkyrie model + portrait are base-CASC tokens, unverified locally.)

## Future / maybe (deferred — only if we really want it)

- **Viking Wild Missiles** (5×25 missile salvo). NOTE: this is NOT a WoL Hyperion Armory upgrade — no "Wild Missiles" exists in any WoL/Nightmare/AP catalog we have; the real WoL Viking missile armory upgrade is **Ripwave Missiles** (`HALORockets`), which our rule-2 system already auto-grants (that's the air splash). The AP "Wild Missiles" is a custom 5-launch `CEffectCreatePersistent` salvo that would replace the Viking's air primary attack — deferred (owner: defer for now).
- **Nightmare-difficulty base** — SUPPORTED as a local build mode: `python3 scripts/build.py build nightmare` (or `package nightmare`) layers our mod on top of Rhyme's "Nightmare Difficulty" pack (its maps keep the `NightmareMod.SC2Mod` dependency, ours is appended after so we win catalog conflicts; the mod is bundled). LOCAL-ONLY: the Nightmare maps (~67 MB) + mod are third-party with no upstream git repo, so they can't be a submodule or a CI build — build locally and `gh release upload <tag> dist/WoL-Unbalanced-Nightmare-v*.zip`. Needs in-game testing for two-mod conflicts.

## WP-C — remaining ported AP upgrades (each a mini-project)

- ~~Wraith: Advanced Laser Technology + Trigger Override~~ — **SHIPPED v0.3.1**. Adv Laser = genlib WraithAU/WraithGU dmg ×2 + WraithA/G Period ×0.8. Trigger Override = a stacking `AttackSpeedMultiplier=1.1` buff (MaxStackCount 10) applied on-fire via a WoLUHasFlag-gated weapon effect set — the **Moebius BarrelAccelerator** pattern (the long-blocked "on each attack" trigger is solved data-only, no galaxy). MercWraith inherits both (parent="Wraith", shared weapon ids).
- Viking: ~~Shredder Rounds (ground splash) / Anti-Mechanical Munition~~ **SHIPPED v0.3.1** (TwinGatlingCannon → TwinGatlingCannonsWoLUSet: WoLUHasFlag splash branch + `AttributeBonus[Mechanical]=20`, ThorsHammer pattern; Hel's Angels merc parity too). **Wild Missiles (5×25 salvo)** deferred — spec ready (a 5-launch CEffectCreatePersistent clone replacing the air primary `LanzerTorpedoes`) but it swaps the Viking's main air attack, so it needs in-game validation before shipping. NOTE: air-mode splash already comes free from the auto-unlocked Ripwave Missiles upgrade.
- Siege Tank: ~~Spider Mines~~ **SHIPPED v0.3.1** (`SpiderMineWoLU` reuses the vanilla `SpawnSpiderMine` → SpiderMine unit; on SiegeTank + sieged + SiegeBreaker merc, both forms). **Transport Hook** deferred — researched (a `CEffectApplyForce` negative-Amount pull, ArtanisVortexForce idiom) but the pull mechanic is experimental + has no projectile visual + needs in-game tuning.
- Predator kit: ~~Charge / Vespene Synthesis~~ **SHIPPED v0.3.1**. Charge = permanent `WoLUPredatorCharge` (MoveSpeedMultiplier 2.2, behavior-add path, avoiding the engine-coupled CAbilAugment). Vespene Synthesis = galaxy timer `PlayerModifyPropertyInt(p, c_playerPropVespene, …, n×5)` per 3 s per living Predator (native verified via injected CampaignLib). Adaptive Defenses + Tactical Jump already shipped.
- Science Vessel: ~~Magellan / EMP Shockwave~~ **SHIPPED v0.3.1**. Magellan = a 2nd free Nano-Repair beam (`NanoRepairWoLU`, "heal 2 at once"; autocast-both is the in-game uncertainty). EMP Shockwave = friendly-fire-safe cloned launch+area (`EMPShockwaveLaunchWoLU`) reusing the vanilla EMPSet drain + EMP2Weapon missile. Defensive Matrix + Tactical Jump already shipped.
- ~~Medic: Restoration / Optical Flare~~ — **SHIPPED v0.3.0** (Restoration = ally debuff-cleanse via Moebius RemoveDebuff; Optical Flare = enemy blind via SightBonus −9 + SuppressDetection; + Stetmann hero parity). Adaptive Medpacks mech/air heal still pending verify (open-issues).
- ~~Reaper: Jet Pack Overdrive~~ — **DROPPED (owner, v0.3.3)**. Literal flight needs a forbidden unit-type morph; the owner is fine with the Reaper not shooting air, so the interim anti-air edit was reverted. Reaper keeps vanilla ground-only targeting.
- ~~Hellbat Aspect (Hellion morph)~~ — **DROPPED (owner): we are not pulling in HotS assets.**

## Cross-cutting

- ~~**Tactical Jump** (Hercules / Science Vessel / BC / Predator)~~ — **SHIPPED v0.3.0** via `CEffectTeleport` (`TacticalJumpWoLU`, point-target warp, WoLUHaveFlag-gated button on all 4 units).
- **Combined/visible upgrade display** — extend the passive `Type=Passive` card icons to any unit still missing them; verify the audit-flagged icon paths.

## WP-D — custom features (highest risk, build last)

- ~~Raven kit~~ — **SHIPPED**: permanent summons (Durable Materials → 3600 s) + **free point-defense (v0.3.3, owner's design)**: rather than a hidden always-on intercept weapon (rejected — it would be active on enemy Ravens too), the player's whole Raven kit is made **free to activate** (`PlacePointDefenseDrone`/`BuildAutoTurret`/`SeekerMissile` energy cost → 0 per-player, the free-cloak-edit class). With the permanent duration, the player spams permanent PDDs + Auto-Turrets = a self-sustaining point-defense platform; Hunter-Seeker is a free manual nuke. Enemy Ravens keep vanilla energy costs (rule 9).
- BC smart-batteries: the fully-blueprinted rogue-kit multi-target-no-overkill system (needs in-game iteration; pre-approved single-target fallback already works).
- Smart-Snipe TargetSort priorities (full 4-tier shipped declaratively; verify the ordering in game).

## Open data questions

- "Resource Efficiency" exact per-unit values are undocumented (only Medic −25/−25/−1 and Ghost Bargain Bin are known) — currently the canonical −25/−25/−1 assumption.

## Recently done (rolling, short)

- v0.3.1: WP-C batch 2 — Wraith Adv Laser + Trigger Override, Viking ground splash + anti-mech, Siege Tank Spider Mines, Predator Charge + Vespene Synthesis, SV Magellan + EMP Shockwave.
- v0.3.0: WP-C batch — Tactical Jump (4 units), Medic Restoration + Optical Flare (+ Stetmann), Reaper anti-air.
- v0.2.4–0.2.5: elite-merc clone-metadata (name/portrait/Jotun anims), stim-60, bunker slot, Liberator transform button, Marauder/Hercules tech; flagged-mechanism fixes (BC ignore-armor backwards→0, Defensive Matrix autocast, Senior Ghost +50% indexed form).
- v0.2.1–0.2.3: merc-actor fix, merc-unlock (post-regression), Thor splash ×2 + Rapid Reload, shield armor names — see [open-issues.md](open-issues.md) Resolved.
- v0.2.0: elite-merc roster (AP Terran Mercenaries + Senior Ghost) via a Merc Compound submenu; all-mercs-from-start.
- The big parity/visible-upgrade/AP-port sweeps — see [plan.md](../plan.md) Status.
