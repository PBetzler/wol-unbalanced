# 26 — Command-card edits (add/repoint buttons; fix hotkeys)

> Add or re-point command-card buttons **without breaking the merged vanilla card**, and fix a
> hotkey collision — by computing the *effective* merged card first.

**Maps to (request):** every card change in the mod — the Marauder/Ghost/Spectre stim buttons, the
single-MULE CC fix, the Spider Mine hotkey — design rules 1/10. **Status:** [STATIC] via the
card-merge simulator (CHECK5) · the buttons *appearing* + the hotkey *firing* are [GAME] — see
Verify.

---

## Result
A new or re-pointed button shows on the card, **fires** (isn't a dead passive), lands in a **free
cell** (doesn't hide an existing button), and a custom hotkey replaces a colliding one (Spider Mine
moves off the Siege-mode "E").

## Mechanism
Vanilla cards are built across **base → campaign → story** layers, and campaigns *edit* the arrays:
`removed="1"` **tombstones** delete inherited entries, and **index-less appends** add to the end.
So you can't eyeball an index against the base card — you must compute the **EFFECTIVE merged
card**. `audit.py` CHECK5 simulates the full merge (with `parent=` resolution +
`removed`/index-less-append semantics). (learnings.md §"Append, don't override" + §"`removed=1`…";
[implementation-patterns.md §9](../implementation-patterns.md).)

Rules, all **GAME-proven the hard way**:
1. **Appends need an explicit `index=`** = the unit's vanilla element count; index-less appends are
   silently **dropped** in our hand-rolled component-folder mod.
2. **To re-point a button the campaign turned PASSIVE, APPEND a fresh full `Type=AbilCmd` button** —
   overriding only its `AbilCmd` leaves `Type=Passive`/the old `Face`, so it never fires (the
   Marauder stim bug).
3. **`removed="1"` is a real tombstone**; a later layer re-setting the same index with a `Link`
   re-occupies it.
4. **Hero rows (2,0–2,3) are often fully occupied** — pick a verified free cell.
5. **Hotkey collision** → clone the button as a `CButton` and bind a fresh key in the hotkeys file
   (the binding is **not** an inline `<Hotkey>` on `CButton`; it's a `Button/Hotkey/<id>=` line in
   `GameHotkeys.txt`).

## Worked example (real, from this repo)

### Rule 2 — append a fresh button to re-point a campaign-passive (Marauder stim)
The campaign tombstones the Marauder's vanilla stim (`AbilArray index 3 removed="1"`) and turns its
stim button into the `AblativeScales` **passive**. The old fix that *only* set `AbilCmd` on that
passive button failed — it stayed `Type=Passive`. The working fix re-adds the ability and **appends
a fresh `Type=AbilCmd` button** in a free cell:
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:115-121  (the bug, documented) -->
<!-- … The OLD button override only set AbilCmd on index 6 — that's the AblativeScales
     PASSIVE button, so it stayed Type=Passive/Face=AblativeScales and never worked as
     stim (the bug). Fix: leave AblativeScales alone and APPEND a real stim button at
     the next free index (10) in a free cell (2,0). -->
```
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:123,128  (CUnit id="Marauder") -->
<AbilArray index="3" Link="StimpackMarauderWoLU"/>     <!-- re-instate the tombstoned ability -->
<LayoutButtons index="10" Face="Stim" Type="AbilCmd" AbilCmd="StimpackMarauderWoLU,Execute" Row="2" Column="0"/>
```
`index="10"` = the next free slot after the merge; `Type="AbilCmd"` (not the inherited Passive);
cell `(2,0)` is free on the merged Marauder card.

### Rule 1 — explicit-index append = the vanilla element count (Marine Magrail)
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:74-78  (the rule, in a comment) -->
<!-- EXPLICIT-INDEX append test: vanilla Marine has AbilArray 0-3 (stop/attack/move/
     Stimpack) and LayoutButtons 0-5, so Magrail = abil index 4, button index 6. … -->
```
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:81,84  (CUnit id="Marine") -->
<AbilArray index="4" Link="MagrailWoLU"/>
<LayoutButtons index="6" Face="MagrailWoLU" Type="AbilCmd" AbilCmd="MagrailWoLU,Execute" Row="2" Column="1"/>
```
The general note — "explicit indices = each unit's vanilla array count = next free slot;
index-less appends do NOT take effect in our dependency mod (proven on Marine)" — is at
`UnitData.xml:14-16`.

### Rule 3 — `removed="1"` tombstone (reference example)
The tombstone the rules describe is the campaign's own. In our file the Jotun behavior slot is now
an **override** (`UnitData.xml:559`, `<BehaviorArray index="1" Link="MercThorDontDie"/>`, comment at
:556 notes "OVERRIDE (not the old removed=1 tombstone)") — so the canonical tombstone to study is
the libertystory layer stripping vanilla Marauder stim:
```xml
<!-- mods/_reference/campaigns/libertystory.sc2campaign/UnitData.xml:601  (CUnit id="Marauder") -->
<AbilArray index="3" removed="1"/>      <!-- the campaign deletes the inherited StimpackMarauder -->
```
Our `<AbilArray index="3" Link="StimpackMarauderWoLU"/>` (above) is exactly the "later layer re-sets
the same index → re-occupies the slot" case.

### Rule 4 + clean re-points — free cells, and overriding only buttons (enemy-shared abilities)
The authoritative "hero rows are taken" note:
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:8-13 -->
<!-- … Button cells chosen against each unit's vanilla card (collisions found the hard way:
     RaynorCommando 2,1 = radar, Raynor 2,0-2,3 all taken, Tychus 2,0/2,1 taken,
     Firebat 2,0/2,1 taken). -->
