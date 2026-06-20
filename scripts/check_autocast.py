#!/usr/bin/env python3
"""CHECK9 — autocast / reactive-trigger INTENT checker.

Verifies that every player autocast ability and every reactive (DamageResponse) behavior
in our GameData triggers on the event its DESIGN INTENT declares — so a wiring mismatch
(e.g. a shield that SHOULD fire on taking damage but is wired to fire on attacking) is
caught automatically, by the gate, without anyone eyeballing it.

This is the answer to "automate the checks that the autocasts trigger on the right events":
the intent lives in the three specs below; the checker reads the ACTUAL wiring from
AbilData.xml / BehaviorData.xml and FAILS on:
  - an autocast ability whose actual validators / air-filter / targetsorts != its intent;
  - a MANUAL_ONLY ability that still carries autocast flags;
  - a DamageResponse behavior whose mode (fatal-morph / fire-on-damage / reduce) != its intent
    (and, for fire-on-damage, the wrong Handled effect);
  - ANY autocast ability or DamageResponse behavior NOT listed in a spec — new ones MUST
    declare their intent here, which is what makes this self-policing.

When intent legitimately changes, edit the spec in the SAME commit as the wiring; the diff
then documents the change and the gate stays honest.

Stdlib-only; UTF-8 stdout (Windows cp1252 console). Run: python scripts/check_autocast.py
"""
import os
import sys
import xml.etree.ElementTree as ET

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GD = os.path.join(ROOT, "src", "mod", "Base.SC2Data", "GameData")

# ---------------------------------------------------------------------------------------
# INTENT SPECS — the design intent. Edit these when intent changes (same commit as wiring).
# ---------------------------------------------------------------------------------------

# Autocast abilities: id -> what its autocast should key off.
#   validators : the exact set of AutoCastValidatorArray ids it must carry
#   air        : True if it should auto-target air only (AutoCastFilters contains "Air")
#   targetsorts: True if it must define a <TargetSorts> priority block
AUTOCAST_INTENT = {
    "StimpackWoLU":               {"validators": {"CasterIsFiringWeapon"},     "air": False, "targetsorts": False},  # perma-stim while firing
    "StimpackMarauderWoLU":       {"validators": {"CasterIsFiringWeapon"},     "air": False, "targetsorts": False},
    "HealWoLU":                   {"validators": {"WoLUHasFlag"},              "air": False, "targetsorts": False},  # player-gated heal autocast (mech+air+bio); inherits heal's energy/warp validators + AutoCastFilters
    "SnipeWoLU":                  {"validators": {"WoLUSnipeWorthwhile"},      "air": False, "targetsorts": True},   # smart-snipe priority
    "EMPWoLU":                    {"validators": {"WoLUTargetEnergyOrShields"},"air": False, "targetsorts": False},  # only vs energy/shields
    "ObliterateWoLU":             {"validators": set(),                        "air": False, "targetsorts": False},  # Psionic Lash: enemy in range
    "YamatoWoLU":                 {"validators": {"WoLUYamatoBigTarget"},      "air": False, "targetsorts": False},  # big targets only
    "MissilePodsWoLU":            {"validators": set(),                        "air": True,  "targetsorts": False},  # anti-air
    "MagrailWoLU":                {"validators": set(),                        "air": False, "targetsorts": False},  # bonus shot, enemy in range
    # (SVDoubleBeamHealWoLU removed in v0.3.24 — the SV heal is now a passive aura behavior
    #  WoLUSVHealAura, not an autocast ability, so CHECK9 no longer tracks it.)
    "EMPShockwaveWoLU":           {"validators": {"WoLUTargetEnergyOrShields"},"air": False, "targetsorts": False},  # only vs energy/shields (SV BW EMP)
    "IrradiateWoLU":              {"validators": set(),                        "air": False, "targetsorts": False},  # enemy biological in range (AutoCastFilters = bio enemy)
    "DukesRevengeYamatoWoLU":     {"validators": {"WoLUYamatoBigTarget"},      "air": False, "targetsorts": False},
    "DukesRevengeMissilePodsWoLU":{"validators": set(),                        "air": True,  "targetsorts": False},
}

# Abilities whose autocast was DELIBERATELY removed — they are manual-cast + triggered
# reactively elsewhere (Defensive Matrix fires via the WoLUDefMatrixOnDamage behavior).
# The checker FAILS if any of these regains autocast flags.
MANUAL_ONLY = {
    "DefensiveMatrixWoLU":        "reactive on damage via WoLUDefMatrixOnDamage (not a state autocast)",
    "DukesRevengeDefensiveMatrixWoLU": "reactive on damage via WoLUDefMatrixOnDamage",
}

# Reactive behaviors: id -> the DamageResponse mode it must implement.
#   mode "fatal-morph"    : Fatal=1 + Handled=<wreck/death effect>  (Immortality Protocol)
#   mode "fire-on-damage" : Handled=<effect> on non-fatal damage    (cast-on-hit; + expected handled id)
#   mode "reduce"         : ModifyFraction<1, no Handled            (passive damage reduction)
DAMAGE_RESPONSE_INTENT = {
    "WoLUDefMatrixOnDamage": {"mode": "fire-on-damage", "handled": "DefensiveMatrixOnDamageSetWoLU"},
    "MercThorDontDie":       {"mode": "fatal-morph"},
    "WoLUAdaptiveDefenses":  {"mode": "reduce"},
}


# ---------------------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------------------
def _roots(filename):
    path = os.path.join(GD, filename)
    return ET.parse(path).getroot() if os.path.exists(path) else None


