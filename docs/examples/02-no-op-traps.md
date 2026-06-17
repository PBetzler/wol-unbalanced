# 02 — The no-op trap reference (what silently does nothing)

> Know **before you write it** which edits compile, run without error, and change *nothing* —
> because the engine accepted the call but the field isn't reachable that way.

**Maps to (request):** every recurring "I fixed it but it didn't work" bug. This recipe is the
**anti-example** index — the single most valuable page for not wasting a session. **Status:**
[STATIC] + [GAME]-confirmed (each trap below cost a real debugging session; see learnings.md).

---

## Why this matters
`CatalogFieldValueModify` and static-XML overrides both **fail silently** on the wrong field
class: no compile error, no runtime error, the call "succeeds" — and the value is unchanged.
The static gate can catch *some* of these (`audit.py` CHECK3/CHECK4/CHECK5), but several are
**invisible to static tools** and only reveal themselves in game. Memorize the table.

## The trap table

| You tried… | Why it's a no-op | What to do instead |
|---|---|---|
| **Per-player edit of an indexed *array* element** — `Options[]`, `AreaArray[]`, `AttributeBonus[Light]` (on effects), `DamageDealtFraction` scalar form | `CatalogFieldValueModify` can edit a field but **cannot create/replace array entries**; indexed-array element edits don't take | Put it in **static XML** ([12](12-simultaneous-fire.md)) or split into a validator-gated **effect clone** ([13](13-flatten-attribute-bonus.md), [14](14-enlarge-splash.md)) |
| **Per-player edit of a `*Array[i].Link`** — `AbilArray[i].Link`, `WeaponArray[i].Link`, `LayoutButtons[j].AbilCmd` | Runtime **LINK** edits are silent no-ops; only scalar/stat fields apply per player | **XML index-override** of the slot, gated inside the clone ([07](07-clone-flag-gate.md), [26](26-command-card-edits.md)) |
| **Per-player edit of a STRING field** — `TargetFilters`, `Button.Requirements`, names | String-field per-player edits don't apply | Clone the ability/weapon with the new string baked in ([09](09-broaden-targeting.md)); requirement *links* → [19](19-unlock-units-merc-calldowns.md) |
| **Per-player edit of a LOAD-TIME field** — unit `CargoSize` | Read once when the bunker loads the unit; the runtime edit never reaches it | Edit the **transport ability's** scalar fields (`MaxCargoCount`/`MaxCargoSize`/`TotalCargoSpace`) — those *do* apply ([21](21-bunker-transport-capacity.md)) |
| **Array append WITHOUT an explicit `index=`** — `<AbilArray Link="X"/>`, `<LayoutButtons .../>` | In our hand-rolled component-folder mod, index-less appends are **dropped** (Magrail was invisible until `index="4"`) | Always set `index=` = the unit's vanilla element count ([26](26-command-card-edits.md)) |
| **A `CAbil*`/`CWeapon*` clone with no `<Effect>`** | The effect link **re-defaults to the clone's own (nonexistent) id** → does nothing (the `HealWoLU`/`YamatoWoLU` bug) | Set `<Effect index="0" value="<real-effect>"/>` explicitly. `audit.py` CHECK4 **fails** on this ([07](07-clone-flag-gate.md)) |
| **Re-point a CARD button the campaign turned passive** by only setting its `AbilCmd` | Leaves `Type=Passive` + old `Face` → never fires as an action (the Marauder stim bug) | **Append a fresh full `Type=AbilCmd` button** instead ([26](26-command-card-edits.md)) |
| **An action `AbilCmd` on a `Type=Passive` button**, or an `AbilCmd` whose ability isn't on the unit's merged AbilArray | Passive buttons never fire; an off-array ability auto-hides | `audit.py` CHECK5 (card-merge sim) **warns** ([26](26-command-card-edits.md)) |
| **Direct stat edit in static XML to "buff the player"** | Static XML is **global** → leaks to enemies (violates rule 9) | Per-player runtime edit ([01](01-per-player-scalar-stat-edit.md)) or a flag-gated clone ([07](07-clone-flag-gate.md)) |
| **Cloned/added area-damage effect with no `SearchFilters`** | Area effects **friendly-fire by default** → hits your own units | Set explicit enemy-only `SearchFilters` (Crucio pattern) ([15](15-friendly-fire-safety.md)) |
| **Autocast on a behavior-class ability** (`CAbilBehavior`, e.g. cloaks) | Behavior-class abilities **cannot autocast at all** (no Blizzard data does it) | Rebuild as `CAbilEffectInstant` ([08](08-autocast-ability.md)) |
| **Cloning a *unit type*** used by mission scripts | Mission scripts check unit types ("all your Marines are dead", drop-pod spawns) → cloning breaks them | Never clone unit types. **Carve-out:** elite-merc clones, whose ids never appear in any WoL map ([18](18-elite-merc-clone.md)) |
| **`ArmorReduction` set to a big number to "ignore armor"** | It's a **multiplier on how much armor applies** (0 = ignore, 1 = normal); `500` makes armor reduce damage 500× | Set `ArmorReduction=0` to ignore armor ([17](17-ignore-armor-fire-moving.md)) |
| **Pointing a new caster at a vanilla `CEffectSet`** with a caster-bound member | A caster-specific member (e.g. `ReplenishNanoConstructor`, Vulture-only) errors and **aborts the whole set** | Point at the core effect alone, or expand the set first ([11](11-effect-set-caster-trap.md)) |
| **Mid-mission `.SC2Save` across a mod change** | A save serializes live state against the mod's exact catalog structure; any data change invalidates it (`.version` files don't fix it) | Dev workflow: after each reinstall, **start the mission fresh** (learnings.md) |

## What the static gate *does* catch (lean on it)
- **CHECK3 (FAIL)** — a `parent=`/`Effect=` that resolves to no real id (typos, invented models).
- **CHECK4 (FAIL)** — the clone-Effect re-default trap (no `<Effect>` and no parent supplying one).
- **CHECK5 (WARN)** — passive-as-action button, off-array `AbilCmd`, cell collision (card sim).
- **CHECK1 (FAIL)** — a clone unit with no proper `CActorUnit` → renders as a sphere.
- **CHECK7 (WARN)** — an armor string-key that doesn't resolve ("unknown" sign).

## What the static gate canNOT catch (these are why [GAME]/[EDITOR] exist)
- An indexed-array per-player edit that "ran" but didn't apply (needs the in-game diag readback —
  `add a UIDisplayMessage(... CatalogFieldValueGet ...)` line, debug-toolkit.md).
- A string-field per-player edit that didn't take.
- A portrait/model render (heart vs portrait), a card button *appearing*, an armor sign *drawing*.
- Any balance/number/visual outcome.

## Verify
- **Static:** run `python scripts/audit.py`; treat any **FAIL** as a real bug, **WARN** as
  read-and-decide. `[STATIC]`
- **In-game:** when in doubt whether a per-player edit reaches a value, add a **diag readback**
  line (`CatalogFieldValueGet`) and have the owner read it from the mission (debug-toolkit.md
  §"When you can't repro locally"). `[GAME]`

## Parked for bunch-verify
None — this is a reference page, not a change. Its job is to keep *other* recipes out of the
queue by steering you to the working mechanism the first time.
</content>
