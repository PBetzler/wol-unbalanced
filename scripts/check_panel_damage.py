#!/usr/bin/env python3
"""CHECK11 — unit-info damage-panel TRUTH check (panel number == player's fired number).

The recurring bug class this gate closes: the unit-info **damage panel** reads a weapon's
`<DisplayEffect>` (or `<Effect>` if `DisplayEffect` is absent) → that effect's `Amount`
(+ every `AttributeBonus[...]`) × `DisplayAttackCount`, resolved per-player. Our clone
architecture reroutes a weapon's **`<Effect>`** (or a missile's **`ImpactEffect`**) to a
`*WoLU(Set)` clone but leaves `DisplayEffect` pinned to the VANILLA effect. The panel is then
display-NEUTRAL to the reroute and only DIVERGES when the player's actually-fired clone child
carries an `Amount` / `AttributeBonus` the panel-effect id does not (after per-player edits).

Two confirmed divergences before this gate:
  * Thor / Jotun AA — panel reads `JavelinMissileLaunchersDamage` (per-player Amount=35 via a
    genlib edit, but AttributeBonus[Light]=4 unchanged → "+4 vs Light"), player fires
    `JavelinMissileLaunchersDamageBuffedWoLU` = flat 35, Light bonus 0 → panel OVER-shows +4 Light.
  * Viking / Hel's Angels ground — panel reads `TwinGatlingCannons` (14, no AttributeBonus),
    player fires `TwinGatlingCannonsWoLU` = 14 + AttributeBonus[Mechanical]=20 → panel UNDER-shows +20.

THE INVARIANT (per rerouted weapon, resolved PER PLAYER):
    panel value  = (DisplayEffect|Effect id)'s resolved Amount + every AttributeBonus[attr]
    actual value = the player's WoLUHasFlag-gated clone child's resolved Amount + every AttributeBonus[attr]
    panel value MUST EQUAL actual value (Amount AND the full AttributeBonus map).
DisplayAttackCount is a constant MULTIPLIER applied to BOTH sides (display only, identical for
panel and actual), so it never affects equality — we compare the per-hit Amount/bonus tuple.
Splash radius / AreaArray is NEVER panel-shown, so an added AreaArray alone is NOT a divergence.

A FAIL names the weapon, the panel-effect id, the player-clone id, the displayed value, the
actual value, and the diverging field (Amount or a specific AttributeBonus[attr]).

WHAT IT COVERS / LIMITS:
  * Covers every static reroute of a weapon `<Effect>` (WeaponData.xml) and a missile/launch
    `ImpactEffect` (EffectData.xml) to a `*WoLU(Set)` clone — the full reroute universe in
    docs/learnings.md (Thor AG, Viking AG, Hel's Angels AG, Thor/Jotun AA, the Wraith sets).
  * Resolves `parent=` inheritance AND per-player `CatalogFieldValueModify` edits (parsed from
    the generated lib, reusing preview.py's resolver) so the comparison is the PLAYER's view.
  * For a reroute SET, the player-fired branch = the member gated by `WoLUHasFlag` (the buffed
    branch); a reroute SET that only WRAPS the vanilla delivery effect (Wraith pattern — the
    member IS the unchanged vanilla launch/persistent effect, no Amount/AttributeBonus clone)
    has no damage clone → nothing to diverge → MATCH.
  * Limit: needs the gitignored reference dump (mods/_reference/) to resolve vanilla parent
    Amounts. ABSENT (CI) → it SKIPS the numeric comparison (like audit.py CHECK3-7 / preview
    CHECK8's typo guard), still printing the reroute map. The local pre-commit gate runs it fully.
  * Limit: it checks the FIRED damage effect only. Per-shot `DisplayAttackCount` and splash
    radius are out of scope by construction (display-identical / never panel-shown).

Run: python scripts/check_panel_damage.py   (exit non-zero on a panel↔actual divergence)
Stdlib-only; UTF-8 stdout (Windows cp1252 console).
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GD = os.path.join(ROOT, "src", "mod", "Base.SC2Data", "GameData")
REF = os.path.join(ROOT, "mods", "_reference")

# Reuse preview.py's per-player edit parser + base-value resolver (parent-chain + merge layers).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview as P  # noqa: E402


def our_catalog(name):
    p = os.path.join(GD, name)
    return ET.parse(p).getroot() if os.path.exists(p) else ET.Element("Catalog")


def fval(el, name):
    """Attribute form OR <Name value=...> child form."""
    if el.get(name) is not None:
        return el.get(name)
    c = el.find(name)
    return c.get("value") if c is not None else None


# ---------------------------------------------------------------------------------------
# Per-player edit overlay. preview.resolve_base gives the VANILLA (static) base; the panel
# and the player BOTH see the per-player CatalogFieldValueModify edits on top. We parse the
# generated lib once and, for an (Effect,id,field), apply the stacked ops in lib order so the
# resolved value is the PLAYER's view (e.g. JavelinMissileLaunchersDamage.Amount Set 35).
# ---------------------------------------------------------------------------------------
def per_player_effect_edits():
    """{(entry_id, field): [(op, value), ...]} for c_gameCatalogEffect edits, in lib order."""
    edits = {}
    for e in P.parse_edits():
        if e["kind"] != "Effect":
            continue
        edits.setdefault((e["entry"], e["field"]), []).append((e["op"], e["value"]))
    return edits


def resolve_effect_field(eid, field, pp_edits):
    """Resolve an effect field's PLAYER-VISIBLE value = vanilla base (parent-chain + merge,
    via preview.resolve_base) then every per-player op stacked in lib order. Returns a float
    or None (field absent everywhere → engine default, treated as 0 by the caller for bonuses).

    NB the per-player edit is keyed to the id it NAMES. A per-player edit on the PARENT id
    (e.g. JavelinMissileLaunchersDamage.Amount=35) reaches a no-Amount child THROUGH catalog
    inheritance at read time (the GAME-confirmed Thor precedent in docs/learnings.md), so when
    a child inherits a field, we resolve the field on the *id whose value the engine reads* —
    which is the nearest ancestor that DEFINES it. We therefore stack per-player edits found on
    ANY id in the resolve chain (the named id + its ancestors) for that field."""
    base, exists = P.resolve_base("Effect", eid, field)
    val = None
    if base is not None:
        try:
            val = float(base)
        except (TypeError, ValueError):
            val = None
    # Apply per-player edits: the named id first, then walk ancestors for an edit on the same
    # field (inheritance means a parent-targeted Set is what the engine reads for the child).
    for cid in _resolve_chain("Effect", eid):
        for op, v in pp_edits.get((cid, field), []):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if op == "Set":
                val = fv
            elif op == "Add" and val is not None:
                val += fv
            elif op == "Subtract" and val is not None:
                val -= fv
            elif op == "Multiply" and val is not None:
                val *= fv
    return val, exists


def _resolve_chain(kind, eid, _seen=None):
    """The id + its parent= ancestors (nearest first), across merge layers — the chain the
    engine reads a field through. Mirrors preview.resolve_base's parent walk."""
    if _seen is None:
        _seen = set()
    if eid in _seen:
        return []
    _seen.add(eid)
    chain = [eid]
    elems = P._find_elems(kind, eid)
    parent = P._parent_of(elems)
    if parent:
        chain += _resolve_chain(kind, parent, _seen)
    return chain


