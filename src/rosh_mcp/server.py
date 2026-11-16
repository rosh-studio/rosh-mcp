#!/usr/bin/env python3
"""
Rosh MCP Server — Model Context Protocol wrapper for the rosh.cloud API.

Lets any MCP-capable AI tool (Claude Desktop, Claude Code, Cursor, Windsurf,
etc.) build live 3D rooms in Rosh without rendering anything (rosh_room_*), and
compile, publish, browse and moderate Rosh programs.

Environment variables:
    ROSH_API_KEY   — rosh.cloud API key (not needed for rosh_room_guide or rosh_docs;
                     rosh_room_look works without one for public rooms)
    ROSH_API_BASE  — API base URL (default: https://rosh.cloud)
"""

import contextlib
import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Rosh")

# ── Config ──

API_BASE = os.environ.get("ROSH_API_BASE", "https://rosh.cloud").rstrip("/")
API_KEY = os.environ.get("ROSH_API_KEY", "")


def _headers() -> dict[str, str]:
    h = {
        "User-Agent": "RoshMCP/0.3",
        "Content-Type": "application/json",
    }
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def _api(method: str, path: str, data: dict | None = None) -> dict:
    """Make an authenticated request to the Rosh API."""
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.request(method, url, headers=_headers(), json=data)
        resp.raise_for_status()
        return resp.json()


def _api_safe(method: str, path: str, data: dict | None = None) -> str:
    """Like _api but returns a formatted string, handling errors gracefully."""
    try:
        result = _api(method, path, data)
        return json.dumps(result, indent=2)
    except httpx.HTTPStatusError as e:
        body = e.response.text
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = body[:500]
        result = {"error": True, "status": e.response.status_code, "detail": detail}
        if e.response.status_code == 401:
            result["hint"] = "Set the ROSH_API_KEY environment variable to a valid rosh.cloud API key (Settings -> API Keys at rosh.cloud)."
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": True, "detail": str(e)}, indent=2)


# ── Tools ──

@mcp.tool()
def rosh_docs() -> str:
    """Get the Rosh language documentation — keywords, widgets, targets, and examples.

    Returns the full language reference including all 25 keywords, available widgets,
    compile targets (web, phaser, threejs), and example programs. No key needed on
    rosh.cloud since 15 Nov 2026 (older servers ask for ROSH_API_KEY). For rooms, read
    rosh_room_guide instead.
    """
    return _api_safe("GET", "/api/v1/docs")


@mcp.tool()
def rosh_compile(code: str, target: str = "web") -> str:
    """Compile Rosh code into a runnable HTML page. Requires ROSH_API_KEY.

    Rosh is a plain-English programming language. Example:
        create box called player at 400 300
        set player color "blue"
        on key "ArrowRight" then set player x to player x + 5

    Args:
        code: Rosh source code to compile
        target: Target platform — "web" (HTML5 canvas), "phaser" (game engine), or "threejs" (3D)
    """
    return _api_safe("POST", "/api/v1/compile", {"code": code, "target": target})


@mcp.tool()
def rosh_publish(title: str, slug: str, code: str, target: str = "web",
                 description: str = "") -> str:
    """Compile and publish a Rosh program to rosh.cloud. Requires API key with write scope.

    The published program gets a public URL at https://rosh.cloud/p/{username}/{slug}

    Args:
        title: Display title for the program
        slug: URL-safe identifier (lowercase, hyphens only, e.g. "space-shooter")
        code: Rosh source code
        target: Target platform — "web", "phaser", or "threejs"
        description: One-line description of what the program does
    """
    return _api_safe("POST", "/api/v1/programs", {
        "title": title,
        "slug": slug,
        "code": code,
        "target": target,
        "description": description,
    })


@mcp.tool()
def rosh_list_programs() -> str:
    """List all programs owned by the authenticated user. Requires API key."""
    return _api_safe("GET", "/api/v1/programs")


