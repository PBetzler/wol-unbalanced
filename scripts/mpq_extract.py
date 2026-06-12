#!/usr/bin/env python3
"""Read-only MPQ archive inspector/extractor via mpyq.

Usage:
  mpq_extract.py list <archive>
  mpq_extract.py extract <archive> <outdir> [name-substring ...]

Extracts into <outdir>, preserving the archive's internal paths. With
name-substrings given, only files whose internal name contains one of them.
"""
import os
import sys

from mpyq import MPQArchive


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd, archive = sys.argv[1], sys.argv[2]
    a = MPQArchive(archive)
    names = [f.decode(errors="replace") for f in a.files or []]
    if cmd == "list":
        for n in sorted(names):
            print(n)
        return 0
    if cmd == "extract":
        outdir = sys.argv[3]
        pats = sys.argv[4:]
        for n in names:
            if pats and not any(p.lower() in n.lower() for p in pats):
                continue
            data = a.read_file(n.encode())
            if data is None:
                print(f"skip (unreadable): {n}")
                continue
            out = os.path.join(outdir, n.replace("\\", "/"))
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(data)
            print(f"{n} ({len(data)}b)")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