```
For an ability the **enemy AI also uses** (Snipe/EMP/Obliterate), you must NOT override the
ability slot — append the clone and **re-point only the card button** (cards are pure UI, AI never
reads them). Ghost/Spectre do this (`UnitData.xml:202-228`): re-point Snipe/EMP/Obliterate buttons
to the `*WoLU` clones, append a fresh stim button (Ghost `index 13`, Spectre `index 14`). A minimal
re-point keeps the existing cell — the single-MULE CC fix sets only `AbilCmd`:
```xml
<!-- src/mod/Base.SC2Data/GameData/UnitData.xml:369  (CUnit id="CommandCenter") -->
<LayoutButtons index="1" AbilCmd="CalldownMULEWoLU,Execute"/>   <!-- inherits Face/Row/Column from the merged card -->
```
(That re-point is safe because index 1 is already an *action* button in the merged card, not a
passive — contrast the Marauder case.)

### Rule 5 — hotkey-collision fix (Spider Mine E → Y)
The vanilla `SpiderMine` button has no `Hotkey`, so it inherits base-CASC `Button/Hotkey/SpiderMine
= E` — the **same key** as Siege mode's "Enter Siege". The fix is **two files**: a `CButton` clone
(same icon, new id) + a fresh hotkey line for that id:
```xml
<!-- src/mod/Base.SC2Data/GameData/ButtonData.xml:18-21 -->
<CButton id="SpiderMineWoLU">
    <Icon value="Assets\Textures\btn-ability-terran-spidermine.dds"/>
    <AlertIcon value="Assets\Textures\btn-ability-terran-spidermine.dds"/>
