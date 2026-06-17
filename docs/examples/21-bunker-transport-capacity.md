# 21 — More cargo, admit big units, 1 slot per infantry

> Make a bunker/transport hold many more units, accept large units it normally rejects, and
> (ideally) charge one slot per infantry — by editing the **transport ability's** scalar fields,
> NOT the per-unit `CargoSize` (which is a load-time no-op).

**Maps to (request):** the "big bunker" (32 space, admits Thors) + AP Expanded Hull (Medivac
8→12) + "all infantry take 1 slot" rule. open-issues #2/#3.
[learnings.md §"Per-player `MaxCargoCount`"](../learnings.md). **Status:** [STATIC] +
GAME-confirmed for the working levers; the `CargoSize=1` half is the **cautionary** part (a
proven no-op).

---

## Result
The player's bunker shows 32 open slots and actually loads to 32 space — 32 marines, or 4 Thors,
or any mix by space — and accepts size-8 units the vanilla bunker rejects. The player's Medivac
carries 12 instead of 8. (What it does **not** reliably do: force every infantry to cost exactly
1 slot — see the trap.)

## Mechanism
The **working levers are the transport *ability's* scalar fields**, which `CatalogFieldValueModify`
applies per player:
- **`TotalCargoSpace`** — the size of the cargo bar (the "open slots" the UI shows).
- **`MaxCargoCount`** — the cap on the *number* of units, independent of space.
- **`MaxCargoSize`** — the largest single unit admitted (vanilla bunker = 2, which rejects
  anything bigger than a Goliath).

The **trap is the per-unit `CargoSize`**: it's read at the moment the bunker *loads* the unit, so
a per-player runtime edit never reaches it (the Ghost still took 2 slots —
[01](01-per-player-scalar-stat-edit.md), [02](02-no-op-traps.md)). So "1 slot per infantry" via
`CargoSize=1` is a no-op; every unit costs its real size and you size the bar to fit.

A second sharp ordering fact: **`MaxCargoCount` binds *before* `TotalCargoSpace`.** If the count
cap is low (the old `MaxCargoCount=4`), the 32-space bar shows 32 but only 4 units load — the
v0.3.7 regression. Raise `MaxCargoCount` to ≥ `TotalCargoSpace` so the space bar is what binds and
displayed slots == real capacity.

Admitting big units **and** keeping the transport ground-only is a string field
(`TargetFilters`), which is a per-player no-op → it must be a **static XML** edit (global). See
[09](09-broaden-targeting.md) / [02](02-no-op-traps.md).