def attribute_bonuses(eid, pp_edits):
    """{attr: float} — the resolved AttributeBonus map for an effect, merging the parent chain
    (a child's own AttributeBonus[attr] overrides the parent's; an attr only on the parent is
    inherited) then applying any per-player edits. An attr absent everywhere is omitted (= 0)."""
    bonuses = {}
    # Walk from the FARTHEST ancestor to the named id so nearer definitions override.
    for cid in reversed(_resolve_chain("Effect", eid)):
        for el in P._find_elems("Effect", cid):
            for ab in el.findall("AttributeBonus"):
                attr = ab.get("index")
                v = ab.get("value")
                if attr is None or v is None:
                    continue
                try:
                    bonuses[attr] = float(v)
                except ValueError:
                    pass
    # Per-player AttributeBonus[attr] edits are a documented NO-OP (indexed-array element on an
    # effect — preview classify() flags them NOOP), so they never change the player's value and
    # we deliberately do NOT apply them. (If one ever existed it'd be a CHECK8 failure already.)
    return {a: v for a, v in bonuses.items() if v != 0.0}


# ---------------------------------------------------------------------------------------
# Reroute discovery. Find every static reroute of a weapon <Effect> / missile ImpactEffect to
# a *WoLU(Set) clone, and derive (panel-effect id, player-fired clone id) for each.
# ---------------------------------------------------------------------------------------
def weapon_reroutes():
    """[(weapon_id, panel_effect_id, our_effect_target)] for each of OUR weapon <Effect> overrides.

    panel_effect_id = the weapon's DisplayEffect if the VANILLA weapon declares one, else our
    reroute target (when there's no DisplayEffect the panel falls back to <Effect>, which we
    rerouted — so the panel then reads our clone directly, e.g. WreckingCrewAssault)."""
    out = []
    for w in our_catalog("WeaponData.xml"):
        if w.tag not in ("CWeaponLegacy", "CWeaponStrafe"):
            continue
        eff = w.find("Effect")
        if eff is None or not eff.get("value"):
            continue
        wid = w.get("id")
        target = eff.get("value")
        # Vanilla DisplayEffect (the panel id) — resolve across the merge layers + parent chain.
        disp = _weapon_display_effect(wid)
        panel = disp if disp else target
        out.append((wid, panel, target))
    return out


