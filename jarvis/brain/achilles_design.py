"""Editable interpretation of the user's Achilles concept sheet, not a scan.

Radial armor, silver swept blades, red underlayer, gold crest and center gem
are constructed as separate solids. The drawing has no dimensions; depth and
underside are inferred, and coordinates are explicitly unmeasured concept units.
"""
import math


def achilles_scene():
    from jarvis.brain.achilles_traced import traced_scene
    return traced_scene()


def build_achilles_scene():
    """Compatibility entry point used by the design engine."""
    return achilles_scene()


def legacy_blockout():
    """Retained compatibility blockout; the traced scene is now the active preset."""
    return achilles_scene()
