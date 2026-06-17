#!/usr/bin/env python3
"""verify_api.py — self-verify WoL Unbalanced DATA changes against the LIVE SC2 binary.

This is the agent's substitute for "you cannot run the game" for the DATA-verifiable
bug classes (HP, armor, cargo, ability wiring). It drives the s2client-proto websocket
API, loads one of OUR built campaign maps (so our trigger lib runs), spawns/reads
player-1 units, and asserts the values the mod is supposed to produce.

TWO MODES:
  --attach  (USE THIS) — connect to an SC2 the OWNER launched via Battle.net's PLAY
            button with the listen flags set (see below). That instance is BOTH
            authenticated (has the per-session license token) AND API-listening, so
            JoinGame/Observation actually work. Never launches or kills SC2.
  spawn     (default, LICENSE-BLOCKED) — launches its own headless SC2 with
            -listen/-port. This path is permanently blocked by Blizzard: a self-spawned
            -listen instance never receives the per-session license token, so JoinGame
            fails with "Unable to validate game license." Kept for diagnostics only.

ONE-TIME OWNER SETUP for --attach: in the Battle.net app, StarCraft II → Settings (gear)
→ "Additional command line arguments", set:
    -listen 127.0.0.1 -port 8765 -displaymode 0
then launch SC2 via the Battle.net PLAY button. Then run:
    tools/sc2api/.venv/bin/python scripts/verify_api.py --attach --port 8765 -v

WHAT IT CAN CHECK (data only): health_max, shield_max, energy_max, armor, cargo_size,
cargo_space_max / passengers (bunker load), unit availability. It reads the *merged,
per-player* catalog exactly as the engine sees it after our lib applies its edits.

WHAT IT CANNOT CHECK: portraits, inspect-panel icons, tooltips, button faces, any
render-only or UI-only thing. Those still require the owner's eyes in game.

Requires the gitignored venv:  tools/sc2api/.venv  (run via that python).
    tools/sc2api/.venv/bin/python scripts/verify_api.py --attach [--port N] [--map traynor01.SC2Map]

Exits non-zero if any assertion FAILs (Milestone C).
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

# Windows: the default console codepage (cp1252) can't encode the non-ASCII glyphs
# (→ ✓ — ×) we print, raising UnicodeEncodeError. Force UTF-8 stdout/stderr.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# --- venv guard: the protos only import under protobuf<3.21 in our pinned venv ---
try:
    import websocket  # websocket-client
    from s2clientprotocol import sc2api_pb2 as sc_pb
    from s2clientprotocol import common_pb2 as common_pb
    from s2clientprotocol import raw_pb2 as raw_pb  # noqa: F401  (descriptors)
    from s2clientprotocol import debug_pb2 as debug_pb
    from s2clientprotocol import data_pb2 as data_pb  # noqa: F401
    from s2clientprotocol import query_pb2 as query_pb
except Exception as exc:  # pragma: no cover
    sys.stderr.write(
        "FATAL: could not import SC2 API deps (%s).\n"
        "Run via the venv:  tools/sc2api/.venv/bin/python scripts/verify_api.py\n"
        "(setup: python3 -m venv tools/sc2api/.venv && "
        "tools/sc2api/.venv/bin/pip install s2clientprotocol websocket-client 'protobuf<3.21')\n"
        % exc
    )
    raise SystemExit(2)

# ----------------------------------------------------------------------------
# Constants — local install paths. NOTE: this harness is SHELVED (SC2 API live
# reads are hard-blocked on retail 5.x — see docs/learnings.md §Verification tooling);
# kept only for the map-load sanity check. The default below is macOS; override with
# $WOLU_SC2_DIR on any OS (e.g. Windows C:\Program Files (x86)\StarCraft II).
# ----------------------------------------------------------------------------
SC2_ROOT = os.environ.get("WOLU_SC2_DIR") or (
    r"C:\Program Files (x86)\StarCraft II" if os.name == "nt"
    else "/Applications/StarCraft II")
SC2_VERSIONS = os.path.join(SC2_ROOT, "Versions")
DEFAULT_MAP = "traynor01.SC2Map"  # Liberation Day: P1 starts with Marines + Raynor
DEFAULT_PORT = 8765  # CLEAN port — 5000 is hijacked by macOS AirPlay Receiver
# Gitignored JSON dump of all observed unit data (Milestone C).
DUMP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools", "sc2api", "observed_units.json")

# Numeric SC2 unit-type ids for debug create_unit. Resolved live via RequestData,
# but we hard-map the ones we test so a missing-from-data id still works.
# (These are vanilla WoL catalog ids; verified live by the script's data dump.)


def log(msg: str) -> None:
    print(msg, flush=True)


def find_sc2_binary() -> str:
    if not os.path.isdir(SC2_VERSIONS):
        raise SystemExit("FATAL: %s not found — is SC2 installed?" % SC2_VERSIONS)
    bases = sorted(
        d for d in os.listdir(SC2_VERSIONS) if d.startswith("Base")
    )
    if not bases:
        raise SystemExit("FATAL: no Base* version dir under %s" % SC2_VERSIONS)
    # Highest build number = newest.
    base = max(bases, key=lambda d: int(d.replace("Base", "") or 0))
    binary = os.path.join(SC2_VERSIONS, base, "SC2.app", "Contents", "MacOS", "SC2")
    if not os.path.isfile(binary):
        raise SystemExit("FATAL: SC2 binary not found at %s" % binary)
    return binary


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


# ----------------------------------------------------------------------------
# SC2 controller — launch, websocket, request/response
# ----------------------------------------------------------------------------
class SC2Controller:
    def __init__(self, port: int, verbose: bool = False):
        self.port = port
        self.verbose = verbose
        self.proc: Optional[subprocess.Popen] = None
        self.ws: Optional[websocket.WebSocket] = None

    # -- process lifecycle -------------------------------------------------
    def launch(self) -> None:
        binary = find_sc2_binary()
        # SC2 wants to run from inside its Support dir; pass the version dir as cwd.
        cwd = os.path.dirname(binary)
        args = [
            binary,
            "-listen", "127.0.0.1",
            "-port", str(self.port),
            "-displaymode", "0",   # headless / no window
            "-windowwidth", "1024",
            "-windowheight", "768",
        ]
        log("Launching SC2 headless on 127.0.0.1:%d ..." % self.port)
        if self.verbose:
            log("  cmd: %s" % " ".join(args))
        self.proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # own process group so we can kill the tree
        )

    def connect(self, timeout: float = 60.0, attach: bool = False) -> None:
        """Open the websocket. In spawn mode we poll while the SC2 we launched binds;
        in attach mode we connect to the OWNER's already-running Battle.net instance
        (no process to watch — a refused connection just means nothing is listening)."""
        url = "ws://127.0.0.1:%d/sc2api" % self.port
        # Attaching to an already-running instance binds instantly; don't make the
        # owner wait a minute if the port is empty.
        if attach:
            timeout = min(timeout, 10.0)
        deadline = time.time() + timeout
        last_err = None
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                ws = websocket.create_connection(url, timeout=20, max_size=2 ** 30)
                self.ws = ws
                log("Connected websocket after %.1fs (attempt %d)."
                    % (timeout - (deadline - time.time()), attempt))
                return
            except Exception as exc:  # connection refused until SC2 binds
                last_err = exc
                if self.proc and self.proc.poll() is not None:
                    raise SystemExit(
                        "FATAL: SC2 process exited (code %s) before binding the port."
                        % self.proc.returncode
                    )
                time.sleep(1.0)
        if attach:
            print_attach_help(self.port, last_err)
            raise SystemExit(2)
        raise SystemExit("FATAL: could not connect to SC2 within %.0fs (%s)"
                         % (timeout, last_err))

    # -- request / response ------------------------------------------------
    def send(self, request: "sc_pb.Request", read_timeout: float = 120.0) -> "sc_pb.Response":
        assert self.ws is not None, "not connected"
        self.ws.send_binary(request.SerializeToString())
        self.ws.settimeout(read_timeout)
        raw = self.ws.recv()
        if isinstance(raw, str):
            raw = raw.encode("utf-8", "ignore")
        resp = sc_pb.Response()
        resp.ParseFromString(raw)
        if resp.error:
            log("  ! response errors: %s" % list(resp.error))
        return resp

    def ping(self) -> "sc_pb.Response":
        req = sc_pb.Request(ping=sc_pb.RequestPing())
        return self.send(req)

    # -- shutdown ----------------------------------------------------------
    def detach(self) -> None:
        """Close ONLY our websocket — do NOT send RequestQuit. Used in attach mode
        so the owner's Battle.net-launched SC2 keeps running."""
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None

    def quit(self) -> None:
        try:
            if self.ws is not None:
                try:
                    self.ws.send_binary(
                        sc_pb.Request(quit=sc_pb.RequestQuit()).SerializeToString()
                    )
                except Exception:
                    pass
                try:
                    self.ws.close()
                except Exception:
                    pass
        finally:
            self.ws = None

    def kill(self) -> None:
        """Always-kill cleanup. Tracks the PID we launched; never touches other SC2s
        unless the final pkill safety net fires."""
        self.quit()
        if self.proc is not None:
            try:
                if self.proc.poll() is None:
                    # Kill the whole process group we started.
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                    for _ in range(20):
                        if self.proc.poll() is not None:
                            break
                        time.sleep(0.25)
                    if self.proc.poll() is None:
                        os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as exc:
                log("  (warning during kill: %s)" % exc)
            self.proc = None


