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
BUILD_TIME_OVERRIDES = {
    "Predator": 10.0,
    "Hercules": 20.0,
    # AP "Optimized Logistics" (faster training; AP gives no exact number — we use
    # -25%, documented assumption) for the units whose table row includes it.
    "Marine": 19.0,    # 25 * 0.75
    "Hellion": 22.0,   # 30 * 0.75 (rounded)
    "Goliath": 30.0,   # 40 * 0.75
}

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


# Vanilla->clone swaps live in static XML index-overrides (UnitData.xml): runtime
# per-player LINK edits (AbilArray/WeaponArray/LayoutButtons) are silent no-ops —
# only scalar stat-like fields apply per player (verified in game, see learnings).
# Player gating happens inside the clones (requirement-gated buttons, validator-gated
# effect branches), never via runtime link swaps.

# No weapon clones any more: Thor's splash is wired by overriding the vanilla
# ThorsHammer weapon's Effect (keeps the weapon id so attack visuals fire). The
# vanilla ThorsHammer windup is already capped by the rule-7 pass below.
CLONE_WEAPONS = {}


def emit():
    # Fail early + clearly if the gitignored reference catalogs aren't present.
    probe = os.path.join(REF, "mods", "liberty.sc2mod", "UnitData.xml")
    if not os.path.exists(probe):
        raise SystemExit(
            f"\ngenlib: reference catalogs not found (expected e.g. {probe}).\n"
            f"  how to fix: download the Liberty XML dumps from SC2Mapster/SC2GameData\n"
            f"              (https://github.com/SC2Mapster/SC2GameData) into mods/_reference/.\n"
            f"  (third-party reference data is gitignored — see README §Building.)\n")
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
    for wid, comment in CLONE_WEAPONS.items():
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogWeapon, "{wid}", "DamagePoint", p, "{DAMAGE_POINT_CAP}", c_upgradeOperationSet);  // {comment}')

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
    # CountMax/CountStart=0 means ZERO charges ("Not enough charges" in game), NOT
    # unlimited. For effectively-unlimited-from-start: start full (CountStart high),
    # big cap (CountMax high), uses cost nothing (CountUse=0), and no cooldown wait
    # (TimeStart/TimeUse=0) so it never runs dry.
    # Train1-8 = the vanilla mercs; Train9-16 = our extra elite mercs (Skibi's Angels /
    # Death Heads / Condor / Jotun / Winged Nightmares / Midnight Riders / Senior Ghost /
    # Brynhilds, defined in static XML) — reassert unlimited-from-start on their static defaults.
    for n in range(1, 17):
        for field, val in (
            ("Charge.CountMax", "99"),
            ("Charge.CountStart", "99"),
            ("Charge.CountUse", "0"),
            ("Cooldown.TimeStart", "0"),
            ("Cooldown.TimeUse", "0"),
        ):
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
        # AP "Resource Efficiency" for the remaining units whose table row lists it.
        # ASSUMPTION: AP's exact per-unit numbers are undocumented; use the canonical
        # RE value (-25 M / -25 G / -1 supply, same as Medic's documented value).
        # Food is stored negative (supply used); Add 1 = -1 supply from any base.
        ("Unit", "Firebat", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption: -25/-25/-1)"),
        ("Unit", "Firebat", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Firebat", "Food", "1", "Add", ""),
        ("Unit", "Reaper", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Reaper", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Reaper", "Food", "1", "Add", ""),
        ("Unit", "Goliath", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Goliath", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Goliath", "Food", "1", "Add", ""),
        ("Unit", "Diamondback", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Diamondback", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Diamondback", "Food", "1", "Add", ""),
        ("Unit", "SiegeTank", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "SiegeTank", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "SiegeTank", "Food", "1", "Add", ""),
        ("Unit", "Raven", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Raven", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Raven", "Food", "1", "Add", ""),
        ("Unit", "Medivac", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Medivac", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Medivac", "Food", "1", "Add", ""),
        ("Unit", "Firebat", "CargoSize", "1", "Set", "rule: all infantry take 1 bunker slot"),
        ("Unit", "Marauder", "CargoSize", "1", "Set", ""),
        ("Unit", "Ghost", "CargoSize", "1", "Set", ""),
        ("Unit", "Spectre", "CargoSize", "1", "Set", ""),
        # CargoSize per-player is read at bunker LOAD time and the runtime edit doesn't
        # reach it (confirmed in game — Ghost still took 2 slots; see learnings/open-issues).
        # Achieve the rule's INTENT (a bunker holds 4 of ANY infantry, including the size-2
        # Ghost/Marauder/Firebat/Spectre) by bumping the bunker's TotalCargoSpace to
        # MaxCargoCount(4) x MaxCargoSize(2) = 8. TotalCargoSpace is a scalar field (same
        # class as the MedivacTransport edit that works), so it DOES apply per player.
        ("Abil", "BunkerTransport", "TotalCargoSpace", "8", "Set", "Bunker holds 4 of any infantry (size-2 units no longer eat 2 slots)"),
        # damage flattening: base damage = old total vs bonus attribute
        ("Effect", "C10CanisterRifle", "Amount", "20", "Set", "Ghost rifle: 10(+10 light) -> 20 flat"),
        ("Effect", "C10CanisterRifle", "AttributeBonus[Light]", "0", "Set", ""),
        ("Effect", "SpecterU", "Amount", "20", "Set", "Spectre rifle: 15(+5 armored) -> 20 flat"),
        ("Effect", "SpecterU", "AttributeBonus[Armored]", "0", "Set", ""),
        # Thor AA: flatten 8(+4 light)=12 < HIP 35 -> 35 per rocket; range = HIP 11 + 1
        ("Effect", "JavelinMissileLaunchersDamage", "Amount", "35", "Set", "Thor AA: HIP floor 35/rocket (LotV Punisher)"),
        ("Effect", "JavelinMissileLaunchersDamage", "AttributeBonus[Light]", "0", "Set", ""),
        ("Weapon", "JavelinMissileLaunchers", "Range", "12", "Set", "Thor AA range = HIP range 11 + 1"),
        # Thor "Rapid Reload" (AP, unit-table) — the ground attack's slow Period (1.93 s)
        # + 0.25 s backswing read as a long "windup" even though DamagePoint is already
        # capped to 0.1. Speed up the attack rate and trim the recovery (Odin mirrors it).
        ("Weapon", "ThorsHammer", "Period", "1.0", "Set", "Thor Rapid Reload: faster ground attack (1.93->1.0)"),
        ("Weapon", "ThorsHammer", "Backswing", "0.1", "Set", "Thor: minimal attack recovery"),
        ("Weapon", "Odin", "Period", "1.0", "Set", "Odin mirrors Thor Rapid Reload"),
        ("Weapon", "Odin", "Backswing", "0.1", "Set", ""),
        # (Thor ground splash is wired by overriding vanilla ThorsHammer's Effect in
        #  WeaponData.xml; the windup cap on ThorsHammer is applied per player above.)
        # (legacy note — runtime catalog
        #  modify cannot CREATE AreaArray entries; the weapon link swap is emitted below.)
        # Siege tank: no friendly fire (campaign implements FF via separate friendly effects)
        ("Effect", "CrucioShockCannonFriendlyDamage", "Amount", "0", "Set", "tank sieged splash: no friendly fire"),
        ("Effect", "CrucioShockCannonFriendlyTargetDamage", "Amount", "0", "Set", ""),
        # Build-prerequisite drops (per-player, rule-9 safe). NOTE: Button.Requirements is
        # a requirement-LINK field; per-player runtime link edits are often silent no-ops
        # (see learnings). These are the rule-compliant attempt — set the train button's
        # requirement to empty (= always available, like Marine Train1). VERIFY IN GAME: if
        # the unit still needs the building, the field is a no-op and the only working lever
        # is TechTreeRestrictionsEnable(p,false), which is rejected here because it would also
        # strip the Merc Compound requirement (violates rule 6).
        ("Abil", "StarportTrain", "InfoArray[Train6].Button.Requirements", "", "Set", "Hercules: no Fusion Core needed (drop requirement)"),
        # Marauder "Internal Tech Module": build without a Tech Lab (BarracksTrain Train4).
        ("Abil", "BarracksTrain", "InfoArray[Train4].Button.Requirements", "", "Set", "Marauder Internal Tech Module: no Tech Lab needed"),
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
        # (SpartanCompany Shaped Hull +25 is applied as a flat LifeMax/LifeStart +25
        #  in the parity sweep below — mirrors the base Goliath exactly. The earlier
        #  x1.2 multiply here was a duplicate of that and double-counted Shaped Hull.)
        ("Unit", "DukesRevenge", "LifeArmor", "2", "Add", "BC line: Behemoth Plating + Moirai drive"),
        ("Unit", "DukesRevenge", "Speed", "1.25", "Multiply", ""),
        ("Unit", "DuskWing", "Speed", "1.25", "Multiply", "Banshee line: Hyperflight Rotors"),
        ("Weapon", "OdinAntiAir", "Range", "12", "Set", "Odin mirrors Thor AA range"),
        # --- AP ports, direct-field batch ---
        # (Super Stimpack lives in the StimpackWoLU clone abilities now — see AbilData.xml
        #  and the clone link swaps emitted below.)
        ("Weapon", "GuassRifle", "Range", "6", "Set", "Marine Laser Targeting System: +1 range (id is Blizzard's typo)"),
        # Rule 10 parity: Raynor (=Marine) variants use their OWN weapons, so the
        # GuassRifle edit above never reached them. +1 range via Add (robust to each
        # weapon's base; keeps the hero ahead of the buffed Marine).
        ("Weapon", "RaynorGaussRifle", "Range", "1", "Add", "Raynor01: Marine LTS +1 range parity"),
        ("Weapon", "CommandoRifle", "Range", "1", "Add", "RaynorCommando: +1 range parity"),
        ("Weapon", "RaynorWeapon", "Range", "1", "Add", "Raynor (Tychus-side hero): +1 range parity"),
        ("Weapon", "KelmorianMinerGaussRifle", "Range", "1", "Add", "War Pigs (Marine merc): LTS +1 range parity"),
        # Laser Targeting also grants +2 sight; mirror it on the Marine line's heroes/merc.
        ("Unit", "WarPig", "Sight", "2", "Add", "War Pigs: LTS +2 sight parity"),
        ("Unit", "Raynor01", "Sight", "2", "Add", "Raynor line: LTS +2 sight parity"),
        ("Unit", "RaynorCommando", "Sight", "2", "Add", ""),
        ("Unit", "Raynor", "Sight", "2", "Add", ""),
        ("Unit", "SCV", "LifeMax", "15", "Add", "AP Hostile Environment Adaptation"),
        ("Unit", "SCV", "LifeStart", "15", "Add", ""),
        ("Unit", "Reaper", "LifeMax", "10", "Add", "AP Ballistic Flightsuit"),
        ("Unit", "Reaper", "LifeStart", "10", "Add", ""),
        ("Unit", "Vulture", "Speed", "1.25", "Multiply", "AP Ion Thrusters"),
        ("Unit", "Vulture", "LifeRegenRate", "1", "Set", "AP Jerry-Rigged Patchup"),
        ("Unit", "Reaper", "LifeRegenRate", "2", "Set", "AP Combat Drugs: out-of-combat regen (approx via flat regen)"),
        ("Unit", "Goliath", "LifeMax", "25", "Add", "AP Shaped Hull"),
        ("Unit", "Goliath", "LifeStart", "25", "Add", ""),
        ("Unit", "Banshee", "Speed", "1.25", "Multiply", "AP Hyperflight Rotors"),
        ("Unit", "Battlecruiser", "LifeArmor", "2", "Add", "AP Behemoth Plating"),
        ("Unit", "Battlecruiser", "Speed", "1.25", "Multiply", "AP Moirai Impulse Drive"),
        ("Abil", "MedivacTransport", "TotalCargoSpace", "12", "Set", "AP Expanded Hull: 8 -> 12 cargo"),
        ("Abil", "MedivacTransport", "MaxCargoCount", "12", "Set", ""),
        # --- AP ports, second direct-field batch (documented values from unit-table
        #     Appendix A; assumptions are marked as such) ---
        ("Unit", "Marine", "Sight", "2", "Add", "Laser Targeting System: +2 vision (range above)"),
        ("Unit", "Marauder", "LifeArmor", "2", "Add", "Marauder Juggernaut Plating"),
        ("Weapon", "PunisherGrenades", "Range", "7", "Set", "Marauder LTS: +1 range (6->7)"),
        ("Unit", "Marauder", "Sight", "2", "Add", ""),
        ("Effect", "FirebatUFull", "AttributeBonus[Light]", "4", "Add", "Firebat Infernal Pre-Igniter: +4 vs light (4->8)"),
        ("Unit", "Firebat", "LifeMax", "100", "Add", "Firebat Kinetic Foam: +100 life (after x2)"),
        ("Unit", "Firebat", "LifeStart", "100", "Add", ""),
        ("Weapon", "Firebat", "Range", "4", "Set", "Firebat Nano Projectors: +2 range (2->4)"),
        ("Weapon", "C10CanisterRifle", "Range", "7", "Set", "Ghost LTS: +1 range (6->7)"),
        ("Unit", "Ghost", "Sight", "2", "Add", ""),
        ("Weapon", "Specter", "Range", "7", "Set", "Spectre mirrors Ghost LTS: +1 range"),
        ("Unit", "Spectre", "Sight", "2", "Add", ""),
        ("Unit", "Hellion", "LifeArmor", "2", "Add", "Hellion Infernal Plating"),
        ("Unit", "Medivac", "ShieldsMax", "100", "Set", "Medivac Scatter Veil: +100 shields"),
        ("Unit", "Medivac", "ShieldsStart", "100", "Set", ""),
        ("Unit", "VikingAssault", "Speed", "1.55", "Multiply", "Viking Aesir Turbines: +55% speed"),
        ("Unit", "VikingFighter", "Speed", "1.55", "Multiply", ""),
        ("Weapon", "Diamondback", "Range", "3", "Add", "Diamondback Tri-Lithium Power Cell max: +3 range"),
        ("Unit", "SiegeTankSieged", "LifeArmor", "3", "Add", "Tank Advanced Siege Tech: +3 armor sieged"),
        ("Weapon", "BacklashRockets", "Range", "8", "Set", "Banshee Advanced Targeting Optics: +2 range (folded flat — player banshees are perma-cloaked)"),
        ("Effect", "BacklashRocketsU", "Amount", "1.25", "Multiply", "Banshee Distortion Blasters: +25% dmg (folded flat)"),
        ("Abil", "NanoRepair", "Cost[0].Vital[Energy]", "0", "Set", "Science Vessel Improved Nano-Repair: free heal"),
        ("Effect", "OdinAADamage", "Amount", "35", "Set", "Odin AA mirrors Thor: HIP floor 35/rocket (was 15, no light bonus)"),
        ("Abil", "heal", "Range", "4", "Set", "Medic Nano Projector: +2 heal range (2->4)"),
        ("Abil", "heal", "TargetFilters", "Visible;Self,Enemy,Structure,Missile,UnderConstruction,Dead,Hidden,Invulnerable", "Set", "Medic Adaptive Medpacks: heal mech + air (drops Ground,Biological requirement) — string-field edit, verify in game"),
        ("Weapon", "Diamondback", "Period", "0.75", "Multiply", "Diamondback Hyperfluxor: faster attack (-25%, assumption)"),
        ("Unit", "Diamondback", "Speed", "1.25", "Multiply", "Diamondback Maglev Propulsion (+25%, assumption)"),
        # Raven (unit-table): "all spawned abilities have unlimited duration" —
        # 3600 s outlasts any mission while avoiding 0/-1 sentinel semantics.
        ("Behavior", "AutoTurretTimedLife", "Duration", "3600", "Set", "Raven: permanent Auto-Turrets (AP Durable Materials, maxed)"),
        ("Behavior", "PointDefenseDroneTimedLife", "Duration", "3600", "Set", "Raven: permanent Point Defense Drones"),
        # Raven self-point-defense, done the rule-9-safe way (owner's design): rather than a
        # hidden always-on intercept weapon on the unit (which would also be active on enemy
        # Ravens), the player's Raven kit is made FREE to activate — energy cost reduced to 0
        # per player (same field/class as the free-cloak edits). Combined with the permanent
        # duration above, the player can spam permanent Point Defense Drones + Auto-Turrets =
        # effectively a self-sustaining point-defense platform; Hunter-Seeker stays a free
        # manual nuke. Enemy Ravens keep the vanilla 100/50/125 energy costs (rule 9).
        ("Abil", "PlacePointDefenseDrone", "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Point Defense Drones (player-only)"),
        ("Abil", "BuildAutoTurret", "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Auto-Turrets (player-only)"),
        ("Abil", "SeekerMissile", "Cost[0].Vital[Energy]", "0", "Set", "Raven: free Hunter-Seeker Missile (player-only)"),
        # Battlecruiser (unit-table): fire while moving (AllowedMovement enum is a
        # vanilla field; weapons ship Slowing/Moving — Moving = no slow-to-fire).
        ("Weapon", "ATSLaserBattery", "AllowedMovement", "Moving", "Set", "BC ATX-style: fire while moving (air->surface)"),
        ("Weapon", "ATALaserBattery", "AllowedMovement", "Moving", "Set", "BC fire while moving (air->air)"),
        # BC attacks ignore armor (unit-table). CONFIRMED semantics: ArmorReduction is a
        # MULTIPLIER on how much the target's armor applies (reference values are only 0 /
        # 0.334 / 1; SnipeDamage="ignores armor" sets it to 0). So 0 = ignore armor, 1 =
        # normal. The earlier 500 was BACKWARDS — it would make armor reduce BC damage 500x
        # (≈0 damage to any armored target). Corrected to 0.
        ("Effect", "ATSLaserBatteryU", "ArmorReduction", "0", "Set", "BC attacks ignore armor (ground): ArmorReduction multiplier 1->0"),
        ("Effect", "ATALaserBatteryU", "ArmorReduction", "0", "Set", "BC attacks ignore armor (air)"),

        # ========================================================================
        # PARITY + COMPLETENESS SWEEP (rules 4/10). Mercs & heroes use DISTINCT
        # weapon ids, so base-unit weapon edits never reach them — mirror them here.
        # Also fills base-unit Laser-Targeting gaps. Range/Sight via Add (robust to
        # each weapon's base value). All per-player (rule 9 safe).
        # ========================================================================
        # -- Base-unit LTS gaps (AP list has Laser Targeting: +1 range, +2 sight) --
        ("Weapon", "P38ScytheGuassPistol", "Range", "1", "Add", "Reaper LTS: +1 range"),
        ("Unit", "Reaper", "Sight", "2", "Add", "Reaper LTS: +2 sight"),
        # (Reaper Jet Pack Overdrive dropped per owner: literal flight needs a forbidden
        #  unit-type morph, and the owner is fine with the Reaper NOT shooting air — so the
        #  anti-air TargetFilters edit was reverted; the Reaper keeps its vanilla ground-only
        #  targeting.)
        ("Weapon", "CrucioShockCannon", "Range", "1", "Add", "Siege Tank LTS: +1 sieged range"),
        ("Weapon", "90mmCannons", "Range", "1", "Add", "Siege Tank LTS: +1 mobile range"),
        ("Unit", "SiegeTank", "Sight", "2", "Add", "Siege Tank LTS: +2 sight"),
        ("Unit", "SiegeTankSieged", "Sight", "2", "Add", ""),
        ("Weapon", "ThorsHammer", "Range", "1", "Add", "Thor LTS: +1 ground range"),
        ("Unit", "Thor", "Sight", "2", "Add", "Thor LTS: +2 sight"),
        ("Unit", "Banshee", "Sight", "2", "Add", "Banshee LTS: +2 sight"),
        # -- Marauder line: Hammer Securities (merc) + Swann (hero): range, sight, +2 armor --
        ("Weapon", "HammerSecurity", "Range", "1", "Add", "Hammer Securities: Marauder LTS range"),
        ("Unit", "HammerSecurity", "Sight", "2", "Add", ""),
        ("Unit", "HammerSecurity", "LifeArmor", "2", "Add", "Hammer Securities: Juggernaut Plating"),
        ("Weapon", "DutchConcussiveGrenade", "Range", "1", "Add", "Swann: Marauder LTS range"),
        ("Unit", "Swann", "Sight", "2", "Add", ""),
        ("Unit", "Swann", "LifeArmor", "2", "Add", "Swann: Juggernaut Plating"),
        # -- Firebat line: Kinetic Foam +100 HP to Devil Dogs + Tychus (on top of x2);
        #    Nano Projectors +2 range to the Devil Dog flamethrower only (Tychus = chaingun) --
        ("Unit", "DevilDog", "LifeMax", "100", "Add", "Devil Dogs: Kinetic Foam +100"),
        ("Unit", "DevilDog", "LifeStart", "100", "Add", ""),
        ("Weapon", "DevilDogFlameThrower", "Range", "2", "Add", "Devil Dogs: Nano Projectors +2 range"),
        ("Unit", "TychusCommando", "LifeMax", "100", "Add", "Tychus: Kinetic Foam +100"),
        ("Unit", "TychusCommando", "LifeStart", "100", "Add", ""),
        ("Unit", "TychusChaingun", "LifeMax", "100", "Add", ""),
        ("Unit", "TychusChaingun", "LifeStart", "100", "Add", ""),
        # -- Ghost line: Nova (=Ghost) range + sight --
        ("Weapon", "Nova", "Range", "1", "Add", "Nova (=Ghost): LTS range"),
        ("Unit", "Nova", "Sight", "2", "Add", ""),
        # -- Spectre line: Tosh (=Spectre) range + sight --
        ("Weapon", "Tosh", "Range", "1", "Add", "Tosh (=Spectre): LTS range"),
        ("Unit", "Tosh", "Sight", "2", "Add", ""),
        # -- Goliath line: Ares-Class (+3 AA / +1 cannon range) + Shaped Hull (+25).
        #    Goliath has NO Laser Targeting (its AP list omits it). --
        ("Weapon", "GoliathA", "Range", "3", "Add", "Goliath Ares-Class: +3 AA range"),
        ("Weapon", "GoliathG", "Range", "1", "Add", "Goliath Ares-Class: +1 cannon range"),
        ("Weapon", "GoliathAUpgraded", "Range", "3", "Add", ""),
        ("Weapon", "GoliathGUpgraded", "Range", "1", "Add", ""),
        ("Weapon", "SpartanCompanyA", "Range", "3", "Add", "Spartan Company: Ares-Class parity"),
        ("Weapon", "SpartanCompanyG", "Range", "1", "Add", ""),
        ("Weapon", "SpartanCompanyAUpgraded", "Range", "3", "Add", ""),
        ("Weapon", "SpartanCompanyGUpgraded", "Range", "1", "Add", ""),
        ("Unit", "SpartanCompany", "LifeMax", "25", "Add", "Spartan Company: Shaped Hull +25"),
        ("Unit", "SpartanCompany", "LifeStart", "25", "Add", ""),
        # -- Siege Tank line: Siege Breakers (range, sight, +3 armor sieged) --
        ("Weapon", "SiegeBreaker", "Range", "1", "Add", "Siege Breakers: LTS mobile range"),
        ("Weapon", "ArcliteShockCannon", "Range", "1", "Add", "Siege Breakers: LTS sieged range"),
        ("Unit", "SiegeBreaker", "Sight", "2", "Add", ""),
        ("Unit", "SiegeBreakerSieged", "Sight", "2", "Add", ""),
        ("Unit", "SiegeBreakerSieged", "LifeArmor", "3", "Add", "Siege Breakers: Advanced Siege Tech +3"),
        # -- Banshee line: Dusk Wings (range, sight) --
        ("Weapon", "DuskWingBanshee", "Range", "2", "Add", "Dusk Wings: Banshee range parity"),
        ("Unit", "DuskWing", "Sight", "2", "Add", ""),
        # -- Thor line: Odin (ground range, sight; AA range/dmg done; ground splash in XML) --
        ("Weapon", "Odin", "Range", "1", "Add", "Odin (=Thor): LTS ground range"),
        ("Unit", "Odin", "Sight", "2", "Add", ""),
        # -- BC line: Jackson's Revenge — fire-while-moving parity (armor/speed done;
        #    ignore-armor on DR damage effects deferred — see uncertainty list) --
        ("Weapon", "DRBattlecruiserG", "AllowedMovement", "Moving", "Set", "Jackson's Revenge: fire while moving (ground)"),
        ("Weapon", "DRBattlecruiserA", "AllowedMovement", "Moving", "Set", "Jackson's Revenge: fire while moving (air)"),
        ("Weapon", "DRCannonsG", "AllowedMovement", "Moving", "Set", ""),
        ("Weapon", "DRCannonsA", "AllowedMovement", "Moving", "Set", ""),

        # -- SCV: Hostile Environment Adaptation — slightly faster attack (AP) --
        ("Weapon", "FusionCutter", "Period", "0.7", "Set", "SCV: faster attack (Hostile Env Adaptation)"),
        # -- Vulture: Auto-Launchers — attack while moving (AP). Ion Thrusters speed
        #    + Jerry-Rigged + Cerberus mine count handled earlier. --
        ("Weapon", "Vulture", "AllowedMovement", "Moving", "Set", "Vulture Auto-Launchers: fire while moving"),
        # Wraith Advanced Laser Technology (AP): stronger air+ground lasers, faster fire.
        # Per-player; reaches MercWraith (Winged Nightmares) automatically — it's a
        # parent="Wraith" clone with no WeaponArray override, so it shares WraithA/G ids.
        ("Effect", "WraithAU", "Amount", "2", "Multiply", "Wraith Advanced Laser Tech: air laser dmg x2 (5->10)"),
        ("Effect", "WraithGU", "Amount", "2", "Multiply", "Wraith Advanced Laser Tech: ground laser dmg x2 (8->16)"),
        ("Weapon", "WraithA", "Period", "0.8", "Multiply", "Wraith Advanced Laser Tech: faster air attack (1.25->1.0)"),
        ("Weapon", "WraithG", "Period", "0.8", "Multiply", "Wraith Advanced Laser Tech: faster ground attack (1.694->1.355)"),

        # --- Special elite mercs (player-only clones; rule-9 safe) ---
        # Senior Ghost: 1.5x Life/Energy/regen via Multiply on the Ghost-clone's inherited
        # base values (damage +50% + armor are handled in static XML — see UnitData).
        ("Unit", "MercSeniorGhost", "LifeMax", "1.5", "Multiply", "Senior Ghost: 1.5x life"),
        ("Unit", "MercSeniorGhost", "LifeStart", "1.5", "Multiply", ""),
        ("Unit", "MercSeniorGhost", "EnergyMax", "1.5", "Multiply", "Senior Ghost: 1.5x energy"),
        ("Unit", "MercSeniorGhost", "EnergyStart", "1.5", "Multiply", ""),
        ("Unit", "MercSeniorGhost", "EnergyRegenRate", "1.5", "Multiply", "Senior Ghost: 1.5x energy regen"),
        # Midnight Riders (Liberator merc): AP Laser Targeting +2 vision (range via behavior).
        ("Unit", "MercLiberator", "Sight", "2", "Add", "Midnight Riders: Liberator LTS +2 vision"),
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

    lines.append("}")
    lines.append("")
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    emit()
