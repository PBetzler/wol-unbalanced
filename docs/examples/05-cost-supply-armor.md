# 05 — Cheaper cost, less supply, more armor (Resource Efficiency etc.)

> Make a unit cost less (minerals/gas), take less supply, and/or carry more armor — for
> the player only.

**Maps to (request):** unit-table economy rows — Predator "no gas / 1 supply", Hercules
"+2 armor", Medic "Resource Efficiency (−25/−25/−1)", Ghost "Bargain Bin Prices
(−100/−50/−1)", and the AP "Resource Efficiency" sweep across the remaining units.
**Status:** [STATIC] proven (all scalar / indexed-scalar fields, recipe
[01](01-per-player-scalar-stat-edit.md)); the **exact RE per-unit numbers are an
[ASSUMPTION]** (open data question — BACKLOG).

---

## Result
The player's Predator costs no gas and 1 supply; the Medic costs 25 less of each resource and
1 less supply; the Ghost is dramatically cheaper; Hercules has +2 armor. Every enemy copy keeps
vanilla cost/supply/armor (rule 9).

## Mechanism
All three levers are **scalar (or indexed-scalar) unit fields**, so each is a per-player
`CatalogFieldValueModify` tuple in the `stat_edits` table — no clone needed:

- **Cost** — `CostResource[Minerals]` and `CostResource[Vespene]` are **indexed *scalar***
  fields (a number addressed by `Minerals`/`Vespene`), which `CatalogFieldValueModify` *can*
  edit per player (the same working class as build-time `InfoArray[..].Time`). `Set 0` zeroes
  gas; `Subtract 25` cuts a cost from any base.
- **Supply** — the field is `Food`, and the engine stores **used supply as a NEGATIVE
  number** (a unit that costs 3 supply has `Food=-3`). So:
  - To set an **exact** supply cost from a known base: `Food Set -1` (= costs 1 supply).
  - To **reduce** supply by 1 from an *unknown* base: `Food Add 1` (moves −3 → −2, i.e. one
    less supply). This `Add 1` form is used across the RE sweep where the base varies.
- **Armor** — `LifeArmor` is a plain scalar; `Add 2` = +2 armor.

(Cross-ref [implementation-patterns.md §1](../implementation-patterns.md); [learnings.md
§"Per-player isolation"]. The `Food`-is-negative semantics is the subtle one — get the sign
wrong and you *add* supply cost.)

## Worked example (real, from this repo)

