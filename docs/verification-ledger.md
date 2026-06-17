# Verification ledger — maximize machine-verifiable, minimize the owner surface

The goal: **verify the most parts mechanically (static gate / editor / preview), and shrink the
"needs the owner in-game" surface to a short list of small, simple, once-verified facts** — so
there's near-zero room for per-instance error.

## The core principle: verify by MECHANISM, not by instance

The mod makes ~150 individual changes, but they ride a **small number of mechanisms**. Once a
mechanism is verified, **every unit/buff that uses it inherits that confidence**. So you never
re-verify 150 buffs — you verify ~6 unproven mechanisms once, and the static gate confirms each
instance is *wired* to a verified mechanism. The per-instance "variation" is then tiny: "this unit
also links the already-verified mechanism X," which `audit.py` checks structurally.

This ledger separates the surface into three layers and names exactly what's left for the owner.

---

## Layer 1 — fully machine/editor verifiable (NO owner needed)

| Surface | Verified by | Status |
|---|---|---|
| Clone/effect/ability/weapon ids resolve | `audit.py` CHECK3/CHECK4 | ✅ auto |
| Command-card merges (button cells, passive-vs-action) | `audit.py` CHECK5 merge simulator | ✅ auto |
| Armor/name string keys resolve | `audit.py` CHECK7 + editor field view | ✅ auto + editor |
| Models / portraits render (mercs) | SC2 Editor Previewer / Data Navigator | ✅ (2026-06-17) |
| Galaxy compiles (no black map) | `galaxy_lint.py` | ✅ auto |
| **Buff VALUES** (every per-player field edit's final number) | **`preview.py` manifest** | ✅ BUILT — `build/preview/buff-manifest.md` lists every edit's `base → final` |
| **Buff APPLICATION class** (each edit lands on a field class that actually applies) | **`preview.py --check` = CHECK8** | ✅ BUILT + in the gate (pre-commit + CI); 326 GOOD / 0 NOOP |

> Lever 1+2 (below) are now LIVE: they moved the single biggest "trust me" chunk — the ~330
> field edits — into this fully-verified layer, and lock it so no no-op runtime edit can return.

## Layer 2 — application mechanisms (verify ONCE → covers ALL instances)

These are *how* a change reaches the player. Each is one mechanism; verifying it once covers every
instance that uses it.

| Mechanism | Covers all… | Status |
|---|---|---|
| Per-player scalar `CatalogFieldValueModify` applies | stat / cost / supply / build-time / range / sight / speed edits | ✅ in-game (Marine 65 vs enemy 45, plan §7) |
| `WoLUnbalancedFlag` grant + `WoLUHaveFlag`/`WoLUHasFlag` gate | every clone button + every validator-gated effect set | ✅ (clones fire for the player only) |
| Lib runs at mission start (canary) | literally everything | ✅ (canary observed) |
| Auto-unlock armory tech (CampaignLib grant loop) | every auto-granted upgrade | ✅ (units/upgrades available) |
| Merc calldown unlock (`TechTreeUnitAllow` + `SummonMercenaries` charges) | all 14 mercs | ✅ v0.2.4 (worth a re-test) |

> With **lever 2** (field-class gate) every runtime edit is *guaranteed* to sit on one of these
> verified-applying classes — so Layer 2 is trustworthy by construction, not by per-edit faith.

## Layer 3 — the IRREDUCIBLE owner surface (emergent in-game behavior)

These can't be shown by any static tool — they're whether a structure *does its thing* at runtime.
Each is **one mechanism, verified once** (a verification map makes them a single Test Document run).
**This whole list is the entire "needs the owner" surface.**

| Mechanism (verify once) | Covers | Status |
|---|---|---|
| Autocast fires (`CAbilEffectInstant` + ability-level flags) | stim, snipe, EMP, defensive matrix, yamato, … | ✅ (stim confirmed) |
| Free cloak + spawn-cloaked + toggle-order | every cloak-capable unit | ✅ (mostly; decloak-button ⚠) |
| Death-response morph chain (Immortality) | Jotun resurrect | ⏳ pending |
| Area effect + `SearchFilters` (no friendly fire) | Thor/Viking/EMP splash | ⏳ pending |
| Simultaneous air+ground fire (`Options[]`) | Thor / Odin / Jotun | ⏳ pending |
| Galaxy per-player timer (Vespene Synthesis) | Predator gas | ⏳ pending |
| TargetSort autocast priority | smart-Snipe ordering | ⏳ pending |
| Stacking on-attack buff (Trigger Override) | Wraith fire-rate ramp | ⏳ pending |

**That's the irreducible surface: ~6 pending mechanism facts.** Not 150 buffs — 6 behaviors, each
verified once, each a tiny per-unit variation on a proven pattern.

---

## The two levers that shrink the surface further

### Lever 1 — Preview lens (auto-verifies every buff VALUE) — ✅ BUILT (`scripts/preview.py`)
`scripts/preview.py` **parses the generated lib** (no genlib change → shipped galaxy byte-identical),
resolves each edit's vanilla base, computes the final, and writes `build/preview/buff-manifest.md` —
every edit as `kind | id | field | op value | base → final`. **`preview.py --mod`** also emits a
loadable static-global `build/preview/WoLUnbalanced-Preview.SC2Mod` (321 overrides / 128 ids) — load
it in the SC2 Editor Data module and the buffed numbers show directly. **EDITOR-CONFIRMED 2026-06-17:**
Marine `LifeMax = 65` (45 + 20), Sight 11; Marauder Life Armor 3, Sight 12; `CargoSize` correctly
un-buffed (the dead edit was removed). Two payoffs:
- **Editor**: load it → every buffed field shows its real number directly (`Marine LifeMax = 65`,
  `Predator Vespene = 0`, `ThorsHammer Range = 13`). You read the numbers, no playtest.
- **Automated audit**: a check diffs preview-vs-vanilla and asserts **every intended delta landed
  and equals `base ± value`** — so all ~150 buff values become *machine-verified*, not trusted.

It's global (leaks to enemies) but **never shipped/played** — purely a verification lens. The
shipped per-player build is untouched. (Same source-of-truth edit list, two emit modes.)

### Lever 2 — Field-class safety gate (locks the application to verified classes) — ✅ BUILT (`preview.py --check`)
**CHECK8** (`scripts/preview.py --check`, now in the pre-commit hook + CI) **FAILS** if any runtime
per-player edit lands on a **known no-op field class** (indexed arrays, `*.Link`, string fields,
load-time `CargoSize` — see [examples/02-no-op-traps.md](examples/02-no-op-traps.md)) or on a typo'd
id. Those must go through a static clone instead. It found + we removed 11 such dead edits + a dead
`SpectreCloak` id (open-issues). Result: **every runtime edit is provably on a class we've verified
applies** → Layer 2's "does it apply?" is answered by construction, per edit, automatically. The
only items it leaves as WARN are the 6 free-cloak regen-array edits (UNCERTAIN, GAME-confirmed).

---

## End state

After both levers:
- **Layer 1** (structure + values) — 100% machine/editor verified.
- **Layer 2** (application) — locked to verified-safe classes by CHECK8; each class proven once.
- **Layer 3** — the *only* owner surface: ~6 emergent-behavior facts, each verified once via the
  verification map (spawn player + enemy units side-by-side, trigger the behaviors).

The "not verified by the tooling" category is then **6 small, simple, mechanism-level checks** —
each covering many units, each hard to get subtly wrong (a behavior either morphs or it doesn't).
That's the minimal, low-error-surface target.

See also: [examples/_QUEUE.md](examples/_QUEUE.md) (the per-recipe checklist),
[verification-checklist.md](verification-checklist.md) (the mission-ordered in-game plan).
</content>
