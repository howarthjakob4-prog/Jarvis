"""3D mesh toolkit + parametric design catalog (stdlib only).

Units: millimeters everywhere in here. The plugin converts the user's
spoken centimeters/inches to mm before calling the catalog.

A Mesh is just vertices + triangular faces. Every catalog function returns
a closed, printable solid (or several closed solids combined — slicers are
fine with that). Exporters: binary STL and text OBJ.
"""
import math
import struct

MM_PER_CM = 10.0
MM_PER_INCH = 25.4


class Mesh:
    def __init__(self):
        self.vertices = []  # [(x, y, z), ...]
        self.faces = []     # [(a, b, c), ...] CCW from outside

    # ----- construction --------------------------------------------------------

    def v(self, x, y, z):
        self.vertices.append((float(x), float(y), float(z)))
        return len(self.vertices) - 1

    def tri(self, a, b, c):
        self.faces.append((a, b, c))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def is_empty(self):
        return not self.faces

    def facet_count(self):
        return len(self.faces)

    def bounds(self):
        """(dx, dy, dz) size in mm."""
        xs = [p[0] for p in self.vertices]
        ys = [p[1] for p in self.vertices]
        zs = [p[2] for p in self.vertices]
        return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    def edge_counts(self):
        """Map each undirected edge to how many faces use it.

        A closed solid has every edge used exactly twice.
        """
        counts = {}
        for a, b, c in self.faces:
            for u, w in ((a, b), (b, c), (c, a)):
                key = (u, w) if u < w else (w, u)
                counts[key] = counts.get(key, 0) + 1
        return counts

    def is_closed(self):
        counts = self.edge_counts()
        return bool(counts) and all(n == 2 for n in counts.values())

    # ----- transforms (return new meshes) -------------------------------------

    def _xform(self, fn):
        out = Mesh()
        out.vertices = [fn(*p) for p in self.vertices]
        out.faces = list(self.faces)
        return out

    def translate(self, dx, dy, dz):
        return self._xform(lambda x, y, z: (x + dx, y + dy, z + dz))

    def scale(self, sx, sy=None, sz=None):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        return self._xform(lambda x, y, z: (x * sx, y * sy, z * sz))

    def rotate_x(self, deg):
        t = math.radians(deg)
        c, s = math.cos(t), math.sin(t)
        return self._xform(lambda x, y, z: (x, y * c - z * s, y * s + z * c))

    def rotate_y(self, deg):
        t = math.radians(deg)
        c, s = math.cos(t), math.sin(t)
        return self._xform(lambda x, y, z: (x * c + z * s, y, -x * s + z * c))

    def rotate_z(self, deg):
        t = math.radians(deg)
        c, s = math.cos(t), math.sin(t)
        return self._xform(lambda x, y, z: (x * c - y * s, x * s + y * c, z))

    def merge(self, other):
        """Combine two meshes into one (each stays a closed solid)."""
        out = Mesh()
        out.vertices = list(self.vertices)
        out.faces = list(self.faces)
        off = len(out.vertices)
        out.vertices.extend(other.vertices)
        out.faces.extend((a + off, b + off, c + off)
                         for a, b, c in other.faces)
        return out

    # ----- export --------------------------------------------------------------

    @staticmethod
    def _normal(a, b, c):
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln < 1e-12:
            return (0.0, 0.0, 0.0)
        return (nx / ln, ny / ln, nz / ln)

    def export_stl(self, path):
        """Binary STL: 80-byte header + uint32 facet count."""
        with open(path, "wb") as f:
            f.write(b"Jarvis3D" + bytes(80 - 8))
            f.write(struct.pack("<I", len(self.faces)))
            for a, b, c in self.faces:
                pa, pb, pc = (self.vertices[a], self.vertices[b],
                              self.vertices[c])
                n = self._normal(pa, pb, pc)
                f.write(struct.pack("<12f", n[0], n[1], n[2],
                                    pa[0], pa[1], pa[2],
                                    pb[0], pb[1], pb[2],
                                    pc[0], pc[1], pc[2]))
                f.write(struct.pack("<H", 0))

    def export_obj(self, path):
        with open(path, "w") as f:
            f.write("# Jarvis 3D design\n")
            for x, y, z in self.vertices:
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            for a, b, c in self.faces:
                f.write(f"f {a + 1} {b + 1} {c + 1}\n")


# ----- primitives ---------------------------------------------------------------

