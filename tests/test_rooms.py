"""Room tools: unit checks, and live checks against a running Rosh server.

Live tests need a server and a key with read,write,world scopes:
    ROSH_TEST_BASE=http://127.0.0.1:5001 ROSH_TEST_KEY_FILE=~/.config/rosh-mcp-test/local_key pytest
They create rooms named mcp-test-<random>. Never point them at rosh.cloud with a
real account's key.
"""
import importlib
import json
import os
import re
import uuid

import pytest

BASE = os.environ.get("ROSH_TEST_BASE", "")
KEY_FILE = os.path.expanduser(os.environ.get("ROSH_TEST_KEY_FILE", ""))
KEY = open(KEY_FILE).read().strip() if KEY_FILE and os.path.exists(KEY_FILE) else ""
live = pytest.mark.skipif(not (BASE and KEY), reason="needs ROSH_TEST_BASE and ROSH_TEST_KEY_FILE")


def load(key: str = KEY, base: str = BASE):
    os.environ["ROSH_API_BASE"] = base or "https://rosh.cloud"
    os.environ["ROSH_API_KEY"] = key
    import rosh_mcp.server as server
    return importlib.reload(server)


# ── Unit ──

@pytest.mark.parametrize("given, owner, slug", [
    ("rosh/blocks", "rosh", "blocks"),
    ("@rosh/blocks", "rosh", "blocks"),
    ("https://rosh.cloud/world/rosh/museum", "rosh", "museum"),
    ("https://rosh.cloud/world/rosh/museum/", "rosh", "museum"),
    ("http://127.0.0.1:5001/world/a_b/c-d", "a_b", "c-d"),
    ("world/rosh/blocks", "rosh", "blocks"),
])
def test_room_ref_reads_every_form(given, owner, slug):
    assert load()._room_ref(given) == (owner, slug)


@pytest.mark.parametrize("bad", ["blocks", "a/b/c", "", "https://rosh.cloud/"])
def test_room_ref_refuses_what_it_cannot_read(bad):
    with pytest.raises(ValueError):
        load()._room_ref(bad)


def test_brief_answer_says_when_a_confirmed_line_changed_nothing():
    s = load()
    out = s._brief_answer("set a.colr to red", {"type": "CONFIRMED_ROSH", "command": "set a.colr to red",
                                                "state_delta": {"created": {}, "updated": {}, "deleted": []}}, [])
    assert out["ok"] and "nothing" in out["note"].lower()


def test_brief_answer_shows_what_the_room_read_the_line_as():
    s = load()
    out = s._brief_answer("make a stone", {"type": "CONFIRMED_ROSH", "command": "create object stone",
                                           "state_delta": {"created": {"stone": {}}}}, [])
    assert out["ran"] == "create object stone" and out["created"] == ["stone"]


def test_brief_answer_refusal_and_silence():
    s = load()
    out = s._brief_answer("x", {"type": "REJECTED", "reason": "rosh_error", "message": "bad"}, [])
    assert out == {"line": "x", "ok": False, "reason": "rosh_error", "message": "bad"}
    assert s._brief_answer("x", None, [])["reason"] == "no_answer"


def test_guide_needs_no_key_and_has_no_properties_rooms_ignore():
    s = load(key="")
    guide = s.rosh_room_guide()
    for prop in re.findall(r"set \w+\.(\w+) to", guide):
        assert prop in KNOWN or prop.startswith("guide_") or prop in {"title", "intro", "year", "source", "rules"} or prop.startswith("rule"), prop


# What the server says a room reads (rosh-portal main.py _KNOWN_ROOM_PROPERTIES, 15 Nov 2026).
KNOWN = {
    "x", "y", "z", "visible", "color", "colour", "material", "scale", "size", "text", "font_size",
    "spin", "pulse", "bounce", "opacity", "patrol", "orbit", "cycle", "label", "label_lift", "label_size",
    "press", "on_click", "door_to", "does", "rule", "wireframe", "shape", "image", "description", "credit",
    "year", "period", "category", "curated", "spacing", "setting", "sky", "ground", "strict",
    "lived", "source", "dates", "dates_note",
}


# ── Live ──

_SHARED: dict = {}


