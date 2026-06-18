# Environment setup — WoL Unbalanced (Windows-first, macOS noted)

Cross-platform setup for a contributor or AI coding agent picking up this repo on a fresh
machine. The repo ships only our own code; the third-party **inputs** (catalog dumps, map
bases, StormLib) are gitignored and obtained separately. This doc is the recipe.

> **New machine?** Read this first, then [HANDOFF.md](HANDOFF.md) (current state + next steps),
> then [../CLAUDE.md](../CLAUDE.md) (the contract).

The dev machine is moving **Mac → Windows 11** (the SC2 Editor crashes on startup on the Mac
but runs on Windows, unlocking the Editor-validation path — see §"SC2 Editor validation"). The
pure-Python dev loop runs identically on both; only the install path and the `mpqpatch` build
differ by OS, and both are handled below.

---

## TL;DR — what you actually need

The owner playtests via the **GitHub release zip** (push a `v*` tag → CI builds the standard
zip → import in CCM). So a local `build` is **optional**. Priority:

| Priority | Item | Why | Without it |
|---|---|---|---|
| **MUST-HAVE** | Python 3.x | runs the whole dev loop | nothing works |
| **MUST-HAVE** | `mods/_reference/` (catalog dumps) | full static gate: `audit.py` CHECK3–7 + the card-merge simulator + `genlib.py` | `genlib`/`audit` can't resolve ids → can't validate a change |
| **MUST-HAVE** | Git + the repo | source of truth | — |
| should-have | `gh` CLI | push tags, cut/upload releases | manual release via the web UI |
| should-have | Git Bash (Windows) | the `.sh` hooks (pre-commit gate, dispatch gate) | run lint/audit manually before each commit |
| **OPTIONAL** | `mods/` map bases + `vendor/StormLib` + `tools/mpqpatch.exe` | local `build`/`install` for faster iteration | use CI + the release zip instead |

**Bottom line:** Python + `mods/_reference/` + the repo = you can make and validate changes and
ship them via a tag. The local build (the hard part — `mpqpatch.exe`) is a nice-to-have for
faster iteration, **not** a blocker. Don't get stuck on it.

---

## 1. Prerequisites

