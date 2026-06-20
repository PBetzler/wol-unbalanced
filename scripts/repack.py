#!/usr/bin/env python3
"""Repack a previous release zip with the current mod (CI release path).

CI cannot rebuild the campaign maps (the map base is not redistributable through
this repo), so tag-triggered releases take the PREVIOUS release zip as the map
carrier, replace the mod component folder with the current src/mod, and update
the metadata version. Map-affecting changes (dependency line, popup text, script
injection) still require a local `scripts/build.py package` release once.

Usage: repack.py <previous-release.zip> <version-tag e.g. v0.2.0>
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_SRC = os.path.join(ROOT, "src", "mod")
MOD_NAME = "WoLUnbalanced.SC2Mod"
TITLE = "WoL Unbalanced"


def main(base_zip: str, tag: str) -> None:
    version = tag.lstrip("v")
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"WoL-Unbalanced-{tag}.zip")

    with zipfile.ZipFile(base_zip) as src, zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.is_dir() or f"/{MOD_NAME}/" in info.filename:
                continue  # mod folder is replaced below
            if info.filename.endswith("metadata.txt"):
                meta = src.read(info).decode("utf-8")
                meta = "".join(
                    f"version={version}\n" if line.startswith("version=") else line + "\n"
                    for line in meta.splitlines()
                )
                dst.writestr(info.filename, meta)
            else:
                dst.writestr(info, src.read(info))
        for dirpath, _, files in os.walk(MOD_SRC):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, MOD_SRC)
                dst.write(full, f"{TITLE}/{MOD_NAME}/{rel}")
        # src/mod has no .version files (build.py generates them at build time) — emit them here
        # too so the repacked release mod matches a local build.py build (parity gap fix: prior
        # CI releases shipped a mod missing DocumentInfo/GameData/GameText.version).
        import build
        for fname, blob in build.version_file_blobs().items():
            dst.writestr(f"{TITLE}/{MOD_NAME}/{fname}", blob)
    print(f"repacked -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
