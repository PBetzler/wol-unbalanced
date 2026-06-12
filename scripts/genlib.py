#!/usr/bin/env python3
"""Generate src/mod/Base.SC2Data/LibWoLUnbalancedGen.galaxy from the reference catalogs.

Reads the vanilla Liberty catalogs in mods/_reference/ and emits per-player
CatalogFieldValueModify calls implementing the global rules. Hand-written logic
stays in LibWoLUnbalanced.galaxy; this file owns only the generated apply-body.
"""
import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "mods", "_reference")
OUT = os.path.join(ROOT, "src", "mod", "Base.SC2Data", "LibWoLUnbalancedGen.galaxy")

CATALOGS = ["mods/liberty.sc2mod", "campaigns/liberty.sc2campaign",
            "campaigns/libertystory.sc2campaign"]

# Player-faction units whose weapons get the rule-7 damage-point cap.
# Heroes and mercenaries inherit the cap (rules 4/10) — their weapons are
# collected from the catalogs automatically.
HERO_MERC_UNITS = [
    "Raynor01", "RaynorCommando", "Raynor", "TychusCommando", "TychusChaingun",
    "Swann", "Stetmann", "Nova", "Tosh", "Odin",
    "WarPig", "DevilDog", "HammerSecurity", "SpartanCompany", "SiegeBreaker",
    "SiegeBreakerSieged", "HelsAngelFighter", "HelsAngelAssault", "DuskWing",
    "DukesRevenge",
]
PLAYER_UNITS = [
    "SCV", "Marine", "Medic", "Firebat", "Marauder", "Reaper", "Ghost", "Spectre",
    "Hellion", "Vulture", "Goliath", "Diamondback", "SiegeTank", "SiegeTankSieged",
    "Thor", "Predator", "Medivac", "Wraith", "VikingAssault", "VikingFighter",
    "Banshee", "Battlecruiser", "Raven", "ScienceVessel", "Hercules",
] + HERO_MERC_UNITS

DAMAGE_POINT_CAP = 0.1
BUILD_TIME_CAP = 60.0
BUILD_TIME_OVERRIDES = {"Predator": 10.0, "Hercules": 20.0}

# Rule 8: free cloak — ability ids with an energy activation cost, and buff
# behaviors with an energy drain (negative regen). Extracted from the catalogs
# below; listed explicitly so the output is reviewable.
CLOAK_ABILS = ["GhostCloak", "BansheeCloak", "WraithCloak", "RogueGhostCloak",
               "DuskWingBansheeCloakingField", "SpectreCloak"]
CLOAK_BEHAVIORS = ["GhostCloak", "BansheeCloak", "WraithCloak", "SpectreCloaking",
                   "PredatorCloaking", "BansheeCloakCrossSpectrumDampeners"]


def load(catalog_file):
    """Yield (source, root) for each reference catalog that has this file."""
    for src in CATALOGS:
        path = os.path.join(REF, src, catalog_file)
        if os.path.exists(path):
            yield src, ET.parse(path).getroot()


def collect_weapons():
    """unit id -> weapon links (campaign catalog wins over mod catalog)."""
    unit_weapons = {}
    for _, root in load("UnitData.xml"):
        for unit in root.iter("CUnit"):
            uid = unit.get("id")
            if uid not in PLAYER_UNITS:
                continue
            links = [w.get("Link") for w in unit.findall("WeaponArray") if w.get("Link")]
            if links:
                unit_weapons[uid] = links  # later catalogs override
    return unit_weapons


def weapon_damage_points():
    """weapon id -> explicit DamagePoint (None if not set => engine default 0.167)."""
    points = {}
    for _, root in load("WeaponData.xml"):
        for w in list(root.iter("CWeaponLegacy")) + list(root.iter("CWeaponStrafe")):
            wid = w.get("id")
            dp = w.find("DamagePoint")
            if wid:
                points[wid] = float(dp.get("value")) if dp is not None else points.get(wid)
    return points


def train_entries():
    """(abil id, index, unit, time) for all CAbilTrain entries, later catalogs win."""
    entries = {}
    for _, root in load("AbilData.xml"):
        for abil in root.iter("CAbilTrain"):
            aid = abil.get("id")
            for info in abil.findall("InfoArray"):
                idx = info.get("index")
                unit_el = info.find("Unit")
                unit = unit_el.get("value") if unit_el is not None else info.get("Unit")
                time = info.get("Time")
                if time is None:
                    t_el = info.find("Time")
                    time = t_el.get("value") if t_el is not None else None
                if idx and unit:
                    key = (aid, idx)
                    prev_time = entries.get(key, (None, None))[1]
                    entries[key] = (unit, float(time) if time else prev_time)
    return entries


