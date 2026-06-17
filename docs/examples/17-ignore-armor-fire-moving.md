# 17 — Attacks ignore target armor; weapons fire while moving

> Two independent vanilla-field levers: make a weapon's damage **ignore the target's armor**, and
> let a weapon **fire on the move** instead of stopping to shoot.

**Maps to (request):** unit-table Battlecruiser "ignores armor" + "fire while moving"; Jackson's
Revenge (BC hero) attack-side parity; Vulture Auto-Launchers fire-on-move — open-issues
`docs/open-issues.md:258` ("BC 'ignore armor' was BACKWARDS", RESOLVED v0.2.5). Cross-refs
[01](01-per-player-scalar-stat-edit.md) (these are plain per-player edits), learnings
§"Attack-while-moving". **Status:** [STATIC] done + [GAME]-reasoned · [GAME] parked for the
observed effect.

---

## Result
The player's Battlecruiser deals full damage regardless of the target's armor, and its lasers fire
while the BC keeps moving (no stop-to-shoot). Same for Jackson's Revenge (hero BC) and the Vulture
(fire while moving). Enemies are unchanged (rule 9).

## Mechanism — two separate fields, both plain per-player edits
Unlike the splash/options recipes, these are **normal scalar/enum fields** that *do* apply
per-player via `CatalogFieldValueModify` ([01](01-per-player-scalar-stat-edit.md)) — no clone
needed.

**(A) Ignore armor — `ArmorReduction` on the damage EFFECT.** This is a **multiplier on how much
of the target's armor applies**, not a flat subtraction:
- `1` = armor applies normally (default).
- `0` = armor is fully ignored.
- Reference values in the entire catalog are **only `0`, `0.334`, `1`** — no value like `500`
  exists anywhere (`grep ArmorReduction mods/_reference/`). `SnipeDamage` "ignores armor" by
  setting it to `0`.
- **The trap:** an earlier build set `ArmorReduction=500` to "ignore armor" — that's **backwards**.
  `500` makes the target's armor reduce BC damage **500×** (≈0 damage to anything armored). Set
  **`0`** to ignore armor. (open-issues `docs/open-issues.md:258`.)

**(B) Fire while moving — `AllowedMovement` enum on the WEAPON.** A vanilla enum:
- `Slowing` (default) = the unit slows/stops to fire.
- `Moving` = the weapon fires without slowing. (learnings §"Attack-while-moving".)

## Worked example (real, from this repo)

### Ignore armor (`ArmorReduction` → 0)
```python
# scripts/genlib.py:397-398  — base Battlecruiser, both attack effects
("Effect", "ATSLaserBatteryU", "ArmorReduction", "0", "Set", "BC attacks ignore armor (ground): multiplier 1->0"),
("Effect", "ATALaserBatteryU", "ArmorReduction", "0", "Set", "BC attacks ignore armor (air)"),
```
```python
# scripts/genlib.py:480-483  — Jackson's Revenge (hero BC) attack-side parity
("Effect", "DRBattlecruiserGU", "ArmorReduction", "0", "Set", "Jackson's Revenge ignores armor (ground)"),
("Effect", "DRBattlecruiserAU", "ArmorReduction", "0", "Set", "Jackson's Revenge ignores armor (air)"),
("Effect", "DRCannonsG",        "ArmorReduction", "0", "Set", "Jackson's Revenge cannons ignore armor (ground)"),
("Effect", "DRCannonsA",        "ArmorReduction", "0", "Set", "Jackson's Revenge cannons ignore armor (air)"),
```
- The edit is on the **damage effect** (`*LaserBatteryU` / `DR*U` / `DRCannons*`), not the weapon —
  `ArmorReduction` lives on `CEffectDamage`.
- Jackson's Revenge is a **distinct hero unit with distinct effect ids** — base BC edits don't
  reach it, so it's mirrored explicitly (the owner saw movement/armor boosts but "nothing on the
  attack side" until the DR damage effects were buffed — `genlib.py:477-479` comment;
  [01 §reach](01-per-player-scalar-stat-edit.md)).

