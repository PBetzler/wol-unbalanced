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
- Behavior-class abilities (`CAbilBehavior` — vanilla stim, cloaks) **cannot autocast
  at all**; no Blizzard data does it. Autocast needs effect-style abilities
  (`CAbilEffectInstant`/`Target` with `AutoCastRange`/`AutoCastFilters`/validators).
- Therefore: **clone architecture** — define `*WoLU` clones in static XML (arrays and
  autocast baked in), gate them behind the `WoLUnbalancedFlag` upgrade (+
  `WoLUHaveFlag` requirement) that only our library grants, and switch the player by
  editing **existing** links per player (`AbilArray[i].Link`, `WeaponArray[i].Link`,
  `LayoutButtons[j].AbilCmd`; indices derived from reference XML in
  `scripts/genlib.py::clone_swaps`).
- **Never clone unit types** — mission scripts check unit types ("all your Marines
  are dead", drop pods spawning `Marine`, …).
- Static XML is global. Safe there: pure definitions, and additions to
  player-exclusive units (heroes, mercs).
- Cloned/added **area-damage effects friendly-fire by default** — set explicit
  `SearchFilters` (campaign's Crucio pattern:
  `Ground;Self,Player,Ally,Neutral,Missile,Stasis,Dead,Hidden,Invulnerable`).

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
