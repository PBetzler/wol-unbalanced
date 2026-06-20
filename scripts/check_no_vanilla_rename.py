#!/usr/bin/env python3
"""CHECK12 — never RE-IDENTIFY a vanilla unit (the "stop touching core units" gate).

THE bug class this enforces (cost a session + owner trust): a change RENAMES or
re-identifies a VANILLA unit — e.g. a throwaway diagnostic `Unit/Name/Marine=Marine
[WoLU LOADED]`. The project's standing discipline is to touch ONLY the player's stats at
runtime and to define NEW player-exclusive clones; vanilla unit IDENTITY (its display name,
and never its TYPE id) is off-limits. Mission/campaign triggers and objective/dialog text key
off unit identity, so renaming a core unit is gratuitous risk for zero benefit — and exactly
the kind of "I forgot what earlier sessions knew" regression we want a MACHINE to catch, not
a memory.

What's allowed vs flagged:
  * ALLOWED — naming our OWN player-exclusive clones (the elite mercs etc.): `Unit/Name/
    MercMedic=Skibi's Angels`. Those ids do NOT exist in the vanilla reference catalogs, so
    they're ours to name.
  * FLAGGED — overriding the name of a VANILLA unit (any id present in the reference
    catalogs: Marine, SCV, Medic, Battlecruiser, …), via either
      (1) a `Unit/Name/<vanilla-id>=` line in our GameStrings.txt, or
      (2) a `<Name .../>` field inside a `<CUnit id="<vanilla-id>">` in our static UnitData.

Add a genuinely-intended exception to EXCEPTIONS below with a one-line reason (there are
none today, and there should almost never be one).

Runs in the pre-commit gate + CI alongside CHECK1-11.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "mods", "_reference")
MOD = os.path.join(ROOT, "src", "mod")
GAMESTRINGS = os.path.join(MOD, "enUS.SC2Data", "LocalizedData", "GameStrings.txt")
UNITDATA = os.path.join(MOD, "Base.SC2Data", "GameData", "UnitData.xml")

# Vanilla-unit-id sources (the catalogs the player actually plays against).
REF_UNITDATA = [
    os.path.join(REF, "liberty.sc2mod", "UnitData.xml"),
    os.path.join(REF, "campaigns", "liberty.sc2campaign", "UnitData.xml"),
    os.path.join(REF, "campaigns", "libertystory.sc2campaign", "UnitData.xml"),
]

# Deliberate, reviewed exceptions: vanilla unit id -> reason. Keep this EMPTY unless an owner
# decision genuinely requires renaming a vanilla unit (and then say why here).
EXCEPTIONS: dict[str, str] = {}


def vanilla_unit_ids() -> set[str]:
    ids: set[str] = set()
    for path in REF_UNITDATA:
        if not os.path.exists(path):
            continue
        for m in re.finditer(r'<CUnit\s+id="([^"]+)"', open(path, encoding="utf-8").read()):
            ids.add(m.group(1))
    return ids


def gamestrings_unit_name_ids() -> list[str]:
    """Unit ids that our GameStrings overrides a display Name for."""
    if not os.path.exists(GAMESTRINGS):
        return []
    out = []
    for line in open(GAMESTRINGS, encoding="utf-8-sig").read().splitlines():
        m = re.match(r"^Unit/Name/([^=]+)=", line)
        if m:
            out.append(m.group(1).strip())
    return out


def xml_named_unit_ids() -> list[str]:
    """Unit ids our static UnitData gives an explicit <Name> field (renames in XML)."""
    if not os.path.exists(UNITDATA):
        return []
    out = []
    root = ET.parse(UNITDATA).getroot()
    for cunit in root.findall("CUnit"):
        uid = cunit.get("id")
        if uid and cunit.find("Name") is not None:
            out.append(uid)
    return out


def main() -> int:
    if not any(os.path.exists(p) for p in REF_UNITDATA):
        print("CHECK12: SKIP — reference catalogs not present (mods/_reference). "
              "Bring them over to enable the vanilla-rename guard.")
        return 0
    vanilla = vanilla_unit_ids()
    fails = []
    for uid in gamestrings_unit_name_ids():
        if uid in vanilla and uid not in EXCEPTIONS:
            fails.append((uid, "GameStrings Unit/Name/ override"))
    for uid in xml_named_unit_ids():
        if uid in vanilla and uid not in EXCEPTIONS:
            fails.append((uid, "static UnitData <Name> field"))

    if fails:
        print("\nCHECK12 FAIL — a VANILLA unit is being re-identified (renamed). Vanilla unit "
              "identity is off-limits (mission/campaign triggers + objective text key off it); "
              "rename only our own player-exclusive clones, never core units:")
        for uid, via in sorted(set(fails)):
            print(f"  - {uid}: renamed via {via}")
        print("\n  Fix: drop the rename. If this is a genuine owner-approved exception, add it to "
              "EXCEPTIONS in scripts/check_no_vanilla_rename.py with a reason.")
        print(f"\nCHECK12: {len(set(fails))} vanilla-unit rename(s) — FAIL.")
        return 1

    n = len(gamestrings_unit_name_ids()) + len(xml_named_unit_ids())
    print(f"CHECK12: ok — {n} unit-name override(s) checked; all target our own clones, "
          "no vanilla unit re-identified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
