# 10 — Control autocast target priority (TargetSort)

> Order an autocast's targets by a real priority — e.g. smart-Snipe picks **healers → lethal
> (clean-kill) → tanky → nearest**, instead of whatever's closest.

**Maps to (request):** unit-table Ghost Comment "Snipe … should auto cast" with the 4-tier intent
(1 healers, 2 just-under-threshold, 3 most HP+shields above, 4 the rest by remaining HP+shields);
BACKLOG "Smart-Snipe". **Status:** [STATIC] — the ordering is declaratively shipped and resolves;
the in-game *order* is [GAME] (declarative ≠ observed). implementation-patterns §10; learnings
§"Abilities, autocast, and targeting".

---

## Result
When the autocast fires, it doesn't pick the nearest valid target — it walks a priority list:
medics/medivacs first, then targets it can one-shot (no overkill waste), then the tankiest, then
nearest. Fewer wasted casts.

## Mechanism
`TargetSorts` are **catalog-definable**, not a fixed engine enum: `CTargetSortValidator`,
`CTargetSortField`, `CTargetSortMarker`, and `CTargetSortPriority` entries in `TargetSortData.xml`
each define an ordering, and an ability's `<TargetSorts><SortArray .../></TargetSorts>` lists them
in priority order. (This was unblocked by the RaynorRogue kit, which proved `CTargetSort*` are
catalog entries — the earlier "fixed 6-value enum" belief was wrong.)

The **direction** is the gotcha: a plain `CTargetSortValidator` sorts the validator's **passers
LAST**; add `<Descending value="1"/>` to put **passers FIRST**. So "prefer healers" =
a `CTargetSortValidator` on a "is-healer" validator **with `Descending=1`**. The `gada` component
auto-discovers `TargetSortData.xml` — no `ComponentList` entry needed. (learnings.md
§"Abilities, autocast, and targeting"; implementation-patterns §10.)

The RaynorRogue kit's `TSTrackedByBattlecruiser` is the **overkill-avoid idiom**: used
*un*-descended, it pushes already-targeted units to the **back**, so the BC spreads fire instead
of piling onto one target. Same primitive, opposite direction.

## Worked example (real, from this repo)

### The custom sorts (our two; the other two tiers are vanilla stock)
```xml
<!-- src/mod/Base.SC2Data/GameData/TargetSortData.xml:9-16 -->
<CTargetSortValidator id="TSWoLUSnipeHealer">
    <Validator value="WoLUTargetIsHealer"/>   <!-- Medic OR Medivac (CValidatorCombine) -->
    <Descending value="1"/>                    <!-- passers FIRST -->
</CTargetSortValidator>
<CTargetSortValidator id="TSWoLUSnipeLethal">
    <Validator value="WoLUSnipeLethal"/>       <!-- target Life <= 45 = clean kill -->
    <Descending value="1"/>
</CTargetSortValidator>
```
The "is-healer" validator is a judgment call (WoL enemy healers = Medic + Medivac; no engine
"healer" flag):
```xml
<!-- src/mod/Base.SC2Data/GameData/ValidatorData.xml:62-82 -->
<CValidatorUnitCompareVital id="WoLUSnipeLethal">
    <Compare value="LE"/> <Value value="45"/> <Vital value="Life"/> <WhichUnit Value="Target"/>
</CValidatorUnitCompareVital>
<CValidatorCombine id="WoLUTargetIsHealer">
    <Type value="Or"/>
    <CombineArray value="WoLUTargetIsMedic"/>   <!-- CValidatorUnitType Value="Medic" -->
    <CombineArray value="WoLUTargetIsMedivac"/> <!-- CValidatorUnitType Value="Medivac" -->
</CValidatorCombine>
```