### Predator (no gas, 1 supply) + Hercules (+2 armor)
```python
# scripts/genlib.py:203-205
("Unit", "Predator", "CostResource[Vespene]", "0", "Set", "Predator: no gas"),
("Unit", "Predator", "Food", "-1", "Set", "Predator: 1 supply"),
("Unit", "Hercules", "LifeArmor", "2", "Add", "Hercules: +2 armor"),
```
Verified against ground truth — vanilla Predator is `Vespene=100`, `Food=-3`
(`liberty.sc2campaign/UnitData.xml` Predator block: `CostResource index="Vespene" value="100"`,
`Food value="-3"`). So `Vespene Set 0` = free gas; `Food Set -1` = drops 3 supply → 1 supply
(an *exact* set, valid because we read the base and know it's −3).

### Medic (Resource Efficiency, documented numbers) + Ghost (Bargain Bin)
```python
# scripts/genlib.py:206-211
("Unit", "Medic", "CostResource[Minerals]", "25", "Subtract", "Medic: AP Resource Efficiency (-25/-25/-1)"),
("Unit", "Medic", "CostResource[Vespene]",  "25", "Subtract", ""),
("Unit", "Medic", "Food", "-1", "Set", ""),
("Unit", "Ghost", "CostResource[Minerals]", "100", "Subtract", "Ghost: AP Bargain Bin Prices (-100/-50/-1)"),
("Unit", "Ghost", "CostResource[Vespene]",  "50",  "Subtract", ""),
("Unit", "Ghost", "Food", "-1", "Set", ""),
```
- `Subtract` for cost (robust: it cuts from the real base whatever it is).
- `Food Set -1` here too — Medic/Ghost both end at 1 supply (an exact set; these are the two
  units whose RE/Bargain-Bin numbers are *documented*, so a `Set` is safe).

### The RE sweep for the remaining units (the `Add 1` supply form)
```python
# scripts/genlib.py:219-239  (one block per unit; Firebat shown, the rest mirror it)
("Unit", "Firebat", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption: -25/-25/-1)"),
("Unit", "Firebat", "CostResource[Vespene]",  "25", "Subtract", ""),
("Unit", "Firebat", "Food", "1", "Add", ""),
# … same triple for Reaper, Goliath, Diamondback, SiegeTank, Raven, Medivac (genlib.py:222-239)
```
- Here supply uses **`Food Add 1`** (not `Set -1`): these units have varying bases, and
  RE means "**one less** supply", so `Add 1` (toward zero from a negative) is the base-agnostic
  way to shave exactly 1 supply. Using `Set -1` would *wrongly* force them all to 1 supply.
- The whole block carries the comment **"assumption: −25/−25/−1"** — see the gotcha below.

### Merc/hero reach
Cost/supply/armor are **per-unit-id** fields → they reach **only that exact unit id**. The
RE/cost sweep targets base units the player builds; mercs/heroes arrive via calldown (no build
cost), so they don't need cost parity. But **armor IS a parity field** — e.g. Hercules-style
`LifeArmor +2` is mirrored onto mercs/heroes with their own ids elsewhere (Hammer Securities
`LifeArmor +2`, Swann `+2`, Spartan armor parity — `genlib.py:423,426`; recipe
[06](06-merc-hero-parity.md)). When you add an armor buff to a base unit, check whether its
merc/hero needs the same on its own id.

## Reusable snippet (swap the ids)
```python
("Unit", "<UNIT_ID>", "CostResource[Vespene]",  "0",   "Set",      "free gas"),
("Unit", "<UNIT_ID>", "CostResource[Minerals]", "25",  "Subtract", "cheaper minerals"),
("Unit", "<UNIT_ID>", "Food", "1",  "Add", "-1 supply (Food is NEGATIVE = supply used)"),
("Unit", "<UNIT_ID>", "LifeArmor", "2", "Add", "+2 armor"),
# RESOLVE FIRST: python scripts/xmlq.py get <UNIT_ID> mods/_reference/campaigns/liberty.sc2campaign/UnitData.xml
#   → read the real Food (negative!), CostResource, and LifeArmor base before choosing Set vs Add.
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`Food` is stored NEGATIVE = supply used.** `Set -1` = costs 1 supply; to *reduce* by 1 from
  an unknown base use **`Add 1`** (toward zero). `Subtract` here would *increase* supply cost —
  the easiest sign-flip bug in the file.
- **`Set` vs `Subtract`/`Add` for cost:** `Set 0` is fine for "free gas"; for a *cut* prefer
  `Subtract` so it works against the real base (and stacks predictably with other cuts).
- **`CostResource[...]` is an indexed SCALAR (works); don't confuse it with indexed-*array*
  no-ops** (`Options[]`, `AttributeBonus[Light]` on effects) — those need a clone
  ([02](02-no-op-traps.md), [13](13-flatten-attribute-bonus.md)).
- **Per-unit-id reach only.** A cost/armor edit on `Medic` does NOT touch Skibi's Angels
  (`MercMedic`) or any merc/hero — add their own ids if parity matters ([06](06-merc-hero-parity.md)).

## Verify
- **Static:** `python scripts/audit.py` (CHECK3) confirms each unit id resolves; `galaxy_lint.py`
  confirms compile. **Does not prove** the cost/supply panel reflects the change. `[STATIC]`
- **In-game (Test Document / owner):** open the build button tooltip / unit info — Predator shows
  0 gas + 1 supply, Medic shows −25/−25 and 1 supply, Hercules shows +2 armor; an enemy of the
  same type is unchanged (rule 9). `[GAME]`

## Parked for bunch-verify
- **[GAME]** Predator build tooltip: 0 gas, 1 supply. Hercules info: +2 armor.
- **[GAME]** Medic / Ghost cost + supply reflect the documented cuts.
- **[GAME] + [ASSUMPTION DATA QUESTION]** The RE sweep numbers (−25/−25/−1) for Firebat / Reaper
  / Goliath / Diamondback / SiegeTank / Raven / Medivac are an assumption (only Medic and the
  Ghost Bargain-Bin numbers are documented). If AP's exact per-unit RE values surface, update the
  sweep (BACKLOG "open data question: Resource Efficiency exact per-unit values are undocumented").
