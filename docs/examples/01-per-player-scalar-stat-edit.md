# 01 — Per-player scalar stat edit (the engine everything else leans on)

> Change a single scalar field on one unit/weapon/ability/effect/behavior — **for the human
> player only**, leaving enemies vanilla (rule 9).

**Maps to (request):** design rules 1–10 broadly; concretely e.g. Marine "+20 HP"
(unit-table Barracks), Predator "no gas / 1 supply" (Factory), Hercules "+2 armor" (Starport),
Marauder "Juggernaut Plating +2 armor", and the whole AP-port stat sweep. **Status:** [STATIC]
proven + [GAME]-confirmed in play for the headline cases (see implementation-patterns §1).

---

## Result
One unit's number changes **only for the player**. Example: the player's Marines have 65 HP;
every enemy Marine still has 45. No new unit, no enemy change — exactly the "my army is
unbalanced and fun, not theirs" contract.

## Mechanism
A per-player edit is a single Galaxy call, emitted from `genlib.py` into the generated apply
lib and run for the human player at mission start:

```
CatalogFieldValueModify(c_gameCatalog<Kind>, "<id>", "<Field>", p, "<value>", c_upgradeOperation<Op>)
```
- `<Kind>` ∈ `Unit | Weapon | Abil | Effect | Behavior | …` → the catalog the id lives in.
- `<Field>` is a **scalar-ish** field path. Plain scalars (`LifeMax`, `LifeArmor`, `Sight`,
  `Speed`, `Range`, `Food`) **and indexed *scalar* fields** like `CostResource[Vespene]`,
  `CostResource[Minerals]`, `InfoArray[Train6].Time` work.
- `p` is the player index (the lib loops the human player).
- `<Op>` ∈ `Set | Add | Subtract | Multiply` (`c_upgradeOperationSet/Add/Subtract/Multiply`).

Why this is the right tool: `CatalogFieldValueModify` is the **only** mechanism that edits one
player's copy of a field. It is the backbone of rule 9. **What it cannot do** (→ recipe
[02](02-no-op-traps.md)): create array entries, edit `*Array[i].Link` link fields, edit string
fields, or change values read once at load time. If your field is one of those, this recipe is
the wrong tool. (learnings.md §"Per-player isolation (rule 9)".)

## Worked example (real, from this repo)
**Marine +20 HP** — the canonical case, emitted directly (not from the tuple table):
```python
# scripts/genlib.py:140-142
lines.append("    // --- Marines: +20 base HP (unit-table) ---")
for f in ("LifeMax", "LifeStart"):
    lines.append(f'    CatalogFieldValueModify(c_gameCatalogUnit, "Marine", "{f}", p, "20", c_upgradeOperationAdd);')
```
Generated into `src/mod/Base.SC2Data/LibWoLUnbalancedGen.galaxy` as:
```
CatalogFieldValueModify(c_gameCatalogUnit, "Marine", "LifeMax",   p, "20", c_upgradeOperationAdd);
CatalogFieldValueModify(c_gameCatalogUnit, "Marine", "LifeStart", p, "20", c_upgradeOperationAdd);
```
Note **both** `LifeMax` *and* `LifeStart` are edited — `LifeMax` raises the cap, `LifeStart` the
spawn value, so the unit spawns at full new HP rather than at the old value and slowly regenning.
This pairing is a recurring rule (see the parity sweep).

Most stat edits live in the **`stat_edits` tuple table** (`genlib.py:199-508`), one tuple per
edit `(catalog, entry, field, value, op, comment)`, expanded by the loop at `genlib.py:509-511`:
```python
# scripts/genlib.py:203-205  (Predator: no gas, 1 supply; Hercules: +2 armor)
("Unit", "Predator", "CostResource[Vespene]", "0", "Set", "Predator: no gas"),
("Unit", "Predator", "Food", "-1", "Set", "Predator: 1 supply"),
("Unit", "Hercules", "LifeArmor", "2", "Add", "Hercules: +2 armor"),
```
- `CostResource[Vespene] Set 0` — indexed **scalar** → applies (same class as the working cost
  cuts). Free gas.
