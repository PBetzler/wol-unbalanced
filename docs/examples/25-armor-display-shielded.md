# 25 — Armor/defense display on a shielded clone

> Show **both** the life-armor sign *and* the shield (Defensive Matrix) sign on a unit that has
> both — and make each resolve to real text, not "unknown".

**Maps to (request):** the elite-merc shields ("each merc keeps its % advantage" + a Defensive
Matrix shield) — open-issues **Bug 3** ("shielded units need the normal armor shown too") and
**#8** ("heart portrait + 'unknown' shield"). **Status:** [STATIC] done — both keys set + resolve
(CHECK7-clean) · the *dual-indicator render* is [GAME]/[EDITOR] (see Verify).

---

## Result
On a shielded elite merc (Skibi's Angels, Winged Nightmares, the Jotun, …) the inspect panel
shows **two** defense signs: the normal **life-armor** indicator **and** the **Defensive Matrix**
shield indicator — each with real text, not the literal word "unknown".

## Mechanism
**Two separate string-KEY fields, both required:**
- `LifeArmorName` = the normal life-armor sign.
- `ShieldArmorName` = the shield (Defensive Matrix) sign.

Each value must be a **string-table KEY** (e.g. `Unit/ShieldArmorName/WoLUDefensiveMatrix`), **not
a literal** — a raw string like `"Defensive Matrix"` renders as **"unknown"** in the panel. Terran
units have **no vanilla shields**, so an added-shield clone must supply `ShieldArmorName` itself
(and its GameStrings key).

The non-obvious half: **a `parent=` clone does NOT reliably surface the base unit's
`LifeArmorName`** either. So you must set `LifeArmorName` **explicitly** on the clone, equal to the
base unit's vanilla value (`TerranInfantryArmor` for infantry, `TerranVehiclePlating` for
vehicles, `TerranShipPlating` for ships) — otherwise the *normal* life-armor sign can read
"unknown" on the shielded clone even though the shield sign is fine. (learnings.md §"`ShieldArmorName`
… must be a string-table KEY"; [implementation-patterns.md §8](../implementation-patterns.md).)

## Worked example (real, from this repo)
Every elite merc (a `parent=<base unit>` clone) sets **both** keys. The full merc section is
`UnitData.xml:498-618`; here are MercMedic (infantry) and MercThor (vehicle):
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:498,507-508  (MercMedic = Skibi's Angels) -->
<CUnit id="MercMedic" parent="Medic">
    ...
    <ShieldArmorName value="Unit/ShieldArmorName/WoLUDefensiveMatrix"/>   <!-- :507  shield sign -->
    <LifeArmorName   value="Unit/LifeArmorName/TerranInfantryArmor"/>     <!-- :508  normal armor sign, explicit -->
```
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:538,547-548  (MercThor = the Jotun) -->
<CUnit id="MercThor" parent="Thor">
    ...
    <ShieldArmorName value="Unit/ShieldArmorName/WoLUDefensiveMatrix"/>   <!-- :547 -->
    <LifeArmorName   value="Unit/LifeArmorName/TerranVehiclePlating"/>    <!-- :548  vehicle, not infantry -->
```
The full set (verified against the clones' attribute classes):

| Merc (id) | `parent=` | `LifeArmorName` key | `ShieldArmorName` key | lines |
|---|---|---|---|---|
| MercMedic | Medic | `TerranInfantryArmor` | `WoLUDefensiveMatrix` | 498 / 507-508 |
| MercReaper | Reaper | `TerranInfantryArmor` | `WoLUDefensiveMatrix` | 510 / 519-520 |
| MercHellion | Hellion | `TerranVehiclePlating` | `WoLUDefensiveMatrix` | 522 / 531-532 |
| MercThor | Thor | `TerranVehiclePlating` | `WoLUDefensiveMatrix` | 538 / 547-548 |
| MercWraith | Wraith | `TerranShipPlating` | `WoLUDefensiveMatrix` | 586 / 595-596 |
| MercSeniorGhost | Ghost | `TerranInfantryArmor` | `WoLUDefensiveMatrix` | 608 / 615-616 |

Note the `LifeArmorName` **matches the attribute class** of the base unit: infantry mercs →
`TerranInfantryArmor`, vehicle mercs → `TerranVehiclePlating`, the ship merc → `TerranShipPlating`.
A mismatch (e.g. an Infantry key on a vehicle) can hide the sign.

### The key definition (the shield key must exist in OUR GameStrings)
```text
# src/mod/enUS.SC2Data/LocalizedData/GameStrings.txt:54
Unit/ShieldArmorName/WoLUDefensiveMatrix=Defensive Matrix
```
This is the **only** armor key we define — because Terran has no vanilla shield key, we author the
shield one. The vanilla `LifeArmorName` keys (`Unit/LifeArmorName/Terran*`) are **not** in our
GameStrings; they resolve through the base-game CASC string table at runtime (the engine's vanilla
mod chain). `audit.py` CHECK7 treats a vanilla `Terran*` key as valid because the same key string
appears as an armor-name attribute on units in the reference dump
(`mods/_reference/mods/liberty.sc2mod/UnitData.xml`).

### Merc/hero reach
These are set on each merc's **own** `Merc*` unit id (player-exclusive static XML — safe, the id
never appears in a WoL map). Base units already have a vanilla `LifeArmorName`; shields are
merc-only, so base units need no `ShieldArmorName`. [STATIC]

## Reusable snippet (swap the ids)
```xml
<!-- A shielded clone: set BOTH keys. RESOLVE the LifeArmorName to the BASE unit's vanilla value
     for its attribute class (TerranInfantryArmor | TerranVehiclePlating | TerranShipPlating). -->
<CUnit id="<MyShieldedClone>" parent="<BaseUnit>">
    <ShieldArmorName value="Unit/ShieldArmorName/<MyShieldKey>"/>   <!-- define this key in GameStrings -->
    <LifeArmorName   value="Unit/LifeArmorName/Terran<Infantry|Vehicle|Ship>..."/>  <!-- explicit -->
</CUnit>
```
```text
# src/mod/enUS.SC2Data/LocalizedData/GameStrings.txt — add the shield key (WoLU-prefixed)
Unit/ShieldArmorName/<MyShieldKey>=<Display Text>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **A literal value shows "unknown".** `ShieldArmorName="Defensive Matrix"` is wrong — it must be a
  KEY (`Unit/ShieldArmorName/WoLUDefensiveMatrix`) that exists in a string table.
- **`parent=` does NOT carry `LifeArmorName` reliably** → set it explicitly on the clone, or the
  *normal* armor sign may read "unknown" even with a good shield sign.
- **Class mismatch hides the sign.** Use the key that matches the unit's attribute class (Infantry
  / Vehicle / Ship) — an infantry key on a vehicle can suppress the indicator.
- **A WoLU-prefixed key must live in OUR GameStrings**; CHECK7 only validates a `WoLU*` key against
  `enUS.SC2Data/LocalizedData/GameStrings.txt`. Vanilla `Terran*` keys validate against the
  reference dump.

## Verify
- **Static:** `python scripts/audit.py` — **CHECK7** (`audit.py:421-460`, WARN) verifies every
  `ShieldArmorName`/`LifeArmorName` value we set **resolves** (WoLU keys in our GameStrings;
  `Terran*` keys via the reference dump). It proves there's **no "unknown" text** — it does **not**
  prove the engine draws **both** indicators side by side (that's UI/preload behavior). `[STATIC]`
- **Editor (Previewer):** select the merc → the inspect/armor display; confirm the shield sign
  resolves to "Defensive Matrix" (not "unknown") and the life-armor sign shows. `[EDITOR]` — add
  to queue.
- **In-game (Test Document / owner):** spawn the merc, open its inspect panel; confirm **both** the
  life-armor indicator **and** the Defensive Matrix shield indicator appear together (the dual-
  indicator render is the piece static can't prove). Mission: any with a Merc Compound + the
  merc's counterpart unlocked. `[GAME]` — add to queue.

## Parked for bunch-verify
- `[EDITOR]` — Each shielded merc's armor signs resolve to text (shield = "Defensive Matrix", not
  "unknown"; life-armor present).
- `[GAME]` — Inspect panel renders **both** the life-armor and the Defensive Matrix indicators
  side by side (open-issues Bug 3 / #8). (The heart-portrait piece is a separate [EDITOR]/[GAME]
  item — see [18](18-elite-merc-clone.md) / CHECK6.)