def box(w, d, h):
    """Closed box centered at the origin."""
    m = Mesh()
    x, y, z = w / 2, d / 2, h / 2
    v = [m.v(px, py, pz)
         for pz in (-z, z) for py in (-y, y) for px in (-x, x)]
    # order: 0:(-,-,-) 1:(+,-,-) 2:(-,+,-) 3:(+,+,-)
    #        4:(-,-,+) 5:(+,-,+) 6:(-,+,+) 7:(+,+,+)
    m.quad(0, 2, 3, 1)  # bottom (-z)
    m.quad(4, 5, 7, 6)  # top (+z)
    m.quad(0, 1, 5, 4)  # front (-y)
    m.quad(2, 6, 7, 3)  # back (+y)
    m.quad(0, 4, 6, 2)  # left (-x)
    m.quad(1, 3, 7, 5)  # right (+x)
    return m


def lathe(profile, segments=48, closed=False):
    """Revolve a (r, y) profile around the Y axis.

    A closed profile loop that touches the axis (r=0) at both ends makes
    a watertight solid (vase). Pass closed=True for a loop that does NOT
    touch the axis (torus): the last ring is stitched back to the first.
    An open profile makes a surface.
    """
    m = Mesh()
    rings = []
    for r, y in profile:
        if r < 1e-9:
            rings.append([m.v(0.0, y, 0.0)])
        else:
            ring = []
            for j in range(segments):
                a = 2.0 * math.pi * j / segments
                ring.append(m.v(r * math.cos(a), y, r * math.sin(a)))
            rings.append(ring)
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for A, B in pairs:
        n = segments
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            c = A[0]
            for j in range(n):
                m.tri(c, B[j], B[(j + 1) % n])
        elif len(B) == 1:
            c = B[0]
            for j in range(n):
                m.tri(A[j], c, A[(j + 1) % n])
        else:
            for j in range(n):
                j2 = (j + 1) % n
                m.quad(A[j], B[j], B[j2], A[j2])
    return m


def cylinder(r, h, segments=48):
    return lathe([(0.0, -h / 2), (r, -h / 2), (r, h / 2), (0.0, h / 2)],
                 segments=segments)


def sphere(r, segments=32, rings=20):
    prof = [(r * math.sin(math.pi * i / rings),
             -r * math.cos(math.pi * i / rings)) for i in range(rings + 1)]
    return lathe(prof, segments=segments)


def extrude_annulus(outer_pts, hole_r, thickness):
    """Extrude a 2D outline (CCW [(x, y), ...]) with a concentric round hole.

    Used for the gear (toothed outline) and the keychain (round outline).
    """
    m = Mesh()
    n = len(outer_pts)
    t = thickness / 2
    o_top = [m.v(x, y, t) for x, y in outer_pts]
    o_bot = [m.v(x, y, -t) for x, y in outer_pts]
    h_top, h_bot = [], []
    for j in range(n):
        a = 2.0 * math.pi * j / n
        h_top.append(m.v(hole_r * math.cos(a), hole_r * math.sin(a), t))
        h_bot.append(m.v(hole_r * math.cos(a), hole_r * math.sin(a), -t))
    for j in range(n):
        j2 = (j + 1) % n
        # top face (+z)
        m.tri(o_top[j], o_top[j2], h_top[j2])
        m.tri(o_top[j], h_top[j2], h_top[j])
        # bottom face (-z)
        m.tri(o_bot[j], h_bot[j], h_bot[j2])
        m.tri(o_bot[j], h_bot[j2], o_bot[j2])
        # outer wall
        m.quad(o_bot[j], o_bot[j2], o_top[j2], o_top[j])
        # hole wall (normal points into the hole)
        m.tri(h_bot[j], h_top[j2], h_bot[j2])
        m.tri(h_bot[j], h_top[j], h_top[j2])
    return m


# ----- parametric catalog --------------------------------------------------------

def phone_stand():
    """Wedge stand: base + leaning back plate + phone lip."""
    base = box(90, 70, 8).translate(0, 0, 4)
    plate = (box(70, 8, 100).rotate_x(20).translate(0, -32, 55))
    lip = box(70, 10, 12).translate(0, -5, 14)
    return base.merge(plate).merge(lip)


def desk_tray():
    """Open organizer tray: bottom + four walls (160 x 110 mm)."""
    base = box(160, 110, 8).translate(0, 0, 4)
    wall_h, wall_t = 36, 6
    front = box(160, wall_t, wall_h).translate(0, -(110 / 2 - wall_t / 2), 8 + wall_h / 2)
    back = box(160, wall_t, wall_h).translate(0, (110 / 2 - wall_t / 2), 8 + wall_h / 2)
    side_d = 110 - 2 * wall_t
    left = box(wall_t, side_d, wall_h).translate(-(160 / 2 - wall_t / 2), 0, 8 + wall_h / 2)
    right = box(wall_t, side_d, wall_h).translate((160 / 2 - wall_t / 2), 0, 8 + wall_h / 2)
    return base.merge(front).merge(back).merge(left).merge(right)