- `Food Set -1` — `Food` is stored **negative = supply used**; `-1` = costs 1 supply. (To
  *reduce* supply from an unknown base you `Add 1`, since used-supply is negative — see the
  Resource-Efficiency rows `genlib.py:219-239`.)
- `LifeArmor Add 2` — +2 armor.

### Merc/hero reach (critical — read [06](06-merc-hero-parity.md))
A per-**unit-id** edit reaches **only that exact unit id**. `Marine` +20 HP does **not** reach
War Pigs (the Marine merc) or Raynor (the hero) — they are *distinct unit ids*. That is why
`genlib.py` lists heroes/standard-mercs explicitly in `HERO_MERC_UNITS` (`genlib.py:21-27`) and
re-applies every headline buff onto their own ids in the parity sweep (`genlib.py:293-507`),
recomputing the % advantage against the *buffed* base ([06](06-merc-hero-parity.md)). The 6
**elite** mercs are `parent=` clones and reach shared *sub-ids* (weapons/abilities) by
inheritance but **not** per-unit-id edits — same rule, see [18](18-elite-merc-clone.md).

## Reusable snippet (swap the ids)
```python
# Add to the stat_edits table in scripts/genlib.py, then `python scripts/genlib.py`.
# RESOLVE FIRST: `python scripts/xmlq.py get <ID> mods/_reference/.../<File>Data.xml`
# confirms <ID> exists and <FIELD> is a real scalar on it.
("<Unit|Weapon|Abil|Effect|Behavior>", "<ID>", "<FIELD>", "<VALUE>", "<Set|Add|Subtract|Multiply>", "<why>"),
```
For HP-style fields, edit **both** the max and the start (`LifeMax`+`LifeStart`,
`EnergyMax`+`EnergyStart`, `ShieldsMax`+`ShieldsStart`).

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **Misspelled id = silent no-op.** Blizzard's Marine rifle is literally `GuassRifle`
  (`genlib.py:318`); our Marine +1 range was dead a whole batch on the "correct" spelling.
  Verify every id letter-by-letter with `xmlq.py`.
- **`CargoSize` per-unit is read at bunker LOAD time** → the runtime edit doesn't reach it (the
  Ghost-took-2-slots bug). Use the transport ability's scalar fields instead ([21](21-bunker-transport-capacity.md)).
- **Indexed *array* / link / string fields are no-ops** — `Options[]`, `AttributeBonus[Light]`
  on some effects, `*Array[i].Link`, `TargetFilters`. Those need a clone ([07](07-clone-flag-gate.md)).
- **`Multiply` then `Add` order matters** — Firebat is `LifeMax ×2` (`genlib.py:201`) then
  `+100` Kinetic Foam (`genlib.py:352`); the lib emits the ×2 before the +100, so it's
  `(base×2)+100`, not `(base+100)×2`. Sequence your tuples accordingly.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 fails if `<ID>` resolves to no real id
  (catches typos). `galaxy_lint.py` proves the generated call compiles. **Does not prove** the
  number is right or that it reflects in game. `[STATIC]`
- **In-game (Test Document / owner):** spawn the unit and read the stat panel; spawn an enemy of
  the same type and confirm it's **unchanged** (rule 9). Headline cases (Marine 65 vs enemy 45)
  are already [GAME]-confirmed (implementation-patterns §1). `[GAME]` for any new edit's value.
- **Editor (Previewer):** the Previewer shows the **static** catalog, **not** per-player runtime
  numbers — so it canNOT confirm a `CatalogFieldValueModify` value. (It *can* confirm a static
  XML literal, e.g. an elite merc's `LifeMax=500`.) Don't expect to see "+20 HP" in the Previewer.

## Parked for bunch-verify
For a **new** scalar edit: one `[GAME]` line — "spawn `<unit>`; stat panel reads `<expected>`;
enemy `<unit>` still vanilla." The shipped headline edits are already confirmed; only *new*
values are parked.
</content>
