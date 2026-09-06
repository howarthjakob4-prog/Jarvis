import json
import math
import tempfile
import unittest
from pathlib import Path

from jarvis.brain.design_engine import mesh, obj_text, preset, save_scene, validate_scene


class DesignEngineTests(unittest.TestCase):
    def test_presets_export_valid_faces_and_dimensions(self):
        for name in ("outpost", "spaceship", "terrain"):
            scene = preset(name); count = 0
            for obj in scene["objects"]:
                vertices, faces = mesh(obj); count += len(vertices)
                for axis in range(3):
                    self.assertAlmostEqual(max(v[axis] for v in vertices)-min(v[axis] for v in vertices), obj["size"][axis])
                for face in faces:
                    self.assertGreaterEqual(len(face), 3); self.assertTrue(all(0 <= i < len(vertices) for i in face))
            lines = obj_text(scene).splitlines(); self.assertEqual(sum(line.startswith("v ") for line in lines), count)
            for line in lines:
                if line.startswith("f "): self.assertTrue(all(1 <= int(i) <= count for i in line.split()[1:]))

    def test_rejects_bad_or_unbounded_geometry(self):
        for update in ({"size": [0,1,1]}, {"position": [math.nan,0,0]}, {"position": [math.inf,0,0]}, {"position": [1001,0,0]}, {"size": [1,2]}, {"kind": "script"}, {"color": "red"}):
            scene = preset(); scene["objects"][0].update(update)
            with self.assertRaises(ValueError): validate_scene(scene)
        for objects in ([], [{}]*201):
            with self.assertRaises(ValueError): validate_scene({"objects": objects})

    def test_saved_scene_round_trip_preserves_edits(self):
        scene = preset("spaceship"); scene["objects"][0]["position"] = [1,2,3]; scene["objects"][0]["color"] = "#123456"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"concept.json"; save_scene(scene,path); self.assertEqual(validate_scene(json.loads(path.read_text())),scene)

    def test_validation_does_not_alias_input(self):
        scene = preset(); clean = validate_scene(scene); clean["objects"][0]["position"][0] = 99; self.assertNotEqual(clean,scene)

    def test_obj_does_not_inject_object_names_as_commands(self):
        scene = preset(); scene["objects"][0]["name"] = "Part\nf 99999 99999 99999"; self.assertNotIn("99999",obj_text(scene))


if __name__ == "__main__": unittest.main()
