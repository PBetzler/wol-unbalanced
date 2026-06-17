# 12 — Simultaneous air + ground fire (a 2-weapon unit fires BOTH at once)

> A unit with two weapons (one AA, one AG) fires **both at the same time** instead of one at a
> time, by un-linking their shared cooldown.

**Maps to (request):** Jotun/Thor "should fire air and ground at once" — open-issues v0.3.7 #2
(`docs/open-issues.md:129` "Bug 4c — Jotun simultaneous air+ground fire", marked STATICALLY
SETTLED). Cross-refs [implementation-patterns.md §5](../implementation-patterns.md). **Status:**
[STATIC] done · [GAME] parked (owner confirms both weapons fire together).

---

## Result
A Thor (two weapons: `JavelinMissileLaunchers` AA + `ThorsHammer` AG) attacks an air target and
a ground target **in the same instant**, with each weapon on its own independent cooldown — not
taking turns. Same for the Odin (`OdinAntiAir` + `Odin`) and the Jotun (`MercThor`, which inherits
the Thor's weapons).

## Mechanism
A legacy weapon's firing discipline lives in its `Options[]` array. With **no `Options` block**,
`LinkedCooldown` **defaults to 1** → every weapon on the unit shares one cooldown clock, so only
one fires at a time. Independent fire is three `Options[]` entries on each weapon:

| Option | Value | Effect |
|---|---|---|
| `LinkedCooldown` | `0` | each weapon keeps its own cooldown (don't share) |
| `OnlyFireWhileInAttackOrder` | `0` | a weapon may fire without an explicit attack order |
| `OnlyFireAtAttackOrderTarget` | `0` | a weapon may pick its own target (not only the ordered one) |

This is the **Goliath Multi-Lock pattern**: the Goliath's `GoliathGUpgraded`/`GoliathAUpgraded`
weapons carry exactly these three flags (`mods/_reference/campaigns/liberty.sc2campaign/WeaponData.xml:757-759`
and `:767-769`). The `MultilockTargetingSystems` upgrade only *un-hides* those weapons — the
independent-fire behavior is baked into the weapon defs, not the upgrade.

**Why it can't be a per-player runtime edit:** `Options[]` is an **indexed array**. A per-player
`CatalogFieldValueModify` on an indexed-array element is a **silent no-op** (cross-ref
[02](02-no-op-traps.md), row "indexed array element"). So the flags MUST live in **static XML** —
which is **GLOBAL** (it reaches enemies too). Accepted tradeoff: enemy Thors also gain
simultaneous fire, but WoL has few/zero enemy Thors. Documented inline at
`src/mod/Base.SC2Data/GameData/WeaponData.xml:22-27`.

## Worked example (real, from this repo)
We add the three `Options[]` flags to **both Thor weapons** and **both Odin weapons**:

```xml
<!-- src/mod/Base.SC2Data/GameData/WeaponData.xml:11-50 -->
<CWeaponLegacy id="ThorsHammer">
    <Effect value="ThorsHammerWoLUSet"/>          <!-- splash redirect, recipe 14 -->
    <Options index="LinkedCooldown" value="0"/>
    <Options index="OnlyFireWhileInAttackOrder" value="0"/>
    <Options index="OnlyFireAtAttackOrderTarget" value="0"/>
</CWeaponLegacy>
<CWeaponLegacy id="JavelinMissileLaunchers">      <!-- Thor AA -->
    <Options index="LinkedCooldown" value="0"/>
    <Options index="OnlyFireWhileInAttackOrder" value="0"/>
    <Options index="OnlyFireAtAttackOrderTarget" value="0"/>
</CWeaponLegacy>
<CWeaponLegacy id="Odin">                          <!-- Odin AG (rule-10 parity) -->
    <Options index="LinkedCooldown" value="0"/>
    <Options index="OnlyFireWhileInAttackOrder" value="0"/>
    <Options index="OnlyFireAtAttackOrderTarget" value="0"/>
</CWeaponLegacy>
<CWeaponLegacy id="OdinAntiAir">                   <!-- Odin AA -->
    <Options index="LinkedCooldown" value="0"/>
    <Options index="OnlyFireWhileInAttackOrder" value="0"/>
    <Options index="OnlyFireAtAttackOrderTarget" value="0"/>
</CWeaponLegacy>
```

Why each line:
- We edit the **vanilla weapon ids** (`ThorsHammer`, `JavelinMissileLaunchers`), not a clone —
  the attack animation binds to `WeaponStart.ThorsHammer`, so cloning the weapon would lose the
  animation ([24](24-clone-visuals.md), learnings §"Don't clone a WEAPON"). Adding `Options[]` to
  the kept id is harmless to visuals.
- All three flags are needed: `LinkedCooldown=0` alone lets the cooldowns run independently, but
  `OnlyFire*` keep a weapon from waiting on the other's attack order/target — without them a
  Thor told to attack a ground unit may never engage the air unit it could also hit.
- Odin is edited separately because it's a distinct unit with distinct weapon ids
  (`Odin`/`OdinAntiAir`), not a `parent="Thor"` clone — per-id edits don't transfer (rule from
  [01 §reach](01-per-player-scalar-stat-edit.md)).

### Merc/hero reach
`MercThor` (the Jotun) is `parent="Thor"` with **no `WeaponArray` override**
(`src/mod/Base.SC2Data/GameData/UnitData.xml`, the `MercThor` block) → it inherits the same
`ThorsHammer`/`JavelinMissileLaunchers` weapon ids, so this **static** edit reaches it
automatically. Odin (hero) is covered by the explicit `Odin`/`OdinAntiAir` edits.
([implementation-patterns.md §5](../implementation-patterns.md), §0.1-B for the inheritance rule.)

## Reusable snippet (swap the ids)
```xml
<!-- RESOLVE FIRST: confirm <WEAPON_ID> is a real CWeaponLegacy id
     (python scripts/xmlq.py get <WEAPON_ID> mods/_reference/.../WeaponData.xml).
     Put this in static XML — Options[] per-player edits are no-ops.
     WARNING: static XML is GLOBAL — enemies using the same weapon id gain this too. -->
<CWeaponLegacy id="<WEAPON_ID>">
    <Options index="LinkedCooldown" value="0"/>
    <Options index="OnlyFireWhileInAttackOrder" value="0"/>
    <Options index="OnlyFireAtAttackOrderTarget" value="0"/>
</CWeaponLegacy>
```
Apply to **every** weapon the unit should fire independently (do both, or the un-flagged one still
ties up the shared clock).

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`Options[]` per-player edit = silent no-op** (indexed array). Static XML is the only path.
- **Static XML is global** — this reaches enemies sharing the weapon id. Acceptable only when few/
  no enemies use it (the Thor case); otherwise you cannot un-link cooldown per-player.
- **Flag only one weapon and it still won't work** — the un-flagged weapon keeps `LinkedCooldown=1`
  and re-couples the clock. Flag *both*.
- **Don't clone the weapon to scope this per-player** — you'd lose `WeaponStart.<id>` animations
  ([24](24-clone-visuals.md)) and gain nothing (the flags aren't player-isolable anyway).

## Verify
- **Static:** `python scripts/audit.py` (CHECK3 confirms the weapon ids resolve; the `Options`
  block is well-formed static XML). `galaxy_lint.py` unaffected (no galaxy change). **Does not
  prove** the unit visibly fires both weapons. `[STATIC]`
- **In-game (Test Document / owner):** put a Thor/Jotun/Odin between an air unit and a ground unit;
  confirm **both** weapons fire in the same window (AA missiles + ground cannon together), not
  alternating. Mission: any with a Thor available. `[GAME]` — parked.
- **Editor (Previewer):** cannot show firing discipline (runtime behavior) — Previewer is static
  render only. Not applicable.

## Parked for bunch-verify
- `[GAME]` — Spawn a Thor (and Jotun, and Odin) with both an air and a ground enemy in range;
  confirm both weapons fire simultaneously (independent cooldowns), not one-at-a-time.
</content>
</invoke>