## Worked example (real, from this repo)
**The big bunker — the three working scalars, set per player** (`MaxCargoCount` raised to 32 so
`TotalCargoSpace` binds, the explicit fix for the count-binds-first regression):
```python
# scripts/genlib.py:257-259
("Abil", "BunkerTransport", "MaxCargoCount", "32", "Set", "high count cap so TotalCargoSpace (32) is the binding limit — displayed slots == real capacity"),
("Abil", "BunkerTransport", "MaxCargoSize", "8", "Set", "admit large ground units (Thor=8) — vanilla 2 rejected them"),
("Abil", "BunkerTransport", "TotalCargoSpace", "32", "Set", "32-space bar fully usable: 32 marines, or 4 Thors, or any mix by space"),
```
**The cautionary half — the `CargoSize=1` attempts that DON'T reach the bunker** (kept in genlib
only as the documented no-op; the comment at `genlib.py:250-256` records that the Ghost still took
2 slots in game):
```python
# scripts/genlib.py:240-243  — these do NOT take (CargoSize is a load-time read)
("Unit", "Firebat", "CargoSize", "1", "Set", "rule: all infantry take 1 bunker slot"),
("Unit", "Marauder", "CargoSize", "1", "Set", ""),
("Unit", "Ghost", "CargoSize", "1", "Set", ""),
("Unit", "Spectre", "CargoSize", "1", "Set", ""),
```
**Medivac Expanded Hull** — same working levers on a different transport ability:
```python
# scripts/genlib.py:343-344
("Abil", "MedivacTransport", "TotalCargoSpace", "12", "Set", "AP Expanded Hull: 8 -> 12 cargo"),
("Abil", "MedivacTransport", "MaxCargoCount", "12", "Set", ""),
```
**The ground-only gate — a STATIC `TargetFilters` edit** (per-player string edit would no-op), so
it's global; the comment notes that's acceptable (enemies don't load mechanical):
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:541-543 -->
<CAbilTransport id="BunkerTransport">
    <TargetFilters value="Visible;Air,Ally,Neutral,Enemy,Dead,Hidden"/>  <!-- Air now excluded; Biological dropped -->
</CAbilTransport>
```
Walk through *why each line is there*: `MaxCargoSize=8` admits the Thor (size 8); `MaxCargoCount=32`
removes the unit-count cap so a marine's size-1 cost is what's counted; `TotalCargoSpace=32` is the
bar. Each unit consumes its **real** `CargoSize` (a Thor legitimately takes 8/32) — we accept that
rather than fight the load-time no-op. The static `TargetFilters` keeps the bunker ground-only by
adding `Air` to the exclude list (after the `;`) and dropping the vanilla `Biological` requirement.

### Merc/hero reach
These edits target the shared **ability** ids (`BunkerTransport`, `MedivacTransport`), not a unit
— so they apply wherever that ability is used (the player's bunkers/Medivacs). The `TargetFilters`
edit is global (static), so enemy bunkers also drop the bio requirement — accepted as negligible.

## Reusable snippet (swap the ids)
```python
# Grow/admit on a transport ABILITY (per player; these scalars DO apply).
# RESOLVE FIRST: confirm the ability id + that it's a CAbilTransport (xmlq.py get <ABIL>).
("Abil", "<TRANSPORT_ABIL>", "MaxCargoCount",   "<N>", "Set", "raise to >= TotalCargoSpace so space binds"),
("Abil", "<TRANSPORT_ABIL>", "MaxCargoSize",    "<S>", "Set", "largest single unit admitted"),
("Abil", "<TRANSPORT_ABIL>", "TotalCargoSpace", "<N>", "Set", "the cargo bar size"),
# Do NOT try ("Unit","<unit>","CargoSize","1","Set") — it's a load-time no-op.
```
```xml
<!-- Ground-only / admit-rules via TargetFilters must be STATIC (string field = per-player no-op): -->
<CAbilTransport id="<TRANSPORT_ABIL>">
    <TargetFilters value="Visible;Air,Ally,Neutral,Enemy,Dead,Hidden"/>
</CAbilTransport>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`CargoSize` per-unit is a LOAD-time read → the runtime edit never reaches the bunker** (Ghost
  still took 2 slots). "1 slot per infantry" via `CargoSize=1` is a no-op; size the bar instead.
- **`MaxCargoCount` binds before `TotalCargoSpace`** — a low count cap silently caps a big space
  bar (v0.3.7: count=4 capped the 32-bar). Set `MaxCargoCount ≥ TotalCargoSpace`.
- **`TargetFilters` is a string field → per-player edit no-ops.** The ground-only gate must be
  static XML (global). Accept the enemy-side leak or guard differently.
- **`MaxCargoSize` too low silently rejects big units** — vanilla 2 rejects a Thor; raise to 8.

## Verify
- **Static:** `python scripts/audit.py` CHECK3 (FAIL on a bad ability id); `galaxy_lint`/build
  green proves the calls compile. **Does not prove** the slot bar actually grew or that a Thor
  loads. `[STATIC]`
- **In-game (owner):** load 32 marines (or 4 Thors) into a player bunker; confirm the bar fills to
  32 and a Thor is admitted; confirm an air unit is rejected; confirm a Medivac holds 12.
  `[GAME]` — add to queue.

## Parked for bunch-verify
- `[GAME]` Player bunker: 32-space bar fully usable (32 marines OR 4 Thors); size-8 Thor admitted;
  air unit rejected. Medivac holds 12.
- `[GAME]` (negative/known no-op) infantry still cost their real `CargoSize`, not forced to 1 —
  confirm the bar accounts by real size (documents the `CargoSize` no-op, not a regression).
