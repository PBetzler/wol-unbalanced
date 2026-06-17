# 19 — Make units & merc calldowns available from game start (no leak)

> Have every unit buildable and every merc calldown ready-to-fire from mission start — with
> unlimited charges — **without** wrongly unlocking the merc's vanilla counterpart (the trap that
> leaked Marauder/Firebat/Factory).

**Maps to (request):** design rule 3 (mercs unlock with their counterpart) + rule 6 (merc
calldowns: unlimited charges, ready at mission start; Compound still required). open-issues
"All 8 standard mercs from start", "Merc-unlock regression". **Status:** [STATIC] done
(direct-allow path verified, charge fields scalar-class); the in-mission availability is [GAME].

---

## Result
At mission start the player can build every unit unlocked so far and can fire every merc
calldown immediately and repeatedly — no 5-minute cooldown, no "Not enough charges", no spurious
counterpart unit appearing in the build menu.

## Mechanism
Two halves, each with a sharp trap.

**(1) Unlock a UNIT — call `TechTreeUnitAllow(p, "<unit>", true)` DIRECTLY.** This allows the
unit's train command for one player. The **trap**: do *not* enable the merc tech-*subgroup* to
unlock a merc — a merc's tech subgroup maps to its **counterpart** unit's group, so enabling it
unlocks Marauder/Firebat/Factory/etc. and does **not** enable the calldown (the v0.2.1
regression). The fix is to allow the merc *unit type* directly so its calldown works, leaving the
counterpart gating to the campaign (`LibWoLUnbalanced.galaxy:91-94` documents exactly this).

**(2) Make a CALLDOWN unlimited + ready — set the `SummonMercenaries` charge/cooldown scalars
per player.** These are plain scalar fields under `InfoArray[TrainN]`, the same class as the
working cost edits, so `CatalogFieldValueModify` applies them. The **key gotcha**: a charge count
of **0 means ZERO charges** ("Not enough charges"), not unlimited — so we use a big cap (99), not
0. We set `Charge.CountMax=99`, `Charge.CountStart=99` (start full), `Charge.CountUse=0` (firing
costs no charge), `Cooldown.TimeStart=0` + `Cooldown.TimeUse=0` (no wait — vanilla is 300 s).

CampaignLib glue makes the merc *purchasable* in the first place: `SetMercStatus(id, Purchased)`
marks every merc hired; a merc's `Locked` state derives from the counterpart's tech group, so
skipping `Locked` mercs preserves rule 3 ([learnings.md §CampaignLib](../learnings.md)).