### Windows 11
- **Python 3.x** — install from [python.org](https://www.python.org/downloads/) (tick "Add
  python.exe to PATH") or `winget install Python.Python.3.12`. The dev-loop scripts have **no
  third-party Python deps** for the gate (`genlib`/`galaxy_lint`/`audit` are stdlib-only).
  `build.py` additionally imports **`mpyq`** (`py -m pip install mpyq`) — only needed for the
  optional local `build`.
  - Command: on Windows use `python` (or `py`); on macOS use `python3`. Both refer to the same
    scripts. This doc writes `python` for Windows; substitute `python3` on Mac.
  - **Create a `python3` shim (Windows).** The hook scripts call `python3`, but the python.org
    installer only ships `python.exe` — so `python3` falls through to the Microsoft Store stub
    and **silently disables the dispatch brief-check hook** (it degrades to "allow everything").
    Fix once by copying the binary:
    `copy "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python3.exe"`.
    Confirm that Python dir sits *ahead* of `…\Microsoft\WindowsApps` on PATH (winget's install does this).
  - **Restart your terminal / Claude Code after installing Python or editing PATH.** A process
    started earlier keeps the old in-memory PATH, so `python`/`python3`/`bash` won't resolve from
    the registry until a fresh process launches.
- **Git** — [git-scm.com](https://git-scm.com/download/win); the installer bundles **Git Bash**,
  which you need for the `.sh` hooks. `winget install Git.Git`.
- **`gh` CLI** — [cli.github.com](https://cli.github.com/) or `winget install GitHub.cli`; then
  `gh auth login`. Needed only for pushing tags / cutting releases.

### macOS (current machine, for reference)
- `python3` (system or Homebrew), `git`, `gh` (`brew install gh`). `mpyq` via
  `python3 -m pip install mpyq`. Bash ships with macOS.

---

## 2. Obtaining the gitignored inputs

Two routes. **Route A (copy from the Mac) is the fast path** — the reference dump and map bases
are platform-independent DATA/source; just copy them. **Route B (fetch from scratch)** is the
README §"Building (contributors)" path if the Mac isn't available.

### Route A — copy from the Mac repo (fastest)
Copy these folders from the Mac repo (`/Users/pbb/Code/privat/sc2-mod/`) into the same relative
paths in the Windows repo (over a network share, USB, or `scp`):

| Copy this | To | Needed for |
|---|---|---|
| `mods/_reference/` | `mods/_reference/` | **MUST-HAVE** — the full static gate |
| `mods/Tactical_Arsenal/` | `mods/Tactical_Arsenal/` | optional — standard map base for local `build` |
| `mods/Nightmare/` | `mods/Nightmare/` | optional — Nightmare local `build` only |
| `vendor/StormLib/` | `vendor/StormLib/` | optional — source for `mpqpatch.exe`; you still RE-BUILD the binary (see §3) |

Do **not** copy `tools/mpqpatch` — it's a Mac binary and won't run on Windows. Rebuild it (§3).
Everything under `mods/` and `vendor/` is gitignored, so copying it never touches git.

### Route B — fetch from scratch (per README §"Building")
All from **[GiantGrantGames' CCM Discord](https://discord.com/invite/ywvCz7CN)** (map bases +
Nightmare pack) or **[SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData)** (catalog dumps):

1. **`mods/_reference/` — the catalog dumps (MUST-HAVE).** From the SC2GameData GitHub dump,
   the Liberty catalogs: `mods/liberty.sc2mod`, `campaigns/liberty.sc2campaign`,
   `campaigns/libertystory.sc2campaign` (and, for various reference patterns, `novastoryassets.sc2mod`
   / `novacampaign.sc2mod`). `genlib.py` reads exactly the three Liberty catalogs (see its
   `CATALOGS` list); `audit.py` resolves ids against everything under `mods/_reference/`.
2. **`mods/Tactical_Arsenal/WoL Tactical Arsenal/*.SC2Map` — the standard map base (optional).**
   Get the *Tactical Arsenal* campaign from the GGG Discord; or export the WoL campaign maps from
   the SC2 Editor. Only needed for local `build`.
3. **`mods/Nightmare/extracted/` (optional, Nightmare variant only).** Rhyme's "Wings of Liberty
   Nightmare Difficulty" pack from the GGG Discord — its extracted maps + `NightmareMod.SC2Mod`.

> The build scripts **fail with a clear "get X from Y" message** if a required input is missing
> (`build.py preflight()`), so you'll be told exactly what's absent.

### Verify the reference dump is in place
```sh
python scripts/genlib.py     # must print "wrote …LibWoLUnbalancedGen.galaxy (… lines)"
python scripts/audit.py      # must end "audit: ok (… clone units, … warning(s), …)"
```
If `genlib`/`audit` error on missing files, `mods/_reference/` is incomplete.

---

## 3. Building `tools/mpqpatch.exe` on Windows (OPTIONAL — local build only)

`mpqpatch` is a ~30-line C program (`tools/mpqpatch.c`) that replaces a single file inside an
MPQ (`.SC2Map`) using **StormLib**. It's gitignored → each machine builds its own. **You only
need it for a local `build`** — if you ship via CI + the release zip, skip this entirely.

The Mac command (README §44, for reference):
```sh
c++ tools/mpqpatch.c -o tools/mpqpatch -Ivendor/StormLib/src -Lvendor/StormLib/build -lstorm -lz -lbz2
```

### ✅ VERIFIED working recipe (Windows 11, portable MinGW + CMake, NO admin)
> Test-compiled on Windows 2026-06-17. This is the confirmed path — `mpqpatch.exe` built and a
> full `build.py build` (30 maps patched) succeeded. It needs **no admin/elevation** (the box was
> a non-admin user), so it's the most reliable unattended option. Options A/B below are
> alternatives.

1. **Get a portable toolchain into a user dir** (no installer, no elevation):
   - **MinGW-w64 GCC** — WinLibs portable zip (latest UCRT x86_64, e.g. `winlibs-x86_64-posix-seh-gcc-*-mingw-w64ucrt-*.zip` from github.com/brechtsanders/winlibs_mingw/releases) → extract → gives `…\mingw64\bin\{g++,gcc,mingw32-make}.exe`.
   - **CMake** — portable zip (`cmake-*-windows-x86_64.zip` from github.com/Kitware/CMake/releases) → extract → `…\cmake-*\bin\cmake.exe`.
   - (A scripted download+extract of both lives at `C:\Users\philip\toolchain\setup.ps1` on this box.)
   - **Clang is NOT a good standalone choice on Windows** — it has no Windows SDK/CRT/linker of its own; it needs an MSVC or MinGW toolchain underneath. Use MinGW (above) or MSVC (Option A).
2. **Build StormLib (static)** with that toolchain on PATH:
   ```bat
   cmake -S vendor\StormLib -B vendor\StormLib\build -G "MinGW Makefiles" -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release
   cmake --build vendor\StormLib\build -j
   :: -> vendor\StormLib\build\libStormLib.a  (note the casing: libStormLib.a, link flag -lStormLib)
   ```
3. **Compile `mpqpatch.c`** against it (static-link so the .exe is portable):
   ```bat
   g++ tools\mpqpatch.c -o tools\mpqpatch.exe -Ivendor\StormLib\src -Lvendor\StormLib\build ^
       -lStormLib -static -static-libgcc -static-libstdc++ -lwininet -lole32
   ```
   `tools\mpqpatch.exe` with no args prints its usage line. Then `python scripts\build.py build`
   works (also needs `py -m pip install mpyq`). Benign at build time: `compact failed, err=1003
   (archive still valid)` — StormLib just skips MPQ compaction; the patch still applies.

### Windows recipe — alternatives (Option A/B; not the verified path above)

**Option A — MSVC + CMake (canonical for StormLib, but needs admin + a multi-GB install).** Needs
*Visual Studio Build Tools* (the "Desktop development with C++" workload) and CMake
(`winget install Kitware.CMake`).

```bat
:: 1. Build StormLib (static lib) from the vendored source, from the repo root
cd vendor\StormLib
cmake -B build -DBUILD_SHARED_LIBS=OFF
cmake --build build --config Release
:: -> produces vendor\StormLib\build\Release\storm.lib (StormLib bundles its own zlib/bzip2)
cd ..\..

:: 2. Compile mpqpatch.c against it. Run from a "x64 Native Tools Command Prompt for VS".
cl /EHsc /I vendor\StormLib\src tools\mpqpatch.c /Fe:tools\mpqpatch.exe ^
   /link vendor\StormLib\build\Release\storm.lib
```
Notes / things to verify on Windows:
- The exact `storm.lib` path/casing depends on the StormLib + CMake version — check what
  `cmake --build` actually wrote under `vendor\StormLib\build\` and point `/link` at it.
- StormLib on Windows vendors its own zlib/bzip2, so (unlike the Mac `-lz -lbz2`) you usually
  do **not** pass separate `-lz`/`-lbz2`. If the link complains about missing zlib/bzip2 symbols,
  add those libs (or build StormLib with its bundled deps enabled).
- `mpqpatch.c` includes `<StormLib.h>` (capital S, no path) — the `/I vendor\StormLib\src` flag
  must put that header on the include path.

**Option B — MinGW-w64 g++** (if you have MSYS2 / `g++` on PATH; mirrors the Mac `c++` line):
```bat
g++ tools\mpqpatch.c -o tools\mpqpatch.exe -Ivendor\StormLib\src -Lvendor\StormLib\build -lstorm -lz -lbz2
```
Same caveat on the lib name/location and on whether `-lz -lbz2` are needed.

**Sanity check:** `tools\mpqpatch.exe` with no args should print its usage line
(`usage: … <archive> <local-file> <archived-name>`).

`build.py` auto-selects `tools/mpqpatch.exe` on Windows vs `tools/mpqpatch` on macOS
(`os.name == "nt"`), so once the `.exe` exists, `python scripts\build.py build` finds it.

---

## 4. SC2 / Editor / CCM paths

| Thing | Windows (default) | macOS |
|---|---|---|
| SC2 install dir | `C:\Program Files (x86)\StarCraft II` | `/Applications/StarCraft II` |
| Override env var (install target) | `WOLU_SC2_USER_DIR` (relocated/OneDrive Documents, or point at the install dir for the old behavior) | `WOLU_SC2_USER_DIR` |
| SC2 Editor exe | `…\StarCraft II\Support64\SC2Editor_x64.exe` (launch via Battle.net → SC2 → "Launch Editor", or directly) | crashes on startup on this Mac |
| `install` target (the **user**-mods root CCM/Editor/game load from) | `…\Documents\StarCraft II\Maps\Campaign` + `…\Mods` | `~/Library/Application Support/Blizzard/StarCraft II/{Maps/Campaign,Mods}` |
| CCM (Custom Campaign Manager) | a portable `.NET` WinForms `.exe` (runs natively on Windows; point its file picker at the SC2 folder) | needs Wine; only used for end-user-parity checks |

`build.py install` targets the **user** SC2 folder (Documents on Windows / Application Support on
macOS) — the one CCM, the Editor, and the game all load user mods/maps from — so a single `install`
can't be shadowed by a CCM-staged copy in that folder (the old install-dir target was). Override
with `WOLU_SC2_USER_DIR` (relocated/OneDrive Documents, or point it at the install dir to restore
the old behavior):
```bat
set WOLU_SC2_USER_DIR=D:\Games\StarCraft II
python scripts\build.py install
```
(`build`/`package` never touch this dir, so a wrong/missing path can't block a build — only
`install`/`uninstall` use it. Don't keep a copy in BOTH the user folder and the install dir — the
game/Editor search both and may open the stale one.)

---

## 5. The dev loop

Identical on both OSes; only `python` vs `python3` and the optional local-build step differ.

```sh
python scripts/genlib.py        # regenerate the per-player apply script from reference XML
python scripts/galaxy_lint.py   # MANDATORY before build — catches black-map compile bugs
python scripts/audit.py         # static catalog/actor audit — sphere-no-model + dead calldowns
python scripts/build.py build   # (OPTIONAL) patch maps + assemble into build/  [needs mpqpatch + map base]
python scripts/build.py install # (OPTIONAL) copy build/ into the SC2 folder
```

The **gate** = `genlib` + `galaxy_lint` + `audit` (+ `check_dispatch_doctrine` + the untracked
warning). `build`/`install` are separate and **not** required to commit. The owner verifies
in-game; you **cannot run the game** from the dev box.

### Shipping a change (the primary path — no local build needed)
```sh
# 1. bump VERSION in scripts/build.py
# 2. mod-only change -> push a v* tag; CI builds + publishes the standard zip:
git tag vX.Y.Z && git push origin vX.Y.Z
# 3. map-affecting change (dependency line / popup text / MapScript injection):
#    build + release manually -> python scripts/build.py package  +  gh release create …
```
(See [../README.md](../README.md) §"CI vs. manual" and CLAUDE.md §"Repo Hygiene & Releases".)

---

## 6. Hooks setup (fresh clone — these are NOT auto-installed)

`.git/hooks` and `.claude/` are **not** versioned, so a fresh clone has neither the git
pre-commit gate nor the Claude Code dispatch gate wired. The hook **scripts** in
`scripts/hooks/` ARE tracked; wire them up once:

### 6a. Git pre-commit gate (lint + audit + dispatch-doctrine + untracked warning)
Run under **Git Bash** (the hooks are bash):
```sh
bash scripts/hooks/install.sh
```
This symlinks `.git/hooks/pre-commit` → `scripts/hooks/pre-commit`. Bypass a hook with
`git commit --no-verify`.

### 6b. Claude Code dispatch + Stop hooks (`.claude/settings.json`)
`.claude/` is gitignored, so this must be **re-created by hand** on Windows. Create
`.claude/settings.json` at the repo root with the `hooks` block below (merge into any existing
`permissions` block; the `hooks` block is the load-bearing part). These run via **Git Bash** —
the `command` uses `bash`, which must be on PATH (it is, if Git for Windows is installed).

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/hooks/agent-pretool-brief-check.sh\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/hooks/stop-engram-summary-check.sh\""
          }
        ]
      }
    ]
  }
}
```
- **PreToolUse(Task)** → `agent-pretool-brief-check.sh`: the dispatch-brief gate (blocks a Task
  whose brief lacks `FIRST ACTION` / `CLAUDE.md` / `ROLE` / `## Result`, or an implement/validate
  dispatch that isn't Opus — see CLAUDE.md §"Agent Dispatch Brief Template").
- **Stop** → `stop-engram-summary-check.sh`: a tripwire that reminds you to save an engram
  session summary. **On Windows, engram (the MCP memory server) may be ABSENT** — the hook is a
  non-blocking reminder, so it's harmless either way. If engram isn't running, the repo docs
  (open-issues.md, plan.md, etc.) are the source of truth, not engram.

> **Windows-path note:** `$CLAUDE_PROJECT_DIR` is expanded by the bash invocation; the scripts
> run fine under Git Bash. If `bash` isn't found, ensure Git for Windows is installed and its
> `usr\bin` (or `cmd`) is on PATH.

---

## 7. SC2 Editor validation (now available on Windows)

The SC2 **Editor runs on Windows** (it crashed on startup on the Mac — the reason for the move).
This unlocks a sanctioned validation path the static gate can't match:

- **Previewer** (`ObjectViewInPreviewer` → portrait aspect) **renders a unit's model + portrait**
  → answers the heart-portrait / sphere questions locally (e.g. the elite-merc portraits). It
  shows the merged STATIC catalog (cards, armor-name resolution, `parent=` wiring) but NOT
  per-player runtime `CatalogFieldValueModify` numbers (those need the lib to run in a game).
- **Test Document (Ctrl+F9)** launches via Battle.net's own license mechanism → should bypass the
  SC2 client-API's `JoinGame` license block and run the mod in-game (the lib applies per-player
  edits; the canary + diag subtitle lines show). Worth a try on a built campaign map.

Details + the full reasoning: [learnings.md](learnings.md) §"Verification tooling" and
[debug-toolkit.md](debug-toolkit.md). The SC2 **client API** for live unit reads is a **confirmed
dead end** on retail 5.x (documented in both) — don't re-chase it.

---

## 8. "Verify on Windows" — what this Mac couldn't test

### Confirmed during Windows bring-up (resolved)
- **Cross-platform encoding bugs — FIXED.** The Mac's default UTF-8 file/console encoding hid two
  bugs that surfaced on Windows (cp1252 default): `genlib.py` wrote the generated lib in cp1252
  (mojibake `—`/`×` in comments), and verbose `audit.py` (plus 4 sibling scripts) **crashed** with
  `UnicodeEncodeError` printing `→ ✓ — ×`. Fixed: `genlib.py` writes `encoding="utf-8", newline="\n"`;
  the CLI scripts force UTF-8 `stdout`/`stderr` at startup. The regenerated lib is now byte-identical
  across OSes. (`--quiet` never crashed, so the pre-commit gate was always safe.)
- **The `.sh` hooks under Git Bash — confirmed working.** Pre-commit gate (lint + audit +
  dispatch-doctrine) runs green; the dispatch brief-check hook correctly blocks a bad brief. Needs
  the `python3` shim (§1) and Git's `bin` on PATH so the harness can invoke `bash`.

### Confirmed on Windows 2026-06-17
- **`mpqpatch.exe` build recipe — CONFIRMED.** The portable MinGW + CMake path (now the verified
  recipe in §3) built `tools/mpqpatch.exe` (880 KB, static) and `vendor/StormLib/build/libStormLib.a`
  with **no admin**. The link flag is `-lStormLib` (lib is `libStormLib.a`) + `-lwininet -lole32`.
- **`python scripts/build.py build` — CONFIRMED.** Patched all 30 campaign maps into `build/`
  (`compact failed err=1003` warnings are benign — StormLib skips MPQ compaction, the patch still
  applies). `py -m pip install mpyq` is required.
- **Editor Previewer validation — CONFIRMED working** (loaded `build/Mods/WoLUnbalanced.SC2Mod`
  via the user `Documents\StarCraft II\Mods\` folder; merc model/portrait/armor verified — see
  [open-issues.md](open-issues.md) §"Editor verification pass").

### Still pending real Windows confirmation (local-build only — not needed to ship)
- **`build.py install` to `C:\Program Files (x86)\StarCraft II`** — not run (that dir needs admin;
  a non-admin alternative is to copy `build/Mods` + `build/Campaign` into
  `Documents\StarCraft II\{Mods,Maps\Campaign}`, which the Editor/game also read — done this round).
- **Editor `Test Document` (Ctrl+F9) in-game run** — not attempted: our mod loads via a
  hand-injected `MapScript.galaxy` include, and the Editor may recompile the map script on test and
  drop it (false-negative risk), plus a possible campaign-license guard. The reliable in-game path
  remains the **CCM release zip** (owner). Worth a careful trial, not assumed to work.