def _attr_or_child(el, name):
    """Field value as attribute OR <Name value=.../> child (SC2 allows both)."""
    if el.get(name) is not None:
        return el.get(name)
    c = el.find(name)
    if c is not None:
        return c.get("value") if c.get("value") is not None else (c.text or "").strip() or "1"
    return None


def parse_autocasts():
    """{id: {autocast, validators:set, air:bool, targetsorts:bool}} for every CAbil* in AbilData."""
    root = _roots("AbilData.xml")
    out = {}
    if root is None:
        return out
    for el in root:
        if not el.tag.startswith("CAbil") or not el.get("id"):
            continue
        autocast = any(f.get("index") == "AutoCast" and f.get("value") == "1"
                       for f in el.findall("Flags"))
        validators = {v.get("value") for v in el.findall("AutoCastValidatorArray") if v.get("value")}
        filters = " ".join(f.get("value", "") for f in el.findall("AutoCastFilters"))
        out[el.get("id")] = {
            "autocast": autocast,
            "validators": validators,
            "air": "Air" in filters,
            "targetsorts": el.find("TargetSorts") is not None,
        }
    return out


def parse_damage_responses():
    """{id: {mode, handled}} for every CBehaviorBuff carrying a <DamageResponse>."""
    root = _roots("BehaviorData.xml")
    out = {}
    if root is None:
        return out
    for el in root:
        if not el.tag.startswith("CBehavior") or not el.get("id"):
            continue
        dr = el.find("DamageResponse")
        if dr is None:
            continue
        fatal = _attr_or_child(dr, "Fatal") in ("1", "true")
        handled = _attr_or_child(dr, "Handled")
        modfrac = _attr_or_child(dr, "ModifyFraction")
        if fatal:
            mode = "fatal-morph"
        elif handled:
            mode = "fire-on-damage"
        elif modfrac is not None and modfrac not in ("1", "1.0"):
            mode = "reduce"
        else:
            mode = "unknown"
        out[el.get("id")] = {"mode": mode, "handled": handled}
    return out


# ---------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------
def main():
    acs = parse_autocasts()
    drs = parse_damage_responses()
    fails, oks = [], 0

    # 1. Every actual autocast ability must match its declared intent.
    for aid, info in sorted(acs.items()):
        if not info["autocast"]:
            if aid in MANUAL_ONLY:
                oks += 1  # correctly autocast-free
            continue
        if aid in MANUAL_ONLY:
            fails.append(f"{aid}: has autocast flags but is MANUAL_ONLY ({MANUAL_ONLY[aid]}) — remove the autocast.")
            continue
        intent = AUTOCAST_INTENT.get(aid)
        if intent is None:
            fails.append(f"{aid}: autocast ability with NO declared intent — add it to AUTOCAST_INTENT "
                         f"(actual validators={sorted(info['validators']) or 'none'}, air={info['air']}, "
                         f"targetsorts={info['targetsorts']}).")
            continue
        diffs = []
        if info["validators"] != intent["validators"]:
            diffs.append(f"validators: got {sorted(info['validators']) or 'none'}, "
                         f"want {sorted(intent['validators']) or 'none'}")
        if info["air"] != intent.get("air", False):
            diffs.append(f"air-filter: got {info['air']}, want {intent.get('air', False)}")
        if info["targetsorts"] != intent.get("targetsorts", False):
            diffs.append(f"targetsorts: got {info['targetsorts']}, want {intent.get('targetsorts', False)}")
        if diffs:
            fails.append(f"{aid}: autocast trigger != intent — " + "; ".join(diffs))
        else:
            oks += 1

    # 2. MANUAL_ONLY abilities must actually exist and be autocast-free.
    for aid in MANUAL_ONLY:
        if aid not in acs:
            fails.append(f"{aid}: declared MANUAL_ONLY but not found in AbilData (stale spec?).")

    # 3. Every reactive DamageResponse behavior must match its declared intent.
    for bid, info in sorted(drs.items()):
        intent = DAMAGE_RESPONSE_INTENT.get(bid)
        if intent is None:
            fails.append(f"{bid}: DamageResponse behavior with NO declared intent — add it to "
                         f"DAMAGE_RESPONSE_INTENT (actual mode={info['mode']}, handled={info['handled']}).")
            continue
        if info["mode"] != intent["mode"]:
            fails.append(f"{bid}: damage-response mode != intent — got {info['mode']}, want {intent['mode']}.")
        elif intent.get("handled") and info["handled"] != intent["handled"]:
            fails.append(f"{bid}: fire-on-damage Handled != intent — got {info['handled']}, want {intent['handled']}.")
        else:
            oks += 1

    # 4. Specs must not reference ids that no longer exist (catch stale intent).
    for aid in AUTOCAST_INTENT:
        if aid not in acs:
            fails.append(f"{aid}: in AUTOCAST_INTENT but not found in AbilData (stale spec?).")
    for bid in DAMAGE_RESPONSE_INTENT:
        if bid not in drs:
            fails.append(f"{bid}: in DAMAGE_RESPONSE_INTENT but no such DamageResponse behavior (stale spec?).")

    print(f"check_autocast: {len(acs)} abilities, {len(drs)} reactive behaviors scanned; "
          f"{oks} trigger(s) match intent.")
    if fails:
        print("\nCHECK9 FAIL — autocast/trigger intent mismatches:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    print("CHECK9: ok — every autocast + reactive trigger matches its declared intent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
