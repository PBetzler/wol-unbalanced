# 03 — Attack windup cap (rule 7) + fixing "feels slow"

> Cap a weapon's pre-shot swing to ≤ 0.1 s for the player (rule 7), and — separately —
> fix an attack that *reads* slow even after the cap, by trimming `Period`/`Backswing`.

**Maps to (request):** design rule 7 ("Attack windup ≤ 0.1 s"); Thor "Rapid Reload"
(unit-table); open-issues "Thor ground attack felt slow / windup didn't reflect"
(RESOLVED v0.2.3) and "Bug 4b — Jotun time-to-first-shot windup" (statically settled).
**Status:** [STATIC] proven + [GAME]-confirmed that the felt-slow culprit was `Period`,
not `DamagePoint` (open-issues, implementation-patterns §6).

---

## Result
The player's weapons land their first shot within ~0.1 s of the attack order (no long
wind-up animation gating the damage), and the Thor/Odin ground attack *also* fires at a
brisk cadence instead of the sluggish vanilla 1.93 s rhythm. Enemies keep vanilla timing.

## Mechanism
Three **different** weapon timing fields control "how slow an attack feels" — confusing
them is the classic trap that wasted a debugging session:

- **`DamagePoint`** = the **pre-damage swing** ("windup"): time from the attack order to
  the damage landing. **This is the rule-7 field.**
- **`Period`** = **time between shots** (the attack-rate clock). A long `Period` reads as
  "slow" even when `DamagePoint` is tiny — this was the *real* Thor culprit.
- **`Backswing`** = **post-damage recovery**. Does **not** delay the first shot, but a
  long backswing makes the unit look like it's loitering between attacks.

All three are plain **scalar** weapon fields, so each is a per-player
`CatalogFieldValueModify` (recipe [01](01-per-player-scalar-stat-edit.md)) — no clone, no
no-op. The rule-7 cap is applied generically by a sweep over every player-unit weapon;
the Thor "Rapid Reload" `Period`/`Backswing` trims are hand-listed tuples. (Cross-ref
[implementation-patterns.md §6](../implementation-patterns.md), [learnings.md
§"Visual actors bind to IDs"] for why we cap on the weapon id and never clone the weapon.)

## Worked example (real, from this repo)

### The rule-7 `DamagePoint` sweep (generic, all player weapons)
```python
# scripts/genlib.py:152-165 — the rule-7 pass
lines.append("    // --- Rule 7: damage point (attack windup) cap at 0.1 s ---")
unit_weapons = collect_weapons()
points = weapon_damage_points()
seen = set()
for uid in PLAYER_UNITS:
    for wid in unit_weapons.get(uid, []):
        if wid in seen:
            continue
        seen.add(wid)
        dp = points.get(wid)
        if dp is None or dp > DAMAGE_POINT_CAP:           # DAMAGE_POINT_CAP = 0.1 (genlib.py:35)
            lines.append(f'    CatalogFieldValueModify(c_gameCatalogWeapon, "{wid}", "DamagePoint", p, "{DAMAGE_POINT_CAP}", c_upgradeOperationSet);  // ...')
```
- `weapon_damage_points()` (`genlib.py:78-87`) reads each weapon's explicit `<DamagePoint>`;
  **a weapon with no `<DamagePoint>` element gets `None`** and is treated as the engine
  default 0.167 — so it is *also* capped (0.167 > 0.1). This is why `JavelinMissileLaunchers`
  (which has no `<DamagePoint>` — verified `liberty.sc2mod/WeaponData.xml:211`) still gets a
  cap line.
- The cap is `Set 0.1`, **not** a multiply — it forces the value regardless of base, only
  when the base exceeds 0.1 (the `dp is None or dp > CAP` guard avoids touching already-fast
  weapons).
- `ThorsHammer`'s vanilla `DamagePoint` is **0.831** (verified `liberty.sc2mod/WeaponData.xml:224`),
  far over the cap → it gets the `Set 0.1` line via `Thor` being in `PLAYER_UNITS`.

### The Thor "Rapid Reload" `Period`/`Backswing` trims (hand-listed)
```python
# scripts/genlib.py:272-275  (in the stat_edits table)
("Weapon", "ThorsHammer", "Period", "1.0", "Set", "Thor Rapid Reload: faster ground attack (1.93->1.0)"),
("Weapon", "ThorsHammer", "Backswing", "0.1", "Set", "Thor: minimal attack recovery"),
("Weapon", "Odin", "Period", "1.0", "Set", "Odin mirrors Thor Rapid Reload"),
("Weapon", "Odin", "Backswing", "0.1", "Set", ""),
```
- Vanilla `ThorsHammer` is `Period=1.93`, `Backswing=0.25` (verified
  `liberty.sc2mod/WeaponData.xml:224`). The `DamagePoint` cap alone left the attack feeling
  slow because **`Period` was the bottleneck** — the lesson the open-issue records.