@mcp.tool()
def rosh_get_program(program_id: int) -> str:
    """Get details of a specific program by ID. Requires API key.

    Args:
        program_id: The numeric program ID
    """
    return _api_safe("GET", f"/api/v1/programs/{program_id}")


@mcp.tool()
def rosh_update_program(program_id: int, title: Optional[str] = None,
                        description: Optional[str] = None, code: Optional[str] = None,
                        target: Optional[str] = None) -> str:
    """Update an existing program. Only provided fields are changed. Requires API key with write scope.

    Args:
        program_id: The numeric program ID
        title: New title (optional)
        description: New description (optional)
        code: New source code (optional)
        target: New target platform (optional)
    """
    data = {}
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if code is not None:
        data["code"] = code
    if target is not None:
        data["target"] = target
    return _api_safe("PUT", f"/api/v1/programs/{program_id}", data)


@mcp.tool()
def rosh_delete_program(program_id: int) -> str:
    """Permanently delete a program. Requires API key with write scope.

    Args:
        program_id: The numeric program ID
    """
    return _api_safe("DELETE", f"/api/v1/programs/{program_id}")


@mcp.tool()
def rosh_hide_program(identifier: str) -> str:
    """Hide a program from public view (moderation). Requires API key with moderate scope.

    Args:
        identifier: Program ID (numeric) or slug (string)
    """
    return _api_safe("POST", f"/api/v1/programs/{identifier}/hide")


@mcp.tool()
def rosh_show_program(identifier: str) -> str:
    """Make a hidden program visible again. Requires API key with moderate scope.

    Args:
        identifier: Program ID (numeric) or slug (string)
    """
    return _api_safe("POST", f"/api/v1/programs/{identifier}/show")


# ── Rooms: live 3D spaces built in Rosh, drawn by any renderer ──
#
# A room lives on rosh.cloud. The browser, Unity, Unreal and the terminal all
# draw the same live room; an agent needs none of them. It writes Rosh, the
# room checks each line and confirms or refuses it, and `look` reads the room
# back as text.