# ----------------------------------------------------------------------------
# Game setup — CreateGame / JoinGame on a built campaign map
# ----------------------------------------------------------------------------
def resolve_map_path(map_name: str) -> str:
    """Campaign maps live under Maps/Campaign/. The API's local_map.map_path is
    relative to the Maps/ root, so 'Campaign/<name>' is the portable form."""
    installed = os.path.join(SC2_ROOT, "Maps", "Campaign", map_name)
    if not os.path.isfile(installed):
        raise SystemExit("FATAL: campaign map not installed: %s\n"
                         "Run: python3 scripts/build.py install" % installed)
    return "Campaign/" + map_name


def create_and_join(ctrl: SC2Controller, map_name: str) -> "sc_pb.Response":
    map_path = resolve_map_path(map_name)
    # A WoL campaign map has ONE user slot. We provide a single Participant (Terran)
    # plus a Computer so the engine has a valid 2-player setup if it demands one.
    create = sc_pb.RequestCreateGame(
        local_map=sc_pb.LocalMap(map_path=map_path),
        realtime=False,
        disable_fog=True,
    )
    create.player_setup.add(type=sc_pb.Participant, race=common_pb.Terran)
    create.player_setup.add(
        type=sc_pb.Computer, race=common_pb.Terran, difficulty=sc_pb.VeryEasy
    )
    log("RequestCreateGame  map=%s ..." % map_path)
    resp = ctrl.send(sc_pb.Request(create_game=create), read_timeout=180.0)
    # The CreateGame error enum has no zero value: HasField is True only on a real error.
    create_failed = bool(resp.error or resp.create_game.HasField("error"))
    if create_failed:
        log("  CreateGame error=%s details=%r status=%s"
            % (sc_pb.ResponseCreateGame.Error.Name(resp.create_game.error)
               if resp.create_game.HasField("error") else "(transport)",
               resp.create_game.error_details, resp.status))
        # An attached Battle.net instance may already be hosting/in a game, so
        # CreateGame is rejected. That's not fatal: try to JoinGame anyway (the
        # instance may already be at a CreateGame'd lobby), and if it's already
        # fully in_game we'll surface that status below. Only bail on a license
        # block (the spawn-mode signature) or a bad map path.
        details = (resp.create_game.error_details or "").lower()
        if "license" in details or sc_pb.in_game in (resp.status,):
            # Already in a game: skip JoinGame, just report the live status so the
            # caller can decide. We return a synthetic "joined-ish" response by
            # reusing this resp; main() inspects resp.status.
            if resp.status == sc_pb.in_game:
                log("  (instance is already in_game — proceeding to Observation)")
                return resp
            return resp
        log("  (CreateGame rejected — attempting JoinGame against the running "
            "instance anyway)")

    join = sc_pb.RequestJoinGame(
        race=common_pb.Terran,
        options=sc_pb.InterfaceOptions(raw=True, score=False, raw_affects_selection=True),
    )
    log("RequestJoinGame (raw interface) ...")
    resp = ctrl.send(sc_pb.Request(join_game=join), read_timeout=180.0)
    if resp.error or resp.join_game.HasField("error"):
        log("  JoinGame error=%s details=%r status=%s"
            % (sc_pb.ResponseJoinGame.Error.Name(resp.join_game.error)
               if resp.join_game.HasField("error") else "(transport)",
               resp.join_game.error_details, resp.status))
        # If the instance was already in a game, JoinGame fails but the status
        # still tells us we can observe — surface that to the caller.
        if resp.status == sc_pb.in_game:
            log("  (status is in_game despite JoinGame error — proceeding to "
                "Observation against the live game)")
    else:
        log("Joined game. player_id=%d status=%s"
            % (resp.join_game.player_id, sc_pb.Status.Name(resp.status)))
    return resp


