#!/usr/bin/env python3
"""Build & install the WoL Unbalanced campaign.

build   — assemble build/Campaign (maps with our dependency appended) and build/Mods
install — copy the build output into the StarCraft II folder
clean   — remove the build output
uninstall — remove installed files from the StarCraft II folder

Map base: the Tactical Arsenal campaign's maps (mods/Tactical_Arsenal). Verified
effectively vanilla: their Triggers/MapScript reference no custom mod libraries,
so we strip their mod dependency and insert ours as the only custom one.
"""
import os, re, shutil, subprocess, sys, tempfile

import mpyq

# Windows: the default console codepage (cp1252) can't encode the non-ASCII glyphs
# (→ ✓ — ×) we print, raising UnicodeEncodeError. Force UTF-8 stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_SRC = os.path.join(ROOT, "mods", "Tactical_Arsenal", "WoL Tactical Arsenal")
MOD_SRC = os.path.join(ROOT, "src", "mod")
BUILD = os.path.join(ROOT, "build")

# --- Cross-platform paths (macOS + Windows) ---------------------------------------
# The map patcher is a compiled C binary (tools/mpqpatch.c -> StormLib); on Windows it
# builds to mpqpatch.exe. It's gitignored, so each machine builds its own — see
# docs/SETUP.md. os.path.exists below tolerates either name.
MPQPATCH = os.path.join(ROOT, "tools",
                        "mpqpatch.exe" if os.name == "nt" else "mpqpatch")


def _default_sc2_dir() -> str:
    """The StarCraft II install dir, OS-specific. Override with $WOLU_SC2_DIR (any OS)
    if SC2 lives somewhere non-default — e.g. a D: drive on Windows, or an EU/region
    folder. Only `install`/`uninstall` touch this; `build`/`package` do not, so a
    missing/wrong SC2 dir never blocks a build."""
    override = os.environ.get("WOLU_SC2_DIR")
    if override:
        return override
    if os.name == "nt":  # Windows — default Battle.net install location
        return r"C:\Program Files (x86)\StarCraft II"
    return "/Applications/StarCraft II"  # macOS


SC2 = _default_sc2_dir()
MOD_NAME = "WoLUnbalanced.SC2Mod"
DEP_LINE = r"file:Mods\WoLUnbalanced.SC2Mod"
TITLE = "WoL Unbalanced"
VERSION = "0.3.10"

# --- Optional Nightmare-difficulty base (LOCAL-ONLY) -------------------------------
# `python3 scripts/build.py build nightmare` (or `package nightmare`) layers our mod on
# top of Rhyme's "Nightmare Difficulty" pack instead of the vanilla Tactical Arsenal
# maps. Those maps ARE the real WoL maps + the NightmareMod difficulty lib (harder
# enemies); we KEEP their NightmareMod dependency and append ours AFTER it (so our
# per-player edits win catalog conflicts), and bundle NightmareMod.SC2Mod alongside ours.
# This is LOCAL-ONLY: the Nightmare maps (~67 MB) + mod are third-party (gitignored, no
# upstream git repo), so it can't be a submodule or a CI build — build it locally and
# `gh release upload <tag> dist/WoL-Unbalanced-Nightmare-v*.zip` to add it to a release.
NIGHTMARE_MAPS_SRC = os.path.join(ROOT, "mods", "Nightmare", "extracted")
NIGHTMARE_MOD = os.path.join(ROOT, "mods", "Nightmare", "extracted", "NightmareMod.SC2Mod")
NIGHTMARE_DEP = r"file:Mods\NightmareMod.SC2Mod"
NIGHTMARE_BASE = False  # set True by the CLI `nightmare` arg

# Where to obtain the gitignored third-party inputs (map bases + the Nightmare pack):
GGG_DISCORD = "https://discord.com/invite/ywvCz7CN"  # GiantGrantGames' Custom Campaign Manager Discord
SC2GAMEDATA = "https://github.com/SC2Mapster/SC2GameData"


def _missing(what: str, path: str, where: str) -> None:
    raise SystemExit(
        f"\nbuild: cannot build — missing {what}.\n"
        f"  expected at: {path}\n"
        f"  how to fix:  {where}\n"
        f"  (this repo ships only our own code; third-party inputs live under the gitignored\n"
        f"   mods/ and vendor/ — see README §Building.)\n")