# Vanilla->clone swaps: the player's units get the improved WoLU versions by editing
# their EXISTING ability/weapon/button links (catalog modify can edit, not create).
# Indices are derived from the reference XML so they can't drift.
STIM_SWAPS = {"Marine": ("Stimpack", "StimpackWoLU"),
              "Marauder": ("StimpackMarauder", "StimpackMarauderWoLU"),
              "WarPig": ("Stimpack", "StimpackWoLU"),
              "HammerSecurity": ("StimpackMarauder", "StimpackMarauderWoLU")}
WEAPON_SWAPS = {"Thor": ("ThorsHammer", "ThorsHammerWoLU")}


def clone_swaps():
    out = []
    seen = set()
    for _, root in load("UnitData.xml"):
        for unit in root.iter("CUnit"):
            uid = unit.get("id")
            if uid in STIM_SWAPS:
                old, new = STIM_SWAPS[uid]
                for i, a in enumerate(unit.findall("AbilArray")):
                    key = (uid, "abil", i)
                    if a.get("Link") == old and key not in seen:
                        seen.add(key)
                        out.append((uid, f"AbilArray[{i}].Link", new, f"{uid}: {old} -> {new}"))
                for ci, card in enumerate(unit.findall("CardLayouts")):
                    for bi, b in enumerate(card.findall("LayoutButtons")):
                        key = (uid, "btn", ci, bi)
                        if b.get("AbilCmd") == f"{old},Execute" and key not in seen:
                            seen.add(key)
                            out.append((uid, f"CardLayouts[{ci}].LayoutButtons[{bi}].AbilCmd", f"{new},Execute", ""))
            if uid in WEAPON_SWAPS:
                old, new = WEAPON_SWAPS[uid]
                for i, w in enumerate(unit.findall("WeaponArray")):
                    key = (uid, "weap", i)
                    if w.get("Link") == old and key not in seen:
                        seen.add(key)
                        out.append((uid, f"WeaponArray[{i}].Link", new, f"{uid}: {old} -> {new}"))
    return out


