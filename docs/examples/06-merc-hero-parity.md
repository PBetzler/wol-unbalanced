# 06 — Merc / hero % advantage parity (rules 4 / 10)

> When you buff a base unit, keep its merc and hero counterparts **ahead** — by mirroring
> the buff onto their own ids AND recomputing their % advantage against the *buffed* base.

**Maps to (request):** design rules 4 ("Mercs keep their % advantage and inherit counterpart
upgrades") and 10 ("Heroes inherit base-unit changes & abilities"); open-issues
"Spartan Company HP didn't rise enough (parity)" (RESOLVED v0.3.8). **Status:** [STATIC]
math proven from the reference catalogs; [GAME] to read the final HP in play.

---

## Result
Buff the Goliath and its merc (Spartan Company) and hero counterparts stay proportionally
stronger — not *equal* to the buffed base, and not *flat-copied* from the old base, but their
**original ratio applied to the new base**. The player's Marines get +20 HP and War Pigs/Raynor
scale with them; the Goliath gets +25 HP and Spartan Company lands at exactly the HP that keeps
its 1.32× lead.

## Mechanism
This is the single most expensive recurring class of bug in the project, and it has two roots
([implementation-patterns.md §0](../implementation-patterns.md) is the canonical analysis):

1. **There are two kinds of merc, and base-unit edits reach them differently.**
   - **Standard mercs + heroes** (War Pigs, Hammer Securities, Spartan Company, Raynor, Swann,
     Nova, Tosh, Odin, …) are **DISTINCT unit ids with DISTINCT weapon ids** — they share
     *nothing* by inheritance. A per-unit edit on `Marine`/`Goliath` does **not** reach them; a
     weapon edit on the base weapon (`PunisherGrenades`) does **not** reach the merc's own weapon
     id. So **every headline buff must be mirrored onto the merc/hero's own ids**.
   - The **6 elite mercs** are `parent=` clones (`MercThor parent="Thor"`, etc.) — they inherit
     *shared sub-ids* (weapon/ability/behavior links), so a per-player edit on a **shared
     weapon/ability id** *does* reach them, but a **per-unit-id** edit (LifeMax/armor/sight on
     "Thor") does **not**. (Recipe [18](18-elite-merc-clone.md).)

2. **A "+X%" advantage must be recomputed against the BUFFED base** — not flat-copied. If the
   merc had 1.32× the base and you buff the base, a flat `+25` on the merc breaks the ratio.
   The merc's new value must be **buffed-base × original-ratio**.

The mechanism for both is still just per-player `CatalogFieldValueModify` tuples (recipe
[01](01-per-player-scalar-stat-edit.md)) — the skill is *which ids* and *what value*.

## Worked example (real, from this repo)

### The hero/merc id list + the parity sweep
```python
# scripts/genlib.py:21-27 — every standard merc + hero that needs explicit mirroring
HERO_MERC_UNITS = [
    "Raynor01", "RaynorCommando", "Raynor", "TychusCommando", "TychusChaingun",
    "Swann", "Stetmann", "Nova", "Tosh", "Odin",
    "WarPig", "DevilDog", "HammerSecurity", "SpartanCompany", "SiegeBreaker",
    "SiegeBreakerSieged", "HelsAngelFighter", "HelsAngelAssault", "DuskWing",
    "DukesRevenge",
]
```
The big "PARITY + COMPLETENESS SWEEP" block (`genlib.py:293-507`) then mirrors every headline
buff onto these ids. Examples:
```python
# Marine line: base Marine +20 HP (45->65) → ratio 65/45 = 1.4444; mirror onto every Marine
# hero/merc by MULTIPLY (keeps each one's own base proportional). genlib.py:294-301
("Unit", "Raynor01", "LifeMax", "1.4444", "Multiply", "Marine line: x65/45 (Raynor variants + War Pigs)"),
("Unit", "WarPig",   "LifeMax", "1.4444", "Multiply", ""),
# Hammer Securities (standard Marauder merc) uses its OWN weapon id — base PunisherGrenades
# edit can't reach it, so mirror range/armor onto its own ids. genlib.py:421-423
("Weapon", "HammerSecurity", "Range", "1", "Add", "Hammer Securities: Marauder LTS range"),
("Unit",   "HammerSecurity", "LifeArmor", "2", "Add", "Hammer Securities: Juggernaut Plating"),
```
Why `Multiply 1.4444` and not `Add 20`? The Marine merc/heroes have *different* base HP than
the Marine — multiplying by the **ratio** keeps each one proportionally buffed (its own base ×
the same factor the base unit got), which is exactly "keep the % advantage."

### The Spartan Company recompute (the lesson)
```python
# scripts/genlib.py:452-458
# Ground truth: SpartanCompany base LifeMax=165 (liberty.sc2campaign), Goliath base 125
# (libertystory layer wins) → buffed Goliath = 125 + 25 (Shaped Hull) = 150. The merc's
# pre-buff advantage is 165/125 = 1.32; to keep that ratio post-buff the merc needs
# 150 × 1.32 ≈ 198. A flat +25 → 190 BROKE parity (the merc fell behind its own ratio).
("Unit", "SpartanCompany", "LifeMax",   "33", "Add", "Spartan Company: parity buff (165 -> 198 = buffed Goliath 150 × 1.32)"),
("Unit", "SpartanCompany", "LifeStart", "33", "Add", ""),
```
The full derivation, all numbers **verified against the reference catalogs**:
- `SpartanCompany` base `LifeMax=165` (`liberty.sc2campaign/UnitData.xml:1779` block:
  `<LifeMax value="165"/>`).
- `Goliath` base `LifeMax=125` (`libertystory.sc2campaign/UnitData.xml:821` block —
  the libertystory layer wins over the mod base).
- Original ratio = 165 / 125 = **1.32**.
- Buffed Goliath = 125 + 25 (AP Shaped Hull, `genlib.py:338`) = **150**.
- Parity target = 150 × 1.32 = **198**. Flat add = 198 − 165 = **+33** (not +25).
- A naive "copy the base's +25" would give 190 → the merc would *lose* its lead. That was the
  v0.3.8 bug; +33 fixes it (open-issues "Spartan Company HP").

> **`LifeMax` AND `LifeStart`:** always edit both (recipe [01](01-per-player-scalar-stat-edit.md))
> so the unit *spawns* at the new max, not at the old value regenning up.

### Elite-merc reach (the easy case — verify, don't mirror)
For the 6 `parent=` elite mercs, a buff on a **shared sub-id** already reaches them: the Wraith
Advanced Laser edits on `WraithAU`/`WraithGU`/`WraithA`/`WraithG` (`genlib.py:493-496`) reach
`MercWraith` automatically because it's a `parent="Wraith"` clone with no `WeaponArray` override.
You still must mirror **per-unit-id** stats (e.g. `MercSeniorGhost` 1.5× Life/Energy via Multiply,
`genlib.py:501-505`) since those don't inherit. (Recipe [18](18-elite-merc-clone.md),
implementation-patterns §0.1-B.)