def preflight() -> None:
    """Fail early with a clear, actionable message if a build input is missing — so anyone
    who clones the repo and runs a build learns exactly what to fetch and from where."""
    if not os.path.exists(MPQPATCH):
        _missing("the StormLib map patcher (tools/mpqpatch[.exe])", MPQPATCH,
                 "build StormLib into vendor/ and compile tools/mpqpatch.c — see README §Building step 3 "
                 "(macOS) or docs/SETUP.md (Windows, builds mpqpatch.exe).")
    maps = NIGHTMARE_MAPS_SRC if NIGHTMARE_BASE else MAPS_SRC
    label = "the Nightmare pack's maps" if NIGHTMARE_BASE else "the map base (Tactical Arsenal campaign)"
    src_hint = (f"download \"Wings of Liberty Nightmare Difficulty\" by Rhyme from GiantGrantGames' "
                f"Discord ({GGG_DISCORD}) and extract it to {NIGHTMARE_MAPS_SRC}/"
                if NIGHTMARE_BASE else
                f"get the \"Tactical Arsenal\" campaign from GiantGrantGames' Discord ({GGG_DISCORD}) "
                f"and extract its maps to {MAPS_SRC}/ (or export the WoL campaign maps from the SC2 Editor)")
    if not os.path.isdir(maps) or not any(n.endswith(".SC2Map") for n in os.listdir(maps)):
        _missing(label, maps, src_hint)
    if NIGHTMARE_BASE and not os.path.isfile(NIGHTMARE_MOD):
        _missing("the Nightmare difficulty mod (NightmareMod.SC2Mod)", NIGHTMARE_MOD,
                 f"download the Nightmare Difficulty pack by Rhyme from GiantGrantGames' Discord ({GGG_DISCORD}).")


def patch_document_info(map_path: str) -> None:
    """Make our mod the last custom (file:Mods\\...) dependency. Idempotent.
    Default: ours is the ONLY custom dep (strip the source campaign's). Nightmare base:
    KEEP the existing custom dep (NightmareMod) and append ours after it."""
    archive = mpyq.MPQArchive(map_path)
    doc = archive.read_file(b"DocumentInfo").decode("utf-8")
    cleaned = doc if NIGHTMARE_BASE else re.sub(r"\s*<Value>file:Mods\\[^<]*</Value>", "", doc)
    if DEP_LINE in cleaned:
        patched = cleaned
    else:
        patched = cleaned.replace(
            "</Dependencies>", f"    <Value>{DEP_LINE}</Value>\n    </Dependencies>"
        )
    if patched == doc:
        return
    assert DEP_LINE in patched, f"no </Dependencies> in {map_path}"
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
        tmp.write(patched)
    try:
        subprocess.run([MPQPATCH, map_path, tmp.name, "DocumentInfo"], check=True)
    finally:
        os.unlink(tmp.name)


GS_NAME = "enUS.SC2Data\\LocalizedData\\GameStrings.txt"
TA_MARKERS = ("Tactical Arsenal", "Pierre", "playing my mod")
TITLE_TEXT = '<c val="00FF40"><s val="Lab_Title">WoL Unbalanced</s></c>'
BODY_TEXT = (
    "WoL Unbalanced loaded successfully.<n/><n/>All armory and lab upgrades unlock "
    "automatically, mercenaries are available from the start, and every change "
    "applies to your units only — enemies stay vanilla."
)


def patch_gamestrings(map_path: str) -> None:
    """Rebrand leftover Tactical Arsenal popups in map-local strings (idempotent)."""
    archive = mpyq.MPQArchive(map_path)
    blob = archive.read_file(GS_NAME.encode())
    if not blob:
        return
    text = blob.decode("utf-8-sig")
    eol = "\r\n" if "\r\n" in text else "\n"
    out, changed = [], False
    for line in text.splitlines():
        key, sep, val = line.partition("=")
        if sep and any(m in val for m in TA_MARKERS):
            val = TITLE_TEXT if ("Lab_Title" in val or len(val) < 120) else BODY_TEXT
            line, changed = key + "=" + val, True
        out.append(line)
    if not changed:
        return
    with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as tmp:
        tmp.write((eol.join(out) + eol).encode("utf-8-sig"))
    try:
        subprocess.run([MPQPATCH, map_path, tmp.name, GS_NAME], check=True)
    finally:
        os.unlink(tmp.name)


