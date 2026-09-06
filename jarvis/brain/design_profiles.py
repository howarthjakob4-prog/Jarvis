"""Validated convex profiles for extruded, editable concept parts."""
import math


def validate_profile(value):
    if not isinstance(value, (list, tuple)) or not 3 <= len(value) <= 32:
        raise ValueError("A prism profile needs 3–32 convex XZ points")
    points = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Each profile point needs X and Z")
        pair = [float(v) for v in point]
        if any(not math.isfinite(v) or abs(v) > 1 for v in pair):
            raise ValueError("Profile coordinates must be finite and between -1 and 1")
        points.append(pair)
    if len({tuple(p) for p in points}) != len(points):
        raise ValueError("Profile points must be distinct")
    signs = []
    for i, a in enumerate(points):
        b = points[(i+1) % len(points)]
        for j, c in enumerate(points):
            if j in (i, (i+1) % len(points)):
                continue
            cross = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if abs(cross) < 1e-10:
                raise ValueError("Profile must be strictly convex")
            signs.append(cross > 0)
    if not all(s == signs[0] for s in signs):
        raise ValueError("Profile must be convex and cannot cross itself")
    return points if signs[0] else list(reversed(points))


def prism_mesh(profile):
    points = validate_profile(profile)
    n = len(points)
    vertices = [(x,y,z) for y in (-.5,.5) for x,z in points]
    faces = [(0,i,i+1) for i in range(1,n-1)]
    faces += [(n,n+i+1,n+i) for i in range(1,n-1)]
    faces += [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
    return vertices, faces
