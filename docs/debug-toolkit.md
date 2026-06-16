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

## SC2 client-API self-verification (`scripts/verify_api.py`)

A second, *automated* runtime probe alongside the in-game diag line. It drives the s2client-proto websocket, loads one of our **built campaign maps** (so the trigger lib runs), spawns/reads player-1 units, and asserts the data-level values the mod should produce — no human needed for the read-out (once the owner's instance is up — see attach setup below).

```sh
# one-time setup (venv is gitignored; only the script is tracked)
python3 -m venv tools/sc2api/.venv
tools/sc2api/.venv/bin/pip install s2clientprotocol websocket-client 'protobuf<3.21'
```

### Live unit reads are BLOCKED on retail (both spawn AND `--attach`)

**Confirmed — sourced research + empirical (do not re-chase this).** `RequestJoinGame` is a hard Blizzard license/mode gate on the retail 5.x binary that NO local setup bypasses: not spawn mode, not `--attach` to a Battle.net-PLAY-launched `-sso` instance (it fails identically, status=`launched`), not reaching the main menu, not `Play Offline`, not timing. The only API binary that allows live reads is the **Linux headless 4.10** (offline; Blizzard never shipped a 5.x equivalent). So `health_max`/`armor`/`cargo` live reads are **not achievable on this macOS retail install**. What still works: `RequestPing` + `RequestCreateGame` (the campaign map LOADS, mod deps resolve) — a useful "the mod loads via the engine" sanity check, nothing more. **Verification reverts to static analysis (`audit.py` + the merge simulator + `implementation-patterns.md`) + the owner's in-game playtest.** `--attach`/`verify_api.py` are kept only for that sanity check, and as a base if a Linux-4.10 headless setup is ever pursued on the Ubuntu box (caveat: 4.10 ≠ 5.0.15, may verify the wrong data).

### (Historical) attach setup — only loads the map; cannot read units

**One-time owner setup (do this once):** in the **Battle.net app** → StarCraft II → the **gear/Settings** next to PLAY → **"Additional command line arguments"**, set exactly:

```
-listen 127.0.0.1 -port 8765 -displaymode 0
```

Then click the Battle.net **PLAY** button and let SC2 reach the main menu. That instance is now **both** license-authenticated **and** API-listening on `127.0.0.1:8765`. Then run:

```sh
# attach to the owner's BNet-launched instance (MUST use the venv python — protos import only under protobuf<3.21)
tools/sc2api/.venv/bin/python scripts/verify_api.py --attach --port 8765 -v
```

`--attach` does **not** launch SC2 and **never kills it** (implies `--keep-open`; on exit it only closes our websocket — the owner's instance keeps running). If nothing is listening on the port it prints the Battle.net-arg setup guide and exits **2**. If the attached instance is already in a game, it surfaces the live `in_game` status and proceeds to Observation rather than crashing.

**What it CAN verify (data-level, machine-checkable):** `health_max`, `shield_max`, `energy_max`, per-unit `armor`/`cargo_size` (from `RequestData`), live `cargo_space_max` (bunker load cap), and the **available-ability list** per unit (`RequestQueryAvailableAbilities`). Its linchpin output is the **merc/hero-vs-base side-by-side table** (`MERC_PAIRS`/`HERO_PAIRS`): spawn `Thor` and `MercThor` (Jotun) together and compare — this empirically answers "do our per-player edits reach MERC/HERO unit types, or only the base id?". All observed unit data is written to the gitignored `tools/sc2api/observed_units.json` for analysis.

**What it CANNOT verify (render/UI-only — still the owner's eyes in game):** portraits, inspect-panel icons & armor signs, tooltips, button faces, displayed damage/upgrade numbers, visual cloak/animations. It reads the *merged per-player catalog* the engine computes, not the UI that renders it.

### Why spawn mode is blocked (kept for diagnostics only)

Default (no `--attach`) spawn mode launches its own headless SC2 with `-listen`/`-port`. It is mechanically complete — SC2 binds the websocket (~11 s), `RequestPing` succeeds, and `RequestCreateGame` on `Campaign/traynor01.SC2Map` reaches `init_game` (a control test with a bogus path returns `InvalidMapPath`, proving our campaign map genuinely **LOADS** — mod deps resolve) — but `RequestJoinGame` is **permanently rejected**: `"Unable to validate game license. Please log in to Blizzard from the game or editor before proceeding."` Root cause (from the Battle.net log): an SC2 spawned directly with `-listen`/`-port` is seen by Battle.net as a *"Pre-existing game session detected without a pending launch"* — Battle.net does NOT hand it the per-session SSO/license token it only grants to instances **it** launches. `RequestData` (unit catalog) and `RequestObservation` are both also gated behind a successful join, so **everything downstream of JoinGame SKIPs** — not because the mod is wrong, but because of this Blizzard-side gate. The script detects this case and prints the attach-mode fix (`print_license_help`), exiting **2** (environment blocker, distinct from exit 1 = a real mod FAIL). The seed-the-session workarounds (launch-once, Play Offline) do **not** fix spawn mode — **and neither does `--attach`** to a BNet-launched instance: `RequestJoinGame` is a hard retail license gate with no local bypass (see the BLOCKED note above).