def missile_impact_reroutes():
    """[(missile_id, panel_effect_id, our_impact_target)] for each of OUR CEffectLaunchMissile
    ImpactEffect overrides on a VANILLA missile id (skip our own brand-new *WoLU launch effects,
    which are new abilities with no panel divergence — they carry their own DisplayEffect-less
    weapon). The panel id is the FIRING weapon's EFFECTIVE (merged) DisplayEffect — so once a
    fix repoints that weapon's DisplayEffect, the check sees the new panel id and passes."""
    out = []
    for e in our_catalog("EffectData.xml"):
        if e.tag != "CEffectLaunchMissile":
            continue
        mid = e.get("id")
        # Only a reroute of a VANILLA missile id matters (our own *WoLU missiles are new abilities).
        if mid.endswith("WoLU"):
            continue
        imp = e.find("ImpactEffect")
        if imp is None or not imp.get("value"):
            continue
        target = imp.get("value")
        # The panel reads the FIRING weapon's DisplayEffect. Identify that weapon by matching the
        # missile's VANILLA ImpactEffect (the damage id the panel originally names) to a weapon
        # whose vanilla DisplayEffect equals it, then resolve that weapon's EFFECTIVE DisplayEffect.
        vanilla_impact = _missile_vanilla_impact(mid)
        panel = _firing_weapon_display_effect(vanilla_impact) if vanilla_impact else None
        out.append((mid, panel, target))
    return out


def _weapon_display_effect(wid):
    """Resolve a weapon's EFFECTIVE DisplayEffect (panel id), merge order = reference layers then
    OUR override LAST (so a repointed DisplayEffect on our layer wins). None if no layer sets it
    (the caller then falls back to <Effect>)."""
    de = None
    for root in list(_ref_weapon_roots()) + [our_catalog("WeaponData.xml")]:
        for el in root:
            if el.tag in ("CWeaponLegacy", "CWeaponStrafe") and el.get("id") == wid:
                d = el.find("DisplayEffect")
                if d is not None and d.get("value"):
                    de = d.get("value")   # later layer wins
    return de


