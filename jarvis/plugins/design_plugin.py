"""3D model designer. Try: 'design a 3D model of a phone stand',
'make me a 3D vase', '3d print a gear', 'design a box 10 by 5 by 2 cm',
'what can you design?', 'show the design'.

Builds a parametric mesh with jarvis.threed, writes STL + OBJ into the
designs/ folder, and speaks a confirmation. 'show the design' (or 'open
the design') opens the latest files with the OS default app.

Naming note: this plugin is called '3d_design' (not 'design') so it sorts
before the 'apps' plugin — otherwise 'open the design' would reach the
app-opener first and try to launch an app literally called 'design'.
"""
import difflib
import os
import re
from datetime import datetime
from pathlib import Path

from .. import threed
from .base import Plugin

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "designs"

_DESIGN_RX = re.compile(r"\b(design|make|create|build|3d[\s-]?print)\b")
_OBJECT_RX = re.compile(
    r"\b(3d|model|stl|phone[\s-]?stand|vase|gear|cog|key[\s-]?chain|"
    r"keyring|fob|desk[\s-]?tray|organizer|tray|box)\b")
_LIST_RX = re.compile(
    r"\b(what|which)\b.*\b(3d|designs?|models?)\b.*\b(can you|do you)\b"
    r"|\blist\b.*\bdesigns?\b")
_OPEN_RX = re.compile(r"\b(open|show)\b.*\b(design|model|stl|it)\b")

_DIM_RX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:by|x|\u00d7)\s*"
    r"(\d+(?:\.\d+)?)\s*(?:by|x|\u00d7)\s*"
    r"(\d+(?:\.\d+)?)\s*"
    r"(mm|millimeters?|cm|centimeters?|in|inch|inches|\")?")
_TEETH_RX = re.compile(r"(\d+)\s*teeth")
_GEAR_DIA_RX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|millimeters?|cm|centimeters?|in|inch|inches|\")"
    r"(?:\s*(?:across|wide|diameter))?")

_UNIT_TO_MM = {
    "mm": 1.0, "millimeter": 1.0, "millimeters": 1.0,
    "cm": 10.0, "centimeter": 10.0, "centimeters": 10.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4, '"': 25.4,
}

# Latest saved files, so 'show the design' / 'open the design' works.
_last_saved = []


def _to_mm(value, unit):
    return float(value) * _UNIT_TO_MM.get((unit or "cm").lower(), 10.0)


class DesignPlugin(Plugin):
    name = "3d_design"
    description = "3D designs: 'design a 3D model of a phone stand'."

    def match(self, text):
        if _OPEN_RX.search(text):
            return True
        if _LIST_RX.search(text):
            return True
        return bool(_DESIGN_RX.search(text) and _OBJECT_RX.search(text))

    def run(self, text):
        if _LIST_RX.search(text):
            return self._list_catalog()
        key, entry = threed.find_design(text)
        if key is None:
            # 'show the design' / 'open the design' (no catalog item named).
            if _OPEN_RX.search(text):
                return self._open_latest()
            return self._unknown(text)
        if key == "custom_box":
            return self._make_box(text)
        if key == "gear":
            return self._make_gear(text)
        mesh = entry["make"]()
        return self._save(key, entry["title"], mesh)

    # ----- catalog ------------------------------------------------------------

    def _list_catalog(self):
        items = "; ".join(
            f"{e['title']} ({e['blurb']})"
            for e in threed.CATALOG.values())
        return ("I can design these 3D models: " + items + ". "
                "Just say, for example, 'design a 3D model of a phone stand'.")

    def _unknown(self, text):
        cleaned = re.sub(
            r"\b(design|designs|make|create|build|print|printing|a|an|the|"
            r"3d|model|models|of|me|please|for)\b", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        aliases = [a for e in threed.CATALOG.values() for a in e["aliases"]]
        guess = difflib.get_close_matches(cleaned, aliases, n=1, cutoff=0.55)
        names = ", ".join(e["title"] for e in threed.CATALOG.values())
        thing = f"'{cleaned}' " if cleaned else ""
        if guess:
            return (f"I don't have a design for {thing}yet — did you mean "
                    f"'{guess[0]}'? I can design: {names}.")
        return (f"I don't have a design for {thing}yet. "
                f"I can design: {names}.")

    # ----- builders -------------------------------------------------------------

    def _make_box(self, text):
        m = _DIM_RX.search(text)
        if not m:
            return ("What size box? Say something like 'design a box "
                    "10 by 5 by 2 centimeters'.")
        w, d, h = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
        unit = (m.group(4) or "cm").lower()
        w_mm, d_mm, h_mm = (_to_mm(w, unit), _to_mm(d, unit), _to_mm(h, unit))
        mesh = threed.custom_box(w_mm, d_mm, h_mm)
        note = "" if m.group(4) else " (assuming centimeters)"
        size = f"{w_mm:g} by {d_mm:g} by {h_mm:g} millimeters{note}"
        return self._save("custom_box", f"Box ({size})", mesh)

    def _make_gear(self, text):
        teeth_m = _TEETH_RX.search(text)
        teeth = max(6, min(int(teeth_m.group(1)), 60)) if teeth_m else 12
        dia_m = _GEAR_DIA_RX.search(text)
        dia = _to_mm(dia_m.group(1), dia_m.group(2)) if dia_m else 60.0
        mesh = threed.gear(teeth=teeth, diameter=dia)
        return self._save("gear", f"Gear ({teeth} teeth, {dia:g} mm)", mesh)

    # ----- saving / opening -----------------------------------------------------

    def _save(self, key, title, mesh):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stl_path = OUTPUT_DIR / f"{key}_{stamp}.stl"
        obj_path = OUTPUT_DIR / f"{key}_{stamp}.obj"
        mesh.export_stl(stl_path)
        mesh.export_obj(obj_path)
        global _last_saved
        _last_saved = [stl_path, obj_path]
        dx, dy, dz = mesh.bounds()
        return (f"Designed {title} — about {dx:.0f} by {dy:.0f} by "
                f"{dz:.0f} millimeters. Saved {stl_path.name} and "
                f"{obj_path.name} in the designs folder. "
                f"Say 'show the design' to open it.")

    def _open_latest(self):
        if not _last_saved:
            return ("No design yet — ask me to design something first, "
                    "like 'design a 3D model of a phone stand'.")
        stl_path = _last_saved[0]
        if not stl_path.exists():
            return (f"The last design ({stl_path.name}) is no longer on "
                    f"disk. Ask me to design it again.")
        if hasattr(os, "startfile"):
            os.startfile(str(stl_path))  # noqa: S606 - user asked to open it
            return f"Opening {stl_path.name}."
        return (f"I can't auto-open files on this system, but the design "
                f"is at {stl_path}.")


plugin = DesignPlugin()