- `Odin` (the hero's weapon, a *distinct* id) is trimmed in parallel so the hero matches —
  base-unit weapon edits do not reach hero weapon ids (recipe [06](06-merc-hero-parity.md)).

### Merc/hero reach
The cap + trims live on the **shared weapon ids** `ThorsHammer` / `JavelinMissileLaunchers`.
`MercThor` is a `parent="Thor"` clone with no `WeaponArray` override, so it fires the *same*
weapon ids → it **inherits the cap and the Rapid Reload automatically** (kind-B reach,
[06](06-merc-hero-parity.md) / implementation-patterns §0.1-B). Odin (a hero with its own
`Odin`/`OdinAntiAir` weapon ids) is handled by the explicit `Odin` tuples above.

## Reusable snippet (swap the ids)
```python
# Rule-7 windup cap on ONE weapon (generic sweep already covers all player weapons):
("Weapon", "<WEAPON_ID>", "DamagePoint", "0.1", "Set", "rule 7: cap pre-shot swing"),
# "Feels slow" after the cap? It's almost always Period (rate), not DamagePoint:
("Weapon", "<WEAPON_ID>", "Period",    "<faster>", "Set", "faster attack rate"),
("Weapon", "<WEAPON_ID>", "Backswing", "0.1",      "Set", "minimal recovery"),
# RESOLVE FIRST: `python scripts/xmlq.py get <WEAPON_ID> mods/_reference/mods/liberty.sc2mod/WeaponData.xml`
# — confirm the id exists and read its real Period/DamagePoint/Backswing before choosing values.
```
Mirror every trim onto a hero's/standard-merc's **own** weapon id (they don't share the base
id — [06](06-merc-hero-parity.md)).

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **Capping `DamagePoint` does NOT fix "feels slow"** if the bottleneck is `Period`. Read all
  three fields before concluding the cap "didn't reflect" (the exact v0.2.3 trap).
- **A weapon with no `<DamagePoint>`** uses the engine default 0.167 (> 0.1) — it still needs
  a cap; `weapon_damage_points()` handles this by treating `None` as over-cap.
- **Misspelled weapon id = silent no-op.** Verify letter-by-letter (`GuassRifle` is Blizzard's
  real typo — `genlib.py:318`).
- **Never clone the weapon to change its timing.** Attack animations bind to `WeaponStart.<id>`
  — a clone with a new id loses them. Edit the vanilla weapon id per player instead
  ([24](24-clone-visuals.md), learnings.md §"Don't clone a WEAPON").
- **`Period` is per-weapon, per-id** — a 2-weapon unit (Thor: ground `ThorsHammer` + air
  `JavelinMissileLaunchers`) has two independent `Period`s. Capping one does nothing to the
  other's cadence (see below).

## Verify
- **Static:** `python scripts/audit.py` (CHECK3) confirms each weapon id resolves; `galaxy_lint.py`
  confirms the generated `CatalogFieldValueModify` lines compile. Grep the generated
  `src/mod/Base.SC2Data/LibWoLUnbalancedGen.galaxy` rule-7 block to confirm `ThorsHammer`
  and `JavelinMissileLaunchers` both get a `DamagePoint ... Set 0.1` line. **Does not prove**
  the in-game feel. `[STATIC]`
- **In-game (Test Document / owner):** order a Thor/Jotun to attack from idle — first shot
  lands ~instantly (windup cap), and the ground attack rhythm is brisk (Rapid Reload). Confirm
  an enemy Thor (if any) still swings slowly (rule 9). `[GAME]`

## Parked for bunch-verify
- **[GAME]** Jotun (`MercThor`) ground attack: first shot ≤ ~0.1 s after the order, cadence
  feels fast (Period 1.0). Mission with a Jotun calldown.
- **[GAME] OPEN SUSPECT — the AA weapon `JavelinMissileLaunchers` `Period` (3.0 s) is NOT
  capped** by the rule-7 pass (the pass only touches `DamagePoint`). If the owner's "windup"
  complaint is about the *anti-air missile cadence*, that's a separate `Period` edit on
  `JavelinMissileLaunchers` (and `OdinAntiAir`), not covered today (open-issues Bug 4b;
  implementation-patterns §6 "Open uncertainty").
