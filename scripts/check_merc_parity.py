#!/usr/bin/env python3
"""CHECK10 — merc/hero PARITY checker (the "how do we stop this from happening").

The recurring bug class: a merc / hero / unit-variant silently MISSES a per-player buff
its BASE unit has (Spartan Company missing Goliath upgrades, Death Heads missing cloak,
Hammer Securities missing super-stim, …). ROOT CAUSE: per-player edits live in two places
that are both keyed to BASE unit ids —

  (a) genlib `CatalogFieldValueModify` edits keyed to the base id (in
      LibWoLUnbalancedGen.galaxy), and
  (b) per-unit-type loops in the hand-written LibWoLUnbalanced.galaxy
      (`libWoLU_AddBehaviorToType` cloak/def-matrix/etc., `libWoLU_ToggleCloakOn`,
      `libWoLU_GraduateSiegeRange`),

— and NEITHER inherits to the counterpart automatically:

  * `parent=` ELITE mercs (MercMedic/MercReaper/MercHellion/MercThor/MercWraith/
    MercSeniorGhost) inherit the base unit's STATIC XML (abilities, cards, weapons, armor)
    but NOT the per-player (a) genlib edits or (b) galaxy loops.
  * STANDALONE mercs (WarPig/DevilDog/HammerSecurity/SpartanCompany/SiegeBreaker/
    HelsAngel*/DuskWing/DukesRevenge) and HEROES (Raynor*/Tychus*/Swann/Stetmann/Nova/
    Tosh/Odin) are separate unit ids — they inherit NOTHING.

So a buff keyed to a base id silently skips the merc/hero, and until this check nothing
caught it. CHECK10 enumerates, for each base unit, the FUNCTIONAL per-player buffs it gets
((a) genlib fields + (b) galaxy-loop memberships), then for each counterpart verifies the
SAME CLASS of buff is present (rule 4: mercs keep a % advantage, so VALUES differ — we check
PRESENCE, not value). Every un-excepted gap FAILS the gate.

SCOPE (deliberate — keeps false positives near zero; documented in the brief's report):
  * We check the two FUNCTIONAL dimensions where the real bugs lived: (a) genlib buff
    fields and (b) galaxy loops. We do NOT enforce the cosmetic WoLU *passive-display card
    faces* (`WoLUUpg*`/`CombatShield`/`ShapedHull`): those are DISPLAY-ONLY (AbilCmd=255,
    grant nothing — the buffs come from (a)+(b)), they're noisy to diff (vanilla campaign
    faces look identical to ours), and audit.py's #3-class check already guards that a face
    MATCHES the unit's capability. Card-face parity is a cosmetics-only nicety, not a buff
    gap — out of scope for a buff-parity gate.
  * Parity is by EFFECT CLASS, not literal id: a cloak loop counts whether the merc cloaks
    via `PersonalCloakingFree` or `SpectreCloakingFree`, and a cloak TOGGLE counts whether
    it uses `BansheeCloak` or `DuskWingBansheeCloakingField`. The CLASS map below collapses
    same-effect ids so a legitimate id difference isn't flagged.
  * COST fields (`CostResource[*]`, `Food`) are EXCLUDED from the functional field set: mercs
    are free unlimited CALLDOWN units (rule 6 — `SummonMercenaries` charges/cooldown zeroed
    in genlib), so reducing a calldown's resource cost is inert; heroes are map-PLACED, never
    trained, so cost edits never fire either. Cost parity is not a buff → not checked.

Run: python scripts/check_merc_parity.py   (exit non-zero on an un-excepted gap)
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
SRC = os.path.join(ROOT, "src", "mod", "Base.SC2Data")
GALAXY_GEN = os.path.join(SRC, "LibWoLUnbalancedGen.galaxy")
GALAXY_HAND = os.path.join(SRC, "LibWoLUnbalanced.galaxy")
GD = os.path.join(SRC, "GameData")
REF = os.path.join(ROOT, "mods", "_reference")
WOL_UNIT_LAYERS = [
    "mods/liberty.sc2mod/UnitData.xml",
    "campaigns/liberty.sc2campaign/UnitData.xml",
    "campaigns/libertystory.sc2campaign/UnitData.xml",
]

# ---------------------------------------------------------------------------------------
# BASE -> counterparts map. `kind` per counterpart: "parent" (elite merc, parent= clone —
# inherits static XML, needs (a)+(b)), or "standalone" (standalone merc / hero — inherits
# nothing). Resolve display↔id done (CLAUDE.md merc/hero id-map): Jackson's Revenge=DukesRevenge,
# Condor=MercHellion, Death Heads=MercReaper, Jotun=MercThor, Skibi's=MercMedic,
# Winged Nightmares=MercWraith, Senior Ghost=MercSeniorGhost.
# ---------------------------------------------------------------------------------------
COUNTERPARTS = {
    # base       : [(counterpart_id, kind), ...]
    "Marine":          [("WarPig", "standalone"), ("Raynor01", "standalone"),
                        ("RaynorCommando", "standalone"), ("Raynor", "standalone")],
    "Firebat":         [("DevilDog", "standalone"), ("TychusCommando", "standalone"),
                        ("TychusChaingun", "standalone")],
    "Marauder":        [("HammerSecurity", "standalone"), ("Swann", "standalone")],
    "Medic":           [("MercMedic", "parent"), ("Stetmann", "standalone")],
    "Goliath":         [("SpartanCompany", "standalone")],
    "SiegeTank":       [("SiegeBreaker", "standalone")],
    "SiegeTankSieged": [("SiegeBreakerSieged", "standalone")],
    "VikingFighter":   [("HelsAngelFighter", "standalone")],
    "VikingAssault":   [("HelsAngelAssault", "standalone")],
    "Banshee":         [("DuskWing", "standalone")],
    "Battlecruiser":   [("DukesRevenge", "standalone")],
    "Reaper":          [("MercReaper", "parent")],
    "Hellion":         [("MercHellion", "parent")],
    "Thor":            [("MercThor", "parent"), ("Odin", "standalone")],
    "Wraith":          [("MercWraith", "parent")],
    "Ghost":           [("MercSeniorGhost", "parent"), ("Nova", "standalone")],
    "Spectre":         [("Tosh", "standalone")],
}

# Genlib Unit-catalog fields that are COST (free-calldown / map-placed → inert) — EXCLUDED
# from the functional buff set so a missing cost-reduction isn't flagged as a gap.
COST_FIELDS = {"Food"}
COST_FIELD_RE = re.compile(r"^CostResource\[")

# Galaxy per-unit-type loop CLASSES (collapse same-effect ids so a legitimate id difference
# — e.g. PersonalCloakingFree vs SpectreCloakingFree — counts as the SAME parity dimension).
#   behavior id / cloak-toggle id -> the parity CLASS it satisfies.
LOOP_CLASS = {
    # permanent free cloak (the buff that makes the unit cloak for free)
    "Behavior:PersonalCloakingFree": "free-cloak",
    "Behavior:SpectreCloakingFree":  "free-cloak",
    # the UI cloak-toggle sync (any toggle id satisfies "cloak-toggle")
    "ToggleCloak:GhostCloak":                   "cloak-toggle",
    "ToggleCloak:BansheeCloak":                 "cloak-toggle",
    "ToggleCloak:WraithCloak":                  "cloak-toggle",
    "ToggleCloak:RogueGhostCloak":              "cloak-toggle",
    "ToggleCloak:DuskWingBansheeCloakingField": "cloak-toggle",
    # the rest map 1:1 to their own class
    "GraduateSiegeRange":            "graduate-siege-range",
    "Behavior:WoLUDefMatrixOnDamage":"defmatrix-on-damage",
    "Behavior:WoLUAdaptiveDefenses": "adaptive-defenses",
    "Behavior:WoLUPredatorCharge":   "predator-charge",
    # TechTreeUnitAllow is unlock-plumbing, not a buff — never a parity requirement (excluded below)
}
# Loop tags that are NOT buffs (plumbing) — never a parity requirement.
LOOP_PLUMBING = {"TechTreeUnitAllow"}


# ---------------------------------------------------------------------------------------
# INTENTIONAL-EXCEPTION ALLOWLIST. Each entry = (base, counterpart, what) -> one-line reason.
#   `what` is the missing item, prefixed by dimension:
#     "field:<Field>"   a genlib Unit field present on base but legitimately N/A on the cp
#     "loop:<class>"    a galaxy loop CLASS present on base but legitimately N/A on the cp
# A gap whose (base, counterpart, what) is in this dict is reported INFO (excused), not FAIL.
#
# NOTE: cost reductions (CostResource[*]/Food) are NOT listed here — they're filtered out of
# the functional field set wholesale by COST_FIELDS / COST_FIELD_RE (mercs are free calldowns,
# heroes are map-placed → cost is never paid), which is the single mechanism for that class.
# This dict is only for genuine per-pair FUNCTIONAL exceptions.
#
# DukesRevenge (Jackson's Revenge) note (not a checked dimension, kept for the audit record):
# it intentionally uses its OWN merc-specific ability clones (DukesRevengeYamatoWoLU /
# DukesRevengeMissilePodsWoLU / DukesRevengeDefensiveMatrixWoLU, static XML + autocast) instead
# of the base BC clones; its def-matrix loop (WoLUDefMatrixOnDamage) is present. No field gaps.
# ---------------------------------------------------------------------------------------
EXCEPTIONS = {
}


# ---------------------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------------------
def parse_genlib_unit_fields():
    """{unit_id: set(field)} — every per-player Unit-catalog CatalogFieldValueModify, keyed
    by entry id. (Only Unit-catalog edits are unit-keyed; weapon/effect edits are keyed by
    weapon/effect id and reach mercs through inherited weapon ids, a separate concern.)"""
    out = {}
    edit_re = re.compile(r'CatalogFieldValueModify\(\s*c_gameCatalogUnit\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"')
    for line in open(GALAXY_GEN, encoding="utf-8"):
        m = edit_re.search(line)
        if m:
            out.setdefault(m.group(1), set()).add(m.group(2))
    return out


def parse_galaxy_loops():
    """{unit_id: set(loop_tag)} — per-unit-type loop memberships in the hand-written lib."""
    text = open(GALAXY_HAND, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'libWoLU_AddBehaviorToType\(\s*libWoLU_Player\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\)', text):
        out.setdefault(m.group(1), set()).add("Behavior:" + m.group(2))
    for m in re.finditer(r'libWoLU_ToggleCloakOn\(\s*libWoLU_Player\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\)', text):
        out.setdefault(m.group(1), set()).add("ToggleCloak:" + m.group(2))
    for m in re.finditer(r'libWoLU_GraduateSiegeRange\(\s*libWoLU_Player\s*,\s*"([^"]+)"\)', text):
        out.setdefault(m.group(1), set()).add("GraduateSiegeRange")
    for m in re.finditer(r'TechTreeUnitAllow\(p,\s*"([^"]+)"', text):
        out.setdefault(m.group(1), set()).add("TechTreeUnitAllow")
    return out


def functional_fields(field_set):
    """Drop cost fields → the set of FUNCTIONAL buff fields keyed to a unit."""
    return {f for f in field_set
            if f not in COST_FIELDS and not COST_FIELD_RE.match(f)}


def loop_classes(tag_set):
    """Map raw loop tags to their parity CLASSES, dropping plumbing + unknown-but-untracked.
    An unknown loop tag (newly added) maps to itself so a NEW loop on a base unit still
    forces a parity decision (fix the merc or except it) — self-policing."""
    classes = set()
    for t in tag_set:
        if t in LOOP_PLUMBING:
            continue
        classes.add(LOOP_CLASS.get(t, t))   # unknown tag → itself (forces a decision)
    return classes


# ---------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------
def main():
    ref_present = os.path.exists(os.path.join(REF, "mods", "liberty.sc2mod", "UnitData.xml"))
    genlib = parse_genlib_unit_fields()
    loops = parse_galaxy_loops()

    fails, excused, ok = [], [], 0
    used_exceptions = set()

    for base, cps in COUNTERPARTS.items():
        b_fields = functional_fields(genlib.get(base, set()))
        b_loops = loop_classes(loops.get(base, set()))
        for cp, kind in cps:
            c_fields = functional_fields(genlib.get(cp, set()))
            c_loops = loop_classes(loops.get(cp, set()))

            gaps = []   # list of ("field:X" | "loop:Y", human description)
            for f in sorted(b_fields - c_fields):
                gaps.append((f"field:{f}", f"genlib Unit field '{f}' on '{base}' has no counterpart edit on '{cp}'"))
            for lc in sorted(b_loops - c_loops):
                gaps.append((f"loop:{lc}", f"galaxy loop class '{lc}' on '{base}' is not applied to '{cp}'"))

            for what, desc in gaps:
                key = (base, cp, what)
                if key in EXCEPTIONS:
                    used_exceptions.add(key)
                    excused.append(f"{base} → {cp} [{kind}]: {desc} — EXCEPTED ({EXCEPTIONS[key]})")
                else:
                    fails.append(f"{base} → {cp} [{kind}]: {desc}. "
                                 f"Add the counterpart edit (scale per rule 4/10), or allowlist it in "
                                 f"EXCEPTIONS with a reason.")
            if not gaps:
                ok += 1

    # Stale-exception guard: every EXCEPTIONS entry must correspond to a real gap (else the
    # data drifted and the exception is hiding nothing / masking a future regression).
    stale = sorted(set(EXCEPTIONS) - used_exceptions)
    for key in stale:
        fails.append(f"stale exception {key} — no such gap exists now (the base/counterpart edit changed). "
                     f"Remove it from EXCEPTIONS.")

    print(f"check_merc_parity: {sum(len(v) for v in COUNTERPARTS.values())} counterpart(s) across "
          f"{len(COUNTERPARTS)} base unit(s) scanned; {ok} with full parity, "
          f"{len(excused)} excused gap(s), {len(EXCEPTIONS)} exception(s) declared.")
    if not ref_present:
        # genlib/galaxy parsing needs no ref dump; this never short-circuits. (Kept for symmetry
        # with the other checks — the parse is purely from our own src/.)
        pass
    for e in excused:
        print(f"  · {e}")

    if fails:
        print("\nCHECK10 FAIL — merc/hero parity gaps (a base-keyed buff doesn't reach the counterpart):")
        for f in fails:
            print(f"  ✗ {f}")
        print(f"\nCHECK10: {len(fails)} un-excepted gap(s) — FAIL.")
        return 1
    print("CHECK10: ok — every merc/hero counterpart has parity for each base-keyed buff "
          "(functional fields + galaxy loops), or a declared exception.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
