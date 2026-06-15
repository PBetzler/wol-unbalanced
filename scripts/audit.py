#!/usr/bin/env python3
"""Static catalog/actor consistency audit — the closest thing to "automatic debugging"
we can do without running SC2 (there is no SC2 MCP / headless mode).

It can't observe the running game, but it catches the *structural* bug classes that have
actually bitten us — most of which were "referenced an id/path that doesn't exist" or a
"wrong command-card index" — BEFORE a build ships. Run before build (with galaxy_lint.py)
and in the pre-commit hook + CI.

  CHECK 1 (FAIL) — Actor consistency. Every player-exclusive unit we DEFINE (a `parent=`
    clone) needs a CActorUnit that inherits a GenericUnit* base AND declares `unitName=`,
    else it renders as a sphere with no attack visuals (the v0.2.0 bug).

  CHECK 2 (FAIL) — Calldown wiring. Every unit summoned by SummonMercenaries must be a
    defined CUnit, have an actor, and be TechTreeUnitAllow'd in the galaxy lib.

  CHECK 3 (FAIL) — parent= resolution. Every `parent=` on one of our data clones must
    resolve to a real id (ours or the reference catalogs). Catches typo'd / invented
    parents (e.g. a "Valkyrie"/"Liberator" that doesn't exist in WoL).

  CHECK 4 (FAIL) — Effect wiring. A CAbilEffect*/CWeaponLegacy clone with NO <Effect> and
    no parent that supplies one RE-DEFAULTS to its own id (nonexistent) and does nothing
    (the HealWoLU bug). Also: any explicit <Effect value=> must resolve.

  CHECK 5 (WARN) — Command-card sanity on OUR buttons (merge-aware). For each LayoutButton
    WE add/override, after merging with the reference catalogs: an action AbilCmd on a
    Type=Passive button never fires (the Marauder bug); an AbilCmd whose ability isn't on
    the unit drives nothing; two of OUR buttons in the same cell collide.

  INFO — base-CASC asset references (Model/Portrait/Icon tokens + .m3/.dds paths) that we
    cannot verify locally. These are NOT proof of correctness — they MUST be confirmed in
    game by the owner before a fix is called done. (A heart portrait / sphere = one is wrong.)

Exit non-zero on any FAIL.
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GD = os.path.join(ROOT, "src", "mod", "Base.SC2Data", "GameData")
GALAXY = os.path.join(ROOT, "src", "mod", "Base.SC2Data", "LibWoLUnbalanced.galaxy")
REF = os.path.join(ROOT, "mods", "_reference")
REF_DIRS = [
    "mods/liberty.sc2mod",
    "mods/mods/liberty.sc2mod",
    "campaigns/liberty.sc2campaign",
    "campaigns/libertystory.sc2campaign",
    "mods/novastoryassets.sc2mod/base.sc2data/GameData",
]
# The catalog layers actually loaded by a WoL campaign map, in merge order. Used for the
# merge-aware card linter (NCO/novastoryassets is NOT loaded by WoL maps, so it's excluded).
WOL_UNIT_LAYERS = [
    "mods/liberty.sc2mod/UnitData.xml",
    "campaigns/liberty.sc2campaign/UnitData.xml",
    "campaigns/libertystory.sc2campaign/UnitData.xml",
]
# Built-in command ids that are always available (not unit-specific abilities), so a button
# pointing at them is fine even if they're not in the unit's AbilArray.
GENERIC_CMDS = {"move", "stop", "attack", "BuildInProgress", "que5CancelToSelection",
                "RallyCommand", "Rally", "255", "Cancel"}
# Parents that live in core.sc2mod (NOT in the WoL reference dump) and are legitimately used.
# Add to this set deliberately when a new core template is referenced — the audit failing on
# an unknown parent is the POINT (it forces a conscious "is this real?" check); blanket-
# skipping a prefix would re-open the door to guesses.
CORE_TEMPLATE_PARENTS = {"DU_WEAP", "DU_WEAP_SPLASH", "DU_WEAP_MISSILE"}

fails: list[str] = []
warns: list[str] = []
infos: list[str] = []


def our_catalog(name):
    path = os.path.join(GD, name)
    return ET.parse(path).getroot() if os.path.exists(path) else ET.Element("Catalog")


def ref_ids():
    """Every id defined anywhere in the reference catalogs (gitignored dump)."""
    ids = set()
    for d in REF_DIRS:
        base = os.path.join(REF, d)
        for f in glob.glob(os.path.join(base, "**", "*.xml"), recursive=True) + glob.glob(os.path.join(base, "*.xml")):
            try:
                root = ET.parse(f).getroot()
            except ET.ParseError:
                continue
            for el in root:
                if el.get("id"):
                    ids.add(el.get("id"))
    return ids


def our_ids():
    ids = set()
    for fn in os.listdir(GD):
        if fn.endswith(".xml"):
            for el in our_catalog(fn):
                if el.get("id"):
                    ids.add(el.get("id"))
    return ids


def fval(el, name):
    """Attribute form OR <Name value=...> child form."""
    if el.get(name) is not None:
        return el.get(name)
    c = el.find(name)
    return c.get("value") if c is not None else None


def index_effect_classes():
    """id -> element for CAbilEffect*/CWeapon* across our XML + the WoL reference layers,
    so CHECK 4 can walk the parent chain for an <Effect>."""
    want = {"CAbilEffectTarget", "CAbilEffectInstant", "CWeaponLegacy", "CWeaponStrafe"}
    idx = {}
    files = [os.path.join(GD, "AbilData.xml"), os.path.join(GD, "WeaponData.xml")]
    for d in REF_DIRS:
        for nm in ("AbilData.xml", "WeaponData.xml"):
            p = os.path.join(REF, d, nm)
            if os.path.exists(p):
                files.append(p)
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except (ET.ParseError, FileNotFoundError):
            continue
        for el in root:
            if el.tag in want and el.get("id") and el.get("id") not in idx:
                idx[el.get("id")] = el  # earlier files (ours first) win for the lookup
    return idx


def merge_unit_card(uid):
    """Return (abil_links:set, buttons:{index:{Face,AbilCmd,Row,Col,Type}}) for a unit,
    merging the WoL reference layers + our mod, resolving parent=. Mirrors SC2 array merge
    (explicit index overrides; index-less appends to the end; removed=1 tombstones)."""
    layers = []
    for rel in WOL_UNIT_LAYERS:
        p = os.path.join(REF, rel)
        layers.append(ET.parse(p).getroot() if os.path.exists(p) else ET.Element("Catalog"))
    layers.append(our_catalog("UnitData.xml"))

    def find(u):
        out = []
        for root in layers:
            for el in root:
                if el.tag == "CUnit" and el.get("id") == u:
                    out.append(el)
        return out

    def resolve(u, seen):
        if u in seen:
            return set(), {}
        seen.add(u)
        elems = find(u)
        parent = next((e.get("parent") for e in elems if e.get("parent")), None)
        abils, btns = (resolve(parent, seen) if parent else (set(), {}))
        abils = set(abils)
        for e in elems:
            ai = 0
            for a in e.findall("AbilArray"):
                link = a.get("Link")
                if a.get("removed") == "1":
                    abils.discard(link)
                elif link:
                    abils.add(link)
                ai += 1
            for card in e.findall("CardLayouts"):
                if (card.get("index") or "0") != "0":
                    continue
                for b in card.findall("LayoutButtons"):
                    i = b.get("index")
                    i = int(i) if i is not None else (max(btns) + 1 if btns else 0)
                    if b.get("removed") == "1":
                        btns.pop(i, None)
                        continue
                    cur = btns.get(i, {})
                    for k, nm in (("Face", "Face"), ("AbilCmd", "AbilCmd"),
                                  ("Row", "Row"), ("Col", "Column"), ("Type", "Type")):
                        v = fval(b, nm)
                        if v is not None:
                            cur[k] = v
                    btns[i] = cur
        return abils, btns

    return resolve(uid, set())


def main():
    units = our_catalog("UnitData.xml")
    actors = our_catalog("ActorData.xml")
    abils = our_catalog("AbilData.xml")

    our_actors = {}
    actor_models = {}
    for a in actors:
        if a.tag == "CActorUnit" and a.get("id"):
            our_actors[a.get("id")] = (a.get("parent"), a.get("unitName"))
            actor_models[a.get("id")] = {sub.get("value") for sub in a
                                         if sub.tag in ("Model", "PortraitModel") and sub.get("value")}

    our_clone_units = {u.get("id"): u for u in units
                       if u.tag == "CUnit" and u.get("id") and u.get("parent") is not None}

    # CHECK 1 — actor consistency.
    for uid in sorted(our_clone_units):
        if uid not in our_actors:
            fails.append(f"CHECK1 actor-missing: clone unit '{uid}' has no CActorUnit -> sphere, no model.")
            continue
        parent, unitname = our_actors[uid]
        if not parent or "GenericUnit" not in parent:
            fails.append(f"CHECK1 actor-parent: CActorUnit '{uid}' must inherit a GenericUnit* base (got {parent!r}).")
        if unitname != uid:
            fails.append(f"CHECK1 actor-unitname: CActorUnit '{uid}' needs unitName=\"{uid}\" (got {unitname!r}).")

    # CHECK 2 — every SummonMercenaries-trained Merc* unit is defined, actored, allowed.
    galaxy = open(GALAXY).read() if os.path.exists(GALAXY) else ""
    defined_unit_ids = {u.get("id") for u in units if u.tag == "CUnit" and u.get("id")}
    for ab in abils.iter("CAbilTrain"):
        if ab.get("id") != "SummonMercenaries":
            continue
        for info in ab.findall("InfoArray"):
            for ue in info.findall("Unit"):
                mu = ue.get("value")
                if not mu or not mu.startswith("Merc"):
                    continue
                if mu not in defined_unit_ids:
                    fails.append(f"CHECK2 calldown-unit: {info.get('index')} trains '{mu}' but no CUnit defines it.")
                if mu not in our_actors:
                    fails.append(f"CHECK2 calldown-actor: calldown unit '{mu}' has no CActorUnit.")
                if f'"{mu}"' not in galaxy:
                    fails.append(f"CHECK2 calldown-allow: '{mu}' is never TechTreeUnitAllow'd -> uncallable.")

    known = ref_ids() | our_ids()

    # CHECK 3 — parent= resolution on our data clones (skip actors: their parents are
    # base-CASC GenericUnit*, which CHECK 1 already validates and the ref dump lacks).
    for fn in ("AbilData.xml", "WeaponData.xml", "BehaviorData.xml", "EffectData.xml",
               "UnitData.xml", "ValidatorData.xml", "UpgradeData.xml"):
        for el in our_catalog(fn):
            p = el.get("parent")
            if p and p not in known and p not in CORE_TEMPLATE_PARENTS:
                fails.append(f"CHECK3 parent-missing: {el.tag} '{el.get('id')}' parent='{p}' resolves nowhere "
                             f"(typo, or an id that doesn't exist in WoL? if it's a real core.sc2mod "
                             f"template, add it to CORE_TEMPLATE_PARENTS).")

    # CHECK 4 — Effect wiring (the clone-default trap + explicit-Effect resolution).
    eidx = index_effect_classes()
    for fn in ("AbilData.xml", "WeaponData.xml"):
        for el in our_catalog(fn):
            if el.tag not in ("CAbilEffectTarget", "CAbilEffectInstant", "CWeaponLegacy", "CWeaponStrafe"):
                continue
            eff = el.find("Effect")
            if eff is not None:
                ev = eff.get("value")
                if ev and ev not in known:
                    fails.append(f"CHECK4 effect-missing: {el.tag} '{el.get('id')}' Effect='{ev}' resolves nowhere.")
                continue
            # No own <Effect>: walk the parent chain for one.
            par, seen, supplied = el.get("parent"), set(), False
            while par and par not in seen:
                seen.add(par)
                pe = eidx.get(par)
                if pe is None:
                    break
                if pe.find("Effect") is not None:
                    supplied = True
                    break
                par = pe.get("parent")
            if not supplied:
                fails.append(f"CHECK4 effect-default-trap: {el.tag} '{el.get('id')}' has no <Effect> and no parent "
                             f"supplies one -> the engine defaults it to its own id (nonexistent) and it does "
                             f"NOTHING. Add <Effect index=\"0\" value=\"...\">.")

    # CHECK 5 — command-card sanity on OUR buttons (merge-aware).
    for u in units:
        if u.tag != "CUnit" or not u.get("id"):
            continue
        our_cells, has_our_button = {}, False
        for card in u.findall("CardLayouts"):
            if (card.get("index") or "0") != "0":
                continue
            if card.findall("LayoutButtons"):
                has_our_button = True
        if not has_our_button:
            continue
        abil_links, merged = merge_unit_card(u.get("id"))
        # Re-scan OUR raw button defs to know which indices/cells WE touched.
        for card in u.findall("CardLayouts"):
            if (card.get("index") or "0") != "0":
                continue
            for b in card.findall("LayoutButtons"):
                if b.get("removed") == "1":
                    continue
                idx = b.get("index")
                ac = fval(b, "AbilCmd")
                typ = fval(b, "Type")
                # use the MERGED view for this index (inherits Face/Type if we only set AbilCmd)
                m = merged.get(int(idx)) if idx is not None and int(idx) in merged else {}
                eff_type = typ or m.get("Type")
                eff_ac = ac or m.get("AbilCmd")
                if not eff_ac or eff_ac in ("255", "255,0", "255,3"):
                    pass  # passive placeholder, fine
                else:
                    abil = eff_ac.split(",")[0]
                    if eff_type == "Passive":
                        warns.append(f"CHECK5 passive-action: {u.get('id')} button[{idx}] is Type=Passive but its "
                                     f"AbilCmd='{eff_ac}' is an action -> the button shows but never fires "
                                     f"(append a real Type=AbilCmd button instead).")
                    if abil not in abil_links and abil not in GENERIC_CMDS:
                        warns.append(f"CHECK5 button-no-abil: {u.get('id')} button[{idx}] AbilCmd='{eff_ac}' but "
                                     f"ability '{abil}' is not on the unit (not in its merged AbilArray) -> "
                                     f"button drives nothing.")
                # collision: another OF OUR buttons on this unit at the same cell
                cell = (fval(b, "Row") or m.get("Row"), fval(b, "Column") or m.get("Col"))
                if cell != (None, None):
                    if cell in our_cells and eff_type != "Passive":
                        warns.append(f"CHECK5 cell-collision: {u.get('id')} buttons [{our_cells[cell]}] and [{idx}] "
                                     f"both at cell {cell[0]},{cell[1]}.")
                    our_cells[cell] = idx

    # INFO — base-CASC asset tokens we can't verify locally.
    refs = ref_ids()
    our_model_ids = {m.get("id") for m in our_catalog("ModelData.xml") if m.tag == "CModel" and m.get("id")}
    resolvable = defined_unit_ids | set(our_actors) | our_model_ids | refs
    casc = sorted({t for toks in actor_models.values() for t in toks if t not in resolvable})
    for t in casc:
        infos.append(f"base-CASC model/portrait token (UNVERIFIED — confirm in game): {t}")

    quiet = "--quiet" in sys.argv
    if not quiet:
        for i in infos:
            print(f"INFO {i}")
        for w in warns:
            print(f"WARN {w}")
        if infos or warns:
            print()
    if fails:
        for f in fails:
            print(f"FAIL {f}")
        print(f"\naudit: {len(fails)} failure(s), {len(warns)} warning(s).")
        sys.exit(1)
    print(f"audit: ok ({len(our_clone_units)} clone units, {len(warns)} warning(s), "
          f"{len(infos)} unverified CASC token(s)).")


if __name__ == "__main__":
    main()