def _missile_vanilla_impact(mid):
    """The VANILLA (reference) ImpactEffect of a missile id (our override changed it, so read the
    reference layer) — the damage id the panel originally names for the firing weapon."""
    for root in _ref_effect_roots():
        for el in root:
            if el.tag == "CEffectLaunchMissile" and el.get("id") == mid:
                imp = el.find("ImpactEffect")
                if imp is not None and imp.get("value"):
                    return imp.get("value")
    return None


def _firing_weapon_display_effect(vanilla_impact):
    """Find the weapon whose VANILLA DisplayEffect == the missile's vanilla ImpactEffect (i.e. the
    weapon that fires this missile and whose panel names this damage), then return that weapon's
    EFFECTIVE (merged, our-override-last) DisplayEffect. Falls back to the vanilla impact id if no
    weapon is found (so the comparison still runs against the original panel id)."""
    for root in _ref_weapon_roots():
        for el in root:
            if el.tag in ("CWeaponLegacy", "CWeaponStrafe"):
                d = el.find("DisplayEffect")
                if d is not None and d.get("value") == vanilla_impact:
                    return _weapon_display_effect(el.get("id"))
    return vanilla_impact


def _ref_weapon_roots():
    for src in P.CATALOGS:
        p = os.path.join(REF, src, "WeaponData.xml")
        if os.path.exists(p):
            try:
                yield ET.parse(p).getroot()
            except ET.ParseError:
                continue


def _ref_effect_roots():
    for src in P.CATALOGS:
        p = os.path.join(REF, src, "EffectData.xml")
        if os.path.exists(p):
            try:
                yield ET.parse(p).getroot()
            except ET.ParseError:
                continue


def player_fired_child(target):
    """Given a reroute target (a *WoLU effect id), return the id of the DAMAGE effect the
    PLAYER actually fires (what the panel must match), or None when the reroute adds no damage
    clone (so the panel can't diverge):
      * a CEffectSet → its member that is a CEffectDamage gated by WoLUHasFlag (the buffed
        branch — the Shaped-Blast pattern). A set whose members are the unchanged vanilla
        DELIVERY effect + a non-damage apply-behavior (the Wraith trigger-override pattern)
        has NO damage clone → return None (the real damage stays the vanilla effect the panel
        already shows).
      * a CEffectDamage directly (un-gated player-exclusive merc clone) → itself.
      * anything else (a launch/apply effect) → None (no damage divergence)."""
    el = _our_effect(target)
    if el is None:
        return target  # not ours / can't introspect — treat the target as the fired id
    if el.tag == "CEffectDamage":
        return target  # a bare damage clone (e.g. WreckingCrewAssaultWoLU) — fired directly
    if el.tag == "CEffectSet":
        # The player fires the set member that is a DAMAGE clone gated by WoLUHasFlag. A
        # non-damage gated member (e.g. WoLUWraithTriggerOverrideApply, a CEffectApplyBehavior)
        # is NOT the damage path — skip it. If no flag-gated DAMAGE clone exists, the set wraps
        # the vanilla delivery (Wraith pattern) → no panel divergence.
        for m in (mm.get("value") for mm in el.findall("EffectArray") if mm.get("value")):
            me = _our_effect(m)
            if me is not None and me.tag == "CEffectDamage" and _has_validator(me, "WoLUHasFlag"):
                return m
        return None
    return None  # launch/apply/etc — no damage clone, nothing for the panel to diverge from


def _our_effect(eid):
    for e in our_catalog("EffectData.xml"):
        if e.get("id") == eid:
            return e
    return None


def _has_validator(el, vid):
    return any(v.get("value") == vid for v in el.findall("ValidatorArray"))


def _fmt(x):
    if x is None:
        return "(unset/0)"
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x)


def _bonus_str(b):
    return "{" + ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(b.items())) + "}" if b else "{}"


