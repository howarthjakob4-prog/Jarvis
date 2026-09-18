"""3D design tests. Everything is local: no network, no GUI, no printer."""
import struct

import pytest

from jarvis import threed
from jarvis.plugins import design_plugin as design_mod
from jarvis.threed import Mesh


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setattr(design_mod, "OUTPUT_DIR", tmp_path / "designs")
    design_mod._last_saved.clear()
    yield
    design_mod._last_saved.clear()


def _read_stl(path):
    with open(path, "rb") as f:
        header = f.read(80)
        (count,) = struct.unpack("<I", f.read(4))
        body = f.read()
    return header, count, body


# ----- exporters ---------------------------------------------------------------

def test_stl_has_valid_header_and_facet_count(tmp_path):
    m = threed.box(10, 20, 30)
    p = tmp_path / "box.stl"
    m.export_stl(p)
    header, count, body = _read_stl(p)
    assert len(header) == 80
    assert count == m.facet_count() == 12
    assert len(body) == count * 50  # 12 floats + uint16 per facet


def test_obj_has_valid_vertices_and_faces(tmp_path):
    m = threed.box(10, 20, 30)
    p = tmp_path / "box.obj"
    m.export_obj(p)
    verts, faces = [], []
    for line in p.read_text().splitlines():
        if line.startswith("v "):
            parts = line.split()
            assert len(parts) == 4
            verts.append([float(x) for x in parts[1:]])
        elif line.startswith("f "):
            idx = [int(x) for x in line.split()[1:]]
            assert len(idx) == 3
            faces.append(idx)
    assert len(verts) == 8
    assert len(faces) == 12
    for a, b, c in faces:
        assert 1 <= a <= len(verts) and 1 <= b <= len(verts) \
            and 1 <= c <= len(verts)


def test_stl_normals_are_unit_or_zero(tmp_path):
    m = threed.sphere(10, segments=12, rings=8)
    p = tmp_path / "s.stl"
    m.export_stl(p)
    with open(p, "rb") as f:
        f.read(84)
        for _ in range(m.facet_count()):
            vals = struct.unpack("<12f", f.read(48))
            f.read(2)
            nx, ny, nz = vals[0], vals[1], vals[2]
            ln = (nx * nx + ny * ny + nz * nz) ** 0.5
            assert abs(ln - 1.0) < 1e-4 or ln == 0.0


# ----- catalog: every design is a closed, non-empty solid -------------------------

def _catalog_meshes():
    return {
        "phone_stand": threed.phone_stand(),
        "desk_tray": threed.desk_tray(),
        "vase": threed.vase(),
        "gear": threed.gear(),
        "gear_20t": threed.gear(teeth=20, diameter=80.0),
        "keychain": threed.keychain(),
        "custom_box": threed.custom_box(100, 50, 20),
    }


@pytest.mark.parametrize("name", list(_catalog_meshes()))
def test_catalog_design_is_closed_solid(name):
    mesh = _catalog_meshes()[name]
    assert isinstance(mesh, Mesh)
    assert not mesh.is_empty(), name
    assert mesh.is_closed(), f"{name} is not watertight"


def test_custom_box_dimensions_in_mm():
    m = threed.custom_box(100, 50, 20)
    dx, dy, dz = m.bounds()
    assert (dx, dy, dz) == pytest.approx((100, 50, 20))


def test_transforms_keep_mesh_closed():
    m = threed.box(10, 10, 10).rotate_x(20).translate(0, -32, 55)
    assert m.is_closed()


# ----- intent parsing --------------------------------------------------------------

@pytest.mark.parametrize("phrase,expected", [
    ("design a 3d model of a phone stand", "phone_stand"),
    ("make me a 3d vase", "vase"),
    ("3d print a gear", "gear"),
    ("design a box 10 by 5 by 2 cm", "custom_box"),
    ("create a keychain", "keychain"),
    ("build a desk organizer", "desk_tray"),
])
def test_find_design_matches_example_phrases(phrase, expected):
    key, entry = threed.find_design(phrase)
    assert key == expected
    assert entry["title"]


@pytest.mark.parametrize("phrase", [
    "design a 3d model of a phone stand",
    "make me a 3d vase",
    "3d print a gear",
    "design a box 10 by 5 by 2 cm",
    "what 3d designs can you make",
    "show the design",
])
def test_plugin_matches_example_phrases(phrase):
    assert design_mod.plugin.match(phrase), phrase


def test_plugin_ignores_unrelated_make():
    assert not design_mod.plugin.match("make me a sandwich")
    assert not design_mod.plugin.match("open notepad")


# ----- end to end: design, save, open ----------------------------------------------

def test_design_writes_stl_and_obj():
    reply = design_mod.plugin.run("design a 3d model of a phone stand")
    assert "Designed" in reply and "Phone Stand" in reply
    stl, obj = design_mod._last_saved
    assert stl.suffix == ".stl" and obj.suffix == ".obj"
    assert stl.exists() and obj.exists()
    _, count, _ = _read_stl(stl)
    assert count > 0


def test_box_parses_cm_dimensions():
    reply = design_mod.plugin.run("design a box 10 by 5 by 2 centimeters")
    assert "Designed" in reply
    stl = design_mod._last_saved[0]
    assert stl.exists()


def test_box_asks_for_dimensions_when_missing():
    reply = design_mod.plugin.run("design a box")
    assert "What size box" in reply
    assert design_mod._last_saved == []


def test_gear_parses_teeth():
    reply = design_mod.plugin.run("3d print a gear with 20 teeth")
    assert "20 teeth" in reply


def test_unknown_design_suggests_catalog_and_writes_nothing():
    reply = design_mod.plugin.run("design a 3d model of a dragon")
    assert "don't have a design" in reply
    assert "Phone Stand" in reply  # catalog listed
    assert design_mod._last_saved == []
    assert not design_mod.OUTPUT_DIR.exists()  # _save never ran


def test_unknown_design_offers_close_match():
    reply = design_mod.plugin.run("design a 3d vaze")
    assert "did you mean" in reply and "vase" in reply


def test_list_designs():
    reply = design_mod.plugin.run("what 3d designs can you make")
    assert "Phone Stand" in reply and "Vase" in reply and "Gear" in reply


def test_open_design_with_nothing_saved():
    reply = design_mod.plugin.run("show the design")
    assert "No design yet" in reply


def test_open_design_without_os_startfile(monkeypatch):
    design_mod.plugin.run("make me a 3d vase")
    # Simulate non-Windows: os.startfile does not exist there anyway;
    # just verify the reply names the file or opens it.
    reply = design_mod.plugin.run("show the design")
    assert "vase_" in reply