## Worked example (real, from this repo)
**Direct unit allow + the documented anti-leak rationale:**
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:90-104
// The merc UNIT must be allowed for its calldown to work (only War Pigs appeared
// otherwise — its counterpart Marine is unlocked). Allow the merc unit types DIRECTLY.
// (v0.2.1 used EnableCampaignTechUnit on the merc tech subgroups, but those map to the
// COUNTERPART unit's group — it wrongly unlocked Marauder/Firebat/Factory/etc. and did
// NOT enable the calldowns. Reverted.)
TechTreeUnitAllow(p, "WarPig", true);
TechTreeUnitAllow(p, "DevilDog", true);
TechTreeUnitAllow(p, "HammerSecurity", true);
... // SpartanCompany, SiegeBreaker(+Sieged), HelsAngelFighter/Assault, DuskWing, DukesRevenge
```
The elite-merc units ([18](18-elite-merc-clone.md)) are allowed the same direct way
(`LibWoLUnbalanced.galaxy:135-140`), as are MULE (`:146`) and the branch Ghost/Spectre
(`:117-120`, gated on the Dominion-Ghost tech group being enabled — that's how rule-3 gating is
preserved for the branch).

**Mark every merc purchased (CampaignLib), then re-apply through the campaign's own paths:**
```galaxy
// src/mod/Base.SC2Data/LibWoLUnbalanced.galaxy:80-89
i = libCamp_gv_TSC_MERC_FIRST;
while (i <= libCamp_gv_TSC_MERC_LAST) {
    libCamp_gf_SetMercStatus(libCamp_gv_tS_MercID[i], libCamp_ge_StoryMercStatus_Purchased);
    i = i + 1;
}
libCamp_gf_ApplyCampaignTech(p);
libCamp_gf_TS_ApplyMercenaryTech(p);
libCamp_gf_TS_ApplyMercUpgrades(p);
```
`libCamp_gf_SetMercStatus` is defined at `mods/_reference/campaigns/libertystory.sc2campaign/`
`TriggerLibs/CampaignLib.galaxy:3516`; the status enum is in `CampaignLib_h.galaxy:160-163`
(`Locked=0`, `Available=1`, `Purchased=2`, `New=3`).

**Make the calldowns unlimited + instant** (genlib loops Train1-15 and sets the scalars):
```python
# scripts/genlib.py:187-195
for n in range(1, 16):
    for field, val in (
        ("Charge.CountMax", "99"),    # NOT 0 — 0 = zero charges, "Not enough charges"
        ("Charge.CountStart", "99"),  # start full
        ("Charge.CountUse", "0"),     # firing costs no charge → never runs dry
        ("Cooldown.TimeStart", "0"),  # ready at mission start (vanilla = 300 s)
        ("Cooldown.TimeUse", "0"),    # no cooldown between casts
    ):
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "SummonMercenaries", "InfoArray[Train{n}].{field}", p, "{val}", c_upgradeOperationSet);')
```
Vanilla `SummonMercenaries InfoArray[Train1]` carries `Charge.CountMax=3`/`CountStart=3`/
`CountUse=1` and `Cooldown.TimeStart=300`/`TimeUse=300`
(`mods/_reference/campaigns/liberty.sc2campaign/AbilData.xml:1413`) — the 300 is the 5-minute
wait we zero out. Train1-8 are the vanilla mercs; Train9-15 are our extra elite mercs (the loop
to 15 reasserts the unlimited-from-start defaults on them; the few removed mercs are harmless
no-op iterations).

### Merc/hero reach
This recipe *is* the reach mechanism for calldowns — the edit targets the shared
`SummonMercenaries` ability, so it covers every `InfoArray[TrainN]` slot. Unit unlocks are
per-unit-id, so each merc/hero unit id is allowed explicitly in the galaxy list above.

## Reusable snippet (swap the ids)
```galaxy
// Unlock a unit for the player (NOT via the merc tech subgroup — that leaks the counterpart):
TechTreeUnitAllow(p, "<UNIT>", true);
```
```python
# Make a SummonMercenaries calldown slot unlimited + instant (genlib emits per player):
# RESOLVE FIRST: confirm the InfoArray index (Train1..N) with xmlq.py get SummonMercenaries.
("Abil", "SummonMercenaries", "InfoArray[Train<N>].Charge.CountMax",   "99", "Set", ""),
("Abil", "SummonMercenaries", "InfoArray[Train<N>].Charge.CountStart", "99", "Set", ""),
("Abil", "SummonMercenaries", "InfoArray[Train<N>].Charge.CountUse",    "0", "Set", ""),
("Abil", "SummonMercenaries", "InfoArray[Train<N>].Cooldown.TimeStart", "0", "Set", ""),
("Abil", "SummonMercenaries", "InfoArray[Train<N>].Cooldown.TimeUse",   "0", "Set", ""),
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **`CountMax/CountStart = 0` is NOT "unlimited" — it's ZERO charges.** The calldown reads "Not
  enough charges" and never fires. Use a big cap (99) + `CountUse=0` so it never decrements.
- **Enabling a merc via its tech subgroup leaks the COUNTERPART** (Marauder/Firebat/Factory) and
  still doesn't enable the calldown (v0.2.1). Always `TechTreeUnitAllow` the merc *unit type*
  directly.
- **The merc must be `Purchased` *and* its unit allowed** — only War Pigs appeared when the merc
  was Purchased but its unit type wasn't allowed (its counterpart Marine was the only thing
  unlocked). Both halves are required.
- **`InfoArray[TrainN].…` is an indexed *scalar* path → it applies per player;** `Charge`/
  `Cooldown` are scalar sub-structs, not the array-element link/append case that no-ops
  ([02](02-no-op-traps.md)).

## Verify
- **Static:** `python scripts/galaxy_lint.py` (the generated calls compile — black-map guard);
  `python scripts/audit.py` CHECK3 (FAIL on a misspelled unit/ability id). **Does not prove** the
  charge value reflects or that the unit is actually buildable mid-mission. `[STATIC]`
- **In-game (owner):** at any mission start, open the Merc Compound and fire each calldown
  repeatedly with no cooldown/charge block; confirm the counterpart's build menu is *not* polluted
  by an unintended unit. `[GAME]` — add to queue.

## Parked for bunch-verify
- `[GAME]` All 8 standard mercs + the 6 elite mercs fire from mission start, unlimited charges,
  no cooldown; no counterpart unit wrongly unlocked (no Marauder/Firebat/Factory leak).
