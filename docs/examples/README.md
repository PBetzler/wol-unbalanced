# WoL Unbalanced — Worked Example Catalog

A **cookbook of verified, reusable examples** for SC2 Wings-of-Liberty campaign modding,
built from the real, shipped implementation of *WoL Unbalanced*. Each recipe answers one
question — **"I want result X; what exact change produces it, and why?"** — with real
`file:line` citations, a copy-pasteable snippet, the gotchas that bite, and how to verify.

The goal (owner's brief): a **thorough catalog** that can be reused to build *other* mods and
*other* changes. When a new request arrives and no recipe covers it, **add one** (see
[§ Adding a recipe](#adding-a-recipe)).

This catalog is the **examples / cookbook** layer. Its companions:
- [implementation-patterns.md](../implementation-patterns.md) — the **analysis** layer (deep
  root-cause reasoning per active bug). Recipes here cite it.
- [learnings.md](../learnings.md) — the **gotcha** layer (hard-won engine facts).
- [debug-toolkit.md](../debug-toolkit.md) — **symptom → fix** recipes + what `audit.py` catches.

---

## How to use a recipe

1. Find the result you want in the [Index](#index) (or grep the catalog).
2. Read **Mechanism** + **Worked example**; copy the snippet; **swap the ids** for yours.
3. **Resolve every id you introduce** against our XML or `mods/_reference/` with
   `python scripts/xmlq.py ids|get` — a wrong id is a silent no-op (the #1 recurring bug).
4. Run the **static gate** (below). Then run the recipe's **Verify** steps.
5. Mark your change's confidence honestly (legend below) — never call a render/in-game effect
   "done" from static proof alone.

### The static gate (the working automated self-verification — run before every build)
```sh
python scripts/genlib.py        # regenerate the per-player apply lib from reference XML
python scripts/galaxy_lint.py   # Galaxy compile sanity (black-map guard) — MANDATORY
python scripts/audit.py         # catalog/actor audit: CHECK1-7 + card-merge simulator
```
Green gate = **necessary, not sufficient**: it proves *structure* (ids resolve, actors exist,
cards merge, arrays are well-formed), never *balance, numbers, or visuals*. The render/runtime
half is the **Editor** + the **owner's playtest** (next section).

---

## Confidence legend (use it in every recipe and every change summary)

- **[STATIC]** — proven from the catalogs/schema here: the id resolves, the field class is a
  known-working one, the mechanism is correct. The static gate can confirm this.
- **[EDITOR]** — verifiable **locally in the SC2 Editor** without a full playtest: a model/
  portrait renders (Previewer), a card button shows, an armor sign resolves. See the runbook.
- **[GAME]** — needs the owner's in-game playthrough (or the blocked API harness) to confirm
  the *effect*: a number reflected, an autocast firing, a death-response morph, splash landing.
- **[ASSUMPTION]** — a value/semantic taken on faith (e.g. AP's exact numbers); flagged inline.

> **The rule:** separate "the id resolves and the mechanism is correct" ([STATIC]) from "the
> effect happens" ([EDITOR]/[GAME]). Most recurring regressions came from conflating the two.

---

## SC2 Editor verification runbook (the local render/in-game lever)

The Editor is the **only local lever** that renders models/portraits and runs the mod in-game
without shipping a release. Two flows:

### A. Previewer — STATIC render checks (portraits, models, cards, armor signs)
Answers the **[EDITOR]** items: "does the elite-merc portrait render (not a heart)?", "is the
unit a sphere?", "does the card button show?", "does the armor sign resolve (not 'unknown')?".
It shows the **merged static catalog** (our XML layered on vanilla) — **not** per-player runtime
`CatalogFieldValueModify` numbers (those need the lib to run in a game → flow B).

1. Launch: `…\StarCraft II\Support64\SC2Editor_x64.exe` (or Battle.net → StarCraft II → the
   dropdown → **Launch Editor**). It opens on the Terrain module with an Untitled Map.
   - **If an AI agent is driving via computer-use:** the editor must be launched **first** (it
     has no Start-menu entry), then granted by its running-process basename **`sc2editor_x64.exe`**
     — `request_access(["StarCraft II Editor"])` resolves to nothing and `["Editor"]` resolves to
     *Notepad*. The grant dialog needs the owner's **in-person approval** (it times out at 5 min
     if nobody clicks), which is why the whole queue is owner-gated.
2. Load our data so the Previewer can see our units. Either:
   - **(build path)** open the **built** mod `build/.../WoLUnbalanced.SC2Mod` (File → Open), **or**
   - **(no-build path)** `File → Dependencies → Add → Other…` and point at our component-folder
     mod, **or** create a throwaway `.SC2Map`, add our mod as a dependency, and open its Data.
3. Open the **Data module** (`F7`). Select a unit (e.g. `MercThor`, `MercMedic`).
4. Open the **Previewer**: right-click the unit's Actor → **Preview Object**, or use the
   Previewer panel. Switch the view aspect to **Portrait** to check the portrait render.
5. Read off the **[EDITOR]** answer and tick the unit in the [Bunch-verify queue](#bunch-verify-queue).

> The exact menu labels vary by Editor build — confirm them on first run and **update this
> runbook** with the precise click-path you used (that turns [EDITOR] steps into a fast loop).

### B. Test Document (`Ctrl+F9`) — in-game runtime checks
Runs the mod in-game via Battle.net's own license token → should bypass the API's `JoinGame`
license block (the API path is a confirmed dead end on retail 5.x — don't re-chase it). The lib
applies the per-player edits; the **canary** + **diag** subtitle lines appear ~1 s / ~10 s in.
Use this for **[GAME]** items (numbers, autocasts, death-response, splash).

1. Build + open a campaign map with our dependency (needs the local map build — see
   [SETUP.md §3](../SETUP.md); blocked until `mpqpatch.exe` is built). Open
   `build/maps/Campaign/<mission>.SC2Map`.
2. `Ctrl+F9` (Test Document). Watch for the **canary**:
   `WoL Unbalanced: data applied, upgrades & mercs granted.` — absent ⇒ the lib didn't run.
3. Run the relevant [verification-checklist.md](../verification-checklist.md) mission steps.

> A campaign-license guard (`EDSTR_ERROR_TESTDOC_NOCAMPAIGNLICENSE`) may or may not fire — note
> the result on first run.

---

## Adding a recipe

When a new request arrives and no recipe fits:
1. Copy [_TEMPLATE.md](_TEMPLATE.md) to `NN-short-slug.md` (next free number).
2. Fill every section. **Resolve every id** (`xmlq.py`); cite real `file:line`.
3. Run the static gate; mark each claim [STATIC]/[EDITOR]/[GAME]/[ASSUMPTION].
4. Add a row to the [Index](#index); add any [EDITOR]/[GAME] checks to the
   [Bunch-verify queue](#bunch-verify-queue).
5. The recipe isn't "done" until its [EDITOR] checks pass in the Editor (owner/grant-gated) —
   until then it's **parked** in the queue, statically complete.

---

## Index

Recipes are grouped by mechanism family. **Foundations (01–02) are required reading** — every
other recipe builds on the per-player-edit engine and its no-op traps.

### Foundations
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [01](01-per-player-scalar-stat-edit.md) | Per-player scalar stat edit | Change HP/armor/sight/speed/cost/supply/build-time **for the player only** |
| [02](02-no-op-traps.md) | The no-op trap reference | Know *up front* what silently does nothing per-player (indexed arrays, links, strings, load-time reads) |

### Stat & economy rules
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [03](03-attack-windup-cap.md) | Attack windup / timing (rule 7) | Cap pre-shot swing ≤0.1 s; fix "feels slow" (Period/Backswing) |
| [04](04-build-time-cap.md) | Build-time cap + overrides (rule 5) | No unit > 60 s; per-unit faster builds (Predator 10 s, Hercules 20 s) |
| [05](05-cost-supply-armor.md) | Cost / supply / armor edits | Free gas, −1 supply, +N armor, Resource-Efficiency cuts |
| [06](06-merc-hero-parity.md) | Merc/hero % advantage parity | Keep a merc/hero's % lead after the base unit is buffed |

### Clone architecture & abilities
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [07](07-clone-flag-gate.md) | Clone + flag-gate backbone | Structural change (arrays/autocast) **player-only**, via `*WoLU` clones |
| [08](08-autocast-ability.md) | Autocast ability (Super Stim) | A unit auto-fires an effect ability in combat |
| [09](09-broaden-targeting.md) | Broaden an ability's targets | Heal can hit mechanical + air (TargetFilters) |
| [10](10-autocast-priority-targetsort.md) | Autocast priority (TargetSort) | Order autocast targets (healer → lethal → tanky → nearest) |
| [11](11-effect-set-caster-trap.md) | Reusing a vanilla effect set | …and the caster-bound member that aborts the whole set |

### Weapons & damage
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [12](12-simultaneous-fire.md) | Simultaneous air+ground fire | A 2-weapon unit fires both at once (Options[] independent fire) |
| [13](13-flatten-attribute-bonus.md) | Flatten "+X vs light/armored" | Show/deal flat damage instead of a conditional bonus |
| [14](14-enlarge-splash.md) | Enlarge splash radius | Bigger AoE (AreaArray) — player-only via clone |
| [15](15-friendly-fire-safety.md) | Friendly-fire safety | A new/cloned area effect that won't hit your own units |
| [16](16-stacking-on-attack-buff.md) | Stacking on-attack buff | +X% per attack up to a cap (Trigger Override) — data-only |
| [17](17-ignore-armor-fire-moving.md) | Ignore armor / fire while moving | Attacks ignore target armor; weapons fire on the move |

### Units, mercs, capacity
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [18](18-elite-merc-clone.md) | Define an elite-merc clone | A player-only buffed clone of a base unit (name, portrait, actor) |
| [19](19-unlock-units-merc-calldowns.md) | Unlock units & merc calldowns | Units/mercs available from start; unlimited charges (no leak) |
| [20](20-auto-unlock-upgrades.md) | Auto-unlock armory upgrades | Every armory upgrade granted at its unit's unlock mission (rule 2) |
| [21](21-bunker-transport-capacity.md) | Bunker / transport capacity | More cargo; admit big units; 1 slot per infantry |
| [22](22-death-response-resurrect.md) | Death-response resurrect chain | A fatal hit rebuilds the unit **as itself**, free |

### Cloak, visuals, display, cards
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [23](23-free-cloak.md) | Free cloak + spawn cloaked (rule 8) | Cloak costs nothing, never drains; units spawn cloaked |
| [24](24-clone-visuals.md) | Keep visuals on clones | Clones keep projectiles/beams/impacts (actors bind to ids) |
| [25](25-armor-display-shielded.md) | Armor/defense display | Both life-armor **and** shield signs show on a shielded clone |
| [26](26-command-card-edits.md) | Command-card edits | Add/repoint buttons without breaking the merged card; fix hotkeys |

### Galaxy-side & kits
| # | Recipe | Result it produces |
|---|--------|--------------------|
| [27](27-galaxy-per-player-effects.md) | Galaxy-side per-player logic | The apply-tech lib, canary/diag, cloak-On order, resource timers |
| [28](28-tactical-jump.md) | Tactical Jump | Point-target warp anywhere (CEffectTeleport) |
| [29](29-permanent-summons-free-kit.md) | Permanent summons + free kit | Unlimited-duration drones/turrets; free-to-activate kit (Raven) |
| [30](30-spider-mines-siege.md) | Spider Mines on a sieged unit | Deploy mines while immobile; fix a hotkey collision |
| [31](31-engineering-bay-upgrade.md) | Unified eng-bay attack/defense upgrade | One 30 s upgrade buffs all infantry/vehicle/ship at a tier |
| [32](32-bc-smart-batteries.md) | BC multi-target no-overkill + autocast | Spread fire to avoid overkill; auto-cast spells (design example) |

---

## Bunch-verify queue

Everything that is **statically complete but needs the Editor or an in-game playtest** — i.e.
needs the owner (the SC2-Editor computer-use grant timed out while the owner was away; the local
map build is blocked on `mpqpatch.exe`). Verify these in a batch via the
[runbook](#sc2-editor-verification-runbook) above.

> Populated during catalog integration — see [_QUEUE.md](_QUEUE.md) for the live, consolidated
> list (every recipe's parked [EDITOR]/[GAME] checks, grouped by verification flow).
</content>
</invoke>
