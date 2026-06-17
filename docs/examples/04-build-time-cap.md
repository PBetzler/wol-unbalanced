# 04 — Build-time cap ≤ 60 s + per-unit overrides (rule 5)

> No player unit takes longer than 60 s to build; specific units build even faster
> (Predator 10 s, Hercules 20 s, and a −25% "Optimized Logistics" batch).

**Maps to (request):** design rule 5 ("Build-time cap 60 s"); unit-table Predator /
Hercules / "Optimized Logistics" Comments. **Status:** [STATIC] proven (the field class is
the indexed-*scalar* `InfoArray[..].Time`, same as recipe [01](01-per-player-scalar-stat-edit.md));
[GAME] for the observed build bar.

---

## Result
The player's train queue shows a ≤ 60 s build time for every trainable unit, with the
overridden units faster still (a Predator pops in 10 s, a Hercules in 20 s). Enemy build
times are untouched (rule 9 — but enemies rarely "build" in WoL anyway).

## Mechanism
Build time is **not** a unit field — it lives on the **TRAIN ability**, in that ability's
`InfoArray[Train<n>].Time` entry (one entry per trainable unit). `InfoArray[..].Time` is an
**indexed *scalar*** (a single number addressed by an array index), which is the *one* kind
of indexed field that `CatalogFieldValueModify` **can** edit per player — exactly the same
class as `CostResource[Vespene]` and `EngineeringBayResearch` research times. (Contrast the
no-op indexed-*array*-element edits like `Options[]` — recipe [02](02-no-op-traps.md).)

So the cap is a per-player `Set` on each over-budget `InfoArray[Train<n>].Time`. We do **not**
touch any unit field — there is no per-unit "build time" to edit; the cost-to-build clock is a
property of the producer's train ability. (Cross-ref [implementation-patterns.md §1](../implementation-patterns.md)
"indexed scalar fields … work".)

## Worked example (real, from this repo)

### The cap + override config
```python
# scripts/genlib.py:36-45
BUILD_TIME_CAP = 60.0
BUILD_TIME_OVERRIDES = {
    "Predator": 10.0,
    "Hercules": 20.0,
    # AP "Optimized Logistics" (faster training; AP gives no exact number — we use
    # -25%, documented assumption) for the units whose table row includes it.
    "Marine": 19.0,    # 25 * 0.75
    "Hellion": 22.0,   # 30 * 0.75 (rounded)
    "Goliath": 30.0,   # 40 * 0.75
}
```

### The emit loop (walks every train entry, overrides win, else cap)
```python
# scripts/genlib.py:168-174
lines.append("    // --- Rule 5: build time cap 60 s (+ explicit overrides) ---")
for (aid, idx), (unit, time) in sorted(train_entries().items()):
    target = BUILD_TIME_OVERRIDES.get(unit)
    if target is None and time is not None and time > BUILD_TIME_CAP:
        target = BUILD_TIME_CAP
    if target is not None and time != target:
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "{aid}", "InfoArray[{idx}].Time", p, "{target}", c_upgradeOperationSet);  // {unit}, was {time}')
```
Why each line is there:
- `train_entries()` (`genlib.py:90-108`) discovers **every** `CAbilTrain` `InfoArray` entry
  across the catalogs (later catalogs win), yielding `(abil id, index) -> (unit, time)`. This
  auto-finds new trainables — no hand list to keep in sync.
- **Override beats cap:** if the unit is in `BUILD_TIME_OVERRIDES`, that exact time wins;
  otherwise, only times **over 60 s** are pulled down to 60. Units already ≤ 60 with no
  override are left alone (the `time != target` guard avoids redundant lines).
