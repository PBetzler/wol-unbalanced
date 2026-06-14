# Debug toolkit

How to diagnose WoL Unbalanced bugs. There is **no SC2 MCP / headless mode**, so we cannot drive or inspect the running game — *runtime* debugging is manual (the in-game diag line + the player observing). But the *structural* bug classes are caught statically before a build ships.

## Automatic (static) — run before every build

```sh
python3 scripts/galaxy_lint.py   # Galaxy compile sanity (braces, use-before-declare) — black-map bugs
python3 scripts/audit.py         # catalog/actor consistency (see below)
python3 scripts/build.py build   # patch maps + assemble
```

`audit.py` catches, with a pointed diagnosis, the classes that have actually bitten us:
- **CHECK1** — a `parent=` clone unit with no proper `CActorUnit` (missing `parent="GenericUnitBase"` / `unitName=`) → the v0.2.0 sphere-no-model bug.
- **CHECK2** — a `SummonMercenaries` calldown whose unit isn't defined / actored / `TechTreeUnitAllow`'d → a dead calldown.
- **INFO** — model/portrait/parent tokens that are base-CASC (not in our XML or the reference dump). These are the references we **cannot verify locally**; if a unit is a sphere or its portrait is a heart, the culprit is in this list.

## Runtime (manual) — the in-game diagnostic

The lib prints subtitle lines ~1 s and ~10 s into every mission ([LibWoLUnbalanced.galaxy](../src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy) `libWoLU_OnGrantTech`). Healthy:
- canary: `WoL Unbalanced: data applied, upgrades & mercs granted.`
- `WoLU diag: clone=5 fx=WoLUStimSet flag=1 m3=StimpackWoLU t1=ThorsHammer`
- `WoLU diag2: acount=5 m4=MagrailWoLU bcount=<N>`

Absent canary ⇒ the lib didn't run (dependency/MapScript injection) or a black-map Galaxy compile failure. `acount=4`/empty `m4` ⇒ static-XML array appends are being dropped. To extend the diag, add a `UIDisplayMessage(... CatalogFieldValueGet(...))` line — it's our only window into the live merged catalog.

## Symptom → diagnosis → fix

**Unit renders as a sphere / no model / no attack animation.** The `CActorUnit` is missing or malformed. A real unit actor is `<CActorUnit id="X" parent="GenericUnitBase" unitName="X"><Model value="<base>"/>…`. `audit.py` CHECK1 catches it.

**A per-player `CatalogFieldValueModify` edit doesn't reflect in-game.** (a) Confirm the generated lib actually emits it: `grep <field> src/mod/Base.SC2Data/LibWoLUnbalancedGen.galaxy`. (b) Some fields aren't runtime-editable for the consuming system even though the call succeeds — e.g. bunker `CargoSize` read at load. (c) The field path may be wrong (`AttributeBonus[Light]` etc.) — verify the structure against the reference catalog with `scripts/xmlq.py`. (d) Runtime LINK edits (`AbilArray[i].Link`, `WeaponArray[i].Link`, `LayoutButtons[j].AbilCmd`) are silent no-ops — only scalar/stat fields apply per player; structural changes go through static-XML clones gated by `WoLUnbalancedFlag`.

**A new card button / appended ability doesn't appear.** Static-XML array appends to an EXISTING entry are dropped unless they carry an **explicit `index=`** (verified in game). Also: a button whose `AbilCmd` references an ability not on the unit auto-hides (this is how we hot-swap morphs).

**A merc/unit isn't available even though "purchased".** The calldown BUTTON and the UNIT are gated separately. `SetMercStatus(Purchased)` + `ApplyMercenaryTech` only allow the button; the unit needs `TechTreeUnitAllow(p, "<unit>", true)` **directly**. Do NOT enable the merc tech-*subgroup* — it maps to the counterpart unit and leaks Marauder/Firebat/Factory/etc. (the v0.2.1 regression).

**A cloned unit shows the parent's name/portrait.** Open issue — `parent=` clones don't pick up `Unit/Name/<id>` / `PortraitModel` the way base units do. Tracked in [open-issues.md](open-issues.md).

**An area/splash effect hits your own units.** Cloned/added area effects friendly-fire by default — set explicit `SearchFilters` (Crucio pattern: `Ground;Self,Player,Ally,Neutral,Missile,…`).

**Black map, no error message.** Galaxy compile failure (single-pass: forward-declare before use). `galaxy_lint.py` before every build, no exceptions.

## When you can't repro locally
Add a targeted `diag` subtitle line reporting the exact field value (`CatalogFieldValueGet`), build, install, and have the owner read it back from the mission. That round-trip is the substitute for runtime inspection.