INCLUDE_LINE = 'include "LibWoLUnbalanced"'
INIT_CALL = "    libWoLU_InitLib();"


def patch_mapscript(map_path: str) -> None:
    """Inject our trigger library into the map's compiled script (idempotent)."""
    archive = mpyq.MPQArchive(map_path)
    s = archive.read_file(b"MapScript.galaxy").decode("utf-8")
    if INCLUDE_LINE in s:
        return
    eol = "\r\n" if "\r\n" in s else "\n"
    lines = s.splitlines(keepends=True)
    last_inc = max(i for i, l in enumerate(lines) if l.startswith('include "TriggerLibs/'))
    lines.insert(last_inc + 1, INCLUDE_LINE + eol)
    s = "".join(lines)
    needle = f"{eol}    InitLibs();{eol}"
    assert needle in s, f"no InitLibs() call site in {map_path}"
    s = s.replace(needle, needle + INIT_CALL + eol, 1)
    with tempfile.NamedTemporaryFile("w", suffix=".galaxy", delete=False) as tmp:
        tmp.write(s)
    try:
        subprocess.run([MPQPATCH, map_path, tmp.name, "MapScript.galaxy"], check=True)
    finally:
        os.unlink(tmp.name)


def patch_document_header(map_path: str) -> None:
    """The binary DocumentHeader embeds the dependency list too — keep it in sync.
    Format: ... u32 count, then `count` null-terminated dependency strings."""
    archive = mpyq.MPQArchive(map_path)
    h = archive.read_file(b"DocumentHeader")
    i = h.find(b"bnet:")
    assert i >= 4, f"no dependency block found in DocumentHeader of {map_path}"
    count = int.from_bytes(h[i - 4 : i], "little")
    deps, pos = [], i
    for _ in range(count):
        end = h.index(b"\x00", pos)
        deps.append(h[pos:end])
        pos = end + 1
    if NIGHTMARE_BASE:
        # Keep every existing dep (incl. NightmareMod) and APPEND ours, bumping the count.
        if DEP_LINE.encode() in deps:
            return
        new_deps = deps + [DEP_LINE.encode()]
        out = (h[: i - 4] + len(new_deps).to_bytes(4, "little")
               + b"".join(d + b"\x00" for d in new_deps) + h[pos:])
    else:
        # Default: replace the source campaign's custom dep with ours (1:1, count unchanged).
        new_deps = [DEP_LINE.encode() if d.startswith(b"file:Mods\\") else d for d in deps]
        if new_deps == deps:
            return
        out = h[:i] + b"".join(d + b"\x00" for d in new_deps) + h[pos:]
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(out)
    try:
        subprocess.run([MPQPATCH, map_path, tmp.name, "DocumentHeader"], check=True)
    finally:
        os.unlink(tmp.name)


def doc_version_counter() -> int:
    """STRICTLY-INCREASING per-build document version.

    Earlier this was derived from VERSION (constant 0.1.0 -> 100 across every dev
    build). That was the bug: SC2 reloads a save when the installed dependency
    version is >= the saved one (forward-compat — this is why other mods update
    cleanly), but a *constant* version means each rebuild is "same version number,
    different content", which the engine rejects with the version-mismatch error.

    A wall-clock-derived counter guarantees every build is a higher version than any
    prior one, so saves made on an earlier build load on a later one. Sized to stay a
    sane, slowly-growing u32 (seconds since 2026-06-01)."""
    import time
    floor = 100  # keep >= the old VERSION-derived value
    return max(floor, int(time.time()) - 1_780_000_000)


