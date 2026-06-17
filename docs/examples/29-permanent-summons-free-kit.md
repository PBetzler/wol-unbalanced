# 29 — Permanent summons + a free-to-activate kit (the Raven)

> Make a unit's summons last **forever** and its whole ability kit **free to activate** — so the
> player can spam permanent drones/turrets into a self-sustaining platform — without buffing
> enemy copies of the same unit (rule 9).

**Maps to (request):** unit-table Raven "all spawned abilities have unlimited duration";
BACKLOG WP-D "Raven kit — SHIPPED: permanent summons + free point-defense (owner's design)";
open-issues "Raven self-Point-Defense (owner-resolved)". **Status:** [STATIC] done — all edits
are scalar per-player edits that resolve; the in-game spam-platform behavior is [GAME].
implementation-patterns §1 (per-player scalar edit) + §13 (the free-cost edit class).

---

## Result
The player's Raven drops **Point Defense Drones and Auto-Turrets that never expire** (3600 s),
and its **Hunter-Seeker, PDD, and Auto-Turret all cost 0 energy**. So the player walls an area
with permanent free turrets/drones and fires free Hunter-Seekers. Enemy Ravens keep the vanilla
durations and the vanilla 125/50/100 energy costs.

## Mechanism
Two independent per-player scalar edits, both via `CatalogFieldValueModify`
([01](01-per-player-scalar-stat-edit.md)) — the same field-class as the working cost/free-cloak
edits, so both apply per player:

1. **Permanent duration** = the summon's *timed-life* **behavior** `Duration` field. The
   Auto-Turret and PDD die when their `*TimedLife` behavior expires; set `Duration=3600` (≈1 h,
   outlasts any mission) **on the behavior**. 3600 is chosen deliberately over `0`/`-1`, which the
   engine reads as **sentinels** (instant/never-relevant) rather than "very long" — a real-number
   duration is the safe lever.

2. **Free activation** = the abilities' **`Cost[0].Vital[Energy]` → 0** per player. This is the
   owner's rule-9-safe design (open-issues): the alternative — a hidden always-on intercept weapon
   on the unit — would also be active on **enemy** Ravens. Zeroing the *energy cost* per player
   instead means only the player's kit is free; enemies keep their costs. `Cost[0].Vital[Energy]`
   is an **indexed scalar** (like `CostResource[Vespene]`), so the per-player edit applies (it is
   the exact same field/class as the rule-8 free-cloak edits, learnings §"Free cloak").

Combined: permanent + free = the player spams an unlimited self-sustaining point-defense field.

## Worked example (real, from this repo)

### Permanent summons (behavior `Duration`)
```python
# scripts/genlib.py:376-377  (in the stat_edits table)
("Behavior", "AutoTurretTimedLife",        "Duration", "3600", "Set", "Raven: permanent Auto-Turrets (AP Durable Materials, maxed)"),
("Behavior", "PointDefenseDroneTimedLife", "Duration", "3600", "Set", "Raven: permanent Point Defense Drones"),
```

### Free kit (zero the energy cost per player)
```python
# scripts/genlib.py:385-387
("Abil", "PlacePointDefenseDrone", "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Point Defense Drones (player-only)"),
("Abil", "BuildAutoTurret",        "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Auto-Turrets (player-only)"),
("Abil", "SeekerMissile",          "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Hunter-Seeker Missile (player-only)"),
```
Each tuple expands to one `CatalogFieldValueModify(c_gameCatalog<Behavior|Abil>, "<id>", "<field>",
p, "<v>", c_upgradeOperationSet)` line (`genlib.py:509-511`). Because they're per-player, the
**enemy** Raven's turrets still expire and its abilities still cost energy — rule 9 holds with no
clone needed.

### Why no clone / no always-on weapon (the rejected design)
The owner explicitly rejected a hidden always-on intercept weapon on the Raven: a static weapon
addition is **global** and would arm enemy Ravens too. The energy-cost edit is the rule-9-safe
substitute — per-player, no enemy leak (open-issues "Raven self-Point-Defense", RESOLVED).

### Merc/hero reach
The Raven has no elite-merc or hero counterpart in WoL, so these edits target the base ids only.
(If it did, a `parent="Raven"` clone would inherit the shared ability/behavior ids — kind B — and
a standard merc with its own ability ids would need explicit mirrors, [06](06-merc-hero-parity.md).)

## Reusable snippet (swap the ids)
```python
# RESOLVE FIRST: the *TimedLife behavior id and the ability id (xmlq.py get <id> .../<File>Data.xml).
# Permanent summon:
("Behavior", "<SUMMON>TimedLife", "Duration", "3600", "Set", "<why> — 3600 outlasts a mission; avoid 0/-1 sentinels"),
# Free-to-activate ability (per-player; enemies keep their cost):
("Abil", "<ABILITY>", "Cost[0].Vital[Energy]", "0", "Set", "<why> (player-only)"),
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **`Duration=0` or `-1` are sentinels**, not "very long" — use a large real number (3600).
- **Editing the wrong layer.** Duration lives on the **`*TimedLife` behavior**, not on the summon
  unit or the placing ability. Cost lives on the **ability**, not the summoned unit. Resolve the
  exact id first.
- **A static weapon/behavior addition is global** → it would buff enemy Ravens (violates rule 9).
  That's why this is a per-player *cost* edit, not an always-on weapon.
- **`Cost[0]` index assumption** — confirm the energy cost is at `Cost[0].Vital[Energy]` for your
  ability (some abilities put the vital at a different `Cost` index); a wrong index is a no-op.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (all four+ ids resolve). The diag-readback idiom
  (`CatalogFieldValueGet` in the lib, [27](27-galaxy-per-player-effects.md)) can confirm the value
  applied if doubted. **Does not prove** the turret survives 3600 s or that the cast is free.
  `[STATIC]`
- **In-game (Test Document / owner):** drop a player Auto-Turret/PDD — it persists indefinitely and
  the cast consumed **no** energy; fire a free Hunter-Seeker; confirm an enemy Raven's turret still
  expires and its casts cost energy. A mission with a Raven (or hire one). `[GAME]`.
- **Editor (Previewer):** n/a — duration/cost are runtime numbers, not a render. `[GAME]` only.

## Parked for bunch-verify
- `[GAME]` — player Auto-Turret/PDD persists ~indefinitely (3600 s); PDD/Auto-Turret/Hunter-Seeker
  cast at 0 energy; enemy Raven summons still expire and still cost energy (rule 9 holds).