@pytest.fixture
def room():
    """One room for the read-mostly tests (room creation is limited to 20 an hour per key)."""
    s = load()
    if "ref" in _SHARED:
        return s, _SHARED["ref"], _SHARED["slug"]
    s = load()
    slug = f"mcp-test-{uuid.uuid4().hex[:8]}"
    made = json.loads(s.rosh_create_room(slug, "# sky: #223344\n# ground: #556677\nset room.title to \"Test\"\n"
                                         "create object plinth\nset plinth.color to grey\n", name="MCP test"))
    assert made.get("success"), made
    _SHARED.update(ref=made["room"], slug=slug)
    return s, made["room"], slug


@live
def test_create_room_then_look_shows_its_starting_things(room):
    s, ref, slug = room
    look = json.loads(s.rosh_room_look(ref))
    assert look["room"] == ref
    assert look["things"]["plinth"]["color"] == "grey"
    assert "build" in look["you_may"]
    assert look["room_look"]["sky"] == "#223344" and look["room_look"]["ground"] == "#556677"
    assert look["room_settings"]["title"] == "Test"


@live
def test_created_room_is_listed(room):
    s, ref, slug = room
    assert slug in [w["slug"] for w in json.loads(s.rosh_list_rooms())["worlds"]]


@live
def test_every_guide_example_is_confirmed_and_lands(room):
    """The guide may only teach lines a real room confirms, and each must show in look."""
    s, ref, slug = room
    lines = []
    for raw in s.ROOM_GUIDE.splitlines():
        line = raw.split("  #")[0].strip()
        if re.match(r"^(create object|set|destroy) ", line) and "<" not in line and not line.startswith("set room."):
            lines.append(line)
    assert len(lines) >= 15
    destroys = [ln for ln in lines if ln.startswith("destroy")]
    body = [ln for ln in lines if not ln.startswith("destroy")]
    out = json.loads(s.rosh_room_do(ref, "\n".join(body), stop_on_refusal=False))
    refused = [r for r in out["results"] if not r["ok"]]
    assert not refused, refused
    things = json.loads(s.rosh_room_look(ref))["things"]
    for line in body:
        m = re.match(r'^set (\w+)\.(\w+) to (.+)$', line)
        if not m:
            continue
        name, prop, value = m.groups()
        got = things[name].get(prop)
        assert got is not None, (line, things[name])
        assert str(got).strip('"').lower() == value.strip('"').lower() or str(got) == value, (line, got)
    gone = json.loads(s.rosh_room_do(ref, "\n".join(destroys)))
    assert gone["confirmed"] == len(destroys)
    assert "stone_1" not in json.loads(s.rosh_room_look(ref))["things"]


@live
def test_a_door_line_with_a_real_room_is_confirmed(room):
    s, ref, slug = room
    out = json.loads(s.rosh_room_do(ref, 'create object door_9\nset door_9.door_to to "/world/rosh/blocks"\n'
                                         'set door_9.label to "To Blocks"'))
    assert out["confirmed"] == 3, out


@live
def test_a_bad_line_is_refused_with_a_reason_and_stops_the_rest(room):
    s, ref, slug = room
    out = json.loads(s.rosh_room_do(ref, "create object lamp_a\nflibble the wotsit\ncreate object lamp_b"))
    assert out["confirmed"] == 1 and out["refused"] == 1 and out["not_sent"] == 1
    bad = out["results"][1]
    assert bad["reason"] and bad["message"]
    assert "lamp_b" not in json.loads(s.rosh_room_look(ref))["things"]


@live
def test_keep_going_past_a_refusal_when_asked(room):
    s, ref, slug = room
    out = json.loads(s.rosh_room_do(ref, "create object lamp_c\nflibble the wotsit\ncreate object lamp_d",
                                    stop_on_refusal=False))
    assert out["confirmed"] == 2 and out["refused"] == 1


@live
def test_look_reports_a_change_made_by_do(room):
    s, ref, slug = room
    s.rosh_room_do(ref, "set plinth.x to 4\nset plinth.size to 2.5")
    plinth = json.loads(s.rosh_room_look(ref))["things"]["plinth"]
    assert float(plinth["x"]) == 4 and float(plinth["size"]) == 2.5


@live
def test_room_link_form_works(room):
    s, ref, slug = room
    owner = ref.split("/")[0]
    look = json.loads(s.rosh_room_look(f"{BASE}/world/{owner}/{slug}"))
    assert look["room"] == ref


