"""Validated convex profile helpers for editable extruded design parts."""
from __future__ import annotations

import math


def validate_profile(profile):
    if not isinstance(profile, (list, tuple)) or not 3 <= len(profile) <= 32:
        raise ValueError("A prism profile needs 3-32 points")
    clean = []
    for point in profile:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Profile points must contain X and Z")
        x, z = float(point[0]), float(point[1])
        if not math.isfinite(x) or not math.isfinite(z) or abs(x) > 1 or abs(z) > 1:
            raise ValueError("Profile points must be finite and normalized to [-1, 1]")
        clean.append([x, z])
    area = sum(clean[i][0] * clean[(i + 1) % len(clean)][1] - clean[(i + 1) % len(clean)][0] * clean[i][1] for i in range(len(clean))) / 2
    if abs(area) < 1e-6:
        raise ValueError("Profile must have area")
    if area < 0:
        clean.reverse()
    sign = None
    for i in range(len(clean)):
        a, b, c = clean[i - 1], clean[i], clean[(i + 1) % len(clean)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) < 1e-8:
            continue
        current = 1 if cross > 0 else -1
        if sign is not None and current != sign:
            raise ValueError("Prism profiles must be convex")
        sign = current
    return clean


def prism_mesh(profile, position, size, rotation_y=0.0):
    profile = validate_profile(profile)
    angle = math.radians(float(rotation_y))
    ca, sa = math.cos(angle), math.sin(angle)
    vertices = []
    for y in (-0.5, 0.5):
        for x, z in profile:
            px, pz = x * size[0] * 0.5, z * size[2] * 0.5
            rx, rz = px * ca - pz * sa, px * sa + pz * ca
            vertices.append((rx + position[0], y * size[1] + position[1], rz + position[2]))
    n = len(profile)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return vertices, faces
