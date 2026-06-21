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
    "Medivac": 31.0,   # 42 * 0.75 (rounded) — Optimized Logistics, makes the WoLUUpgOptLogistics face true
}

# Rule 8: free cloak — ability ids with an energy activation cost, and buff
# behaviors with an energy drain (negative regen). Extracted from the catalogs
# below; listed explicitly so the output is reviewable.
CLOAK_ABILS = ["GhostCloak", "BansheeCloak", "WraithCloak", "RogueGhostCloak",
               "DuskWingBansheeCloakingField"]  # no "SpectreCloak": dead id — Spectres cloak via
#              RogueGhostCloak (already listed); the bogus id was a silent no-op (preview CHECK8)
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


# Rule: Terran add-ons build in 10 s. Add-on build time lives on a CAbilBuild's
# InfoArray[BuildN].Time — the SAME verified per-player nested-scalar class as
# CAbilTrain InfoArray[TrainN].Time and EngineeringBayResearch InfoArray[ResearchN].Time
# (an attr on the InfoArray element; CHECK8-GOOD once preview.py's classifier accepts
# Build*). We ENUMERATE the (ability, BuildIndex, unit) set from the reference catalogs
# rather than hardcoding, so any new add-on Build entry is covered automatically.
ADDON_ABILS = ["BarracksAddOns", "FactoryAddOns", "StarportAddOns"]
ADDON_BUILD_TIME = 10.0


