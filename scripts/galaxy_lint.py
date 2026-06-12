#!/usr/bin/env python3
"""Minimal Galaxy sanity lint: balanced braces/parens, and no use-before-declaration
of our own libWoLU_* functions (Galaxy is single-pass; an out-of-order call kills the
whole map script at compile time -> black map, no error message)."""
import glob
import re
import sys

ok = True
# Process in include order (the Gen file is included at the top of the main lib),
# carrying declarations forward across files.
paths = sorted(glob.glob("src/mod/Base.SC2Data/*.galaxy"), key=lambda p: "Gen" not in p)
declared = set()  # prototypes and definitions seen so far
for path in paths:
    s = open(path).read()
    if s.count("{") != s.count("}") or s.count("(") != s.count(")"):
        print(f"FAIL {path}: unbalanced braces/parens")
        ok = False
        continue
    for i, line in enumerate(s.splitlines(), 1):
        line = line.split("//")[0]
        decl = re.match(r"\s*(?:void|bool|int|string|fixed|trigger|unit|unitgroup)\s+(libWoLU\w+)\s*\(", line)
        if decl:
            declared.add(decl.group(1))
            continue
        for call in re.findall(r"\b(libWoLU\w+)\s*\(", line):
            if call not in declared:
                print(f"FAIL {path}:{i}: '{call}' used before declaration")
                ok = False
    print(("ok   " if ok else "see  ") + path)

sys.exit(0 if ok else 1)
