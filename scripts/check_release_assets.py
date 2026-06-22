#!/usr/bin/env python3
"""Release-asset enforcement — a published release MUST also ship the Nightmare variant
zip WHEN the Nightmare base is provided locally.

WHY: CI auto-builds only the STANDARD zip (``WoL-Unbalanced-v<VERSION>.zip``) on a ``v*``
tag — it has none of the third-party inputs. The Nightmare zip
(``WoL-Unbalanced-Nightmare-v<VERSION>.zip``) is a LOCAL build + manual ``gh release
upload``, which is the step most easily forgotten. This check queries the GitHub release
and FAILS if:
  * the STANDARD zip is missing, OR
  * the Nightmare base is present locally
    (``mods/Nightmare/extracted/NightmareMod.SC2Mod``) but the Nightmare zip is not
    attached to the release.

When the Nightmare base is ABSENT (a fresh clone / CI), the Nightmare zip is NOT required —
matching the rule "ship Nightmare IF the files are provided locally". This is the published-
release half of the enforcement; the ``pre-push`` git hook is the build-time half (it blocks
pushing the release tag until the Nightmare zip is built locally).

Run: ``python scripts/check_release_assets.py [--version X.Y.Z]``  (defaults to VERSION in
scripts/build.py). Requires the ``gh`` CLI authenticated to the repo.

Exit codes: 0 = ok, 1 = a missing-asset violation, 2 = could not verify (release not
published yet, or ``gh`` unavailable/unauthenticated). Stdlib-only; UTF-8 stdout.
"""
import argparse
import json
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Same marker the build uses to decide the Nightmare base is available (build.py NIGHTMARE_MOD).
NIGHTMARE_MARKER = os.path.join(ROOT, "mods", "Nightmare", "extracted", "NightmareMod.SC2Mod")


def read_version():
    """The VERSION constant in scripts/build.py (the single source of truth for the tag/zip names)."""
    bp = os.path.join(ROOT, "scripts", "build.py")
    with open(bp, encoding="utf-8") as f:
        m = re.search(r'^VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
    if not m:
        sys.exit("check_release_assets: could not read VERSION from scripts/build.py")
    return m.group(1)


def release_asset_names(tag):
    """Asset names on the GitHub release `tag`, or None if it can't be read (no release / no gh)."""
    try:
        out = subprocess.run(
            ["gh", "release", "view", tag, "--json", "assets"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        print("check_release_assets: the `gh` CLI is not installed — cannot verify the release.")
        return None
    if out.returncode != 0:
        err = (out.stderr or "").strip()
        print(f"check_release_assets: cannot read release {tag} via gh ({err or 'release not found'}).")
        return None
    try:
        data = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        print("check_release_assets: unexpected gh output (not JSON).")
        return None
    return [a.get("name", "") for a in data.get("assets", [])]


def main():
    ap = argparse.ArgumentParser(description="Verify a release ships the required asset zips.")
    ap.add_argument("--version", help="release version (default: VERSION in scripts/build.py)")
    args = ap.parse_args()

    version = args.version or read_version()
    tag = f"v{version}"
    std_zip = f"WoL-Unbalanced-v{version}.zip"
    nightmare_zip = f"WoL-Unbalanced-Nightmare-v{version}.zip"
    base_local = os.path.isfile(NIGHTMARE_MARKER)

    print(f"check_release_assets: verifying release {tag} "
          f"(Nightmare base {'PRESENT' if base_local else 'absent'} locally).")

    assets = release_asset_names(tag)
    if assets is None:
        return 2  # could not verify (release not published yet, or gh unavailable)

    print(f"  attached: {', '.join(assets) if assets else '(none)'}")

    fails = []
    if std_zip not in assets:
        fails.append(f"the STANDARD zip '{std_zip}' is not attached to {tag} "
                     f"(CI should publish it on the tag — check the Release workflow).")
    if base_local and nightmare_zip not in assets:
        fails.append(
            f"the NIGHTMARE zip '{nightmare_zip}' is not attached to {tag}, but the Nightmare "
            f"base is present locally → the release MUST ship it.\n"
            f"    Fix: python3 scripts/build.py package nightmare && "
            f"gh release upload {tag} dist/{nightmare_zip}")

    if fails:
        print("\nRELEASE-ASSET CHECK FAIL:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1

    req = "standard + Nightmare" if base_local else "standard (Nightmare base absent → not required)"
    print(f"\ncheck_release_assets: ok — {tag} ships the required assets ({req}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