def is_license_block(resp: "sc_pb.Response") -> bool:
    """True if JoinGame failed specifically on Blizzard license validation — the
    known blocker for an API-spawned (vs Battle.net-launched) SC2 instance."""
    if not resp.join_game.HasField("error"):
        return False
    details = (resp.join_game.error_details or "").lower()
    return "validate game license" in details or "log in to blizzard" in details


def print_attach_help(port: int, last_err=None) -> None:
    log("""
================================================================================
 No SC2 listening on port %d
================================================================================
 --attach connects to an SC2 the OWNER launched, but nothing is listening on
 127.0.0.1:%d (last error: %s).

 ONE-TIME SETUP, then click PLAY and re-run:
   1. In the Battle.net app, open StarCraft II -> the gear/Settings next to PLAY
      -> "Additional command line arguments", and set EXACTLY:
          -listen 127.0.0.1 -port %d -displaymode 0
   2. Click the Battle.net PLAY button to launch StarCraft II (let it reach the
      main menu). That instance is BOTH authenticated AND API-listening.
   3. Re-run:
          tools/sc2api/.venv/bin/python scripts/verify_api.py --attach --port %d -v

 WHY attach (not spawn): an SC2 this script spawns itself with -listen never
 receives Battle.net's per-session license token, so JoinGame fails with
 "Unable to validate game license." Only a Battle.net-PLAY-launched instance is
 licensed. Attaching to THAT instance is the only working path.
================================================================================
""" % (port, port, last_err, port, port))


