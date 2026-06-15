#!/usr/bin/env python3
"""Quick credits-coverage reminder — run before each release / git upload (see CLAUDE.md
§Repo Hygiene & Releases). Warns if a third-party blueprint source we rely on isn't
mentioned in README.md §Credits. This is a REMINDER, not a hard gate (it's not in the
pre-commit hook); a human still decides what warrants a credit.

When you start copying data/blueprints from a new third-party mod, add it to SOURCES
below — the check then nags until README.md credits it. Blizzard-owned content
(Liberty, Nova Covert Ops, co-op) is covered by the blanket Blizzard notice; NCO is
listed anyway because we lean on its chains heavily.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Third-party source -> a lowercase token that must appear in README.md §Credits.
SOURCES = {
    "StarCraft II Archipelago": "archipelago",
    "WoL Perpetual Randomizer (fishmaster26)": "perpetual randomizer",
    "Nightmare Difficulty (Rhyme)": "rhyme",
    "Tactical Arsenal (Pierre)": "tactical arsenal",
    "Moebius pack": "moebius",
    "RaynorRogue kit": "rogue",
    "EZ Upgrade": "ez upgrade",
    "Blizzard Nova Covert Ops": "nova covert ops",
    "SC2Mapster/SC2GameData": "sc2mapster",
    "GiantGrantGames CCM (7thAce)": "sc2ccm",
}


def main() -> None:
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read().lower()
    missing = [name for name, tok in SOURCES.items() if tok not in readme]
    if missing:
        print("CREDITS reminder — README.md §Credits may be missing a source:")
        for m in missing:
            print(f"  - {m}")
        print("If you used it, add it to README.md Credits (or drop it from "
              "scripts/check_credits.py SOURCES if unused). Reminder, not a gate.")
        sys.exit(1)
    print(f"credits: ok ({len(SOURCES)} tracked sources all present in README §Credits).")


if __name__ == "__main__":
    main()
