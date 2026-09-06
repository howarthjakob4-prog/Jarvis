"""Local, bounded mesh generation for the Nova Frontier concept workspace."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from jarvis.brain.design_profiles import validate_profile, prism_mesh
from jarvis.brain.design_outlines import validate_outline, outline_mesh


def _vector(value, default, positive=False):
    value = default if value is None else value
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Position and size must contain three numbers")
    result = [float(v) for v in value]
    if any(not math.isfinite(v) or abs(v) > 1000 or (positive and v <= 0) for v in result):
        raise ValueError("Coordinates must be finite and within 1000; sizes must be positive")
    return result


def validate_scene(scene):
    if not isinstance(scene, dict):
        raise ValueError("A design must be an object")
    objects = scene.get("objects")
    if not isinstance(objects, list) or not 1 <= len(objects) <= 200:
        raise ValueError("A design needs 1–200 objects")
    clean = {"version": 1, "project": str(scene.get("project", "Nova Frontier"))[:100],
             "title": str(scene.get("title", "Untitled concept"))[:120], "objects": []}
    if scene.get("units") == "concept":
        clean["units"] = "concept"
    if scene.get("reference_asset") == "achilles":
        clean["reference_asset"] = "achilles"
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict) or obj.get("kind") not in ("box", "cylinder", "pyramid", "prism", "outline"):
            raise ValueError("Supported shapes: box, cylinder, pyramid, prism, outline")
        color = obj.get("color", "#67cbd4")
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Colors must be six-digit hex values")
        item = {"name": str(obj.get("name", f"Part {index + 1}"))[:80], "kind": obj["kind"],
                "position": _vector(obj.get("position"), [0,0,0]), "size": _vector(obj.get("size"), [1,1,1], True),
                "color": color}
        if obj["kind"] == "prism":
            item["profile"] = validate_profile(obj.get("profile"))
            item["rotation_y"] = float(obj.get("rotation_y", 0))
        elif obj["kind"] == "outline":
            item["outline"] = validate_outline(obj.get("outline"))
            item["rotation_y"] = float(obj.get("rotation_y", 0))
        clean["objects"].append(item)
    return clean


def mesh(obj):
    kind = obj["kind"]
    if kind == "prism":
        vertices, faces = prism_mesh(obj["profile"])
    elif kind == "outline":
        vertices, faces = outline_mesh(obj["outline"])
    elif kind == "box":
        vertices=[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]
        faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,4,7,3)]
    elif kind == "pyramid":
        vertices=[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5),(-.5,-.5,.5),(0,.5,0)]
        faces=[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]
    else:
        segments=16; vertices=[]
        for y in (-.5,.5):
            vertices.extend((math.cos(i*math.tau/segments)*.5,y,math.sin(i*math.tau/segments)*.5) for i in range(segments))
        faces=[tuple(range(segments-1,-1,-1)),tuple(range(segments,segments*2))]
        for i in range(segments):
            j=(i+1)%segments; faces.append((i,j,segments+j,segments+i))
    angle=math.radians(float(obj.get("rotation_y",0))); ca,sa=math.cos(angle),math.sin(angle)
    result=[]
    for v in vertices:
        scaled=[v[i]*obj["size"][i] for i in range(3)]
        x,z=scaled[0]*ca-scaled[2]*sa,scaled[0]*sa+scaled[2]*ca
        result.append((x+obj["position"][0],scaled[1]+obj["position"][1],z+obj["position"][2]))
    return result,faces


def preset(name="outpost"):
    if name == "achilles":
        from jarvis.brain.achilles_design import build_achilles_scene
        return validate_scene(build_achilles_scene())
    objects=[]
    def part(label,kind,position,size,color="#67cbd4"):
        objects.append(dict(name=label,kind=kind,position=position,size=size,color=color))
    if name=="outpost":
        part("Landing foundation","cylinder",[0,-.3,0],[12,.6,12],"#273c51"); part("Command hub","cylinder",[0,1.1,0],[4,2.2,4])
        part("Observation roof","pyramid",[0,2.9,0],[4.6,1.4,4.6],"#c8e8f0")
        for x in (-4,4):
            part("Habitat","box",[x,.7,0],[2.5,1.4,3],"#a0b2c7"); part("Connector","box",[x/2,.45,0],[2,.7,1])
        part("Communications mast","cylinder",[0,4,0],[.15,2,.15],"#f6b65b")
    elif name=="spaceship":
        part("Hull","box",[0,0,0],[2,1,7],"#a0b2c7"); part("Cockpit","box",[0,.65,-1.5],[1.5,.6,2])
        for x in (-2,2):
            part("Wing","box",[x,-.2,.6],[2.5,.18,3],"#526985"); part("Engine","box",[x,0,2],[.9,.9,2.6],"#f6b65b")
    elif name=="terrain":
        part("Terrain base","box",[0,-.5,0],[14,1,12],"#394e50")
        for i,(x,z,h) in enumerate([(-4,1,4),(0,3,5),(4,2,3),(-2,-3,2.5),(4,-3,2)]): part(f"Ridge {i+1}","pyramid",[x,h/2,z],[5,h,4],"#849589")
    else: raise ValueError("Choose outpost, spaceship, terrain, or achilles")
    return validate_scene({"title":f"Nova Frontier - {name.title()}","objects":objects})


def obj_text(scene):
    scene=validate_scene(scene); lines=["# Nova Frontier concept mesh - Y up"]; offset=1
    for i,obj in enumerate(scene["objects"]):
        vertices,faces=mesh(obj); lines.append(f"o part_{i+1}")
        lines.extend("v "+" ".join(f"{v:.8g}" for v in vertex) for vertex in vertices)
        lines.extend("f "+" ".join(str(v+offset) for v in face) for face in faces); offset+=len(vertices)
    return "\n".join(lines)+"\n"


def save_scene(scene,path): Path(path).write_text(json.dumps(validate_scene(scene),indent=2),encoding="utf-8")
def save_obj(scene,path): Path(path).write_text(obj_text(scene),encoding="utf-8")