def write_version_files(mod_dir: str) -> None:
    """Emit the per-section .version files the editor maintains and our hand-rolled
    component folder lacked. NOTE: these do NOT make mid-mission saves survive mod
    changes — a .SC2Save serializes live game state against the catalog's exact
    structure (upgrade names, ability IDs, array indices in save.ioSync), so any data
    change invalidates it regardless of version numbers (verified: see learnings.md).
    These files are release hygiene (a monotonic version for end-user update parity);
    the dev workflow for changed mods is to start the mission fresh, not reload a save.

    44-byte layout decoded from an editor-saved mod (Tactical Arsenal): 'cdes' +
    reversed section tag, then 9 LE dwords [format=2, editor build, 5, 0, section
    const, editor build, VERSION COUNTER, last-modified timestamp, 1]."""
    import struct

    counter = doc_version_counter()
    ts = 1750000000 + counter
    sections = {
        # filename: (reversed tag, editor build dword, section const)
        "DocumentInfo.version": (b"ofni", 0x159B4, 0x0A),
        "GameData.version": (b"adag", 0x16018, 0x0B),
        "GameText.version": (b"txet", 0x16018, 0x0B),
    }
    for fname, (tag, build_no, const) in sections.items():
        blob = b"cdes" + tag + struct.pack(
            "<9I", 2, build_no, 5, 0, const, build_no, counter, ts, 1
        )
        assert len(blob) == 44
        with open(os.path.join(mod_dir, fname), "wb") as f:
            f.write(blob)


def build() -> None:
    preflight()
    maps_out = os.path.join(BUILD, "Campaign")
    mods_out = os.path.join(BUILD, "Mods")
    shutil.rmtree(BUILD, ignore_errors=True)
    os.makedirs(maps_out)
    os.makedirs(mods_out)

    maps_src = NIGHTMARE_MAPS_SRC if NIGHTMARE_BASE else MAPS_SRC
    for name in sorted(os.listdir(maps_src)):
        src = os.path.join(maps_src, name)
        if name.endswith(".SC2Map") and os.path.isfile(src):
            dst = os.path.join(maps_out, name)
            shutil.copy2(src, dst)
            patch_document_info(dst)
            patch_document_header(dst)
            patch_mapscript(dst)
            patch_gamestrings(dst)
        # the source campaign's own mod and metadata are reference-only, not shipped

    shutil.copytree(MOD_SRC, os.path.join(mods_out, MOD_NAME))
    write_version_files(os.path.join(mods_out, MOD_NAME))
    if NIGHTMARE_BASE:
        # Bundle Rhyme's difficulty mod alongside ours (it's a 132 KB MPQ file).
        shutil.copy2(NIGHTMARE_MOD, os.path.join(mods_out, "NightmareMod.SC2Mod"))
    # IMPORTANT: both variants use the SAME campaign title (and the same WoL map names +
    # CampaignLib banks), so CCM/SC2 treat them as ONE campaign — i.e. they're
    # interchangeable: a between-mission (Hyperion) save made on one variant continues on
    # the other when you swap which zip is installed. They differ only by desc + map files +
    # the bundled NightmareMod. (Mid-mission .SC2Saves still won't transfer — those bind to
    # the catalog; reload from the Hyperion between missions.)
    title = TITLE
    desc = ("[NIGHTMARE] Funnily overpowered Wings of Liberty vs. Rhyme's Nightmare-difficulty "
            "enemies. Interchangeable with the standard build — swap freely from a Hyperion save."
            if NIGHTMARE_BASE else
            "Funnily overpowered Wings of Liberty: your units only, enemies stay vanilla. Not to be taken seriously.")
    with open(os.path.join(BUILD, "metadata.txt"), "w") as f:
        f.write(f"title={title}\n"
                f"desc={desc}\n"
                "author=Philip (vibe coded with Claude)\n"
                "campaign=WoL\n"
                f"version={VERSION}\n")
    print(f"built -> {BUILD}" + (" [NIGHTMARE base]" if NIGHTMARE_BASE else ""))


