# 15 — Friendly-fire safety (a new/cloned area effect that won't hit your own units)

> Any new or cloned area-damage effect hits **your own units** by default. The one line that fixes
> it — and the plane token that decides air vs ground vs both.

**Maps to (request):** the Hard Rule "cloned/added area-damage effects friendly-fire by default —
always set explicit `SearchFilters` (Crucio pattern)" (`CLAUDE.md`). Cross-refs
[implementation-patterns.md §10](../implementation-patterns.md), learnings §"Cloned/added
area-damage effects friendly-fire". **Status:** [STATIC] done across all our area clones · [GAME]
parked (owner confirms no self-damage).

---

## Result
The player's splash/AoE damage hits **only enemies** — never your own, allied, neutral, or
in-transit units. Without this, every recipe that adds splash ([14](14-enlarge-splash.md)) or a new
area effect would nuke your own army.

## Mechanism
A `CEffectDamage` with `Kind=Splash`/`AreaArray`, or any area-search effect (`CEffectEnumArea`),
searches **all** units in radius unless you constrain it. `SearchFilters` is the constraint, in the
form:
```
<plane>;<excluded flags, comma-separated>
```
- **`<plane>`** = `Ground` (only ground units), `Air` (only air), or `-` (both planes).
- The flag list **excludes** those categories from the search. The project's standard enemy-only
  set is the campaign's **Crucio pattern**:
  `Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable` — i.e. exclude yourself, your
  player's units, allies, neutrals, missiles, and the various non-targetable states, leaving only
  enemies.

This is a **string field on the effect**, set in static XML inside the clone. (It is *not* a
per-player runtime edit — `SearchFilters` is a string and per-player string edits are no-ops anyway
[02](02-no-op-traps.md); but here it lives in the clone definition, which is the right place.)
Pick the plane to match the weapon: a ground weapon's splash → `Ground`; an AA weapon's splash →
`Air`; an EMP-style effect that should hit everything → `-`.

## Worked example (real, from this repo)
Every area clone we ship sets the Crucio filter. The plane token differs by weapon role:

```xml
<!-- Thor GROUND splash → plane "Ground"  (src/mod/Base.SC2Data/GameData/EffectData.xml:56) -->
<SearchFilters value="Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>

<!-- Thor AA splash → plane "Air"          (EffectData.xml:93) -->
<SearchFilters value="Air;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>

<!-- Viking ground (TwinGatlingCannonsWoLU) splash → plane "Ground" (EffectData.xml:114) -->
<SearchFilters value="Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>

<!-- Science Vessel EMP Shockwave → plane "-" (hits air AND ground, like BW EMP) (EffectData.xml:181) -->
<SearchFilters value="-;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
```

Why each plane:
- **`ThorsHammerDamageWoLU` `Ground;...`** — the ground cannon splash should not reach friendly
  ground units. Air units are irrelevant to a ground weapon, but the plane also stops it bleeding
  onto allied air via the search. (`EffectData.xml:50-59`.)
- **`JavelinMissileLaunchersDamageBuffedWoLU` `Air;...`** — the AA rocket splash should not catch
  your own air units (Banshees/Vikings hovering nearby). (`EffectData.xml:89-95`.)
- **`TwinGatlingCannonsWoLU` `Ground;...`** — Viking assault-mode ground splash, same as the Thor.
  (`EffectData.xml:110-117`.)
- **`EMPShockwaveSearchWoLU` `-;...`** — BW EMP drained both planes; here the `-` plane plus the
  exclude list means it drains enemy energy/shields on air *and* ground, but **never your own**
  (the vanilla `EMPSearch` filter `-;Hidden,Invulnerable` would have drained your own energy —
  the whole reason this clone exists, see `EffectData.xml:165-182`). (`EffectData.xml:175-182`.)

### Reach note
These filters live on the effect ids the player's weapons fire. Because they're inside the
buffed/cloned effect (gated to the flagged player or on a player-exclusive merc), the enemy
**vanilla** branch is untouched — enemy splash keeps its own (vanilla) targeting. Mercs/heroes that
inherit the shared effect ids inherit the safe filter too.

## Reusable snippet (swap the plane + ids)
```xml
<!-- RESOLVE FIRST: nothing to resolve — this is a fixed string. Pick the plane.
     Put it on EVERY new/cloned CEffectDamage with AreaArray/Kind=Splash, and every CEffectEnumArea. -->
<SearchFilters value="<Ground|Air|->;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable"/>
```
- Ground weapon splash → `Ground`. AA weapon splash → `Air`. Hits-both (EMP-like) → `-`.
- Keep the exclude list verbatim — it's the proven enemy-only set. Dropping `Self`/`Player`/`Ally`
  re-enables friendly fire.

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **No `SearchFilters` = friendly fire by default.** This is the single easiest area-effect bug to
  ship — the default search includes your own units. Always add it when you add splash or an area
  effect.
- **Wrong plane** — `Ground` on an AA effect (or vice-versa) silently narrows the search to the
  wrong plane and the splash may seem to "miss". Match the plane to the weapon's target type, or
  use `-` for both.
- **A per-player edit can't add this** — `SearchFilters` is a string; per-player string edits are
  no-ops ([02](02-no-op-traps.md)). It must be a literal in the (static) clone.
- **Don't confuse with the weapon's `TargetFilters`** — `TargetFilters` is *acquisition* (what the
  weapon will aim at); `SearchFilters` is the *area search* (who the blast hits once it lands). You
  need the latter for friendly-fire safety.

## Verify
- **Static:** `python scripts/audit.py` — CHECK3/CHECK4 confirm the effect/clone resolves. The
  audit does **not** assert a `SearchFilters` is present (it can't know an effect *should* be
  enemy-only) — this is a **manual discipline** to apply on every area clone. `[STATIC]` for "the
  filter string is well-formed and on the effect."
- **In-game (Test Document / owner):** fire the splash near your own units; confirm **zero**
  self-damage (HP unchanged) while enemies in radius take damage. Mission: any with the unit.
  `[GAME]` — parked.
- **Editor (Previewer):** cannot render area damage; n/a.

## Parked for bunch-verify
- `[GAME]` — Thor ground splash, Thor AA splash, Viking ground splash, and SV EMP Shockwave each
  damage/drain enemies in radius but cause **no** self/ally damage (place own units inside the blast
  and confirm HP/energy unchanged).
</content>