- It edits **`c_gameCatalogAbil` … `InfoArray[<idx>].Time`** — the *ability's* indexed scalar,
  the working lever. Editing a unit field would do nothing (there isn't one).

### The real ids it resolves to (verified ground truth)
- **Predator** = `FactoryTrain` `InfoArray[Train10]`, vanilla `Time=40`
  (`libertystory.sc2campaign/AbilData.xml:227-229`) → overridden to **10**.
- **Hercules** = `StarportTrain` `InfoArray[Train6]`, vanilla `Time=70`
  (`libertystory.sc2campaign/AbilData.xml:232-235`) → vanilla 70 > 60 *and* override 20 ⇒
  the override **20** wins.
So the generated lines are e.g.
`CatalogFieldValueModify(c_gameCatalogAbil, "FactoryTrain", "InfoArray[Train10].Time", p, "10.0", c_upgradeOperationSet);  // Predator, was 40.0`.

### Merc/hero reach
Build time is a property of the **producer's train ability**, not the unit — heroes and mercs
arrive via **calldowns** (`SummonMercenaries`, recipe [19](19-unlock-units-merc-calldowns.md)),
not the train queue, so build-time parity is a non-issue for them. The cap only matters for
units the player actually trains from a structure.

## Reusable snippet (swap the ids)
```python
# A: rely on the generic cap — nothing to write; any new trainable > 60 s is auto-capped
#    by the emit loop (it discovers all CAbilTrain InfoArray entries).
# B: a specific faster build time — add the UNIT to BUILD_TIME_OVERRIDES:
BUILD_TIME_OVERRIDES = { ..., "<UNIT_ID>": <seconds>.0 }
# RESOLVE FIRST: find the train abil + index that produces <UNIT_ID>:
#   python scripts/xmlq.py refs <UNIT_ID> mods/_reference/campaigns/libertystory.sc2campaign/AbilData.xml
#   → confirms which CAbilTrain InfoArray[Train<n>] has <Unit value="<UNIT_ID>"/> and its base Time.
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **There is no unit "build time" field.** Editing the unit does nothing; the time is on the
  *train ability's* `InfoArray[Train<n>].Time`. Get the keying wrong (wrong abil id or wrong
  `Train<n>` index) and it's a silent miss.
- **`InfoArray[..].Time` is an indexed SCALAR (works); `InfoArray[..].Button.Requirements` is an
  indexed LINK (no-op).** Same array, opposite reachability — see the failed Hercules/Marauder
  "drop the prerequisite" attempts (`genlib.py:290-292`, recipe [02](02-no-op-traps.md)).
- **A unit produced by *two* abilities** (e.g. a normal + a tech-lab variant) needs both
  `InfoArray` entries hit — `train_entries()` enumerates all of them, so the cap covers each,
  but a hand override keyed only by unit name relies on the loop matching every producer.
- **The −25% "Optimized Logistics" numbers are an [ASSUMPTION]** (AP gives no exact value;
  documented in the config comment). Flagged, not a fact.

## Verify
- **Static:** `python scripts/audit.py` (CHECK3) confirms the train abil ids resolve;
  `galaxy_lint.py` confirms the emitted lines compile. Grep the generated
  `LibWoLUnbalancedGen.galaxy` rule-5 block for the `FactoryTrain … Train10 … "10.0"` and
  `StarportTrain … Train6 … "20.0"` lines. **Does not prove** the build bar shows the new time.
  `[STATIC]`
- **In-game (Test Document / owner):** queue a Predator (bar ≈ 10 s), a Hercules (≈ 20 s), and
  any vanilla > 60 s unit (capped to 60). `[GAME]`

## Parked for bunch-verify
- **[GAME]** Train a Predator (Factory) — build bar ≈ 10 s. Mission with Factory access.
- **[GAME]** Train a Hercules (Starport) — build bar ≈ 20 s. Mission with Starport access.
- **[GAME]** Confirm the −25% Optimized-Logistics units (Marine 19 / Hellion 22 / Goliath 30)
  read those times — and adjust if the owner pins down AP's real Optimized-Logistics value
  ([ASSUMPTION] today).