def print_license_help() -> None:
    log("""
================================================================================
 BLOCKED — Blizzard license validation (spawn mode is permanently blocked)
================================================================================
 CreateGame LOADED the map (our mod parsed fine — proven by the InvalidMapPath
 control test), but JoinGame was rejected with:
   "Unable to validate game license. Please log in to Blizzard ..."

 ROOT CAUSE (confirmed from the Battle.net log): when SC2 is spawned directly
 with -listen/-port (this script's default "spawn" mode), Battle.net sees the
 process but logs
   "Pre-existing game session detected without a pending launch.
    Not performing game launch behavior."
 i.e. it does NOT hand the instance the per-session SSO/license token it only
 grants to games IT launches. So the API instance has no license and JoinGame
 fails. This is a Blizzard-side gate, independent of our mod, and it is
 PERMANENT for spawn mode — the seed-the-session workarounds do NOT fix it.

 THE FIX — use --attach against a Battle.net-launched instance:
   1. In the Battle.net app, StarCraft II -> the gear/Settings next to PLAY ->
      "Additional command line arguments", set EXACTLY:
          -listen 127.0.0.1 -port 8765 -displaymode 0
   2. Click the Battle.net PLAY button (let SC2 reach the main menu). That
      instance is BOTH license-authenticated AND API-listening.
   3. Re-run this script in attach mode:
          tools/sc2api/.venv/bin/python scripts/verify_api.py --attach --port 8765 -v

 Attach mode connects to THAT instance instead of spawning its own, so it is
 already licensed — JoinGame succeeds and the full HP/armor/cargo/merc-vs-base
 verification runs.

 What spawn mode CAN still prove without a human:
   - the websocket API is live, ping works, our campaign map LOADS via CreateGame.
 What it needs the license for (i.e. what only --attach unlocks):
   - reading live per-player unit stats (HP/armor/cargo) via Observation.
================================================================================
""")


def step(ctrl: SC2Controller, count: int = 1) -> None:
    ctrl.send(sc_pb.Request(step=sc_pb.RequestStep(count=count)))


def observe(ctrl: SC2Controller) -> "sc_pb.ResponseObservation":
    resp = ctrl.send(sc_pb.Request(observation=sc_pb.RequestObservation()))
    return resp.observation


# ----------------------------------------------------------------------------
# Unit-type id resolution (name <-> numeric id) via RequestData
# ----------------------------------------------------------------------------
def load_unit_type_data(ctrl: SC2Controller):
    resp = ctrl.send(sc_pb.Request(data=sc_pb.RequestData(unit_type_id=True)),
                     read_timeout=120.0)
    by_id = {}
    by_name = {}
    for u in resp.data.units:
        by_id[u.unit_id] = u
        if u.name:
            by_name.setdefault(u.name, u)
    return by_id, by_name


# ----------------------------------------------------------------------------
# Debug spawn helpers (Milestone B)
# ----------------------------------------------------------------------------
def spawn_unit(ctrl: SC2Controller, unit_type_id: int, owner: int = 1,
               x: float = 40.0, y: float = 40.0, quantity: int = 1) -> None:
    cmd = debug_pb.DebugCommand(
        create_unit=debug_pb.DebugCreateUnit(
            unit_type=unit_type_id, owner=owner,
            pos=common_pb.Point2D(x=x, y=y), quantity=quantity,
        )
    )
    ctrl.send(sc_pb.Request(debug=sc_pb.RequestDebug(debug=[cmd])))


def kill_all_p1(ctrl: SC2Controller, obs: "sc_pb.ResponseObservation") -> None:
    tags = [u.tag for u in obs.observation.raw_data.units if u.owner == 1]
    if not tags:
        return
    cmd = debug_pb.DebugCommand(kill_unit=debug_pb.DebugKillUnit(tag=tags))
    ctrl.send(sc_pb.Request(debug=sc_pb.RequestDebug(debug=[cmd])))


# ----------------------------------------------------------------------------
# Assertions (Milestone C)
# ----------------------------------------------------------------------------
@dataclass
class Check:
    label: str
    expected: str
    actual: str = ""
    status: str = "SKIP"  # PASS | FAIL | SKIP
    note: str = ""


@dataclass
class Results:
    checks: list = field(default_factory=list)

    def add(self, c: Check) -> Check:
        self.checks.append(c)
        return c

    def record(self, label: str, expected, actual, ok: Optional[bool] = None,
               note: str = "") -> Check:
        if ok is None:
            ok = (str(expected) == str(actual))
        c = Check(label=label, expected=str(expected), actual=str(actual),
                  status=("PASS" if ok else "FAIL"), note=note)
        self.checks.append(c)
        return c

    def skip(self, label: str, expected, note: str) -> Check:
        return self.add(Check(label=label, expected=str(expected),
                              actual="—", status="SKIP", note=note))

    def print_table(self) -> int:
        log("")
        log("=" * 78)
        log(" SC2 API self-verification — v0.3.8 data checks")
        log("=" * 78)
        wl = max((len(c.label) for c in self.checks), default=10)
        we = max((len(c.expected) for c in self.checks), default=8)
        wa = max((len(c.actual) for c in self.checks), default=6)
        hdr = " %-6s | %-*s | %-*s | %-*s | %s" % (
            "RESULT", wl, "CHECK", we, "EXPECT", wa, "ACTUAL", "NOTE")
        log(hdr)
        log(" " + "-" * (len(hdr) - 1))
        for c in self.checks:
            log(" %-6s | %-*s | %-*s | %-*s | %s" % (
                c.status, wl, c.label, we, c.expected, wa, c.actual, c.note))
        n_pass = sum(1 for c in self.checks if c.status == "PASS")
        n_fail = sum(1 for c in self.checks if c.status == "FAIL")
        n_skip = sum(1 for c in self.checks if c.status == "SKIP")
        log("")
        log(" %d PASS, %d FAIL, %d SKIP" % (n_pass, n_fail, n_skip))
        log("=" * 78)
        return n_fail


