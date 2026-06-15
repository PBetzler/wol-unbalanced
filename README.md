# WoL Unbalanced

A **StarCraft II: Wings of Liberty** campaign mod for [GiantGrantGames' Custom Campaign Manager](https://github.com/7thAce/SC2CCM), built around one idea: **your army becomes funnily overpowered, the enemy stays exactly vanilla.**

> ⚠️ **Not to be taken seriously.** This is a power-fantasy romp through the WoL campaign, not a balance patch. It's in the name.

> 🤖 **Mostly vibe coded.** This project was built in conversation with an AI coding agent (Claude), largely as an experiment to check what current models are capable of — from reverse-engineering MPQ archives and Blizzard's campaign trigger libraries to generating the Galaxy script that applies the changes. Expect pragmatic solutions and the occasional rough edge.

## What it does

All changes apply **only to the player's units** — enemies keep vanilla stats.

- **Every campaign armory upgrade is auto-unlocked** the moment its unit is unlocked — no credits needed.
- **Both sides of every either/or choice**: each lab research pair grants both options, and you get Ghost *and* Spectre, Raven *and* Science Vessel, Predator *and* Hercules.
- **Mercenaries are hired automatically** as soon as their regular counterpart is unlocked.
- **No unit builds longer than 60 s** (Battlecruiser 110→60 s; Hercules 20 s; Predator 10 s).
- **Attack windup (damage point) capped at 0.1 s** for player weapons — Firebats and Thors feel *snappy*.
- **Cloaking is always free**: no energy cost, no drain.
- Per-unit buffs (Marines +20 HP is just the start) — the full change list lives in [unit-table.md](unit-table.md) and [plan.md](plan.md), with many more ported from the mods below in progress.

## How it works

The campaign maps stay vanilla — the build pipeline only patches each map's dependency list (`DocumentInfo` + `DocumentHeader`) to load our data mod, injects one `include` into the compiled `MapScript.galaxy`, and rebrands a leftover popup. The mod itself is a component-folder `.SC2Mod` whose Galaxy library applies every change **per player** at mission start (catalog modifications + the campaign's own tech-granting functions, e.g. `libCamp_gf_TS_BuyAllTech`). No maps are ever re-saved in the editor. Details in [plan.md](plan.md).

## Download & install

Grab the latest `WoL-Unbalanced-*.zip` from the [Releases page](../../releases) and import it with [GiantGrantGames' Custom Campaign Manager](https://github.com/7thAce/SC2CCM) like any other custom campaign (the zip follows the standard CCM layout: one folder with the mission maps, the mod, and `metadata.txt`). The maps in the zip are Blizzard's own Wings of Liberty campaign maps with one changed dependency line, as is standard for CCM campaigns.

Releases for mod-only changes are automated: pushing a `v*` tag repacks the previous release zip with the current mod ([release workflow](.github/workflows/release.yml)). Map-affecting changes need a local `python3 scripts/build.py package` once.

## Building

This repo contains **only our own code and data** — no Blizzard content and no third-party mod files are redistributed. To build you need to provide (under the gitignored `mods/` folder):

1. A vanilla-equivalent WoL map set as map base (we use the *Tactical Arsenal* campaign's maps — see credits; alternatively export the campaign maps from the SC2 Editor),
2. The Liberty catalog XML dumps from [SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData) under `mods/_reference/`,
3. [StormLib](https://github.com/ladislav-zezula/StormLib) cloned into `vendor/` and built, then `c++ tools/mpqpatch.c -o tools/mpqpatch -Ivendor/StormLib/src -Lvendor/StormLib/build -lstorm -lz -lbz2`.

Then:

```sh
python3 scripts/genlib.py        # regenerate the data-application Galaxy script
python3 scripts/build.py build   # assemble the campaign (maps + mod + metadata)
python3 scripts/build.py install # copy into the StarCraft II folder
```

## Credits

This mod stands on the shoulders of the SC2 custom campaign community. Used as blueprints, references and data sources:

- **[StarCraft II Archipelago](https://github.com/TheCondor07/Starcraft2ArchipelagoData)** (TheCondor07) and the [Archipelago](https://github.com/ArchipelagoMW/Archipelago) SC2 world — the main inspiration for the per-unit upgrade pool.
- **Wings of Liberty Perpetual Randomizer** by fishmaster26 — upgrade-pool ideas and the reference for how CCM campaigns are structured.
- **Wings of Liberty Nightmare Difficulty** by Rhyme (TheRealRhyme) — reference for clean data-catalog patching, and the base for the optional Nightmare-difficulty build (`build.py build nightmare` layers our mod on top of Rhyme's pack; if that variant is distributed it bundles `NightmareMod.SC2Mod` and Rhyme's maps, the standard CCM way — credit to Rhyme).
- **Tactical Arsenal** by Pierre — upgrade implementation reference, and its vanilla-faithful map set is our (default) map base.
- **Moebius / WoL Nightmare (Moebius Pack)** — data blueprints for several effects: `RemoveDebuff` (Medic Restoration), `BarrelAccelerator` (Wraith Trigger Override), `DamageResponse ModifyFraction` (Predator Adaptive Defenses), and the local-portrait-`CModel` fix (`SCVPortrait2`).
- **Raynor has Gone Rogue(like)! (the RaynorRogue `Kit@` mod)** — blueprints for catalog-defined `CTargetSort*` (smart-Snipe priority) and the multi-target Battlecruiser battery system.
- **EZ Upgrade** — the per-player `CatalogFieldValueModify` pattern.
- **Blizzard's Nova Covert Ops (`novastoryassets`)** — Super Stimpack and railgun (Magrail) blueprints (Blizzard content; see the Blizzard notice below).
- **[SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData)** — vanilla catalog and trigger-library dumps.
- **[GiantGrantGames' Custom Campaign Manager](https://github.com/7thAce/SC2CCM)** (7thAce) and the GGG/CCM Discord community that makes all of this playable.
- [Liquipedia](https://liquipedia.net/starcraft2/) and the [StarCraft Wiki](https://starcraft.fandom.com/) for campaign data research.

## License

Everything original in this repository (scripts, Galaxy code, documentation) is released under the [MIT License](LICENSE) — free use, have fun.

StarCraft® II, the Wings of Liberty campaign, and all related game data and assets are © Blizzard Entertainment, Inc. and subject to the Blizzard End User License Agreement. This is a non-commercial fan modification. The **default build** redistributes no Blizzard game files and no third-party mod files (its maps are Blizzard's own WoL campaign maps with one changed dependency line). The **optional Nightmare-difficulty build** (`build.py build nightmare`) bundles Rhyme's "Nightmare Difficulty" pack — its maps and `NightmareMod.SC2Mod` — the standard self-contained-campaign approach in the CCM ecosystem; distribute that variant only with credit to Rhyme (as above).