### The priority list on the ability
```xml
<!-- src/mod/Base.SC2Data/GameData/AbilData.xml:93-98 (inside SnipeWoLU) -->
<TargetSorts RequestCount="1">
    <SortArray value="TSWoLUSnipeHealer"/>   <!-- 1) healers first       (custom) -->
    <SortArray value="TSWoLUSnipeLethal"/>   <!-- 2) clean kills (<=45)   (custom) -->
    <SortArray value="TSLifeLargestFirst"/>  <!-- 3) tankiest             (vanilla stock) -->
    <SortArray value="TSDistance"/>          <!-- 4) nearest              (vanilla stock) -->
</TargetSorts>
```
Honesty note: only the **first two** `TS*` ids are defined in our `TargetSortData.xml`; tiers 3–4
(`TSLifeLargestFirst`, `TSDistance`) are **vanilla stock sorts** referenced by id. The 4-tier
priority is real and shipped; the design intent for "HP+shields" is approximated by `LifeLargest`
+ the worthwhile-floor (`AutoCastValidatorArray="WoLUSnipeWorthwhile"`, AbilData.xml:92). The list
order in `<TargetSorts>` is the priority; earlier sorts dominate.

### Direction recap (the trap)
- **`Descending=1`** → validator passers FIRST (our healer/lethal tiers: prefer them).
- **No `Descending`** → validator passers LAST (the RaynorRogue overkill-avoid idiom: push
  already-attacked units to the back to spread fire).

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: confirm your validators exist (xmlq.py get <VALIDATOR> .../ValidatorData.xml)
     and that the stock TS* ids you reference are real (TSDistance, TSLifeLargestFirst, …). -->
<!-- TargetSortData.xml — one sort per tier you want to control: -->
<CTargetSortValidator id="TS<NAME>">
    <Validator value="<VALIDATOR>"/>
    <Descending value="1"/>   <!-- 1 = prefer passers; omit = de-prioritize passers (overkill-avoid) -->
</CTargetSortValidator>
<!-- on the ability, in PRIORITY ORDER (first dominates): -->
<TargetSorts RequestCount="1">
    <SortArray value="TS<NAME>"/>
    <SortArray value="<...next tier...>"/>
    <SortArray value="TSDistance"/>   <!-- final tiebreak: nearest -->
</TargetSorts>
```

## Gotchas / no-op traps → full list in [02](02-no-op-traps.md)
- **Direction is inverted by default** — a plain `CTargetSortValidator` sorts passers **last**.
  Forgetting `<Descending value="1"/>` puts your "preferred" tier at the **bottom**.
- **Order in `<TargetSorts>` is the priority** — earlier `SortArray` entries dominate; reordering
  changes behavior.
- **No "healer" engine flag** — "is a healer" must be expressed as a validator (unit-type Or, as
  here). It's a judgment call about which units count; document it.
- **Stock vs custom ids** — referencing a `TS*` id that isn't defined (ours or vanilla) is a
  silent miss. Confirm stock sort ids exist before citing them.
- **This sorts; it doesn't gate.** Use `AutoCastValidatorArray`/`AutoCastFilters` to *exclude*
  bad targets (e.g. the worthwhile floor); `TargetSorts` only *orders* the survivors.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3 (every `Validator=`/`SortArray=` id resolves).
  `galaxy_lint.py` n/a (pure data). **Does not prove** the engine applies the order at runtime.
  `[STATIC]`
- **In-game (owner / Test Document):** Ghost autocast Snipe into a mixed enemy group containing a
  Medic/Medivac + a near-dead unit — confirm it shoots the **healer/lethal** target before a
  full-HP one, and avoids overkill. Mission with enemy Medics (a mid-campaign Terran fight).
  `[GAME]` — the ordering is declaratively shipped; in-game order **unverified**.
- **Editor (Previewer):** n/a (priority is runtime behavior, not a render). `[GAME]` only.

## Parked for bunch-verify
- `[GAME]` — Ghost smart-Snipe autocast prioritizes Medic/Medivac, then clean-kill (≤45 HP)
  targets, then tankiest, then nearest, in a mixed enemy group; no overkill waste. (Declarative
  order is shipped; observe the actual firing order.)