</CButton>   <!-- NOTE: no inline <Hotkey> here — the binding lives in GameHotkeys.txt -->
```
```text
# src/mod/enUS.SC2Data/LocalizedData/GameHotkeys.txt:2
Button/Hotkey/SpiderMineWoLU=Y
```
All four spider-mine card buttons use `Face="SpiderMineWoLU"` (`UnitData.xml:404,414,420,426`), so
the new hotkey `Y` replaces the colliding `E` everywhere; Enter Siege keeps `E`. The rationale is
documented at `ButtonData.xml:11-17`.

### Merc/hero reach
Cards are per-unit-id, so a button edit reaches only the unit whose `CUnit` block carries it. Elite
mercs (`parent=` clones) **inherit** the base unit's merged card (and thus the base's re-pointed
buttons) — so a base-unit card fix usually reaches them for free; heroes/standard-mercs are
distinct ids and get their own button edits (e.g. Stetmann re-points its own heal button). [STATIC]

## Reusable snippet (swap the ids)
```xml
<!-- Append a fresh action button at the unit's next free index (= vanilla element count).
     RESOLVE: run audit.py CHECK5 to get the EFFECTIVE merged card before choosing index + cell. -->
<AbilArray index="<freeAbilIdx>" Link="<MyAbilOrClone>"/>
<LayoutButtons index="<freeBtnIdx>" Face="<Face>" Type="AbilCmd"
               AbilCmd="<MyAbilOrClone>,Execute" Row="<freeRow>" Column="<freeCol>"/>
```
```text
# Hotkey override (two files): clone the CButton, then bind a key in GameHotkeys.txt
#   ButtonData.xml: <CButton id="<MyButton>"><Icon .../></CButton>
#   GameHotkeys.txt: Button/Hotkey/<MyButton>=<LETTER>
```

## Gotchas / no-op traps  → full list in [02](02-no-op-traps.md)
- **Index-less append → dropped** in our component-folder mod. Always set `index=`.
- **Re-pointing only `AbilCmd` on a campaign-passive button → still passive.** Append a full
  `Type=AbilCmd` button instead.
- **A runtime `LayoutButtons[j].AbilCmd` edit is a no-op** — card edits are **static XML
  index-overrides**, never `CatalogFieldValueModify`.
- **An `AbilCmd` whose ability isn't on the unit's merged `AbilArray` auto-hides.** Wire the
  ability (append it) before pointing a button at it. CHECK5 warns.
- **A colliding cell silently hides one of the two buttons.** Pick a free cell from the *merged*
  card, not the base card. Hero rows 2,0–2,3 are usually full.
- **The hotkey binding is NOT an inline `<Hotkey>` on `CButton`** — it's a `Button/Hotkey/<id>=`
  line in `GameHotkeys.txt`.

## Verify
- **Static:** `python scripts/audit.py` — **CHECK5** (`merge_unit_card` at `audit.py:142-195`;
  checks at `audit.py:344-389`, WARN) simulates the base→campaign→story→our-mod merge and warns on
  **passive-as-action** (`CHECK5 passive-action`), **off-array `AbilCmd`** (`CHECK5 button-no-abil`),
  and **cell collisions** (`CHECK5 cell-collision`). It runs only when the reference dump is present
  (skipped in CI). **Proves** the card merges cleanly; **does not prove** the button is visible or
  the hotkey fires. `[STATIC]`
- **Editor (Previewer):** open the unit's card; confirm the new button appears in its cell with the
  right icon. `[EDITOR]` — add to queue.
- **In-game (Test Document / owner):** the button shows **and works** (stim fires + autocasts; the
  single MULE button calls down; Spider Mine deploys on **Y** while Enter Siege stays **E**).
  Missions: Marauder/Ghost/Spectre stim — any with those units; Spider Mine — a Siege Tank mission.
  `[GAME]` — add to queue.

## Parked for bunch-verify
- `[EDITOR]` — Each appended/re-pointed button renders in its cell with the right icon (Marauder
  stim 2,0; Marine Magrail 2,1; Ghost/Spectre stim; the single CC MULE).
- `[GAME]` — Buttons fire (stim autocasts, MULE calls down); Spider Mine hotkey is **Y**, Enter
  Siege stays **E**, no collision (open-issues #3/#1/#5/#10).