def vase():
    """Hollow watertight vase: closed lathe profile (outer wall, rim,
    inner wall, floor). About 76 mm wide, 100 mm tall."""
    profile = [
        (0.0, 0.0),
        (28.0, 0.0), (34.0, 6.0), (38.0, 25.0), (36.0, 55.0),
        (30.0, 80.0), (26.0, 92.0), (27.0, 100.0),   # outer wall + rim
        (23.0, 100.0),                                 # rim
        (22.0, 90.0), (26.0, 70.0), (30.0, 45.0),
        (28.0, 20.0), (22.0, 10.0), (0.0, 10.0),       # inner wall + floor
    ]
    return lathe(profile, segments=64)


def gear(teeth=12, diameter=60.0, thickness=8.0, hole_diameter=8.0):
    """Toothed wheel with a center hole. All sizes in mm."""
    tip_r = diameter / 2.0
    root_r = tip_r * 0.82
    step = 2.0 * math.pi / teeth
    outer = []
    for i in range(teeth):
        base = i * step
        outer.append((root_r * math.cos(base), root_r * math.sin(base)))
        outer.append((tip_r * math.cos(base + 0.28 * step),
                      tip_r * math.sin(base + 0.28 * step)))
        outer.append((tip_r * math.cos(base + 0.52 * step),
                      tip_r * math.sin(base + 0.52 * step)))
        outer.append((root_r * math.cos(base + 0.80 * step),
                      root_r * math.sin(base + 0.80 * step)))
    return extrude_annulus(outer, hole_diameter / 2.0, thickness)


def keychain():
    """Keychain fob: disc with center hole + hanging loop."""
    disc = extrude_annulus(
        [(16.0 * math.cos(2 * math.pi * j / 48),
          16.0 * math.sin(2 * math.pi * j / 48)) for j in range(48)],
        2.5, 3.0)
    loop_profile = [(4.0 + 1.6 * math.cos(t), 1.6 * math.sin(t))
                    for t in [2 * math.pi * i / 24 for i in range(24)]]
    loop = lathe(loop_profile, segments=24, closed=True).rotate_x(90).translate(17.5, 0, 0)
    return disc.merge(loop)


def custom_box(w_mm, d_mm, h_mm):
    """Plain box, dimensions in mm (already converted by the plugin)."""
    w_mm = max(1.0, min(float(w_mm), 500.0))
    d_mm = max(1.0, min(float(d_mm), 500.0))
    h_mm = max(1.0, min(float(h_mm), 500.0))
    return box(w_mm, d_mm, h_mm).translate(0, 0, h_mm / 2)


CATALOG = {
    "phone_stand": {
        "title": "Phone Stand",
        "aliases": ["phone stand", "phone holder", "stand"],
        "make": lambda: phone_stand(),
        "blurb": "a leaning phone stand with a lip (90 x 70 mm base)",
    },
    "desk_tray": {
        "title": "Desk Tray",
        "aliases": ["desk tray", "tray", "organizer", "desk organizer"],
        "make": lambda: desk_tray(),
        "blurb": "an open organizer tray with walls (160 x 110 mm)",
    },
    "vase": {
        "title": "Vase",
        "aliases": ["vase", "flower vase"],
        "make": lambda: vase(),
        "blurb": "a hollow watertight vase (76 mm wide, 100 mm tall)",
    },
    "gear": {
        "title": "Gear",
        "aliases": ["gear", "cog", "toothed wheel"],
        "make": lambda: gear(),
        "blurb": "a toothed gear with a center hole (12 teeth, 60 mm)",
    },
    "keychain": {
        "title": "Keychain",
        "aliases": ["keychain", "key chain", "keyring", "fob"],
        "make": lambda: keychain(),
        "blurb": "a keychain fob disc with a hanging loop",
    },
    "custom_box": {
        "title": "Custom Box",
        "aliases": ["box"],
        "make": None,  # needs dimensions from speech; plugin builds it
        "needs_dims": True,
        "blurb": "a box in any size you name, e.g. 10 by 5 by 2 cm",
    },
}


def find_design(text):
    """Return (key, entry) for the catalog item named in text, else (None, None).

    Longer aliases win so 'phone stand' beats 'stand'.
    """
    best, best_entry, best_len = None, None, -1
    for key, entry in CATALOG.items():
        for alias in entry["aliases"]:
            if alias in text and len(alias) > best_len:
                best, best_entry, best_len = key, entry, len(alias)
    return best, best_entry
