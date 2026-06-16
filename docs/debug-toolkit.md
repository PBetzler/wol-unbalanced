# Debug toolkit

How to diagnose WoL Unbalanced bugs. There is **no SC2 MCP / headless mode**, so we cannot drive or inspect the running game — *runtime* debugging is manual (the in-game diag line + the player observing). But the *structural* bug classes are caught statically before a build ships.

## Automatic (static) — run before every build

```sh
python3 scripts/galaxy_lint.py   # Galaxy compile sanity (braces, use-before-declare) — black-map bugs
python3 scripts/audit.py         # catalog/actor consistency (see below)
python3 scripts/build.py build   # patch maps + assemble
```

`audit.py` catches, with a pointed diagnosis, the classes that have actually bitten us. It is a
**FAIL gate** (non-zero exit) for the high-confidence classes and prints WARN/INFO for the rest:
- **CHECK1 (FAIL)** — a `parent=` clone unit with no proper `CActorUnit` (missing `parent="GenericUnitBase"` / `unitName=`) → the v0.2.0 sphere-no-model bug.
- **CHECK2 (FAIL)** — a `SummonMercenaries` calldown whose unit isn't defined / actored / `TechTreeUnitAllow`'d → a dead calldown.
- **CHECK3 (FAIL)** — a `parent=` on one of our data clones that resolves to **no real id** (ours or the reference catalogs). Catches invented/typo'd parents — e.g. the "Valkyrie"/"Liberator" models that don't exist in WoL. (Genuine core.sc2mod templates like `DU_WEAP` live in `CORE_TEMPLATE_PARENTS` — add deliberately, never blanket-skip.)
- **CHECK4 (FAIL)** — the clone-Effect trap: a `CAbilEffect*`/`CWeapon*` clone with **no `<Effect>` and no parent that supplies one** re-defaults to its own (nonexistent) id and silently does nothing (the `HealWoLU`/`YamatoWoLU` bug). Also fails on an explicit `<Effect value=>` that resolves nowhere.
- **CHECK5 (WARN)** — merge-aware command-card sanity on **our** buttons: an action `AbilCmd` on a `Type=Passive` button (never fires — the Marauder bug); an `AbilCmd` whose ability isn't on the unit's merged AbilArray (drives nothing); two of our buttons colliding in one cell. It simulates the base→campaign→story→our-mod array merge, so the reported indices/cells match in-game.
- **#3-class check (WARN)** — a `Type=Passive` decorative card whose Face implies a capability the unit lacks: a vehicle/ship-hull face (`ShapedHull`) on a non-vehicle/ship unit, a weapon-range face (`WoLUUpgLaserTargeting`) on a weaponless unit, or a `DefensiveMatrix` shield face used as a card at all (shields belong in the `ShieldArmorName` sign). Catches "Shaped Hull on a Medic" — the recurring elite-merc blanket-card bug.
- **CHECK6 (INFO)** — portrait cross-reference: each `PortraitModel` token we emit is checked against the reference dump; if a real vanilla actor references the same token as a `PortraitModel`, it's promoted to `portrait-ok` (valid base-CASC token), else it stays `portrait-UNVERIFIED` (still confirm in game — a heart means it didn't resolve).
- **CHECK7 (WARN)** — armor string-key resolution: every `ShieldArmorName`/`LifeArmorName` value we set must resolve to a real string key (`WoLU*` in our `enUS GameStrings.txt`; vanilla `Terran*` keys via the reference dump), or the inspect panel reads "unknown".
- **INFO** — base-CASC model/`.m3`/`.dds` references we **cannot verify locally**, printed as `UNVERIFIED — confirm in game` (portrait tokens are categorized separately by CHECK6). These are NOT proof of correctness: a fix that depends on one is "pending owner confirmation", never "done". If a unit is a sphere or its portrait is a heart, the culprit is here / in CHECK6.

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
