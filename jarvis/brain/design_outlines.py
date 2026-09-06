"""Concave outline validation and ear-clipped solid extrusion."""
from functools import lru_cache
import math


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def validate_outline(value):
    if not isinstance(value,(list,tuple)) or not 3 <= len(value) <= 128:
        raise ValueError("An outline needs 3–128 XZ points")
    points = []
    for p in value:
        if not isinstance(p,(list,tuple)) or len(p) != 2:
            raise ValueError("Outline points need X and Z")
        p = [float(v) for v in p]
        if any(not math.isfinite(v) or abs(v) > 1 for v in p):
            raise ValueError("Outline coordinates must be finite and within [-1,1]")
        points.append(p)
    if len({tuple(p) for p in points}) != len(points):
        raise ValueError("Outline points must be distinct")
    n = len(points)
    def between(a,b,p):
        return min(a[0],b[0])-1e-10 <= p[0] <= max(a[0],b[0])+1e-10 and min(a[1],b[1])-1e-10 <= p[1] <= max(a[1],b[1])+1e-10
    for i,a in enumerate(points):
        b = points[(i+1)%n]
        for j in range(i+1,n):
            if j == (i+1)%n or (j+1)%n == i:
                continue
            c,d = points[j],points[(j+1)%n]
            ac,ad,ca,cb = cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
            touches = ((abs(ac)<1e-10 and between(a,b,c)) or
                       (abs(ad)<1e-10 and between(a,b,d)) or
                       (abs(ca)<1e-10 and between(c,d,a)) or
                       (abs(cb)<1e-10 and between(c,d,b)))
            if (ac*ad < 0 and ca*cb < 0) or touches:
                raise ValueError("Outline cannot cross or touch itself")
    area = sum(points[i][0]*points[(i+1)%n][1]-points[(i+1)%n][0]*points[i][1] for i in range(n))
    if abs(area)<1e-10:
        raise ValueError("Outline must enclose an area")
    return points if area>0 else list(reversed(points))


@lru_cache(maxsize=512)
def _cached_mesh(raw):
    points = validate_outline(raw)
    changed = True
    while changed and len(points)>3:
        changed = False
        for i in range(len(points)):
            if abs(cross(points[i-1],points[i],points[(i+1)%len(points)])) < 1e-10:
                points.pop(i)
                changed = True
                break
    remaining = list(range(len(points)))
    triangles = []
    while len(remaining)>3:
        for offset,b in enumerate(remaining):
            a,c = remaining[offset-1],remaining[(offset+1)%len(remaining)]
            if cross(points[a],points[b],points[c]) <= 1e-10:
                continue
            occupied = any(min(cross(points[a],points[b],points[p]),
                               cross(points[b],points[c],points[p]),
                               cross(points[c],points[a],points[p])) >= -1e-10
                           for p in remaining if p not in (a,b,c))
            if occupied:
                continue
            triangles.append((a,b,c))
            remaining.pop(offset)
            break
        else:
            raise ValueError("Could not triangulate outline")
    triangles.append(tuple(remaining))
    n = len(points)
    vertices = tuple((x,y,z) for y in (-.5,.5) for x,z in points)
    faces = triangles + [tuple(i+n for i in reversed(t)) for t in triangles]
    faces += [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
    return vertices,tuple(faces)


def outline_mesh(profile):
    return _cached_mesh(tuple(tuple(p) for p in profile))