## Reusable snippet (swap the ids)
```python
# Standard merc/hero (DISTINCT ids) — mirror the buff onto THEIR ids:
("Unit",   "<MERC_OR_HERO_UNIT_ID>", "<Field>", "<value>", "<Op>", "parity: ..."),
("Weapon", "<MERC_OR_HERO_WEAPON_ID>", "Range", "1", "Add", "parity: own weapon id"),
# Recompute a "+X% advantage" against the BUFFED base:
#   new_merc = buffed_base * (orig_merc / orig_base)        # the ratio, applied to the new base
#   flat_add = round(new_merc - orig_merc)
# RESOLVE FIRST:
#   python scripts/xmlq.py get <MERC_ID>  .../UnitData.xml   # its OWN base LifeMax + weapon id
#   python scripts/xmlq.py get <BASE_ID>  .../UnitData.xml   # base LifeMax (mind which catalog layer wins)
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **Flat-copying the base's buff onto a merc breaks the % advantage.** Use **buffed-base ×
  original-ratio** (the Spartan Company lesson). Prefer `Multiply` by the ratio when the merc's
  own base differs from the base unit's.
- **Standard mercs/heroes share NOTHING by inheritance** — distinct unit *and* weapon ids. A
  base-weapon edit (`PunisherGrenades`, `GuassRifle`) silently misses them; mirror onto their own
  weapon id (`HammerSecurity`, `KelmorianMinerGaussRifle`, `RaynorGaussRifle`, …).
- **Which catalog layer wins matters for "base".** Goliath base HP is 125 from *libertystory*,
  not the mod's value — read the layer that actually applies (`xmlq.py` the campaign/story file),
  or your ratio is wrong.
- **Edit `LifeStart` with `LifeMax`** or the unit spawns at the old HP and slowly regens up.
- **Elite mercs (`parent=`) need only per-unit-id mirrors** — shared sub-id buffs already reach
  them; double-mirroring a shared id would double-count.

## Verify
- **Static:** `python scripts/audit.py` (CHECK3) confirms every merc/hero id resolves;
  `galaxy_lint.py` confirms compile. The **math** is checkable by hand against the cited base
  values. **Does not prove** the in-game HP. `[STATIC]`
- **In-game (Test Document / owner):** spawn the buffed base and the merc/hero side by side; read
  the HP bars — the merc/hero stays proportionally ahead (Spartan Company ≈ 198 vs buffed Goliath
  150). An enemy Goliath is still 125 (rule 9). `[GAME]`

## Parked for bunch-verify
- **[GAME]** Spartan Company HP reads ≈ 198 next to a buffed Goliath (150). Mission with both.
- **[GAME]** Marine-line heroes/mercs (Raynor, War Pigs) HP scaled by ×1.4444 over their own
  bases; range/sight parity reads on their own weapon ids.
- **[GAME]** Each elite merc (`parent=` clone) inherits shared-id buffs (e.g. MercWraith gets the
  Advanced-Laser damage/period) without a separate mirror.