ROOM_GUIDE = """\
ROSH ROOMS: a short guide for agents (rosh-mcp)

A room is a live 3D space on rosh.cloud. You change it by sending Rosh lines
(rosh_room_do); the room checks each one and says CONFIRMED or REFUSED with a
reason. rosh_room_look returns everything in it as text. Anyone with the room's
link sees the same room, live, in a browser (and in Unity or Unreal clients).

WRITE ROSH, NOT ENGLISH. The room reads plain English loosely and may drop words
("a tall stone next to the plinth" makes a plain cube). Spell out each property.

MAKE AND REMOVE
  create object stone_1              # a new thing; names: letters, digits, _ and -
                                     # (not a bare word like "a" or "the")
  destroy stone_1

PLACE AND SIZE (metres; y is up; the ground is y = 0)
  set stone_1.x to 3                 # left/right
  set stone_1.z to -2                # towards/away
  set stone_1.size to 2              # 1 is about a metre across
  Leave y out: things stand on the ground. Set y only to lift something into
  the air (set lamp_1.y to 3); it is the height of the thing's middle, so a
  thing given y = 0 sinks halfway into the ground.
  set stone_1.height to 2.5          # a plain shape's size along one axis, in
  set stone_1.width to 0.8           # metres: height (up), width (left/right),
  set stone_1.depth to 0.3           # depth (towards/away); each falls back to size
  (Width, height and depth shape plain shapes: cube, sphere, cylinder, cone,
  plane. Models and doors use size. There is no .position or .stretch: use x,
  y, z, size, width, height and depth.)

SEEING WITHOUT A SCREEN
  rosh_room_look returns layout_notes: things that overlap, things one behind
  another from where visitors stand (their signs pile up), and things outside
  the first view. Fix each note, then look again.

LOOK
  set stone_1.shape to cylinder      # cube, sphere, cylinder, cone, torus, plane
  set stone_1.color to grey          # a colour name or #rrggbb
  set stone_1.opacity to 0.5
  set stone_1.wireframe to true
  set stone_1.label to "Pictish stone"   # a sign above it
  set stone_1.description to "Carved about 800 AD."   # shown when clicked

MOVEMENT
  set stone_1.spin to 1              # turns; 0 stops
  set stone_1.bounce to 1
  set stone_1.pulse to 1

DOORS
  create object door_1
  set door_1.door_to to "/world/<owner>/<other-room>"
  set door_1.label to "To the garden"

THE ROOM ITSELF (best in the room's starting code, rosh_create_room)
  # sky: #87b7d8                     # header lines at the top of the code
  # ground: #47703a
  # camera: 8 1.8 14 -> 0 1.4 0      # where a visitor stands -> looks
  set room.title to "Pictish stones"
  set room.intro to "Four carved stones from north-east Scotland."
  set room.guide_1 to "Click a stone to read about it."

LIMITS (a value outside is REFUSED with the range; nothing is clamped)
  x and z: -500 to 500        y: -50 to 500         size, width, height, depth: 0.01 to 100
  spin, bounce, pulse: -20 to 20                     opacity: 0 to 1
  A door may only lead to a room on this site (a path like /world/rosh/blocks).
  Colours: red, green, blue, yellow, orange, purple, pink, brown, black, white,
  grey, gold, silver, navy, teal, lime, coral, crimson, violet, indigo, maroon,
  olive, aqua, cyan, magenta, sapphire, lavender, turquoise, mustard, emerald,
  amber, fuchsia; each also as dark-, deep-, light-, pale- (darkred, palegreen);
  or a code like #3366cc. Anything else is refused with the nearest names.
  True/false (wireframe, visible, locked): true, false, yes, no, on, off.
  Shapes: cube, sphere, cylinder, cone, torus, plane, pyramid, or a model the
  room knows (rosh/museum's: amphora, cauldron, sword, torc...).

YOUR OWN FACTS
  A room keeps any property you set (set stone_1.year to 800), and refuses
  nothing for being unknown, but a near-typo of a real property (colr) is
  flagged. Never invent facts about real objects; say where a fact came from
  (set stone_1.source to "...").

WHO MAY CHANGE IT (visitors with the link, no key)
  Things you add live with rosh_room_do are yours: visitors can't change or
  remove them. Things in the starting code belong to the room:
  - a new room is "shared": visitors may add their own things, and may move,
    recolour or relabel the room's things, but not remove them;
  - with `set room.rules to museum` in the starting code, visitors can't add
    things or change labels and records; they may still move and recolour;
  - with `set room.rule.build to 9` in the starting code, visitors may only
    look (levels are numbers: 0 look, 3 build, 5 edit, 9 own).

STARTING CODE vs LIVE CHANGES
  rosh_create_room takes the room's starting code (the lines above, one per
  line). Lines that can't run are listed under "problems" in its reply (and
  in rosh_room_look as code_problems). rosh_set_room_code replaces the code and
  resets the live room to it (live additions go); rosh_room_do changes the live
  room without touching the code. Small fixes: rosh_room_do. A rethink:
  rosh_set_room_code.
"""


def _room_ref(room: str) -> tuple[str, str]:
    """'owner/slug', '@owner/slug' or a rosh.cloud room link -> (owner, slug)."""
    text = room.strip().rstrip("/")
    if "://" in text:
        text = text.split("://", 1)[1].split("/", 1)[-1]
    parts = [p for p in text.split("/") if p]
    if parts and parts[0] == "world":
        parts = parts[1:]
    if len(parts) != 2:
        raise ValueError(f"Can't read the room {room!r}: give 'owner/slug' or the room's link.")
    return parts[0].lstrip("@"), parts[1]