def package() -> None:
    """Zip the build in the CCM campaign layout: one top-level folder, flat maps +
    metadata.txt + the mod component folder (same shape as the reference zips)."""
    import zipfile

    build()
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    # Same top-folder name for both variants => CCM imports them into the SAME campaign
    # (interchangeable / shared Hyperion save). Only the zip FILENAME differs.
    folder = TITLE
    zname = (f"WoL-Unbalanced-Nightmare-v{VERSION}.zip" if NIGHTMARE_BASE
             else f"WoL-Unbalanced-v{VERSION}.zip")
    zpath = os.path.join(dist, zname)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(BUILD, "metadata.txt"), f"{folder}/metadata.txt")
        for name in sorted(os.listdir(os.path.join(BUILD, "Campaign"))):
            z.write(os.path.join(BUILD, "Campaign", name), f"{folder}/{name}")
        # every Mods/ entry: our component folder + (nightmare) the NightmareMod MPQ file
        mods_root = os.path.join(BUILD, "Mods")
        for entry in sorted(os.listdir(mods_root)):
            full = os.path.join(mods_root, entry)
            if os.path.isfile(full):
                z.write(full, f"{folder}/{entry}")
            else:
                for dirpath, _, files in os.walk(full):
                    for fn in sorted(files):
                        ffull = os.path.join(dirpath, fn)
                        rel = os.path.relpath(ffull, mods_root)
                        z.write(ffull, f"{folder}/{rel}")
    print(f"packaged -> {zpath}")


def install() -> None:
    r"""Mirror CCM's "Set Active Campaign" for the WoL slot, into the game install dir
    (sc2BasePath): CLEAR the loose files in Maps\Campaign (the WoL campaign maps + metadata)
    while PRESERVING the swarm/void/nova/voidprologue SUBFOLDERS (the other campaigns' slots),
    then copy our maps + a CCM-format metadata.txt in. The mod (.SC2Mod) goes to Mods\, exactly
    where CCM's handleDependencies puts it. Activation is by file presence — CCM writes no
    controlling file (verified from its source, github.com/7thAce/SC2CCM)."""
    maps_dst = os.path.join(SC2, "Maps", "Campaign")
    mods_dst = os.path.join(SC2, "Mods")
    os.makedirs(maps_dst, exist_ok=True)
    os.makedirs(mods_dst, exist_ok=True)
    # Clear the WoL slot: loose FILES only — never the other-campaign subfolders.
    for name in os.listdir(maps_dst):
        p = os.path.join(maps_dst, name)
        if os.path.isfile(p):
            os.unlink(p)
    # Copy our campaign maps (skip mpqpatch .tmp leftovers) + the CCM-format metadata.txt.
    for name in os.listdir(os.path.join(BUILD, "Campaign")):
        if name.endswith(".tmp"):
            continue
        shutil.copy2(os.path.join(BUILD, "Campaign", name), os.path.join(maps_dst, name))
    meta = os.path.join(BUILD, "metadata.txt")
    if os.path.exists(meta):
        shutil.copy2(meta, os.path.join(maps_dst, "metadata.txt"))
    # Mod -> Mods\ (replace any existing copy).
    for name in os.listdir(os.path.join(BUILD, "Mods")):
        src = os.path.join(BUILD, "Mods", name)
        dst = os.path.join(mods_dst, name)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    print(f"installed -> {SC2} (cleared WoL Maps/Campaign slot; maps + metadata.txt; mod -> Mods/)")


def uninstall() -> None:
    r"""Reverse install (CCM "Reset to Default" for the WoL slot): remove our campaign maps +
    metadata.txt from Maps\Campaign (loose files; the other-campaign subfolders are untouched)
    and our mod from Mods\."""
    maps_dir = os.path.join(SC2, "Maps", "Campaign")
    for name in os.listdir(os.path.join(BUILD, "Campaign")):
        p = os.path.join(maps_dir, name)
        if os.path.exists(p):
            os.unlink(p)
    meta = os.path.join(maps_dir, "metadata.txt")
    if os.path.exists(meta):
        os.unlink(meta)
    for name in os.listdir(os.path.join(BUILD, "Mods")):
        p = os.path.join(SC2, "Mods", name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.unlink(p)
    print("uninstalled")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if "nightmare" in args:
        NIGHTMARE_BASE = True  # noqa: F811 — module-global toggle read by the patch/build fns
        args = [a for a in args if a != "nightmare"]
    cmd = args[0] if args else "build"
    {"build": build, "install": install, "package": package, "clean": lambda: shutil.rmtree(BUILD, ignore_errors=True), "uninstall": uninstall}[cmd]()
