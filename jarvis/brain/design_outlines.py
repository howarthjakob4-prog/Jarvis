"""Helpers for validating and extruding editable 2D outlines into concept meshes."""
from __future__ import annotations

import math


def validate_outline(outline):
    if not isinstance(outline, (list, tuple)) or not 3 <= len(outline) <= 64:
        raise ValueError("An outline needs 3-64 points")
    clean = []
    for point in outline:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Outline points must contain X and Z")
        x, z = float(point[0]), float(point[1])
        if not math.isfinite(x) or not math.isfinite(z) or abs(x) > 1 or abs(z) > 1:
            raise ValueError("Outline points must be finite and normalized to [-1, 1]")
        clean.append([x, z])
    area = sum(clean[i][0] * clean[(i + 1) % len(clean)][1] - clean[(i + 1) % len(clean)][0] * clean[i][1] for i in range(len(clean))) / 2
    if abs(area) < 1e-6:
        raise ValueError("Outline must have area")
    if area < 0:
        clean.reverse()
    return clean


def outline_mesh(outline, position, size, rotation_y=0.0):
    outline = validate_outline(outline)
    angle = math.radians(float(rotation_y))
    ca, sa = math.cos(angle), math.sin(angle)
    vertices = []
    for y in (-0.5, 0.5):
        for x, z in outline:
            px, pz = x * size[0] * 0.5, z * size[2] * 0.5
            rx, rz = px * ca - pz * sa, px * sa + pz * ca
            vertices.append((rx + position[0], y * size[1] + position[1], rz + position[2]))
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return vertices, faces