### Fire while moving (`AllowedMovement` → Moving)
```python
# scripts/genlib.py:390-391  — base Battlecruiser, both weapons
("Weapon", "ATSLaserBattery", "AllowedMovement", "Moving", "Set", "BC fire while moving (air->surface)"),
("Weapon", "ATALaserBattery", "AllowedMovement", "Moving", "Set", "BC fire while moving (air->air)"),
```
```python
# scripts/genlib.py:473-476  — Jackson's Revenge weapons
("Weapon", "DRBattlecruiserG", "AllowedMovement", "Moving", "Set", "Jackson's Revenge: fire while moving (ground)"),
("Weapon", "DRBattlecruiserA", "AllowedMovement", "Moving", "Set", "Jackson's Revenge: fire while moving (air)"),
("Weapon", "DRCannonsG",       "AllowedMovement", "Moving", "Set", ""),
("Weapon", "DRCannonsA",       "AllowedMovement", "Moving", "Set", ""),
```
```python
# scripts/genlib.py:489  — Vulture Auto-Launchers
("Weapon", "Vulture", "AllowedMovement", "Moving", "Set", "Vulture Auto-Launchers: fire while moving"),
```
- The edit is on the **weapon** (`ATSLaserBattery` / `Vulture` / `DR*`), not the effect —
  `AllowedMovement` is a `CWeaponLegacy` field.
- Note the field/id split between the two levers: **armor** = `ArmorReduction` on the **effect**;
  **movement** = `AllowedMovement` on the **weapon**. A BC needs both edits on both ids.

### Merc/hero reach
Per [01 §reach](01-per-player-scalar-stat-edit.md): these are per-id edits, so they reach **only**
the exact weapon/effect ids listed. The base BC and Jackson's Revenge use **distinct** ids, which is
why both are listed. The Vulture's merc/hero counterparts (if any) would need their own ids added.

## Reusable snippet (swap the ids)
```python
# Add to stat_edits in scripts/genlib.py, then `python scripts/genlib.py`.
# RESOLVE FIRST: <EFFECT_ID> is a CEffectDamage; <WEAPON_ID> is a CWeaponLegacy (xmlq.py get ...).
("Effect", "<EFFECT_ID>", "ArmorReduction", "0", "Set", "<unit> ignores armor (0 = ignore, 1 = normal)"),
("Weapon", "<WEAPON_ID>", "AllowedMovement", "Moving", "Set", "<unit> fires while moving"),
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`ArmorReduction` is a multiplier, not a subtraction** — `0` ignores armor, `1` is normal. A big
  number (`500`) is **backwards** and makes the unit deal ≈0 damage to armored targets
  (the shipped-then-fixed BC bug, `docs/open-issues.md:258`).
- **Right field on the right id** — `ArmorReduction` is on the *effect* (`CEffectDamage`);
  `AllowedMovement` is on the *weapon* (`CWeaponLegacy`). Putting either on the wrong catalog id is
  a no-op (id won't have the field).
- **Heroes/mercs use distinct ids** — a base-unit edit won't reach Jackson's Revenge; list each id
  ([01 §reach](01-per-player-scalar-stat-edit.md)).
- **`AllowedMovement` is an enum string** — but it's a real scalar enum field that *does* apply
  per-player (it is NOT one of the no-op string fields like `TargetFilters`); use the exact token
  `Moving`.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 confirms every effect/weapon id resolves. `Set 0`
  / `Set Moving` are scalar/enum edits in the known-good class. **Does not prove** the damage
  actually ignores armor or the BC visibly fires on the move. `[STATIC]`
- **In-game (Test Document / owner):** attack a high-armor enemy with the player BC and confirm
  damage matches the no-armor number (compare vs an enemy BC, which should still be reduced).
  Order the BC to move past a target and confirm it keeps firing without stopping. Vulture: same
  move-and-shoot check. `[GAME]` — parked.
- **Editor (Previewer):** per-player runtime numbers aren't visible in the Previewer (static
  catalog only). n/a.

## Parked for bunch-verify
- `[GAME]` — Player BC + Jackson's Revenge deal full (un-reduced) damage to a high-armor target;
  enemy BC still reduced (confirms `ArmorReduction=0` applied and is player-only).
- `[GAME]` — Player BC, Jackson's Revenge, and Vulture fire while moving (no stop-to-shoot).
</content>
