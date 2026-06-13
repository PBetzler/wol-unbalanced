# Engineering learnings — SC2 WoL campaign modding

Hard-won, non-obvious facts this project had to discover the hard way. Read before
touching the matching area; **contribute back** when you re-derive something new
(also save it to engram — see CLAUDE.md §Session Memory). Each entry leads with the
gotcha; authoritative details live in the code/plan, not here.

## Maps are the only injection point

- The campaign UI prefers loose `Maps/Campaign/<name>.SC2Map` files over CASC — that's
  the entire mechanism. Loose-file shadowing of `Mods/Liberty.SC2Mod` does NOT work
  (tested: CASC wins over the legacy `file:` fallback), and extension mods don't apply
  to campaign.
- Every map needs THREE patches (all in `scripts/build.py`): the `DocumentInfo`
  dependency line, the **same dependency list duplicated in the binary
  `DocumentHeader`** (u32 count + null-terminated strings after the first `bnet:`
  byte sequence — missing this gives "map references content that no longer exists"),
  and a `MapScript.galaxy` include+init injection for the trigger library.
- Component-**folder** `.SC2Mod` directories work fine (no MPQ packing needed for the
  mod); maps are MPQs — patch them with StormLib (`tools/mpqpatch.c`).
- Map line endings vary per map (CRLF vs LF) — patchers must detect, not assume.

## Per-player isolation (rule 9) and the clone architecture

- `CatalogFieldValueModify(catalog, entry, field, player, value, op)` applies a change
  for ONE player — the backbone of "buff us, not them". But it can only **edit
  existing fields**; creating array entries (`AbilArray`, `LayoutButtons`,
  `AreaArray`, `EffectArray`) is a **silent no-op**.
- Behavior-class abilities (`CAbilBehavior` — cloaks; **not** stim, which is
  `CAbilEffectInstant` even in vanilla) **cannot autocast at all**; no Blizzard data
  does it. Autocast needs effect-style abilities (`CAbilEffectInstant`/`Target`).
- **Never hand-guess ability/effect schemas — copy a working Blizzard chain
  verbatim** and adapt ids (cost: two sessions). The killers found by diffing against
  NCO's Super Stimpack (`mods/novastoryassets.sc2mod` in the SC2GameData dump):
  `<Effect value=.../>` without `index="0"` on `CAbilEffectInstant` silently leaves
  the ability with **no effect** (manual cast does nothing); `AutoCast`/`AutoCastOn`
  are **ability-level** `<Flags>`, not `CmdButtonArray` flags; effect chains use
  `Value="Source"` (not Caster) and the attribute form
  (`<VitalArray index="Life" Change="30"/>`).
- Therefore: **clone architecture** — define `*WoLU` clones in static XML (arrays and
  autocast baked in) and wire them in by **XML index-overrides** of the vanilla slots
  (`<AbilArray index="3" Link="StimpackWoLU"/>`; indices verified against reference
  XML). Per-player runtime LINK edits (`AbilArray[i].Link`, `WeaponArray[i].Link`,
  `LayoutButtons[j].AbilCmd` via `CatalogFieldValueModify`) are **silent no-ops** —
  only scalar stat-like fields apply per player.
- **Append, don't override, abilities that enemies actively use** (Snipe, Obliterate):
  replacing the AbilArray slot would lock the requirement-gated clone for AI too and
  change enemy behavior. Append the clone as a NEW ability slot and index-override
  only the card BUTTON's `AbilCmd` — cards are pure UI, the AI never reads them.
  (Override-in-place is fine only when the vanilla ability was requirement-gated and
  never granted to AI — the stim case.)