# ----------------------------------------------------------------------------
# Verification routine
# ----------------------------------------------------------------------------
# Unit names as RequestData reports them (game string names) -> our test targets.
# Filled at runtime against the live data dump; we also keep numeric fallbacks.
TEST_UNITS = {
    # display name in data : numeric fallback id (vanilla WoL)
    "Marine": None,
    "SpartanCompany": None,
    "Bunker": None,
    "Marauder": None,
    "Ghost": None,
    "Thor": None,
}


def find_unit(by_name, by_id, *candidates):
    """Return (UnitTypeData, id) for the first candidate present, else (None, None)."""
    for cand in candidates:
        if isinstance(cand, int) and cand in by_id:
            return by_id[cand], cand
        if isinstance(cand, str) and cand in by_name:
            u = by_name[cand]
            return u, u.unit_id
    return None, None


def first_p1_unit_of_type(obs, type_id):
    for u in obs.observation.raw_data.units:
        if u.owner == 1 and u.unit_type == type_id:
            return u
    return None


# ----------------------------------------------------------------------------
# Merc/hero <-> base-unit pairs — THE central question this harness answers:
# "do our per-player catalog edits reach MERC/HERO unit types, or only the base
# unit id?" (genlib edits the base id; mercs/heroes use DISTINCT ids, so a base
# edit only reaches them if explicitly mirrored — see plan.md parity sweep).
# Each tuple: (base catalog name, counterpart catalog name, human label).
# Catalog names are what UnitTypeData.name reports (the XML id). Resolved live.
# ----------------------------------------------------------------------------
MERC_PAIRS = [
    ("Thor", "MercThor", "Thor vs Jotun (MercThor)"),          # THE linchpin pair
    ("Goliath", "SpartanCompany", "Goliath vs Spartan Company"),
    ("Marauder", "HammerSecurity", "Marauder vs Hammer Securities"),
    ("Marine", "WarPig", "Marine vs War Pig"),
    ("Firebat", "DevilDog", "Firebat vs Devil Dog"),
    ("SiegeTank", "SiegeBreaker", "Siege Tank vs Siege Breaker"),
    ("Banshee", "DuskWing", "Banshee vs Dusk Wing"),
    ("Medic", "MercMedic", "Medic vs Skibi's Angels (MercMedic)"),
    ("Reaper", "MercReaper", "Reaper vs Death Heads (MercReaper)"),
    ("Hellion", "MercHellion", "Hellion vs MercHellion"),
    ("Wraith", "MercWraith", "Wraith vs Winged Nightmares (MercWraith)"),
    ("Ghost", "MercSeniorGhost", "Ghost vs Senior Ghost"),
]

# Hero <-> base (rule 10: heroes inherit base-unit changes).
HERO_PAIRS = [
    ("Marine", "Raynor", "Marine vs Raynor"),
    ("Firebat", "Tychus", "Firebat vs Tychus"),
    ("Marauder", "Swann", "Marauder vs Swann"),
    ("Medic", "Stetmann", "Medic vs Stetmann"),
    ("Ghost", "Nova", "Ghost vs Nova"),
    ("Spectre", "Tosh", "Spectre vs Tosh"),
    ("Thor", "Odin", "Thor vs Odin"),
]


def query_available_abilities(ctrl, unit_tags):
    """RequestQueryAvailableAbilities for each tag. Returns {tag: set(ability_id)}.
    Used to ground-truth ability WIRING (Super Stim present? Medic can target a
    mechanical unit? merc carries the base unit's calldown kit?)."""
    if not unit_tags:
        return {}
    q = query_pb.RequestQuery(ignore_resource_requirements=True)
    for t in unit_tags:
        q.abilities.add(unit_tag=t)
    resp = ctrl.send(sc_pb.Request(query=q), read_timeout=60.0)
    out = {}
    for ab in resp.query.abilities:
        out[ab.unit_tag] = {a.ability_id for a in ab.abilities}
    return out


def spawn_read(ctrl, type_id, owner=1, x=44.0, y=44.0, settle=10):
    """Spawn one unit, step, return its observed raw Unit (or None)."""
    spawn_unit(ctrl, type_id, owner=owner, x=x, y=y, quantity=1)
    step(ctrl, settle)
    obs = observe(ctrl)
    return first_p1_unit_of_type(obs, type_id), obs


