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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_SRC = os.path.join(ROOT, "mods", "Tactical_Arsenal", "WoL Tactical Arsenal")
MOD_SRC = os.path.join(ROOT, "src", "mod")
BUILD = os.path.join(ROOT, "build")
MPQPATCH = os.path.join(ROOT, "tools", "mpqpatch")
SC2 = "/Applications/StarCraft II"
MOD_NAME = "WoLUnbalanced.SC2Mod"
DEP_LINE = r"file:Mods\WoLUnbalanced.SC2Mod"
TITLE = "WoL Unbalanced"
VERSION = "0.2.1"


def patch_document_info(map_path: str) -> None:
    """Make our mod the only custom (file:Mods\\...) dependency. Idempotent."""
    archive = mpyq.MPQArchive(map_path)
    doc = archive.read_file(b"DocumentInfo").decode("utf-8")
    cleaned = re.sub(r"\s*<Value>file:Mods\\[^<]*</Value>", "", doc)
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
    maps_out = os.path.join(BUILD, "Campaign")
    mods_out = os.path.join(BUILD, "Mods")
    shutil.rmtree(BUILD, ignore_errors=True)
    os.makedirs(maps_out)
    os.makedirs(mods_out)

    for name in sorted(os.listdir(MAPS_SRC)):
        src = os.path.join(MAPS_SRC, name)
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
    with open(os.path.join(BUILD, "metadata.txt"), "w") as f:
        f.write(f"title={TITLE}\n"
                "desc=Funnily overpowered Wings of Liberty: your units only, enemies stay vanilla. Not to be taken seriously.\n"
                "author=Philip (vibe coded with Claude)\n"
                "campaign=WoL\n"
                f"version={VERSION}\n")
    print(f"built -> {BUILD}")


def package() -> None:
    """Zip the build in the CCM campaign layout: one top-level folder, flat maps +
    metadata.txt + the mod component folder (same shape as the reference zips)."""
    import zipfile

    build()
    dist = os.path.join(ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    zpath = os.path.join(dist, f"WoL-Unbalanced-v{VERSION}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(BUILD, "metadata.txt"), f"{TITLE}/metadata.txt")
        for name in sorted(os.listdir(os.path.join(BUILD, "Campaign"))):
            z.write(os.path.join(BUILD, "Campaign", name), f"{TITLE}/{name}")
        modroot = os.path.join(BUILD, "Mods", MOD_NAME)
        for dirpath, _, files in os.walk(modroot):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, modroot)
                z.write(full, f"{TITLE}/{MOD_NAME}/{rel}")
    print(f"packaged -> {zpath}")


def install() -> None:
    maps_dst = os.path.join(SC2, "Maps", "Campaign")
    mods_dst = os.path.join(SC2, "Mods")
    os.makedirs(maps_dst, exist_ok=True)
    os.makedirs(mods_dst, exist_ok=True)
    for name in os.listdir(os.path.join(BUILD, "Campaign")):
        shutil.copy2(os.path.join(BUILD, "Campaign", name), os.path.join(maps_dst, name))
    for name in os.listdir(os.path.join(BUILD, "Mods")):
        src = os.path.join(BUILD, "Mods", name)
        dst = os.path.join(mods_dst, name)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    print(f"installed -> {SC2} (Maps/Campaign + Mods)")


def uninstall() -> None:
    for name in os.listdir(os.path.join(BUILD, "Campaign")):
        p = os.path.join(SC2, "Maps", "Campaign", name)
        if os.path.exists(p):
            os.unlink(p)
    for name in os.listdir(os.path.join(BUILD, "Mods")):
        p = os.path.join(SC2, "Mods", name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.unlink(p)
    print("uninstalled")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "install": install, "package": package, "clean": lambda: shutil.rmtree(BUILD, ignore_errors=True), "uninstall": uninstall}[cmd]()