- **Appends MUST carry an explicit index** — `<AbilArray Link="X"/>` and
  `<LayoutButtons Face="X" .../>` WITHOUT an index are silently dropped in our
  dependency mod (confirmed in game: Magrail invisible until given `index="4"`; works
  after). Use the next free slot = the unit's vanilla element count (e.g. Marine has
  AbilArray 0-3 → Magrail at `index="4"`, LayoutButtons 0-5 → button at `index="6"`).
  Vanilla cards are contiguous, so count = next free index. (TA-style index-less
  appends may work in a fully editor-saved mod, but NOT in our hand-rolled component
  folder — don't trust them.)
- A `CAbilEffectTarget`/`CWeaponLegacy` with **no `Effect` element defaults the link
  to its own id** (vanilla `Obliterate` ability → `Obliterate` damage effect). Clones
  must set `Effect` explicitly or they point at a nonexistent `<clone-id>` effect.
- **Verify Blizzard ids letter-by-letter** — the Marine rifle is `GuassRifle`
  (Blizzard's typo). A runtime edit on a misspelled id is a silent no-op; our Marine
  +1 range was dead for a whole batch. Same for card cells: audit the unit's vanilla
  card before placing buttons (hero rows 2,0–2,3 are often fully occupied; a
  colliding button silently hides one of the two).
- XML index-overrides are GLOBAL, so the player gate lives inside the clone:
  **abilities** gate their button on the `WoLUHaveFlag` requirement (flag upgrade
  only our library grants); **weapons** fire without buttons, so the clone must stay
  stat-identical to vanilla and the buff lives in a player-gated effect branch — the
  campaign's Shaped Blast pattern: weapon → `CEffectSet` → sibling effects with
  `CValidatorPlayerRequirement` gates (HasFlag = buffed, NoFlag via `CRequirementNot`
  = vanilla). Per-player stat buffs (e.g. windup cap) go on the **clone id** at
  runtime — neither runtime edits on the vanilla id nor parent inheritance propagate
  to a clone after load.
- **Never clone unit types** — mission scripts check unit types ("all your Marines
  are dead", drop pods spawning `Marine`, …).
- Static XML is global. Safe there: pure definitions, and additions to
  player-exclusive units (heroes, mercs).
- Cloned/added **area-damage effects friendly-fire by default** — set explicit
  `SearchFilters` (campaign's Crucio pattern:
  `Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable`).

## Abilities, autocast, and targeting

- **`parent=` on a `CAbil*` clone** inherits the whole vanilla ability (cost, effect,
  range); override only the autocast block + the gated button. Cheapest way to add an
  autocast variant without re-specifying the effect chain (used by the BC kit:
  `YamatoWoLU parent="Yamato"`, etc.). Works for weapons too (`ThorsHammerWoLU`).
- **TargetSorts are catalog-definable** via `CTargetSortValidator` / `CTargetSortField`
  / `CTargetSortMarker` / `CTargetSortPriority` entries in `TargetSortData.xml` — NOT a
  fixed enum (the built-in `TS*` names are just the stock ones). So nuanced autocast
  priority IS expressible: `CTargetSortValidator` orders targets by a validator,
  `CTargetSortField` by any unit field. **Direction**: a plain `CTargetSortValidator`
  sorts passers LAST; add `<Descending value="1"/>` to put passers FIRST (confirmed
  from the RaynorRogue kit's `TSTrackedByBattlecruiser`, used un-descended to push
  already-attacked targets to the back for overkill avoidance). The `gada` component
  auto-discovers `TargetSortData.xml` — no ComponentList entry needed.
  (Smart-Snipe uses this: healer → lethal → tanky → nearest.)
- **Damage reduction** is a `CBehaviorBuff` with a `<DamageResponse ModifyFraction="0.5"
  ModifyMinimumDamage="1">` block (schema confirmed against the Moebius pack's
  `AdvancedShielding`; 0.5 = take half damage). `<Kind index="Ranged" value="1"/>`
  entries are meant to filter by damage kind, but the reference sets them all to 0 with
  no obvious effect — treat Kind-filtering as unverified and prefer halving all damage.
- `CValidatorUnitCompareField` reads any unit field (e.g. `LifeMax`); default WhichUnit
  is the validated/target unit. `CValidatorUnitCompareVital` reads current Life/Energy/
  Shields with an explicit `<WhichUnit Value="Target"/>`. Both compose under
  `CValidatorCombine` (Or/And) — the toolkit for autocast gates.
- **Attack-while-moving** is the weapon's `AllowedMovement` enum (`Slowing` default,
  `Moving` = fire on the move) — a vanilla field, no custom work.
- **Save compatibility**: a mod must ship per-section `.version` files
  (`DocumentInfo/GameData/GameText.version`, 44-byte format) with a monotonically
  increasing counter, or every content change invalidates existing saves. The editor
  maintains these automatically; a hand-rolled component folder must emit them
  (`scripts/build.py::write_version_files`). Old saves made before versioning was
  added stay broken — only forward compatibility is fixed.

## Galaxy script

- Galaxy is **single-pass** like C: use-before-definition is a compile error, and a
  MapScript compile failure kills every trigger → mission loads as a **black map with
  no error message** (campaign suppresses the script-error dialog).
  `scripts/galaxy_lint.py` (CI + local) catches brace and declaration-order bugs.
- Diagnostic canary: the subtitle line at ~1 s/10 s game time. Absent ⇒ library
  didn't run. Map-init messages are useless — intro cinematics swallow them.
- Our injected init registers before mission triggers, so anything depending on the
  mission's own setup (tech application) runs on timers (1 s + 10 s re-run).

## CampaignLib (libertystory) internals

- Missions apply story tech via `libCamp_gf_ApplyCampaignTech(player)`.
  `libCamp_gf_TS_BuyAllTech()` marks all 44 armory techs purchased, BUT
  `TS_UpdateTechStates()` reverts techs whose **tech group** (unit category) the
  story hasn't introduced — in a unit's own unlock mission nothing applies. Bypass:
  loop `libCamp_gv_tS_TechID[]` and grant rewards directly
  (`libCamp_gf_StoryTechAbilityCommand/StoryTechUpgrade` →
  `TechTreeAbilityAllow` / `libNtve_gf_SetUpgradeLevelForPlayer`).
- Mercs: `libCamp_gf_SetMercStatus(id, Purchased)`; Locked derives from the
  counterpart's tech group — skip Locked mercs and rule 3 gating is preserved.
- Lab research lives in `libCamp_gv_tSX_ResearchState[1..20]` as adjacent pairs
  (Raven/SV = 7/8, Predator/Hercules = 15/16); Ghost/Spectre are tech groups 20/21.
- Campaign upgrades already list **merc** units in their `EffectArray`s (e.g.
  `CombatShield` covers `WarPig`) but never heroes — extend via XML `CUpgrade`
  appends (`MarauderLifeBoost` = Kinetic Foam).
- State persists via ConversationState values and mission banks.

## Data sources

- [SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData): full dumps —
  `mods/liberty.sc2mod`, `campaigns/liberty.sc2campaign` (catalogs; campaign stats
  differ from wikis — Ghost is 150/150), `campaigns/libertystory.sc2campaign`
  (CampaignLib sources), `campaigns/liberty.sc2campaign/base.sc2maps` (vanilla map
  fallback), `mods/missionpacks/novacampaign.sc2mod` (Nova Covert Ops — origin of
  many Archipelago upgrade designs, e.g. healing stim), `mods/starcoop` (co-op).
- Hero ↔ base map: Raynor01/RaynorCommando/Raynor=Marine,
  TychusCommando/TychusChaingun=Firebat, Swann=Marauder, Stetmann=Medic, Nova=Ghost,
  Tosh=Spectre, Odin=Thor. Ready-made free-cloak behaviors exist:
  `PersonalCloakingFree`, `SpectreCloakingFree`.
- Merc calldown: `SummonMercenaries` `InfoArray[Train1..8]` with `Charge.CountMax/
  CountStart` and `Cooldown.TimeStart` (vanilla 300 = 5 min wait at mission start).