@live
def test_unknown_room_is_a_clear_error():
    s = load()
    out = json.loads(s.rosh_room_look("nobody-here-xyz/nothing"))
    assert out["error"] and out["status"] == 404


GUEST_TABLE = {  # line: (shared, museum), as the guide says (probed 15 Nov 2026)
    "create object visitor_lamp": (True, False),
    "set plinth.color to pink": (True, True),
    "set plinth.x to 3": (True, True),
    'set plinth.label to "Hi"': (True, False),
    "destroy plinth": (False, False),
    "set owner_lamp.color to red": (False, False),
    "destroy owner_lamp": (False, False),
}


@live
@pytest.mark.parametrize("museum", [False, True], ids=["shared", "museum"])
def test_what_a_guest_may_do_matches_the_guide(museum):
    s = load()
    code = ("set room.rules to museum\n" if museum else "") + "create object plinth\nset plinth.color to grey\n"
    ref = json.loads(s.rosh_create_room(f"mcp-test-{uuid.uuid4().hex[:8]}", code))["room"]
    assert json.loads(s.rosh_room_do(ref, "create object owner_lamp"))["confirmed"] == 1
    guest = load(key="")
    try:
        for line, allowed in GUEST_TABLE.items():
            out = json.loads(guest.rosh_room_do(ref, line))
            assert out["confirmed"] == int(allowed[museum]), (line, out)
    finally:
        load()


@live
def test_a_look_only_room_refuses_a_guest_plainly():
    s = load()
    ref = json.loads(s.rosh_create_room(f"mcp-test-{uuid.uuid4().hex[:8]}",
                                        "set room.rule.build to 9\ncreate object plinth\n"))["room"]
    guest = load(key="")
    try:
        assert "plinth" in json.loads(guest.rosh_room_look(ref))["things"]
        out = json.loads(guest.rosh_room_do(ref, "set plinth.x to 3"))
        assert out["confirmed"] == 0 and out["results"][0]["reason"] == "look_only", out
    finally:
        load()
    assert json.loads(s.rosh_room_do(ref, "set plinth.x to 3"))["confirmed"] == 1


@live
def test_set_room_code_replaces_the_starting_code(room):
    s, ref, slug = room
    out = json.loads(s.rosh_set_room_code(slug, "create object other\n"))
    assert out.get("success"), out


@live
def test_other_peoples_rooms_cannot_be_changed_by_this_key():
    s = load()
    out = json.loads(s.rosh_room_do("rosh/museum", "create object intruder"))
    assert out["confirmed"] == 0, out


# ── Layout notes (no rendering) ──

def test_layout_notes_find_things_in_line_from_the_camera_and_overlaps():
    s = load()
    things = {
        "sign": {"x": 0, "z": 6, "size": 1, "label": "Welcome"},
        "stone": {"x": 0, "z": 0, "size": 2, "label": "Stone"},
        "far_left": {"x": -40, "z": 0, "size": 1},
        "touching": {"x": 0.5, "z": 0, "size": 1},
        "fine": {"x": 6, "z": 0, "size": 1, "label": "Fine"},
    }
    notes = " | ".join(s._layout_notes(things, "0 1.7 12 -> 0 1.4 0"))
    assert "sign is in front of stone and their signs overlap" in notes
    assert "far_left is outside the first view" in notes
    assert "stone and touching overlap" in notes
    assert "fine" not in notes


def test_layout_notes_assume_the_default_camera_and_say_so():
    s = load()
    notes = s._layout_notes({"a": {"x": 0, "z": 5, "label": "A"}, "b": {"x": 0, "z": 0, "label": "B"}}, None)
    assert any("default view" in n for n in notes)


def test_a_well_spaced_room_has_no_layout_notes():
    s = load()
    things = {f"t{i}": {"x": -6 + 4 * i, "z": 0, "size": 1.5, "label": f"T{i}"} for i in range(4)}
    assert s._layout_notes(things, "0 1.7 12 -> 0 1.4 0") == []


def test_layout_notes_warn_when_y_sinks_a_thing():
    s = load()
    notes = " | ".join(s._layout_notes({"sun": {"x": 0, "z": 0, "y": 0, "size": 10},
                                        "lamp": {"x": 20, "z": 0, "y": 3, "size": 1}}, None))
    assert "sun is partly underground" in notes and "lamp is partly underground" not in notes