@contextlib.contextmanager
def _room_socket(room: str):
    """The room's live socket, opened with the API key: yields (socket, room info, CONNECTED message)."""
    from websockets.sync.client import connect

    owner, slug = _room_ref(room)
    info = _api("GET", f"/api/v1/world/{owner}/{slug}")
    ws_url = info["ws_url"]
    # The server names its own public address; when talking to a local or
    # relayed server, keep the address this client was given.
    base = API_BASE.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = base + ws_url[ws_url.index("/ws/"):]
    headers = {"User-Agent": "RoshMCP/0.3"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    with connect(ws_url, additional_headers=headers, open_timeout=20, max_size=32 * 1024 * 1024) as ws:
        while True:
            message = json.loads(ws.recv(timeout=15))
            if message.get("type") == "CONNECTED":
                break
        yield ws, info, message


def _await_answer(ws, request_id: str, timeout: float = 20.0) -> tuple[dict | None, list[str]]:
    """Read until the room confirms or refuses this request; collect anything it says."""
    import time

    said: list[str] = []
    end = time.monotonic() + timeout
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return None, said
        try:
            message = json.loads(ws.recv(timeout=left))
        except TimeoutError:
            return None, said
        if message.get("request_id") != request_id:
            continue
        kind = message.get("type")
        if kind in ("SAY", "NOTE"):
            text = message.get("text") or message.get("message")
            if text:
                said.append(text)
            continue
        if kind in ("CONFIRMED_ROSH", "REJECTED"):
            return message, said


def _brief_answer(line: str, answer: dict | None, said: list[str]) -> dict:
    if answer is None:
        return {"line": line, "ok": False, "reason": "no_answer",
                "message": "The room didn't answer within 20 seconds."}
    out: dict = {"line": line, "ok": answer.get("type") == "CONFIRMED_ROSH"}
    if out["ok"]:
        ran = answer.get("command")
        if ran and ran.strip() != line.strip():
            out["ran"] = ran  # what the room read the line as
        delta = answer.get("state_delta") or {}
        for key in ("created", "updated"):
            if delta.get(key):
                out[key] = sorted(delta[key])
        if delta.get("deleted"):
            out["deleted"] = sorted(delta["deleted"])
        if not any(k in out for k in ("created", "updated", "deleted")) and "inspection" not in answer:
            out["note"] = "Confirmed, but nothing in the room changed."
        if "inspection" in answer:
            out["inspection"] = answer["inspection"]
        for key in ("message", "note", "warning"):
            if answer.get(key) and key not in out:
                out[key] = answer[key]
    else:
        out["reason"] = answer.get("reason")
        out["message"] = answer.get("message")
        if answer.get("suggestions"):
            out["suggestions"] = answer["suggestions"]
    if said:
        out["said"] = said
    return out


LOOK_MAX_THINGS = 150
LOOK_MAX_VALUE = 300


def _brief_things(objects: dict) -> dict:
    """The room's things without bookkeeping fields, long values shortened."""
    hidden = {"uuid", "type", "object_type", "created_by"}
    out = {}
    for name, props in sorted(objects.items()):
        brief = {}
        for k, v in (props or {}).items():
            if k in hidden:
                continue
            text = v if isinstance(v, str) else json.dumps(v, default=str)
            if len(text) > LOOK_MAX_VALUE:
                v = text[:LOOK_MAX_VALUE] + f"... ({len(text)} characters)"
            brief[k] = v
        out[name] = brief
    return out


def _error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        try:
            detail = e.response.json()
        except ValueError:
            detail = e.response.text[:500]
        return json.dumps({"error": True, "status": e.response.status_code, "detail": detail}, indent=2)
    return json.dumps({"error": True, "detail": f"{type(e).__name__}: {e}"}, indent=2)


@mcp.tool()
def rosh_room_guide() -> str:
    """How to build a Rosh room: the lines a room understands, with examples. Read this first.

    No API key needed. Rooms are live 3D spaces on rosh.cloud, built by sending Rosh lines;
    you never need to see or render them.
    """
    return ROOM_GUIDE


@mcp.tool()
def rosh_create_room(slug: str, code: str = "", name: Optional[str] = None) -> str:
    """Create a new room from starting Rosh code. Requires an API key with write scope.

    Read rosh_room_guide first for the lines a room understands. The result's "url" is
    the room's address (give that one, not a guess); anyone with the link can see it.

    Args:
        slug: the room's address part: lowercase letters, digits and hyphens, e.g. "pictish-stones"
        code: the room's starting Rosh code, one line per statement (may be empty)
        name: the room's display name (defaults to the slug)
    """
    try:
        result = _api("POST", "/api/v1/worlds", {"slug": slug, "name": name or slug, "code": code,
                                                 "render_target": "threejs"})
        if result.get("success"):
            result["room"] = f"{result['owner']}/{result['slug']}"
            result["url"] = f"{API_BASE}/world/{result['owner']}/{result['slug']}"
            result["next"] = ("Change it live with rosh_room_do; read it with rosh_room_look."
                              + (" Some starting lines didn't run: see problems." if result.get("problems") else ""))
        return json.dumps(result, indent=2)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@mcp.tool()
def rosh_list_rooms() -> str:
    """List the rooms you own. Requires an API key."""
    try:
        result = _api("GET", "/api/v1/worlds")
        return json.dumps(result, indent=2)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@mcp.tool()
def rosh_set_room_code(slug: str, code: str, reset_now: bool = True) -> str:
    """Replace the starting code of a room you own, and (by default) reset the live room to
    it, so rosh_room_look shows the new code. Requires an API key with write and world scopes.

    Resetting puts the room back to its code: anything added live since (by you or by
    visitors) goes. Pass reset_now=false to save the code without touching the live room.

    Args:
        slug: the room's slug (one of yours)
        code: the new starting Rosh code
        reset_now: reset the live room to the new code (default true)
    """
    try:
        result = _api("PUT", f"/api/v1/worlds/{slug}", {"code": code})
    except Exception as e:  # noqa: BLE001
        return _error(e)
    if result.get("success") and reset_now and result.get("owner"):
        # The live room keeps its state until it is reset; an agent that looked after
        # saving saw the old room (agent runs A01, 16 Nov).
        reset = json.loads(rosh_room_do(f"{result['owner']}/{slug}", "reset world"))
        first = (reset.get("results") or [{}])[0]
        result["reset"] = "done: the live room now matches the code" if first.get("ok") else (
            f"not done ({first.get('reason') or reset.get('detail')}): the live room still shows the old code")
    elif result.get("success"):
        result["reset"] = "not asked: the live room still shows the old code until it is reset"
    return json.dumps(result, indent=2)


@mcp.tool()
def rosh_delete_room(slug: str) -> str:
    """Permanently delete one of your rooms (not your main room). Requires an API key
    with write scope. Everyone in it is sent out, and its link stops working.

    Args:
        slug: the room's slug (one of yours)
    """
    try:
        return json.dumps(_api("DELETE", f"/api/v1/worlds/{slug}"), indent=2)
    except Exception as e:  # noqa: BLE001
        return _error(e)


@mcp.tool()
def rosh_room_do(room: str, rosh: str, stop_on_refusal: bool = True) -> str:
    """Send Rosh lines to a live room and report what each one did.

    Each line is checked by the room and either CONFIRMED (with the things it created,
    updated or deleted) or REFUSED (with a reason). Everyone viewing the room sees the
    change at once. Needs an API key with the 'world' scope to change a room; read
    rosh_room_guide for the lines a room understands. Write Rosh, not English.

    Args:
        room: "owner/slug" or the room's link, e.g. "rosh/blocks"
        rosh: one or more Rosh lines, one per line (blank lines and # comments are skipped)
        stop_on_refusal: stop at the first refused line (default true)
    """
    lines = [ln.strip() for ln in rosh.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    if not lines:
        return json.dumps({"error": True, "detail": "No Rosh lines to send."})
    results = []
    info: dict = {}
    try:
        with _room_socket(room) as (ws, info, _):
            for i, line in enumerate(lines):
                request_id = f"mcp-{os.getpid()}-{i}"
                ws.send(json.dumps({"type": "ROSH_COMMAND", "command": line, "request_id": request_id}))
                answer, said = _await_answer(ws, request_id)
                results.append(_brief_answer(line, answer, said))
                if stop_on_refusal and not results[-1]["ok"]:
                    break
    except Exception as e:  # noqa: BLE001
        code = getattr(getattr(e, "rcvd", None), "code", None)
        if code == 4403:
            # The room closes the socket on a change from someone who may only look.
            results.append({"line": lines[len(results)], "ok": False, "reason": "look_only",
                            "message": "You may only look in this room (its rules keep changes to its "
                                       "owner, or your key lacks the 'world' scope), so nothing changed."})
        elif not results:
            return _error(e)
        else:
            results.append({"error": True, "detail": f"{type(e).__name__}: {e}"})
    done = sum(1 for r in results if r.get("ok"))
    summary = {"room": f"{info.get('owner')}/{info.get('slug')}", "sent": len(results),
               "confirmed": done, "refused": len(results) - done,
               "not_sent": len(lines) - len(results), "results": results}
    return json.dumps(summary, indent=2)


@mcp.tool()
def rosh_room_look(room: str, names: str = "") -> str:
    """Read a live room as text: its things and their properties, what you may do there,
    and layout notes (overlaps, things hidden from where visitors stand, things underground).

    Works for any public room; private rooms need a key that can open them. A big room
    lists its first 150 things; ask for others by name.

    Args:
        room: "owner/slug" or the room's link, e.g. "rosh/museum"
        names: optional: only these things, comma-separated; a name ending in * matches
               every name starting with it (e.g. "stone_*, sign")
    """
    try:
        with _room_socket(room) as (_, info, connected):
            pass
    except Exception as e:  # noqa: BLE001
        return _error(e)
    state = connected.get("state") or {}
    may = connected.get("may") or {}
    out = {
        "room": f"{info.get('owner')}/{info.get('slug')}",
        "name": info.get("name"),
        "url": f"{API_BASE}/world/{info.get('owner')}/{info.get('slug')}",
        "you_may": sorted(k for k, v in may.items() if v),
        "things": _brief_things(state.get("objects") or {}),
    }
    everything = out["things"]
    wanted = [n.strip() for n in names.split(",") if n.strip()]
    if wanted:
        def chosen(name: str) -> bool:
            return any(name == w or (w.endswith("*") and name.startswith(w[:-1])) for w in wanted)
        out["things"] = {n: p for n, p in everything.items() if chosen(n)}
    elif len(everything) > LOOK_MAX_THINGS:
        out["things"] = dict(list(everything.items())[:LOOK_MAX_THINGS])
        out["more"] = (f"{len(everything) - LOOK_MAX_THINGS} more things not listed "
                       f"({len(everything)} in all); ask for them with names=...")
    out["count"] = len(everything)
    meta = state.get("meta") or {}
    if meta:
        out["room_settings"] = meta
    if connected.get("seed_problems"):
        out["code_problems"] = connected["seed_problems"]
    look = _room_look_lines(info.get("owner"), info.get("slug"))
    if look:
        out["room_look"] = look
    notes = _layout_notes(everything, look.get("camera"), look.get("ground"))
    if len(notes) > 40:
        notes = notes[:40] + [f"... and {len(notes) - 40} more notes."]
    if notes:
        out["layout_notes"] = notes
    return json.dumps(out, indent=2)


DEFAULT_CAMERA = "0 1.7 12 -> 0 1.4 0"


def _num(value, default: float = 0.0) -> float:
    try:
        return float(str(value).split()[0])
    except (TypeError, ValueError, IndexError):
        return default


_COLOUR_HEX: dict = {}


def _colour_hex(word) -> Optional[tuple[int, int, int]]:
    """A colour word or code as (r, g, b), from the room server's own colour table."""
    import re
    text = str(word or "").strip().strip('"').lower()
    m = re.fullmatch(r"#?([0-9a-f]{6}|[0-9a-f]{3})", text)
    if m:
        h = m.group(1) if len(m.group(1)) == 6 else "".join(c * 2 for c in m.group(1))
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    if not _COLOUR_HEX:
        try:
            with httpx.Client(timeout=10, headers={"User-Agent": "RoshMCP/0.3"}) as client:
                js = client.get(f"{API_BASE}/static/js/rosh-colors.js").text
            table = js[js.index("const COLOR_MAP = {"):js.index("};", js.index("const COLOR_MAP = {"))]
            _COLOUR_HEX.update({n: h for n, h in re.findall(r"^\s+([a-z]+):\s*0x([0-9a-f]{6})", table, re.M)})
        except Exception:  # noqa: BLE001 - no table, no colour notes
            _COLOUR_HEX["_none"] = ""
    h = _COLOUR_HEX.get(text)
    if h:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    # The browser's shades (rosh-colors.js SHADE_QUALIFIERS): "palebrown", "darkred".
    for word, toward, t in (("dark", 0, 0.45), ("deep", 0, 0.45), ("light", 255, 0.45), ("pale", 255, 0.65),
                            ("bright", 0, 0.0), ("vivid", 0, 0.0)):
        if text.startswith(word) and _COLOUR_HEX.get(text[len(word):]):
            base = _COLOUR_HEX[text[len(word):]]
            return tuple(round(int(base[i:i + 2], 16) + (toward - int(base[i:i + 2], 16)) * t) for i in (0, 2, 4))
    return None


def _layout_notes(things: dict, camera: Optional[str], ground: Optional[str] = None) -> list[str]:
    """What a visitor would notice, worked out from positions and sizes (no rendering):
    things that overlap, things one behind another from where visitors stand (their
    signs pile up), and things outside the first view."""
    import math

    placed = {}
    tall: dict = {}
    span: dict = {}   # (bottom, top) in metres
    for name, p in things.items():
        if str(p.get("visible", "true")).lower() in ("false", "no", "off", "0"):
            continue
        size = max(_num(p.get("size"), 1.0), 0.1)
        if p.get("door_to") or str(p.get("shape", "")).strip('"').lower() == "door":
            # Drawn as a door with its frame: about 1.1 wide and 2.1 high at size 1
            # (measured in the browser, 16 Nov). The castle run's door hid its gatehouse.
            across, tall[name] = 1.1 * size, 2.1 * size
        else:
            # Across the ground: the wider of width and depth; up: height (each falls back to size).
            across = max(_num(p.get("width"), size), _num(p.get("depth"), size), 0.1)
            tall[name] = max(_num(p.get("height"), size), 0.1)
        # With no y a thing stands on the ground; a y is its middle.
        bottom = _num(p.get("y")) - tall[name] / 2 if p.get("y") is not None else 0.0
        span[name] = (bottom, bottom + tall[name])
        placed[name] = (_num(p.get("x")), _num(p.get("z")), across, bool(p.get("label")))

    def stacked(a: str, b: str) -> bool:
        """One stands on (or floats above) the other: no overlap, and neither hides the other
        (an object on its plinth; agent run A01-1 found these reported as clashes, 16 Nov)."""
        (a0, a1), (b0, b1) = span[a], span[b]
        return a0 >= b1 - 0.05 or b0 >= a1 - 0.05
    notes: list[str] = []
    for name, p in sorted(things.items()):
        if p.get("y") is None or name not in placed:
            continue
        y, height = _num(p.get("y")), tall[name]
        if y < height / 2 - 0.01:
            notes.append(f"{name} is partly underground: y = {y:g} is the height of its middle and it is "
                         f"{height:g} tall. Remove y to stand it on the ground (forget {name}.y), "
                         f"or set y to at least {height / 2:g}.")
    # Flat and close to the ground's colour: a path or a rug visitors won't see
    # (the garden run's cream path on pale grass, 16 Nov).
    ground_rgb = _colour_hex(ground) if ground else None
    if ground_rgb:
        for name, p in sorted(things.items()):
            if name not in tall or tall[name] > 0.15 or not p.get("color"):
                continue
            rgb = _colour_hex(p.get("color"))
            def light(c):
                return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255
            # Close in colour, or close in brightness: seen at a low angle, a flat thing
            # as bright as the ground disappears even in another hue.
            apart = sum((x - y) ** 2 for x, y in zip(rgb, ground_rgb)) ** 0.5 if rgb else 999
            if rgb and (apart < 90 or (apart < 140 and abs(light(rgb) - light(ground_rgb)) < 0.12)):
                high = _num(p.get("height"), _num(p.get("size"), 1.0))
                notes.append(f"{name} is flat ({high:g} m high) and close to the ground's colour "
                             f"({p.get('color')} on {ground}): visitors may not see it. Use a colour that "
                             "stands out from the ground, or raise it a little.")
    names = sorted(placed)
    for i, a in enumerate(names):
        ax, az, asz, _ = placed[a]
        for b in names[i + 1:]:
            bx, bz, bsz, _ = placed[b]
            if not stacked(a, b) and math.hypot(ax - bx, az - bz) < (asz + bsz) / 2 * 0.9:
                notes.append(f"{a} and {b} overlap (centres {math.hypot(ax - bx, az - bz):.1f} m apart, "
                             f"sizes {asz:g} and {bsz:g}).")
    cam = camera or DEFAULT_CAMERA
    try:
        eye, target = [[float(v) for v in part.split()] for part in cam.split("->")]
        ex, ez, tx, tz = eye[0], eye[2], target[0], target[2]
    except (ValueError, IndexError):
        return notes
    facing = math.atan2(tx - ex, -(tz - ez))
    seen = []
    for name, (x, z, size, labelled) in placed.items():
        dist = math.hypot(x - ex, z - ez)
        if dist < 0.5:
            continue
        bearing = math.atan2(x - ex, -(z - ez)) - facing
        bearing = math.degrees((bearing + math.pi) % (2 * math.pi) - math.pi)
        if abs(bearing) > 35:
            notes.append(f"{name} is outside the first view (about {abs(bearing):.0f} degrees to the "
                         f"{'right' if bearing > 0 else 'left'} of where visitors look).")
        else:
            seen.append((name, bearing, dist, size, labelled))
    for i, (a, ab, ad, asz, al) in enumerate(seen):
        for b, bb, bd, bsz, bl in seen[i + 1:]:
            if stacked(a, b):
                continue
            near, far = (a, b) if ad < bd else (b, a)
            gap = abs(ab - bb)
            # Apparent half-widths in degrees, plus room for a sign.
            reach = math.degrees(math.atan2(asz / 2, ad)) + math.degrees(math.atan2(bsz / 2, bd))
            if gap < max(reach, 4.0 if (al and bl) else 0):
                notes.append(f"From where visitors stand, {near} is in front of {far}"
                             + (" and their signs overlap" if (al and bl) else "")
                             + f" (only {gap:.0f} degrees apart). Move one sideways (x).")
    if notes and not camera:
        notes.append(f"(No `# camera:` line, so the default view {DEFAULT_CAMERA} was assumed.)")
    return notes


def _room_look_lines(owner: str, slug: str) -> dict:
    """The room's own header lines (`# sky:`, `# ground:`, `# camera:`, `# fog:`,
    `# visual:`), read from the starting code its page carries (`const spaceCode`)."""
    import re

    try:
        with httpx.Client(timeout=20, headers={"User-Agent": "RoshMCP/0.3"}) as client:
            page = client.get(f"{API_BASE}/world/{owner}/{slug}").text
        m = re.search(r'const spaceCode = ("(?:[^"\\]|\\.)*")', page)
        code = json.loads(m.group(1)) if m else ""
    except Exception:  # noqa: BLE001
        return {}
    found: dict = {}
    for line in code.splitlines():
        h = re.match(r"\s*#\s*(sky|ground|camera|fog|visual):\s*(.+?)\s*$", line)
        if h:
            found.setdefault(h.group(1), h.group(2))
    return found


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