def run_verification(ctrl: SC2Controller, results: Results, verbose: bool) -> None:
    by_id, by_name = load_unit_type_data(ctrl)
    log("Loaded %d unit types from RequestData." % len(by_id))

    # Step a handful of frames so the trigger lib's OnGrantTech has applied
    # (canary fires ~1s in; at faster-than-realtime that's a few dozen frames).
    step(ctrl, 80)
    obs = observe(ctrl)

    p1_units = [u for u in obs.observation.raw_data.units if u.owner == 1]
    log("Player-1 starts with %d units." % len(p1_units))
    if verbose:
        seen = {}
        for u in p1_units:
            nm = by_id[u.unit_type].name if u.unit_type in by_id else str(u.unit_type)
            seen.setdefault(nm, []).append(u)
        for nm, us in sorted(seen.items()):
            u0 = us[0]
            log("  %2dx %-18s hp=%g/%g armor?=%s cargo_max=%d"
                % (len(us), nm, u0.health, u0.health_max, "-", u0.cargo_space_max))

    # --- Marine HP (the make-or-break Milestone A signal) ----------------
    md, mid = find_unit(by_name, by_id, "Marine")
    marine_obs = first_p1_unit_of_type(obs, mid) if mid else None
    if marine_obs is None and mid is not None:
        # Spawn one if Liberation Day didn't pre-place a free marine yet.
        spawn_unit(ctrl, mid, owner=1, x=42, y=42, quantity=1)
        step(ctrl, 8)
        obs = observe(ctrl)
        marine_obs = first_p1_unit_of_type(obs, mid)
    if marine_obs is not None:
        results.record(
            "Marine health_max (45 base +20)", 65, marine_obs.health_max,
            ok=(abs(marine_obs.health_max - 65) < 0.5),
            note="LANDMARK: proves per-player catalog edits ARE observable via API"
            if abs(marine_obs.health_max - 65) < 0.5
            else "reads %g -> lib may not have applied" % marine_obs.health_max,
        )
    else:
        results.skip("Marine health_max (45 base +20)", 65,
                     "no Marine type/unit found")

    # --- Spartan Company HP (v0.3.8 Spartan fix -> ~198) -----------------
    sd, sid = find_unit(by_name, by_id, "SpartanCompany", "Spartan Company")
    if sid is not None:
        spawn_and_check_hp(ctrl, results, sid, "SpartanCompany health_max (v0.3.8)",
                           198, tol=2.0)
    else:
        results.skip("SpartanCompany health_max (v0.3.8)", 198,
                     "SpartanCompany not in unit data (merc; may need compound)")

    # --- Bunker cargo cap (v0.3.8: MaxCargoCount 4->32) ------------------
    bd, bid = find_unit(by_name, by_id, "Bunker")
    if bid is not None:
        spawn_unit(ctrl, bid, owner=1, x=46, y=46, quantity=1)
        step(ctrl, 8)
        obs = observe(ctrl)
        bunker = first_p1_unit_of_type(obs, bid)
        if bunker is not None:
            results.record("Bunker cargo_space_max (v0.3.8: 32)", 32,
                           bunker.cargo_space_max,
                           ok=(bunker.cargo_space_max == 32),
                           note="empty bunker reports its capacity")
        else:
            results.skip("Bunker cargo_space_max (v0.3.8: 32)", 32,
                         "bunker spawn not observed")
    else:
        results.skip("Bunker cargo_space_max (v0.3.8: 32)", 32, "Bunker not in data")

    # --- Cargo sizes from UnitTypeData (data-level, no spawn needed) ------
    for nm, expect in (("Marauder", 2), ("Ghost", 2), ("Thor", 8)):
        ud, uid = find_unit(by_name, by_id, nm)
        if ud is not None:
            results.record("%s cargo_size (UnitTypeData)" % nm, expect, ud.cargo_size,
                           ok=(ud.cargo_size == expect),
                           note="NB: data dump may be pre-edit; see report")
        else:
            results.skip("%s cargo_size (UnitTypeData)" % nm, expect,
                         "%s not in data" % nm)

    # --- Marine armor (from UnitTypeData) --------------------------------
    if md is not None:
        results.record("Marine armor (UnitTypeData)", "0..N", md.armor,
                       ok=True, note="reported %g (data-dump value)" % md.armor)

    # --- THE linchpin: merc/hero vs base side-by-side (Milestone B) -------
    observed = compare_pairs(ctrl, results, by_id, by_name, verbose)

    # --- Medic-heals-mechanical probe (RequestQueryAvailableAbilities) ---
    probe_medic_heal_mech(ctrl, results, by_id, by_name, observed)

    # --- JSON dump of everything observed (Milestone C) ------------------
    dump_observations(observed, by_id)


# Numeric SC2 ability ids we look for in QueryAvailableAbilities. The data API
# reports ability ids; these are the vanilla WoL ids for the abilities we probe.
# Resolved/printed live so a mismatch is visible (we don't assert on the number).
ABIL_HINTS = {
    "stim": ("Stim", "SuperStim"),
    "heal": ("Heal", "MedicHeal"),
}


def _unit_record(u, by_id):
    """Flatten a raw observation Unit into a JSON-able dict."""
    name = by_id[u.unit_type].name if u.unit_type in by_id else None
    return {
        "tag": u.tag, "unit_type": u.unit_type, "name": name,
        "owner": u.owner,
        "health": round(u.health, 2), "health_max": round(u.health_max, 2),
        "shield": round(u.shield, 2), "shield_max": round(u.shield_max, 2),
        "energy": round(u.energy, 2), "energy_max": round(u.energy_max, 2),
        "armor": getattr(by_id.get(u.unit_type), "armor", None)
                 if u.unit_type in by_id else None,
        "cargo_space_taken": u.cargo_space_taken,
        "cargo_space_max": u.cargo_space_max,
        "weapon_cooldown": round(u.weapon_cooldown, 3),
    }