# ---------------------------------------------------------------------------------------
def main():
    ref_present = os.path.exists(os.path.join(REF, "mods", "liberty.sc2mod", "WeaponData.xml"))
    pp_edits = per_player_effect_edits()

    reroutes = []  # (label, weapon/missile id, panel_id, player_clone_id)
    for wid, panel, target in weapon_reroutes():
        reroutes.append(("weapon", wid, panel, player_fired_child(target)))
    for mid, panel, target in missile_impact_reroutes():
        reroutes.append(("missile", mid, panel, player_fired_child(target)))

    print(f"check_panel_damage: {len(reroutes)} rerouted weapon/missile(s) found.")
    for kind, wid, panel, clone in reroutes:
        print(f"  · [{kind}] {wid}: panel reads '{panel}', player fires "
              f"'{clone if clone else '(vanilla delivery — no damage clone)'}'")

    if not ref_present:
        print("\ncheck_panel_damage: reference dump (mods/_reference/) absent — skipping the "
              "numeric panel↔actual comparison (runs in the local pre-commit gate where the "
              "dump exists). Reroute map printed above.")
        return 0

    fails = []
    checked = 0
    for kind, wid, panel_id, clone_id in reroutes:
        if clone_id is None:
            continue  # wraps vanilla delivery → no damage clone → no divergence by construction
        if panel_id is None:
            fails.append(f"[{kind}] {wid}: could not resolve the panel-effect id (no DisplayEffect "
                         f"and no Effect fallback) — verify the weapon/missile def.")
            continue
        checked += 1
        p_amt, p_exists = resolve_effect_field(panel_id, "Amount", pp_edits)
        a_amt, a_exists = resolve_effect_field(clone_id, "Amount", pp_edits)
        p_bonus = attribute_bonuses(panel_id, pp_edits)
        a_bonus = attribute_bonuses(clone_id, pp_edits)

        if not p_exists:
            fails.append(f"[{kind}] {wid}: panel effect '{panel_id}' resolves to no catalog entry "
                         f"(typo?). Verify the DisplayEffect/Effect id letter-by-letter.")
            continue
        if not a_exists:
            fails.append(f"[{kind}] {wid}: player clone '{clone_id}' resolves to no catalog entry "
                         f"(typo?). Verify the reroute target id.")
            continue

        diverging = []
        # Amount (None == engine default; compare as 0 when one side is unset but the other isn't)
        pa = p_amt if p_amt is not None else 0.0
        aa = a_amt if a_amt is not None else 0.0
        if pa != aa:
            diverging.append(f"Amount (panel {_fmt(p_amt)} vs actual {_fmt(a_amt)})")
        # AttributeBonus map — every attr present on either side must match.
        for attr in sorted(set(p_bonus) | set(a_bonus)):
            pv = p_bonus.get(attr, 0.0)
            av = a_bonus.get(attr, 0.0)
            if pv != av:
                diverging.append(f"AttributeBonus[{attr}] (panel {_fmt(pv)} vs actual {_fmt(av)})")

        if diverging:
            fails.append(
                f"[{kind}] {wid}: PANEL ≠ ACTUAL — the unit-info damage panel reads '{panel_id}' "
                f"(Amount {_fmt(p_amt)}, bonuses {_bonus_str(p_bonus)}) but the player FIRES "
                f"'{clone_id}' (Amount {_fmt(a_amt)}, bonuses {_bonus_str(a_bonus)}). "
                f"Diverging: {'; '.join(diverging)}. "
                f"Fix: repoint the weapon's <DisplayEffect> to '{clone_id}' so the panel shows the "
                f"player's fired value (a STATIC DisplayEffect change is display-only → rule-9-safe).")

    if fails:
        print("\nCHECK11 FAIL — the damage panel shows a different number than the player fires:")
        for f in fails:
            print(f"  ✗ {f}")
        print(f"\nCHECK11: {len(fails)} panel↔actual divergence(s) across {checked} checked reroute(s) — FAIL.")
        return 1

    print(f"\nCHECK11: ok — every rerouted weapon's panel number equals the player's fired number "
          f"({checked} reroute(s) with a damage clone checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
