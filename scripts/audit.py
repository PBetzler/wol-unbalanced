#!/usr/bin/env python3
"""Static catalog/actor consistency audit — the closest thing to "automatic debugging"
we can do without running SC2 (there is no SC2 MCP / headless mode).

It can't observe the running game, but it catches the *structural* bug classes that
have actually bitten us, before a build ships:

  CHECK 1 (FAIL) — Actor consistency. Every player-exclusive unit we DEFINE (a `parent=`
    clone, e.g. the Merc* mercs) needs a CActorUnit that inherits a GenericUnit* base AND
    declares `unitName=` — otherwise it renders as a sphere with no attack visuals. This is
    the exact v0.2.0 bug.

  CHECK 2 (FAIL) — Calldown wiring. Every unit summoned by SummonMercenaries (InfoArray
    Unit="X") must be a defined CUnit, have an actor, and be allow-listed for the player
    in the galaxy lib (TechTreeUnitAllow) — else the calldown is dead/uncallable.

  INFO — CASC-dependent references. Model/PortraitModel/parent tokens that resolve to
    neither our static XML nor the reference catalogs are base-CASC ids we CANNOT verify
    locally. They're printed as the "verify in game" list (a sphere = one of these is wrong).

Exit non-zero on any FAIL. Run before build (galaxy_lint.py + this), and in CI.
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

fails: list[str] = []
infos: list[str] = []


def our_catalog(name):
    path = os.path.join(GD, name)
    return ET.parse(path).getroot() if os.path.exists(path) else ET.Element("Catalog")


def ref_ids():
    """All ids defined anywhere in the reference catalogs (gitignored dump)."""
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


def main():
    units = our_catalog("UnitData.xml")
    actors = our_catalog("ActorData.xml")
    abils = our_catalog("AbilData.xml")

    # Actors we define: id -> (has_parent, unitName)
    our_actors = {}
    actor_models = {}  # id -> set of Model/PortraitModel tokens
    for a in actors:
        if a.tag == "CActorUnit" and a.get("id"):
            our_actors[a.get("id")] = (a.get("parent"), a.get("unitName"))
            toks = set()
            for sub in a:
                if sub.tag in ("Model", "PortraitModel") and sub.get("value"):
                    toks.add(sub.get("value"))
            actor_models[a.get("id")] = toks

    # Units we DEFINE that need an actor: `parent=` clones (genuinely new unit types).
    # A CUnit with no parent= is an OVERRIDE of an existing base unit (e.g. MercCompound
    # gets submenu buttons) — it already has the base's actor, so it's excluded.
    our_units = {}
    for u in units:
        if u.tag != "CUnit" or not u.get("id"):
            continue
        if u.get("parent") is not None:
            our_units[u.get("id")] = u

    # CHECK 1 — actor consistency.
    for uid in sorted(our_units):
        if uid not in our_actors:
            fails.append(f"CHECK1 actor-missing: unit '{uid}' (a clone/new unit) has no CActorUnit -> sphere, no model.")
            continue
        parent, unitname = our_actors[uid]
        if not parent or "GenericUnit" not in parent:
            fails.append(f"CHECK1 actor-parent: CActorUnit '{uid}' must inherit a GenericUnit* base (got parent={parent!r}) -> sphere.")
        if unitname != uid:
            fails.append(f"CHECK1 actor-unitname: CActorUnit '{uid}' needs unitName=\"{uid}\" (got {unitname!r}) -> wrong/empty identity.")

    # CHECK 2 — every SummonMercenaries-trained unit is defined, actored, and allowed.
    galaxy = open(GALAXY).read() if os.path.exists(GALAXY) else ""
    defined_unit_ids = {u.get("id") for u in units if u.tag == "CUnit" and u.get("id")}
    for ab in abils.iter("CAbilTrain"):
        if ab.get("id") != "SummonMercenaries":
            continue
        for info in ab.findall("InfoArray"):
            for ue in info.findall("Unit"):
                mu = ue.get("value")
                if not mu or not mu.startswith("Merc"):
                    continue  # vanilla mercs are base-defined
                if mu not in defined_unit_ids:
                    fails.append(f"CHECK2 calldown-unit: SummonMercenaries {info.get('index')} trains '{mu}' but no CUnit defines it.")
                if mu not in our_actors:
                    fails.append(f"CHECK2 calldown-actor: calldown unit '{mu}' has no CActorUnit.")
                if f'"{mu}"' not in galaxy:
                    fails.append(f"CHECK2 calldown-allow: calldown unit '{mu}' is never TechTreeUnitAllow'd in the galaxy lib -> may be uncallable.")

    # INFO — model/portrait tokens that are base-CASC (not in our XML, not in the ref dump).
    refs = ref_ids()
    our_ids = defined_unit_ids | set(our_actors)
    casc = set()
    for toks in actor_models.values():
        for t in toks:
            if t not in our_ids and t not in refs:
                casc.add(t)
    for t in sorted(casc):
        infos.append(f"base-CASC model/portrait token (verify renders in game): {t}")

    # Report
    quiet = "--quiet" in sys.argv
    if not quiet:
        for i in infos:
            print(f"INFO {i}")
        if infos:
            print()
    if fails:
        for f in fails:
            print(f"FAIL {f}")
        print(f"\naudit: {len(fails)} failure(s).")
        sys.exit(1)
    print(f"audit: ok ({len(our_units)} player units checked, {len(infos)} CASC token(s) flagged).")


if __name__ == "__main__":
    main()
