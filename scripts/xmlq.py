#!/usr/bin/env python3
"""Read-only SC2 catalog XML query tool (replaces ad-hoc python heredocs).

Usage:
  xmlq.py get <id> <files...>        print full element(s) whose id matches exactly
  xmlq.py ids <regex> <files...>     list element class+id where id matches regex
  xmlq.py refs <name> <files...>     print lines (with numbers) containing name
  xmlq.py cards <unitid> <files...>  summarize a CUnit's weapons/abils/card buttons
"""
import re
import sys
import xml.etree.ElementTree as ET


def blocks(path):
    """Yield (classname, id, start_line, text) for every top-level catalog entry."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r'\s*<(C\w+) id="([^"]*)"', lines[i])
        if not m:
            i += 1
            continue
        cls, ident = m.group(1), m.group(2)
        if lines[i].rstrip().endswith("/>"):
            yield cls, ident, i + 1, lines[i]
            i += 1
            continue
        for j in range(i, len(lines)):
            if f"</{cls}>" in lines[j]:
                yield cls, ident, i + 1, "\n".join(lines[i:j + 1])
                i = j
                break
        else:
            i += 1
            continue
        i += 1


def attr_or_child(el, name):
    if el.get(name) is not None:
        return el.get(name)
    child = el.find(name)
    if child is not None:
        return child.get("value")
    return None


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    cmd, needle, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    for path in files:
        if cmd == "get":
            for cls, ident, line, text in blocks(path):
                if ident == needle:
                    print(f"=== {path}:{line} ===\n{text}\n")
        elif cmd == "ids":
            rx = re.compile(needle)
            for cls, ident, line, _ in blocks(path):
                if rx.search(ident):
                    print(f"{path}:{line}: {cls} id={ident}")
        elif cmd == "refs":
            for n, l in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                if needle in l:
                    print(f"{path}:{n}: {l.rstrip()}")
        elif cmd == "cards":
            root = ET.parse(path).getroot()
            for u in root.iter("CUnit"):
                if u.get("id") != needle:
                    continue
                print(f"=== {needle} ({path}) ===")
                for w in u.findall("WeaponArray"):
                    print(f"  weapon: {w.get('Link')}")
                for a in u.findall("AbilArray"):
                    print(f"  abil: {a.get('Link')}")
                for ci, card in enumerate(u.findall("CardLayouts")):
                    cells = []
                    for b in card.findall("LayoutButtons"):
                        face = attr_or_child(b, "Face") or "?"
                        row = attr_or_child(b, "Row") or "?"
                        col = attr_or_child(b, "Column") or "?"
                        cells.append(f"{face}@{row},{col}")
                    print(f"  card[{ci}]: {'; '.join(cells)}")
        else:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
