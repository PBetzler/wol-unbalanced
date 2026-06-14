# Backlog

Forward-looking work for WoL Unbalanced — the *features* still to build, separate from architecture ([plan.md](../plan.md)), the spec ([unit-table.md](../unit-table.md)), confirmed bugs ([open-issues.md](docs/open-issues.md)), and the test plan ([verification-checklist.md](verification-checklist.md)).

Maintain: newest decisions at the top of each section; when an item ships, move it to **Recently done** with the version.

## Active / next (prioritized)

1. **Clear the open-issues bug list** ([open-issues.md](open-issues.md)) — the elite-merc clone metadata (name/portrait), damage-display flatten, and the functional fixes (stim-60, transform button, bunker slot, Marauder tech-lab) are ahead of new features while the owner is actively playtesting.
2. **Brynhilds — Valkyrie merc** (the one remaining AP Terran-Mercenary extra). Needs the AP/Brood-War Valkyrie unit + bundled `.m3` assets transplanted — not a base unit. Submenu has a free row for it.

## WP-C — remaining ported AP upgrades (each a mini-project)

- Wraith: Advanced Laser Technology + **Trigger Override** (stacking +10%/attack, cap +100%; reuse the Graduating-Range galaxy-stacking helper, driven off an attack event).
- Viking: Shredder Rounds (ground splash) / Anti-Mechanical Munition / Wild Missiles (5×25 salvo). **Researched (reference-cited spec ready):** air splash already comes free from auto-unlocked Ripwave; ground splash + anti-mech need the ThorsHammer-style clone (TwinGatlingCannons has no AreaArray/AttributeBonus); Wild Missiles = a 5-launch CEffectCreatePersistent salvo clone. Pending integration.
- Siege Tank: Spider Mines / Transport Hook.
- Predator kit: Charge / Vespene Synthesis (Adaptive Defenses already shipped).
- Science Vessel: Magellan / EMP Shockwave (Defensive Matrix shipped; Tactical Jump shipped v0.3.0).
- ~~Medic: Restoration / Optical Flare~~ — **SHIPPED v0.3.0** (Restoration = ally debuff-cleanse via Moebius RemoveDebuff; Optical Flare = enemy blind via SightBonus −9 + SuppressDetection; + Stetmann hero parity). Adaptive Medpacks mech/air heal still pending verify (open-issues).
- ~~Reaper: Jet Pack Overdrive~~ — **anti-air SHIPPED v0.3.0** (drop the required `Ground` token from `P38ScytheGuassPistol` TargetFilters). Literal FLIGHT is BLOCKED: flight is a unit-type/morph property (not a live-editable field) and "never clone unit types" forbids the morph route — owner decision needed if literal flight is wanted.
- Hellbat Aspect (Hellion morph) — needs HotS assets; the one named rule-1 exception.

## Cross-cutting

- ~~**Tactical Jump** (Hercules / Science Vessel / BC / Predator)~~ — **SHIPPED v0.3.0** via `CEffectTeleport` (`TacticalJumpWoLU`, point-target warp, WoLUHaveFlag-gated button on all 4 units).
- **Combined/visible upgrade display** — extend the passive `Type=Passive` card icons to any unit still missing them; verify the audit-flagged icon paths.

## WP-D — custom features (highest risk, build last)

- Raven kit: permanent summons (Durable Materials → 3600 s, shipped) + Point-Defense-Drone as a Raven self-autocast (PDD-as-unit).
- BC smart-batteries: the fully-blueprinted rogue-kit multi-target-no-overkill system (needs in-game iteration; pre-approved single-target fallback already works).
- Smart-Snipe TargetSort priorities (full 4-tier shipped declaratively; verify the ordering in game).

## Open data questions

- "Resource Efficiency" exact per-unit values are undocumented (only Medic −25/−25/−1 and Ghost Bargain Bin are known) — currently the canonical −25/−25/−1 assumption.

## Recently done (rolling, short)

- v0.3.0: WP-C batch — Tactical Jump (4 units), Medic Restoration + Optical Flare (+ Stetmann), Reaper anti-air.
- v0.2.4–0.2.5: elite-merc clone-metadata (name/portrait/Jotun anims), stim-60, bunker slot, Liberator transform button, Marauder/Hercules tech; flagged-mechanism fixes (BC ignore-armor backwards→0, Defensive Matrix autocast, Senior Ghost +50% indexed form).
- v0.2.1–0.2.3: merc-actor fix, merc-unlock (post-regression), Thor splash ×2 + Rapid Reload, shield armor names — see [open-issues.md](open-issues.md) Resolved.
- v0.2.0: elite-merc roster (AP Terran Mercenaries + Senior Ghost) via a Merc Compound submenu; all-mercs-from-start.
- The big parity/visible-upgrade/AP-port sweeps — see [plan.md](../plan.md) Status.
