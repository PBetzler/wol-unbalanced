# Open Issues

The canonical bug tracker for WoL Unbalanced — confirmed in-game defects, not the test plan ([verification-checklist.md](verification-checklist.md) is the "what to test", this is the "what's broken"). Each entry is a concrete defect with the version it was seen in + root-cause notes.

Format: `- [ ]` open, `- [x]` resolved. Newest at the top of each section. When a fix ships, move the item to **Resolved** with the version + the actual fix.

Running gate: `python3 scripts/audit.py` catches the structural classes statically (missing/malformed actors, dead calldowns) before a build ships; the rest below need in-game observation.

## Clone metadata (the Merc* elite mercs)

- [ ] **Cloned merc units show the PARENT's name** (Jotun→"Thor", Midnight Riders→"Viking", Winged Nightmares→"Wraith", Senior Ghost→"Ghost"). Seen v0.2.3. The `Unit/Name/Merc*` strings exist and the *buy-button* name is correct, so it's specific to how a `parent=` unit clone resolves its display name (the v0.2.1 actor fix gave them models + unitName but not the name). Needs a dig — possibly the unit needs an explicit name field, or the clone inherits a name token from the parent.
- [ ] **Cloned merc portraits show the default "heart" placeholder.** Seen v0.2.3. The `CActorUnit` sets `PortraitModel="<base>Portrait"` but it doesn't bind. `scripts/audit.py` flags every such token as base-CASC (MedicPortrait/ThorPortrait/GhostAlternatePortrait/…) — one of those is the wrong id, or PortraitModel isn't the right mechanism for a GenericUnitBase actor.
- [ ] **Inspect panel armor/defense category** — shield armor was "unknown" (FIXED v0.2.2 via `ShieldArmorName`); re-verify the life-armor category reads correctly on all elite mercs.

## Damage display + values

- [ ] **"X dmg + X vs light/armored" should flatten to "X dmg"** everywhere (Ghost 20+20, Thor AA 35+35, Spectre, etc.). Seen v0.2.3. The genlib `AttributeBonus[Light/Armored]=0` edits aren't reflecting on the card. Needs the right effect field (the effect lives in core CASC, not the local reference dump).
- [ ] **Senior Ghost should read 30 dmg** (base ghost 20 × the merc's +50% `DamageDealtFraction`). The card shows 20; the behavior buff may not display on the card (in-game damage may still be 30 — confirm), or the +50% isn't applying.
- [ ] **Advanced-stim units with > Marine HP should heal 60, not 30** (Reaper/Ghost/Spectre/Hellion currently on the 30-heal stim variant). Reassign them to the 60-heal `StimpackMarauderWoLU` variant.

## Units / mechanics

- [ ] **Liberator merc (Midnight Riders) has no transform button.** Seen v0.2.1–0.2.3. `MercLiberator` overrides AbilArray[3] → `MercLiberatorDeploy` + a card button, but the button doesn't appear. Investigate after the clone metadata is sorted (the broken actor may have masked it).
- [ ] **Jotun (Thor merc): no projectile/muzzle on its ground attack, and it plays the AA-attack animation against ground targets.** Seen v0.2.1–0.2.3. Weapon-actor binding on the Thor clone — the attack visuals bind to the base `Thor`, not `MercThor`.
- [ ] **Ghost takes 2 bunker slots despite genlib `CargoSize=1`** (base Ghost = 2, base Reaper = 1). Seen v0.2.3. The per-player runtime `CargoSize` edit may not affect bunker capacity (read at a different time). Needs a different lever or a static (rule-9-bending) edit.
- [ ] **Marauder "Internal Tech Module" upgrade doesn't drop the Tech Lab requirement** — still needs a Tech Lab to build. Seen v0.2.3. Apply the Hercules-style `Button.Requirements` edit to the Marauder train command.
- [ ] **All 8 standard mercs available from start** — ATTEMPTED v0.2.2 (direct `TechTreeUnitAllow` of the merc unit types, after v0.2.1's tech-subgroup approach regressed). Needs re-test: do all 8 now appear, with no counterpart/building leakage?

## UX

- [ ] **The elite-merc submenu should stay open after buying a merc**, so you can buy a second without re-opening it. Seen v0.2.3. Standard SC2 resets the card to the main page after a command — needs a flag or a different submenu approach.

## Resolved (most recent first)

- [x] **Thor ground attack felt slow / "windup didn't reflect"** — RESOLVED v0.2.3: the `DamagePoint` cap (0.831→0.1) was already applied; the real cause was the slow `Period` (1.93s). Added the unit-table's Rapid Reload (`ThorsHammer`/`Odin` Period→1.0, backswing→0.1).
- [x] **Merc-unlock regression: Marauder/Firebat/Factory/Armory/Starport buildable in early missions** — RESOLVED v0.2.2: v0.2.1's `EnableCampaignTechUnit` on merc tech-subgroups mapped to the *counterpart* units; replaced with direct `TechTreeUnitAllow` of the merc unit types.
- [x] **Thor splash too small** — RESOLVED v0.2.2: ground-splash radius doubled (0.8/1.25 → 1.6/2.5).
- [x] **Elite-merc shield defense reads "unknown"** — RESOLVED v0.2.2: all shielded clones got `ShieldArmorName`.
- [x] **All elite mercs render as a sphere / no model / no attack visuals** — RESOLVED v0.2.1: the `CActorUnit` entries lacked `parent="GenericUnitBase"` + `unitName=`. `scripts/audit.py` now guards this class.
- [x] **Senior Ghost on Nova's character model instead of a ghost** — RESOLVED v0.2.1→GhostAlternate model.