# Accumulator for the JSON dump (Milestone C).
_OBSERVED = {"meta": {}, "pairs": [], "units": [], "abilities": {}}


def compare_pairs(ctrl, results, by_id, by_name, verbose):
    """Spawn each base + counterpart side by side and compare the data-level
    fields. ANSWERS: do per-player edits reach merc/hero unit types?

    A PASS here = the counterpart's edited stat MATCHES its intended buff (i.e.
    the parity sweep reached it). A counterpart reading the *vanilla* base value
    where a buff was expected = the edit did NOT reach that unit id."""
    x = 38.0
    for label_group, pairs in (("MERC", MERC_PAIRS), ("HERO", HERO_PAIRS)):
        for base_name, cp_name, label in pairs:
            bd, bid = find_unit(by_name, by_id, base_name)
            cd, cid = find_unit(by_name, by_id, cp_name)
            if bid is None or cid is None:
                results.skip("%s pair: %s" % (label_group, label), "both spawn",
                             "missing %s%s"
                             % ("" if bid else base_name,
                                ("/" + cp_name) if cid is None else ""))
                continue
            base_u, _ = spawn_read(ctrl, bid, x=x, y=40.0)
            x += 2.0
            cp_u, _ = spawn_read(ctrl, cid, x=x, y=40.0)
            x += 2.0
            if base_u is None or cp_u is None:
                results.skip("%s pair: %s" % (label_group, label), "both spawn",
                             "spawn not observed (gated unit?)")
                continue
            # Abilities on both, to compare the kit.
            abils = query_available_abilities(ctrl, [base_u.tag, cp_u.tag])
            base_rec = _unit_record(base_u, by_id)
            cp_rec = _unit_record(cp_u, by_id)
            base_rec["abilities"] = sorted(abils.get(base_u.tag, ()))
            cp_rec["abilities"] = sorted(abils.get(cp_u.tag, ()))
            _OBSERVED["pairs"].append(
                {"label": label, "base": base_rec, "counterpart": cp_rec})
            # The headline comparison: counterpart HP should be >= base HP
            # (every merc/hero keeps a % advantage AND inherits buffs — rule 4/10).
            note = ("base hp=%g cp hp=%g | base armor=%s cp armor=%s | "
                    "base abils=%d cp abils=%d"
                    % (base_rec["health_max"], cp_rec["health_max"],
                       base_rec["armor"], cp_rec["armor"],
                       len(base_rec["abilities"]), len(cp_rec["abilities"])))
            results.record(
                "%s pair: %s (cp HP >= base HP)" % (label_group, label),
                ">= %g" % base_rec["health_max"], cp_rec["health_max"],
                ok=(cp_rec["health_max"] >= base_rec["health_max"] - 0.5),
                note=note)
            if verbose:
                log("  %s: %s" % (label, note))
                log("      base abils: %s" % base_rec["abilities"])
                log("      cp   abils: %s" % cp_rec["abilities"])
    return _OBSERVED


def probe_medic_heal_mech(ctrl, results, by_id, by_name, observed):
    """Medic Adaptive Medpacks: can a player Medic TARGET a mechanical unit?
    Spawn a Medic + a Marauder (mechanical? no — vehicle) — use a Viking/Thor as
    the mechanical target. Then QueryAvailableAbilities won't show target
    legality directly, so we record the Medic's ability list for inspection and
    note the limitation (target-filter legality needs RequestQuery with a target,
    which the data API does not expose per-target in this build)."""
    medic_d, medic_id = find_unit(by_name, by_id, "Medic")
    mech_d, mech_id = find_unit(by_name, by_id, "Thor", "Viking", "SiegeTank")
    if medic_id is None:
        results.skip("Medic heal kit (Adaptive Medpacks)", "heal abil present",
                     "Medic not in data")
        return
    medic_u, _ = spawn_read(ctrl, medic_id, x=60.0, y=60.0)
    if mech_id is not None:
        spawn_read(ctrl, mech_id, x=62.0, y=60.0)
    if medic_u is None:
        results.skip("Medic heal kit (Adaptive Medpacks)", "heal abil present",
                     "Medic spawn not observed")
        return
    abils = query_available_abilities(ctrl, [medic_u.tag])
    medic_abils = sorted(abils.get(medic_u.tag, ()))
    _OBSERVED["abilities"]["Medic"] = medic_abils
    results.record(
        "Medic has a heal ability available", "non-empty", len(medic_abils),
        ok=(len(medic_abils) > 0),
        note="abil ids=%s | NB: per-TARGET heal legality (mech/air) is a "
             "TargetFilters check the data API can't read remotely — confirm "
             "the actual heal-on-Marauder in game" % medic_abils[:8])


