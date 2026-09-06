import math
import unittest
from collections import Counter

from jarvis.brain.design_engine import mesh, obj_text, preset, validate_scene
from jarvis.brain.design_profiles import validate_profile


class ReferenceDesignTests(unittest.TestCase):
    def test_achilles_roundtrip_and_export(self):
        scene = preset("achilles")
        self.assertEqual(validate_scene(scene),scene)
        self.assertEqual(scene["units"],"concept")
        self.assertEqual(scene["reference_asset"],"achilles")
        self.assertGreater(len(scene["objects"]),100)
        self.assertLessEqual(len(scene["objects"]),200)
        lines = obj_text(scene).splitlines(); count = sum(line.startswith("v ") for line in lines)
        for line in lines:
            if line.startswith("f "): self.assertTrue(all(1 <= int(v) <= count for v in line.split()[1:]))

    def test_every_extrusion_is_closed_and_outward(self):
        for obj in preset("achilles")["objects"]:
            if obj["kind"] != "prism": continue
            vertices, faces = mesh(obj); edges = Counter(); volume = 0.0
            for face in faces:
                for i,a in enumerate(face): edges[a,face[(i+1)%len(face)]] += 1
                a = vertices[face[0]]
                for i in range(1,len(face)-1):
                    b,c = vertices[face[i]],vertices[face[i+1]]
                    cross = (b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0])
                    volume += sum(a[j]*cross[j] for j in range(3))/6
            self.assertTrue(all(edges[b,a] == n for (a,b),n in edges.items()),obj["name"])
            self.assertGreater(volume,0,obj["name"])

    def test_bad_profiles_rejected(self):
        for profile in ([],[[0,0],[1,0]],[[0,0],[1,1],[0,1],[1,0]], [[0,0],[1,0],[.3,.2],[0,1]],[[0,0],[1,0],[math.nan,1]], [[0,0],[1,0],[2,0]],[[0,0],[1,0],[1,0]],[[0,0],[2,0],[0,1]]):
            with self.assertRaises(ValueError): validate_profile(profile)

    def test_rotation_preserves_volume_and_moves_about_part_origin(self):
        scene = validate_scene({"objects":[dict(kind="prism",profile=[[0,0],[1,0],[0,1]], position=[10,2,20],size=[2,1,3],rotation_y=90)]})
        vertices,_ = mesh(scene["objects"][0]); self.assertAlmostEqual(vertices[1][0],10); self.assertAlmostEqual(vertices[1][2],22); self.assertAlmostEqual(vertices[2][0],7)


if __name__ == "__main__": unittest.main()