def addon_build_entries():
    """(abil id, build index, unit, time) for the Terran add-on CAbilBuild abilities,
    for every InfoArray that builds a *TechLab / *Reactor / *TechReactor. Later catalogs
    win on Time (libertystory adds the Build3/Build4 TechReactor entries on top of the base
    Build1 TechLab / Build2 Reactor)."""
    entries = {}
    for _, root in load("AbilData.xml"):
        for abil in root.iter("CAbilBuild"):
            aid = abil.get("id")
            if aid not in ADDON_ABILS:
                continue
            for info in abil.findall("InfoArray"):
                idx = info.get("index")
                unit_el = info.find("Unit")
                unit = unit_el.get("value") if unit_el is not None else info.get("Unit")
                time = info.get("Time")
                if time is None:
                    t_el = info.find("Time")
                    time = t_el.get("value") if t_el is not None else None
                if idx and unit and (unit.endswith("TechLab") or unit.endswith("Reactor")
                                     or unit.endswith("TechReactor")):
                    key = (aid, idx)
                    prev = entries.get(key)
                    entries[key] = (unit, float(time) if time else (prev[1] if prev else None))
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
    # Train1-8 = the vanilla mercs; Train9-13 + Train15 = our extra elite mercs (Skibi's
    # Angels / Death Heads / Condor / Jotun / Winged Nightmares / Senior Ghost, defined in
    # static XML) — reassert unlimited-from-start on their static defaults. (Train14 Midnight
    # Riders + Train16 Brynhilds removed per owner; the extra loop iterations are harmless
    # no-ops on the now-absent InfoArray entries.)
    for n in range(1, 16):
        for field, val in (
            ("Charge.CountMax", "99"),
            ("Charge.CountStart", "99"),
            ("Charge.CountUse", "0"),
            ("Cooldown.TimeStart", "0"),
            ("Cooldown.TimeUse", "0"),
        ):
            lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "SummonMercenaries", "InfoArray[Train{n}].{field}", p, "{val}", c_upgradeOperationSet);')

    lines.append("")
    lines.append("    // --- Merc calldown cost parity: match the base unit's per-player cost cut ---")
    # Several base units get a per-player CostResource cut (AP Resource Efficiency etc. in
    # stat_edits below). That edits the UNIT's TRAIN cost — it does NOT reach the merc
    # counterpart, whose summon cost is the SummonMercenaries calldown's InfoArray[TrainN]
    # Resource value (a DIFFERENT field; the merc UNIT's CostResource is inert — mercs are
    # SUMMONED, not trained). Reduce each merc's calldown cost by the SAME amount its base unit
    # got, floored at 0 (true parity). genlib knows the static base values, so we COMPUTE the
    # final at build time as max(0, current - cut) and emit a Set (no negative-from-Subtract
    # risk). Only emitted where the resource is actually present AND the value actually changes.
    # The Resource path is InfoArray[TrainN].Resource[Minerals]/[Vespene] (verified vs the
    # vanilla SummonMercenaries Train2 = Min 100 / Ves 75 and our static Train9-15). Heroes are
    # map-PLACED (never trained) → their cost is moot, nothing to do.
    #
    # (Train index, current Min, current Ves, Min cut, Ves cut, merc label)
    #   Vanilla mercs (Train1-8, reference catalog) + extra elite mercs (Train9-15, our XML).
    #   Only mercs whose BASE unit gets a cost cut appear here; the rest stay unchanged.
    MERC_COST_CUTS = [
        # Train  curMin  curVes  cutMin  cutVes  label
        ("Train2",  100,   75,     25,    25,   "Devil Dogs (Firebat -25/-25)"),
        ("Train3",  None,  25,     25,    25,   "Spartan Company (Goliath -25/-25; no minerals)"),
        ("Train9",  100,   None,   25,    25,   "Skibi's Angels / MercMedic (Medic -25/-25; no vespene)"),
        ("Train10", 100,   None,   25,    25,   "Death Heads / MercReaper (Reaper -25/-25; no vespene)"),
        ("Train15", 175,   None,  100,    50,   "Senior Ghost / MercSeniorGhost (Ghost -100/-50; no vespene)"),
    ]
    for train, cur_min, cur_ves, cut_min, cut_ves, label in MERC_COST_CUTS:
        for res, cur, cut in (("Minerals", cur_min, cut_min), ("Vespene", cur_ves, cut_ves)):
            if cur is None:        # resource not present on this calldown → nothing to cut
                continue
            final = max(0, cur - cut)
            if final == cur:       # cut floored to no change (e.g. base unit got no cut here)
                continue
            lines.append(
                f'    CatalogFieldValueModify(c_gameCatalogAbil, "SummonMercenaries", '
                f'"InfoArray[{train}].Resource[{res}]", p, "{final}", c_upgradeOperationSet);  '
                f'// {label}: {res} {cur} -> {final}')

    lines.append("")
    lines.append("    // --- Terran add-ons build in 10 s (build-time cap on add-on CAbilBuild Time) ---")
    # InfoArray[BuildN].Time on BarracksAddOns/FactoryAddOns/StarportAddOns — the same verified
    # per-player nested-scalar class as Train/Research Time (CHECK8-GOOD). Enumerated from the
    # reference catalogs (Build1=TechLab 25s, Build2=Reactor 50s, Build3/Build4=TechReactor 50s on
    # ALL THREE add-on abilities — Starport included, which the original analysis missed; the sweep
    # caught it). 10 s is well under the rule-5 60 s cap. Buildings have no merc/hero variant, so
    # this is rule-9-safe with no parity mirroring needed.
    for (aid, idx), (unit, time) in sorted(addon_build_entries().items()):
        if time == ADDON_BUILD_TIME:
            continue
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "{aid}", "InfoArray[{idx}].Time", p, "{ADDON_BUILD_TIME}", c_upgradeOperationSet);  // {unit}, was {time}')

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
        # The SIEGED form is a SEPARATE unit id — it must get the SAME -1 supply, or morphing to
        # siege charges the missing +1 supply (regression that broke The Dig). Both forms are
        # vanilla -3 -> -2 = 2 supply, so sieging stays supply-neutral.
        ("Unit", "SiegeTankSieged", "Food", "1", "Add", "Sieged tank: match mobile supply (no +1 on siege)"),
        ("Unit", "Raven", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Raven", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Raven", "Food", "1", "Add", ""),
        ("Unit", "Medivac", "CostResource[Minerals]", "25", "Subtract", "AP Resource Efficiency (assumption)"),
        ("Unit", "Medivac", "CostResource[Vespene]", "25", "Subtract", ""),
        ("Unit", "Medivac", "Food", "1", "Add", ""),
        # (Removed per-unit CargoSize=1 on Firebat/Marauder/Ghost/Spectre: CargoSize is a bunker
        #  LOAD-time read, so the per-player runtime edit is a no-op [preview CHECK8 / learnings].
        #  The working "infantry fit the bunker" lever is the BunkerTransport scalars below.)
        # #3 (v0.3.8): BIG bunker — 32 space, Thors allowed (owner decision). The UI "open
        # slots" bar is driven by TotalCargoSpace (=32); the previous MaxCargoCount=4 was the
        # *unit-count* cap that bound FIRST → the bar showed 32 but only 4 units loaded (the
        # regression). Raise MaxCargoCount to 32 so TotalCargoSpace becomes the binding limit:
        # displayed slots == real capacity. 32 size-1 marines, OR 4 size-8 Thors, OR any mix by
        # space (a Thor legitimately consumes 8/32). MaxCargoSize=8 admits the size-8 Thor
        # (vanilla 2 rejected anything bigger than a Goliath). CargoSize per-player is read at
        # bunker LOAD time and the runtime edit doesn't reach it (confirmed in game — Ghost still
        # took 2 slots), so we DON'T try to force CargoSize=1; every unit costs its real size.
        # The ground-only gate is the static TargetFilters edit (AbilData; Air excluded). These
        # MaxCargoCount/Size/TotalCargoSpace are scalar fields of the SAME class+ability-kind as
        # the working per-player MedivacTransport.MaxCargoCount=12 edit (Expanded Hull, treated as
        # working) → they apply per player; in particular MaxCargoCount IS runtime-editable here.
        ("Abil", "BunkerTransport", "MaxCargoCount", "32", "Set", "high count cap so TotalCargoSpace (32) is the binding limit — displayed slots == real capacity"),
        ("Abil", "BunkerTransport", "MaxCargoSize", "8", "Set", "admit large ground units (Thor=8) — vanilla 2 rejected them"),
        ("Abil", "BunkerTransport", "TotalCargoSpace", "32", "Set", "32-space bar fully usable: 32 marines, or 4 Thors, or any mix by space"),
        # Bunker durability (owner: too squishy). Vanilla Bunker (liberty.sc2mod) LifeMax=400,
        # LifeStart=400, LifeArmor=1; no campaign layer overrides these. There is NO Bunker merc/
        # hero/clone in WoL, so a single per-player Bunker edit suffices (no parity mirroring).
        # LifeMax/LifeStart/LifeArmor are CHECK8-GOOD scalar field classes (apply per player).
        # LifeStart ×4 so a freshly-built bunker spawns at the new max (400/1600 otherwise).
        ("Unit", "Bunker", "LifeMax", "4", "Multiply", "Bunker: 4x HP (400 -> 1600) — owner: too squishy"),
        ("Unit", "Bunker", "LifeStart", "4", "Multiply", "Bunker: start at full new max"),
        ("Unit", "Bunker", "LifeArmor", "3", "Set", "Bunker: >=3 armor (vanilla 1, building-armor upgrades don't reach it) — set flat 3"),
        # damage flattening: the Amount edit raises the base (GOOD, applies per player); the paired
        # AttributeBonus[Light/Armored]=0 lines were REMOVED — they were no-ops (indexed-array element,
        # preview CHECK8). Net: the rifles ship with the base raised but the +vs-light/armored bonus
        # STILL PRESENT (Ghost 20 +10 vs light, Spectre 20 +5 vs armored). True flat-N needs a
        # Shaped-Blast effect clone (recipe 13) — tracked in open-issues "X dmg + X vs light/armored".
        ("Effect", "C10CanisterRifle", "Amount", "20", "Set", "Ghost rifle: base 10 -> 20"),
        ("Effect", "SpecterU", "Amount", "20", "Set", "Spectre rifle: base 15 -> 20"),
        # Thor AA: range = HIP 11 + 1. The flat-35 (no light bonus) for the PLAYER is delivered by the
        # JavelinMissileLaunchersDamageBuffedWoLU effect clone (player branch), not this base edit.
        ("Effect", "JavelinMissileLaunchersDamage", "Amount", "35", "Set", "Thor AA base -> 35 (player path uses the buffed clone)"),
        ("Weapon", "JavelinMissileLaunchers", "Range", "12", "Set", "Thor AA range = HIP range 11 + 1"),
        # Thor AA barrage (owner): DOUBLE the missiles per attack AND cut the attack interval to 2/3.
        #  PeriodCount on the CEffectCreatePersistent = how many missiles a single attack fires; the
        #  weapon's DisplayAttackCount is the panel's "Nx" multiplier (kept honest = same ×2 so the panel
        #  total matches the real 8). Period is the attack interval. All three are plain scalar value=
        #  children (NOT array elements) → CHECK8-GOOD per-player class, same shape as Range/Period above.
        #  Multiply (not Set) so they scale whatever upgrades/edits leave the live value at.
        #  Reaches MercThor (Jotun) for free: parent="Thor", no WeaponArray override → shares these ids.
        #  PeriodicPeriodArray has 4 entries [0,0.125,0.25,0.125]; PeriodCount=8 overruns it, so SC2
        #  repeats the last entry (0.125) for missiles 5-8 → barrage spans 0+0.125+0.25+0.125+0.125*4 = 1.0s,
        #  which fits inside the new ~2.0s weapon Period (no overlap).
        ("Effect", "JavelinMissileLaunchersPersistent", "PeriodCount", "2", "Multiply", "Thor/Jotun AA: double missiles per attack (4 -> 8)"),
        ("Weapon", "JavelinMissileLaunchers", "DisplayAttackCount", "2", "Multiply", "Thor/Jotun AA: panel count matches the real 8 (4 -> 8)"),
        ("Weapon", "JavelinMissileLaunchers", "Period", "0.6667", "Multiply", "Thor/Jotun AA: attack interval to 2/3 (3 -> ~2.0)"),
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
        # (Removed: Button.Requirements="" for Hercules (StarportTrain Train6) + Marauder
        #  (BarracksTrain Train4) — a requirement-LINK field, confirmed no-op per-player
        #  [preview CHECK8]. The feature is OWNER-BLOCKED: the only working lever
        #  TechTreeRestrictionsEnable(p,false) also strips the Merc Compound requirement (rule 6).
        #  Tracked in open-issues "Marauder Tech Lab / Hercules Fusion Core drop".)
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
        # Odin AA barrage (rule 10 — Odin = Thor hero): same DOUBLE-missiles + 2/3-interval as the base
        #  Thor, on Odin's SEPARATE AA chain (weapon OdinAntiAir -> persistent OdinAA). Same CHECK8-GOOD
        #  scalar fields. OdinAA's PeriodicPeriodArray is [0,0.2,0.2,0.2]; PeriodCount=8 repeats the last
        #  (0.2) for missiles 5-8 → barrage spans 0+0.2*7 = 1.4s, fitting inside the new ~1.667s Period.
        ("Effect", "OdinAA", "PeriodCount", "2", "Multiply", "Odin AA: double missiles per attack (4 -> 8)"),
        ("Weapon", "OdinAntiAir", "DisplayAttackCount", "2", "Multiply", "Odin AA: panel count matches the real 8 (4 -> 8)"),
        ("Weapon", "OdinAntiAir", "Period", "0.6667", "Multiply", "Odin AA: attack interval to 2/3 (2.5 -> ~1.667)"),
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
        # Firebat: flat +5 attack damage to ALL targets (owner request — replaces the old
        #  "Infernal Pre-Igniter +vs-light" framing with a clean flat buff). FirebatUFull is the
        #  Firebat's single damage effect (weapon Firebat -> FirebatSet -> [Firebat persistent,
        #  FirebatUFull]; the persistent flame's FlameThrowerDamageSet also fires FirebatUFull).
        #  Effect.Amount is the CHECK8-GOOD per-player damage field. NOTE: the +4-vs-LIGHT bonus is
        #  HARDCODED in static XML on this same effect (AttributeBonus[Light]=4) and CANNOT be
        #  removed per-player without an effect clone (recipe 13) — it persists; the unit now reads
        #  13 (+4 vs light). See open-issues + the dispatch report (part 2 stopped at the guardrail).
        ("Effect", "FirebatUFull", "Amount", "5", "Add", "Firebat: +5 flat attack damage (8 -> 13). +4-vs-light still hardcoded in XML (see open-issues)"),
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
        # (Removed v0.3.x: the "Abil NanoRepair Cost[0].Vital[Energy]=0" edit. The player's SV
        #  heal is now the passive WoLUSVHealAura behavior (a permanent hidden CBehaviorBuff that
        #  periodically heals all nearby friendlies, applied player-only via libWoLU_AddBehaviorToType,
        #  not a per-player cost edit); the vanilla NanoRepair button is no longer card-exposed to
        #  the player, so the old edit was an orphaned no-op — dropped to avoid a misleading line.)
        ("Effect", "OdinAADamage", "Amount", "35", "Set", "Odin AA mirrors Thor: HIP floor 35/rocket (was 15, no light bonus)"),
        ("Abil", "heal", "Range", "4", "Set", "Medic Nano Projector: +2 heal range (2->4)"),
        # (Removed: heal TargetFilters — a string field, no-op per-player [preview CHECK8]. The
        #  heal-mechanical/air feature is already delivered by the HealWoLU clone on the Medic +
        #  Stetmann AbilArray (recipe 09); this runtime edit was dead-redundant.)
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
        # ALL BCs fire 3x faster: weapon Period /3 (base BC ATS/ATA + Jackson's Revenge DR weapons).
        # Period is the per-player "fire rate" scalar (GOOD class). These weapons set no explicit
        # DamagePoint/Backswing (engine default 0.167) → the rule-7 pass sets DamagePoint=0.1, which
        # would bottleneck the new 0.075 s period. So ALSO trim DamagePoint(0.04)+Backswing(0.02)
        # below the new period so the full 3x rate actually holds (rule-7-compliant: 0.04 < 0.1).
        ("Weapon", "ATSLaserBattery", "Period", "0.3333", "Multiply", "BC fire 3x faster (0.225 -> 0.075)"),
        ("Weapon", "ATALaserBattery", "Period", "0.3333", "Multiply", "BC fire 3x faster (AA)"),
        ("Weapon", "DRBattlecruiserG", "Period", "0.3333", "Multiply", "Jackson's Revenge fire 3x faster (ground)"),
        ("Weapon", "DRBattlecruiserA", "Period", "0.3333", "Multiply", "Jackson's Revenge fire 3x faster (air)"),
        ("Weapon", "DRCannonsG", "Period", "0.3333", "Multiply", "Jackson's Revenge cannons 3x faster (ground)"),
        ("Weapon", "DRCannonsA", "Period", "0.3333", "Multiply", "Jackson's Revenge cannons 3x faster (air)"),
        ("Weapon", "ATSLaserBattery", "DamagePoint", "0.04", "Set", "BC: trim windup so the 3x rate isn't bottlenecked"),
        ("Weapon", "ATSLaserBattery", "Backswing", "0.02", "Set", ""),
        ("Weapon", "ATALaserBattery", "DamagePoint", "0.04", "Set", ""),
        ("Weapon", "ATALaserBattery", "Backswing", "0.02", "Set", ""),
        ("Weapon", "DRBattlecruiserG", "DamagePoint", "0.04", "Set", ""),
        ("Weapon", "DRBattlecruiserG", "Backswing", "0.02", "Set", ""),
        ("Weapon", "DRBattlecruiserA", "DamagePoint", "0.04", "Set", ""),
        ("Weapon", "DRBattlecruiserA", "Backswing", "0.02", "Set", ""),
        ("Weapon", "DRCannonsG", "DamagePoint", "0.04", "Set", ""),
        ("Weapon", "DRCannonsG", "Backswing", "0.02", "Set", ""),
        ("Weapon", "DRCannonsA", "DamagePoint", "0.04", "Set", ""),
        ("Weapon", "DRCannonsA", "Backswing", "0.02", "Set", ""),

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
        # Firebat +5 damage parity (rule 4 — keep the merc's % advantage). DevilDogDamage is the
        #  flamethrower's damage effect (DevilDogSet -> [DevilDogCreatePersistent, DevilDogDamage]).
        #  DevilDog base 10 / Firebat base 8 = 1.25 ratio -> scale +5 by 1.25 = +6.25 (10 -> 16.25).
        #  (Like the Firebat, the +5-vs-light AttributeBonus on DevilDogDamage stays hardcoded.)
        ("Effect", "DevilDogDamage", "Amount", "6.25", "Add", "Devil Dogs: Firebat +5 parity x1.25 ratio (10 -> 16.25)"),
        # Tychus (rule 10, Firebat hero) — chaingun, NOT the flamethrower. Two units/weapons:
        #  TychusCommando -> TychusCommandoChaingun -> TychusCommandoAttackDamage (Amount 5),
        #  TychusChaingun -> TychusChaingun weapon (Effect defaults to its own id) -> TychusChaingun
        #  effect (Amount 16). Add flat +5 to each (inherits the base Firebat +5; no light bonus).
        ("Effect", "TychusCommandoAttackDamage", "Amount", "5", "Add", "TychusCommando: Firebat +5 dmg (chaingun, 5 -> 10)"),
        ("Effect", "TychusChaingun", "Amount", "5", "Add", "TychusChaingun: Firebat +5 dmg (chaingun, 16 -> 21)"),
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
        # (Spartan-from-bunker AA: the per-player Arc=360 candidate was REVERTED v0.3.11 — owner
        #  playtest confirmed a bunkered Spartan STILL won't fire AA, so it's an inherent SC2
        #  turret-from-bunker limitation, not fixable by widening the weapon arc. open-issues "bunker".)
        # SpartanCompany (Goliath merc) parity (v0.3.8). Ground truth: SpartanCompany base
        # LifeMax=165 (liberty.sc2campaign), Goliath base 125 (libertystory layer wins) →
        # buffed Goliath = 125 + 25 (Shaped Hull) = 150. The merc's pre-buff advantage is
        # 165/125 = 1.32; to keep that ratio post-buff the merc needs 150 × 1.32 ≈ 198. A flat
        # +25 → 190 BROKE parity (the merc fell behind its own ratio). +33 → 165 + 33 = 198.
        ("Unit", "SpartanCompany", "LifeMax", "33", "Add", "Spartan Company: parity buff (165 -> 198 = buffed Goliath 150 × 1.32)"),
        ("Unit", "SpartanCompany", "LifeStart", "33", "Add", ""),
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
        # Jackson's Revenge attack-side parity with the base BC: ignore armor (ArmorReduction
        # multiplier 1->0, same as the ATSLaserBatteryU fix). The user saw movement/armor
        # boosts but "nothing on the attack side" — the DR damage effects weren't buffed.
        ("Effect", "DRBattlecruiserGU", "ArmorReduction", "0", "Set", "Jackson's Revenge ignores armor (ground)"),
        ("Effect", "DRBattlecruiserAU", "ArmorReduction", "0", "Set", "Jackson's Revenge ignores armor (air)"),
        ("Effect", "DRCannonsG", "ArmorReduction", "0", "Set", "Jackson's Revenge cannons ignore armor (ground)"),
        ("Effect", "DRCannonsA", "ArmorReduction", "0", "Set", "Jackson's Revenge cannons ignore armor (air)"),

        # -- SCV: Hostile Environment Adaptation — slightly faster attack (AP) --
        ("Weapon", "FusionCutter", "Period", "0.7", "Set", "SCV: faster attack (Hostile Env Adaptation)"),
        # -- Vulture: Auto-Launchers — attack while moving (AP). Ion Thrusters speed
        #    + Jerry-Rigged + Cerberus mine count handled earlier. --
        ("Weapon", "Vulture", "AllowedMovement", "Moving", "Set", "Vulture Auto-Launchers: fire while moving"),
        # -- Smart Servos (AP) — ATTACK-WHILE-MOVING half of the WoLUUpgSmartServos face
        #    (Hellion + Viking). AllowedMovement is a vanilla scalar weapon field (BC pattern,
        #    CHECK8-GOOD); the FASTER-TRANSFORM half is the WoLUSmartServos CUpgrade (UpgradeData).
        #    Hellion: weapon InfernalFlameThrower has NO AllowedMovement (defaults Slowing).
        #    MercHellion (Condor) is parent="Hellion" and SHARES InfernalFlameThrower → reached
        #    automatically (no separate entry needed). --
        ("Weapon", "InfernalFlameThrower", "AllowedMovement", "Moving", "Set", "Hellion Smart Servos: fire while moving"),
        #    Viking air (LanzerTorpedoes, vanilla Slowing) + Viking ground (TwinGatlingCannon, no
        #    AllowedMovement). AllowedMovement is an independent scalar field on the weapon —
        #    unaffected by the TwinGatlingCannon Effect reroute in our WeaponData.xml.
        ("Weapon", "LanzerTorpedoes", "AllowedMovement", "Moving", "Set", "Viking (fighter) Smart Servos: fire while moving"),
        ("Weapon", "TwinGatlingCannon", "AllowedMovement", "Moving", "Set", "Viking (assault) Smart Servos: fire while moving"),
        #    Hel's Angels (Viking merc, standalone — inherits NOTHING, separate weapon ids): air
        #    WreckingCrewFighter (vanilla Slowing) + ground WreckingCrewAssault (no AllowedMovement;
        #    its Effect is rerouted in WeaponData.xml but AllowedMovement is independent).
        ("Weapon", "WreckingCrewFighter", "AllowedMovement", "Moving", "Set", "Hel's Angels (fighter): Smart Servos fire while moving parity"),
        ("Weapon", "WreckingCrewAssault", "AllowedMovement", "Moving", "Set", "Hel's Angels (assault): parity"),
        # Wraith Advanced Laser Technology (AP): stronger air+ground lasers, faster fire.
        # Per-player; reaches MercWraith (Winged Nightmares) automatically — it's a
        # parent="Wraith" clone with no WeaponArray override, so it shares WraithA/G ids.
        ("Effect", "WraithAU", "Amount", "2", "Multiply", "Wraith Advanced Laser Tech: air laser dmg x2 (5->10)"),
        ("Effect", "WraithGU", "Amount", "2", "Multiply", "Wraith Advanced Laser Tech: ground laser dmg x2 (8->16)"),
        ("Weapon", "WraithA", "Period", "0.8", "Multiply", "Wraith Advanced Laser Tech: faster air attack (1.25->1.0)"),
        ("Weapon", "WraithG", "Period", "0.8", "Multiply", "Wraith Advanced Laser Tech: faster ground attack (1.694->1.355)"),

        # ========================================================================
        # AP Shaped Hull (+HP) — makes the ShapedHull passive face TRUE on Thor +
        # SiegeTank + Banshee (it was already real on Goliath/SpartanCompany, +25 flat
        # Add via LifeMax/LifeStart — match that established convention exactly; unit-table
        # gives no different per-unit number). NONE of these units currently get any
        # LifeMax/LifeStart edit (confirmed — no double-apply). Flat +25 Add (not Multiply)
        # keeps each merc/hero AHEAD of its buffed base (rule 4). Per-player → rule-9 safe.
        # ========================================================================
        # -- Thor (base LifeMax 400) + family Jotun/Odin --
        ("Unit", "Thor", "LifeMax", "25", "Add", "AP Shaped Hull"),
        ("Unit", "Thor", "LifeStart", "25", "Add", ""),
        #    Jotun (MercThor, parent="Thor") has its OWN explicit LifeMax=500 in our static XML
        #    → the base Thor edit does NOT reach it; needs its own entry (rule 4).
        ("Unit", "MercThor", "LifeMax", "25", "Add", "Jotun: Thor Shaped Hull +25 parity"),
        ("Unit", "MercThor", "LifeStart", "25", "Add", ""),
        #    Odin (standalone Thor hero, LifeMax 2500) — separate id, inherits nothing (rule 10).
        ("Unit", "Odin", "LifeMax", "25", "Add", "Odin: Thor Shaped Hull +25 parity (rule 10)"),
        ("Unit", "Odin", "LifeStart", "25", "Add", ""),
        # -- SiegeTank — HP is PER-FORM (both SiegeTank and SiegeTankSieged define their own
        #    LifeMax=150). Buff BOTH forms or sieging would DROP 25 HP. Family Siege Breakers
        #    (SiegeBreaker + SiegeBreakerSieged, both standalone, LifeMax=200, per-form). --
        ("Unit", "SiegeTank", "LifeMax", "25", "Add", "AP Shaped Hull"),
        ("Unit", "SiegeTank", "LifeStart", "25", "Add", ""),
        ("Unit", "SiegeTankSieged", "LifeMax", "25", "Add", "Shaped Hull: match sieged form so morphing doesn't drop HP"),
        ("Unit", "SiegeTankSieged", "LifeStart", "25", "Add", ""),
        ("Unit", "SiegeBreaker", "LifeMax", "25", "Add", "Siege Breakers: Shaped Hull +25 parity"),
        ("Unit", "SiegeBreaker", "LifeStart", "25", "Add", ""),
        ("Unit", "SiegeBreakerSieged", "LifeMax", "25", "Add", "Siege Breakers: match sieged form"),
        ("Unit", "SiegeBreakerSieged", "LifeStart", "25", "Add", ""),
        # -- Banshee (base LifeMax 140) + family Dusk Wings (DuskWing, standalone, LifeMax 175) --
        ("Unit", "Banshee", "LifeMax", "25", "Add", "AP Shaped Hull"),
        ("Unit", "Banshee", "LifeStart", "25", "Add", ""),
        ("Unit", "DuskWing", "LifeMax", "25", "Add", "Dusk Wings: Banshee Shaped Hull +25 parity"),
        ("Unit", "DuskWing", "LifeStart", "25", "Add", ""),

        # --- Special elite mercs (player-only clones; rule-9 safe) ---
        # Senior Ghost: 1.5x Life/Energy/regen via Multiply on the Ghost-clone's inherited
        # base values (damage +50% + armor are handled in static XML — see UnitData).
        ("Unit", "MercSeniorGhost", "LifeMax", "1.5", "Multiply", "Senior Ghost: 1.5x life"),
        ("Unit", "MercSeniorGhost", "LifeStart", "1.5", "Multiply", ""),
        ("Unit", "MercSeniorGhost", "EnergyMax", "1.5", "Multiply", "Senior Ghost: 1.5x energy"),
        ("Unit", "MercSeniorGhost", "EnergyStart", "1.5", "Multiply", ""),
        ("Unit", "MercSeniorGhost", "EnergyRegenRate", "1.5", "Multiply", "Senior Ghost: 1.5x energy regen"),

        # ========================================================================
        # CHECK10 MERC/HERO-PARITY FIXES (rules 4/10). The per-player edits above are
        # keyed to BASE unit ids; `parent=` elite mercs (Merc*) inherit the base's STATIC
        # XML but NOT these per-player edits, and standalone mercs/heroes inherit nothing.
        # So a base-keyed Unit buff silently SKIPS the counterpart (the recurring class
        # scripts/check_merc_parity.py now guards). Mirror the FUNCTIONAL base buffs onto the
        # counterparts that were missing them, scaled per rule 4 (keep the merc's % advantage)
        # / rule 10 (mirror the base for heroes). Player-only (these ids are player-exclusive).
        # ========================================================================
        # -- Hel's Angels (Viking merc, both modes): Aesir Turbines +55% speed parity. Multiply
        #    preserves any merc % advantage (= the base VikingFighter/VikingAssault edit). --
        ("Unit", "HelsAngelFighter", "Speed", "1.55", "Multiply", "Hel's Angels: Viking Aesir Turbines +55% speed parity"),
        ("Unit", "HelsAngelAssault", "Speed", "1.55", "Multiply", ""),
        # -- Death Heads (Reaper merc, parent="Reaper"): inherit the Reaper's per-player buffs
        #    the merc was missing (base Reaper edits don't reach a parent= clone). LTS sight,
        #    Combat-Drugs regen (Set, same as base), Ballistic Flightsuit +10 life (flat Add on
        #    top of the merc's elite 150 base — keeps it ahead of the buffed base Reaper, rule 4). --
        ("Unit", "MercReaper", "Sight", "2", "Add", "Death Heads: Reaper LTS +2 sight parity"),
        ("Unit", "MercReaper", "LifeRegenRate", "2", "Set", "Death Heads: Reaper Combat Drugs regen parity"),
        ("Unit", "MercReaper", "LifeMax", "10", "Add", "Death Heads: Reaper Ballistic Flightsuit +10 life parity"),
        ("Unit", "MercReaper", "LifeStart", "10", "Add", ""),
        # -- Condor (Hellion merc, parent="Hellion"): Infernal Plating +2 armor parity. --
        ("Unit", "MercHellion", "LifeArmor", "2", "Add", "Condor: Hellion Infernal Plating +2 armor parity"),
        # -- Jotun (Thor merc, parent="Thor"): LTS +2 sight parity (the AA/ground range + windup
        #    reach it via inherited weapon ids; only the unit-keyed Sight was missing). --
        ("Unit", "MercThor", "Sight", "2", "Add", "Jotun: Thor LTS +2 sight parity"),
        # -- Senior Ghost (Ghost merc, parent="Ghost"): LTS +2 sight parity (its 1.5x life/energy
        #    is above; the Ghost weapon-range LTS reaches it via the inherited C10CanisterRifle id;
        #    only the unit-keyed Sight was missing). --
        ("Unit", "MercSeniorGhost", "Sight", "2", "Add", "Senior Ghost: Ghost LTS +2 sight parity"),
        # (Midnight Riders / Brynhilds removed per owner — their intended Liberator/Valkyrie
        #  models don't exist in WoL, so they only ever looked like a Viking/Wraith.)
    ]
    for cat, entry, field, val, op, comment in stat_edits:
        suffix = f"  // {comment}" if comment else ""
        lines.append(f'    CatalogFieldValueModify(c_gameCatalog{cat}, "{entry}", "{field}", p, "{val}", c_upgradeOperation{op});{suffix}')

    lines.append("")
    lines.append("    // --- Engineering Bay: combined upgrades research in 30 s (weapon/armor levels) ---")
    # The Eng Bay buttons the player clicks differ by LAB state: BEFORE the Ultra-Capacitors /
    # Vanadium-Plating lab research, Research3/4/5 (weapons) + Research7/8/9 (armors) grant the
    # BASE Level ids (liberty.sc2mod AbilData.xml:1699-1734); AFTER it, those hide and
    # Research11/12/13 (weapons) + Research14/15/16 (armors) grant the UltraCapacitors/
    # VanadiumPlating wrappers (libertystory.sc2campaign AbilData.xml:172-201). Set 30 s on ALL
    # of them so the "30 s each" feature holds in BOTH lab states.
    for idx in ("Research3", "Research4", "Research5", "Research7", "Research8", "Research9",
                "Research11", "Research12", "Research13", "Research14", "Research15", "Research16"):
        lines.append(f'    CatalogFieldValueModify(c_gameCatalogAbil, "EngineeringBayResearch", "InfoArray[{idx}].Time", p, "30", c_upgradeOperationSet);')

    # NOTE: hero stim abilities/buttons are NOT granted here — CatalogFieldValueModify
    # cannot CREATE array entries (AbilArray/LayoutButtons), only edit existing ones.
    # They live in src/mod/Base.SC2Data/GameData/UnitData.xml instead (hero units are
    # player-exclusive, so static XML is rule-9-safe for them).

    lines.append("}")
    lines.append("")
    # Force UTF-8 + LF regardless of platform: Windows' default file encoding is
    # cp1252 and text mode rewrites \n -> \r\n, which would mangle the em-dash/×
    # comment chars and flip line endings vs the committed (Mac-authored) lib.
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    emit()