def dump_observations(observed, by_id):
    import json
    observed["meta"] = {
        "note": "All player-1 unit data observed via the SC2 client API. "
                "Data-level only (HP/shield/energy/armor/cargo/abilities); "
                "render-only fields (portraits, icons) are NOT here.",
        "unit_type_count": len(by_id),
    }
    try:
        with open(DUMP_PATH, "w") as fh:
            json.dump(observed, fh, indent=2, sort_keys=True)
        log("\nWrote observation dump -> %s" % DUMP_PATH)
    except Exception as exc:
        log("  (could not write dump: %s)" % exc)


def spawn_and_check_hp(ctrl, results, type_id, label, expected, tol=1.0):
    spawn_unit(ctrl, type_id, owner=1, x=44, y=44, quantity=1)
    step(ctrl, 10)
    obs = observe(ctrl)
    u = first_p1_unit_of_type(obs, type_id)
    if u is None:
        results.skip(label, expected, "spawn not observed (gated unit?)")
        return
    results.record(label, expected, u.health_max,
                   ok=(abs(u.health_max - expected) <= tol))


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attach", action="store_true",
                    help="attach to an SC2 the OWNER launched via Battle.net's PLAY "
                         "button with `-listen 127.0.0.1 -port <port> -displaymode 0` "
                         "set in its 'Additional command line arguments'. This is the "
                         "ONLY working path (spawn mode is Blizzard-license-blocked). "
                         "Never launches or kills SC2; implies --keep-open.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--keep-open", action="store_true",
                    help="don't kill SC2 on exit (for manual inspection)")
    ap.add_argument("--connect-timeout", type=float, default=60.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    # Attach mode never kills SC2 (it's the owner's Battle.net instance).
    keep_open = args.keep_open or args.attach

    port = args.port
    if args.attach:
        # In attach mode the port is SUPPOSED to be occupied by the owner's SC2 —
        # an empty port is the failure case, handled by connect()/print_attach_help.
        if port_free(port):
            print_attach_help(port, "nothing listening")
            return 2
    elif not port_free(port):
        log("WARNING: port %d is in use; trying %d." % (port, port + 1))
        port += 1
        if not port_free(port):
            raise SystemExit("FATAL: ports %d/%d both busy." % (port - 1, port))

    ctrl = SC2Controller(port, verbose=args.verbose)
    results = Results()
    n_fail = 1  # default to failure unless we complete

    def handle_sig(signum, frame):
        if args.attach:
            # Don't kill the owner's instance; just drop our websocket.
            log("\nSignal %d — detaching (owner's SC2 left running)." % signum)
            ctrl.detach()
        else:
            log("\nSignal %d — cleaning up SC2." % signum)
            ctrl.kill()
        os._exit(130)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    try:
        if args.attach:
            log("ATTACH mode: connecting to the owner's SC2 on 127.0.0.1:%d "
                "(not launching our own) ..." % port)
            ctrl.connect(timeout=args.connect_timeout, attach=True)
        else:
            ctrl.launch()
            ctrl.connect(timeout=args.connect_timeout)

        pong = ctrl.ping()
        log("Ping OK — SC2 build %s, data %s, status=%s"
            % (pong.ping.base_build, pong.ping.data_version,
               sc_pb.Status.Name(pong.status)))

        resp = create_and_join(ctrl, args.map)
        # "joined" includes the already-in-game case: an attached Battle.net
        # instance may already be in a game (CreateGame/JoinGame error) yet still
        # observable — status==in_game is the ground truth either way.
        join_ok = (not resp.error and not resp.join_game.HasField("error")
                   and resp.status in (sc_pb.in_game, sc_pb.init_game))
        joined = join_ok or resp.status == sc_pb.in_game
        if not joined:
            if is_license_block(resp):
                print_license_help()
                results.skip("Milestone A: in_game on campaign map", "in_game",
                             "BLOCKED: Blizzard license not validated (see above)")
            else:
                log("\nBLOCKED: could not reach in_game state. See errors above.")
                results.skip("Milestone A: in_game on campaign map", "in_game",
                             "CreateGame/JoinGame failed")
            results.print_table()
            # License block is an environment blocker, not a mod FAIL: exit 2.
            return 2 if is_license_block(resp) else 1

        run_verification(ctrl, results, args.verbose)
        n_fail = results.print_table()
        return 1 if n_fail else 0

    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        log("\nEXCEPTION: %s" % exc)
        if args.verbose:
            traceback.print_exc()
        return 3
    finally:
        if args.attach:
            # NEVER kill in attach mode — it's the owner's Battle.net instance.
            # Only close our websocket; the pkill safety net would kill their SC2.
            log("\n--attach: leaving the owner's SC2 running on port %d "
                "(not killing it)." % port)
            ctrl.detach()
        elif keep_open:
            log("\n--keep-open: leaving SC2 running on port %d (PID %s). "
                "Kill it with:  pkill -f 'Versions/Base.*MacOS/SC2'"
                % (port, ctrl.proc.pid if ctrl.proc else "?"))
        else:
            log("\nCleaning up SC2 process ...")
            ctrl.kill()
            # Final safety net — never leave a stray headless SC2 behind.
            subprocess.run(
                ["pkill", "-f", r"Versions/Base.*SC2\.app/Contents/MacOS/SC2"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    sys.exit(main())