def emit():
    lines = [
        "//==================================================================================================",
        "// GENERATED by scripts/genlib.py — do not edit by hand.",
        "//==================================================================================================",
        "",
        "void libWoLUGen_Apply (int p) {",
    ]

    lines.append("    // --- Marines: +20 base HP (unit-table) ---")
    for f in ("LifeMax", "LifeStart"):
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogUnit, "Marine", "{f}", p, "20", c_upgradeOperationAdd);')

    lines.append("")
    lines.append("    // --- Rule 8: free cloak (no activation cost, no energy drain) ---")
    for a in CLOAK_ABILS:
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "{a}", "Cost[0].Vital[Energy]", p, "0", c_upgradeOperationSet);')
    for b in CLOAK_BEHAVIORS:
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogBehavior, "{b}", "Modification.VitalRegenArray[Energy]", p, "0", c_upgradeOperationSet);')

    lines.append("")
    lines.append("    // --- Rule 7: damage point (attack windup) cap at 0.1 s ---")
    unit_weapons = collect_weapons()
    points = weapon_damage_points()
    seen = set()
    for uid in PLAYER_UNITS:
        for wid in unit_weapons.get(uid, []):
            if wid in seen:
                continue
            seen.add(wid)
            dp = points.get(wid)
            if dp is None or dp > DAMAGE_POINT_CAP:
                lines.append(f'    CatalogFieldValueModify(c_gameCatalogWeapon, "{wid}", "DamagePoint", p, "{DAMAGE_POINT_CAP}", c_upgradeOperationSet);  // {uid}, was {dp if dp is not None else "default 0.167"}')

    lines.append("")
    lines.append("    // --- Rule 5: build time cap 60 s (+ explicit overrides) ---")
    for (aid, idx), (unit, time) in sorted(train_entries().items()):
        target = BUILD_TIME_OVERRIDES.get(unit)
        if target is None and time is not None and time > BUILD_TIME_CAP:
            target = BUILD_TIME_CAP
        if target is not None and time != target:
            lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "{aid}", "InfoArray[{idx}].Time", p, "{target}", c_upgradeOperationSet);  // {unit}, was {time}')

    lines.append("")
    lines.append("    // --- Rule 6: merc calldowns — unlimited charges, ready at mission start ---")
    for n in range(1, 9):
        for field, val in (("Charge.CountMax", "0"), ("Charge.CountStart", "0"), ("Cooldown.TimeStart", "0")):
            lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "SummonMercenaries", "InfoArray[Train{n}].{field}", p, "{val}", c_upgradeOperationSet);')

    lines.append("")
    lines.append("    // --- Per-unit stats (unit-table comments) ---")
    stat_edits = [
        # (catalog, entry, field, value, op, comment)
        ("Unit", "Firebat", "LifeMax", "2", "Multiply", "Firebat: double HP (100 -> 200)"),
        ("Unit", "Firebat", "LifeStart", "2", "Multiply", ""),
        ("Unit", "Predator", "CostResource[Vespene]", "0", "Set", "Predator: no gas"),
        ("Unit", "Predator", "Food", "-1", "Set", "Predator: 1 supply"),
        ("Unit", "Hercules", "LifeArmor", "2", "Add", "Hercules: +2 armor"),
        ("Unit", "Medic", "CostResource[Minerals]", "25", "Subtract", "Medic: AP Resource Efficiency (-25/-25/-1)"),
        ("Unit", "Medic", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Medic", "Food", "-1", "Set", ""),
        ("Unit", "Ghost", "CostResource[Minerals]", "100", "Subtract", "Ghost: AP Bargain Bin Prices (-100/-50/-1)"),
        ("Unit", "Ghost", "CostResource[Vespene]", "50", "Subtract", ""),
        ("Unit", "Ghost", "Food", "-1", "Set", ""),
        ("Unit", "Spectre", "CostResource[Minerals]", "100", "Subtract", "Spectre mirrors Ghost"),
        ("Unit", "Spectre", "CostResource[Vespene]", "50", "Subtract", ""),
        ("Unit", "Spectre", "Food", "-1", "Set", ""),
        ("Unit", "Firebat", "CargoSize", "1", "Set", "rule: all infantry take 1 bunker slot"),
        ("Unit", "Marauder", "CargoSize", "1", "Set", ""),
        ("Unit", "Ghost", "CargoSize", "1", "Set", ""),
        ("Unit", "Spectre", "CargoSize", "1", "Set", ""),
        # damage flattening: base damage = old total vs bonus attribute
        ("Effect", "C10CanisterRifle", "Amount", "20", "Set", "Ghost rifle: 10(+10 light) -> 20 flat"),
        ("Effect", "C10CanisterRifle", "AttributeBonus[Light]", "0", "Set", ""),
        ("Effect", "SpecterU", "Amount", "20", "Set", "Spectre rifle: 15(+5 armored) -> 20 flat"),
        ("Effect", "SpecterU", "AttributeBonus[Armored]", "0", "Set", ""),
        # Thor AA: flatten 8(+4 light)=12 < HIP 35 -> 35 per rocket; range = HIP 11 + 1
        ("Effect", "JavelinMissileLaunchersDamage", "Amount", "35", "Set", "Thor AA: HIP floor 35/rocket (LotV Punisher)"),
        ("Effect", "JavelinMissileLaunchersDamage", "AttributeBonus[Light]", "0", "Set", ""),
        ("Weapon", "JavelinMissileLaunchers", "Range", "12", "Set", "Thor AA range = HIP range 11 + 1"),
        # (Thor ground splash lives in the ThorsHammerWoLU weapon clone — runtime catalog
        #  modify cannot CREATE AreaArray entries; the weapon link swap is emitted below.)
        # Siege tank: no friendly fire (campaign implements FF via separate friendly effects)
        ("Effect", "CrucioShockCannonFriendlyDamage", "Amount", "0", "Set", "tank sieged splash: no friendly fire"),
        ("Effect", "CrucioShockCannonFriendlyTargetDamage", "Amount", "0", "Set", ""),
        # Hercules trainable without Fusion Core
        ("Abil", "StarportTrain", "InfoArray[Train6].Button.Requirements", "HaveAttachedTechLab", "Set", "Hercules: no Fusion Core needed"),
        # --- Hero/merc parity (rules 4/10): keep % advantage over changed base units ---
        ("Unit", "Raynor01", "LifeMax", "1.4444", "Multiply", "Marine line: x65/45 (Raynor variants + War Pigs)"),
        ("Unit", "Raynor01", "LifeStart", "1.4444", "Multiply", ""),
        ("Unit", "RaynorCommando", "LifeMax", "1.4444", "Multiply", ""),
        ("Unit", "RaynorCommando", "LifeStart", "1.4444", "Multiply", ""),
        ("Unit", "Raynor", "LifeMax", "1.4444", "Multiply", ""),
        ("Unit", "Raynor", "LifeStart", "1.4444", "Multiply", ""),
        ("Unit", "WarPig", "LifeMax", "1.4444", "Multiply", ""),
        ("Unit", "WarPig", "LifeStart", "1.4444", "Multiply", ""),
        ("Unit", "TychusCommando", "LifeMax", "2", "Multiply", "Firebat line: x2 (Tychus variants + Devil Dogs)"),
        ("Unit", "TychusCommando", "LifeStart", "2", "Multiply", ""),
        ("Unit", "TychusChaingun", "LifeMax", "2", "Multiply", ""),
        ("Unit", "TychusChaingun", "LifeStart", "2", "Multiply", ""),
        ("Unit", "DevilDog", "LifeMax", "2", "Multiply", ""),
        ("Unit", "DevilDog", "LifeStart", "2", "Multiply", ""),
        ("Unit", "SpartanCompany", "LifeMax", "1.2", "Multiply", "Goliath line: x150/125 (Shaped Hull +25)"),
        ("Unit", "SpartanCompany", "LifeStart", "1.2", "Multiply", ""),
        ("Unit", "DukesRevenge", "LifeArmor", "2", "Add", "BC line: Behemoth Plating + Moirai drive"),
        ("Unit", "DukesRevenge", "Speed", "1.25", "Multiply", ""),
        ("Unit", "DuskWing", "Speed", "1.25", "Multiply", "Banshee line: Hyperflight Rotors"),
        ("Weapon", "OdinAntiAir", "Range", "12", "Set", "Odin mirrors Thor AA range"),
        # --- AP ports, direct-field batch ---
        # (Super Stimpack lives in the StimpackWoLU clone abilities now — see AbilData.xml
        #  and the clone link swaps emitted below.)
        ("Weapon", "GaussRifle", "Range", "6", "Set", "Marine Laser Targeting System: +1 range"),
        ("Unit", "SCV", "LifeMax", "15", "Add", "AP Hostile Environment Adaptation"),
        ("Unit", "SCV", "LifeStart", "15", "Add", ""),
        ("Unit", "Reaper", "LifeMax", "10", "Add", "AP Ballistic Flightsuit"),
        ("Unit", "Reaper", "LifeStart", "10", "Add", ""),
        ("Unit", "Vulture", "Speed", "1.25", "Multiply", "AP Ion Thrusters"),
        ("Unit", "Vulture", "LifeRegenRate", "1", "Set", "AP Jerry-Rigged Patchup"),
        ("Unit", "Goliath", "LifeMax", "25", "Add", "AP Shaped Hull"),
        ("Unit", "Goliath", "LifeStart", "25", "Add", ""),
        ("Unit", "Banshee", "Speed", "1.25", "Multiply", "AP Hyperflight Rotors"),
        ("Unit", "Battlecruiser", "LifeArmor", "2", "Add", "AP Behemoth Plating"),
        ("Unit", "Battlecruiser", "Speed", "1.25", "Multiply", "AP Moirai Impulse Drive"),
        ("Abil", "MedivacTransport", "TotalCargoSpace", "12", "Set", "AP Expanded Hull: 8 -> 12 cargo"),
        ("Abil", "MedivacTransport", "MaxCargoCount", "12", "Set", ""),
    ]
    for cat, entry, field, val, op, comment in stat_edits:
        suffix = f"  // {comment}" if comment else ""
        lines.append(f'    CatalogFieldValueModify(c_gameCatalog{cat}, "{entry}", "{field}", p, "{val}", c_upgradeOperation{op});{suffix}')

    lines.append("")
    lines.append("    // --- Engineering Bay: combined upgrades research in 30 s (weapon/armor levels) ---")
    for idx in ("Research3", "Research4", "Research5", "Research7", "Research8", "Research9"):
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "EngineeringBayResearch", "InfoArray[{idx}].Time", p, "30", c_upgradeOperationSet);')

    # NOTE: hero stim abilities/buttons are NOT granted here — CatalogFieldValueModify
    # cannot CREATE array entries (AbilArray/LayoutButtons), only edit existing ones.
    # They live in src/mod/Base.SC2Data/GameData/UnitData.xml instead (hero units are
    # player-exclusive, so static XML is rule-9-safe for them).

    lines.append("")
    lines.append("    // --- Clone swaps: player units use the improved WoLU versions (vanilla stays enemy-side) ---")
    for uid, field, val, comment in clone_swaps():
        suffix = f"  // {comment}" if comment else ""
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogUnit, "{uid}", "{field}", p, "{val}", c_upgradeOperationSet);{suffix}')

    lines.append("}")
    lines.append("")
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    emit()
