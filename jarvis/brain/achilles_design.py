"""Editable interpretation of the user's Achilles concept sheet, not a scan.

Radial armor, silver swept blades, red underlayer, gold crest and center gem
are constructed as separate solids. The drawing has no dimensions; depth and
underside are inferred, and coordinates are explicitly unmeasured concept units.
"""
import math


def achilles_scene():
    """Return the traced study when valid, otherwise the safe 129-part blockout.

    The uploaded traced study contains a small number of self-touching outline
    contours. Keep that authored data in the project, but never let one bad
    contour prevent Jarvis from opening/exporting the 3D workspace.
    """
    from jarvis.brain.achilles_traced import traced_scene
    from jarvis.brain.design_outlines import validate_outline

    scene = traced_scene()
    try:
        for obj in scene.get("objects", []):
            if obj.get("kind") == "outline":
                validate_outline(obj.get("profile"))
        return scene
    except ValueError:
        return legacy_blockout()


def legacy_blockout():
    objects = []
    red, scarlet, silver = "#ab202c", "#f34b35", "#dce5ed"
    dark, gold, yellow = "#273144", "#d9a51d", "#ffe178"

    def plate(name, points, y, height, color, turn=0):
        objects.append(dict(name=name,kind="prism",position=[0,y,0],
            size=[6,height,6],profile=[[x/6,z/6] for x,z in points],
            rotation_y=turn,color=color))

    def disc(name, x, y, z, diameter, height, color):
        objects.append(dict(name=name,kind="cylinder",position=[x,y,z],
                            size=[diameter,height,diameter],color=color))

    def polar(radius, degrees):
        a = math.radians(degrees)
        return radius*math.cos(a), radius*math.sin(a)

    def sector(name, start, end, inner, outer, y, height, color, steps=6):
        for i in range(steps):
            a,b = start+(end-start)*i/steps, start+(end-start)*(i+1)/steps
            plate(f"{name} {i+1}", [polar(inner,a),polar(outer,a),polar(outer,b),polar(inner,b)], y,height,color)

    disc("Underside / inferred spindle",0,-.62,0,.9,.65,dark)
    disc("Underside / inferred chassis",0,-.12,0,7.6,.65,dark)
    disc("Crimson energy layer",0,.22,0,8.2,.48,red)
    for turn in (0,180):
        sector("Silver attack wing",15+turn,135+turn,3.95,5.05,.56,.3,silver,8)
        sector("Blade bevel",18+turn,130+turn,4.82,5.15,.73,.10,"#f3f7fb",8)
        sector("Inner graphite seam",20+turn,125+turn,3.82,3.95,.76,.10,dark,7)
        plate("Swept blade tip",[polar(4.05,124),polar(5.15,124),polar(4.85,155)],.57,.36,silver,turn)
        plate("Blade tip highlight",[polar(4.72,128),polar(5.13,128),polar(4.85,155)],.79,.08,"#f7fbff",turn)
        sector("Crimson outer armor",-35+turn,10+turn,3.3,4.9,.74,.42,red,4)
        for angle in (-34,-15,4):
            a = angle+turn
            plate("Red armor spike",[polar(3.45,a),polar(4.7,a),polar(5.22,a+13),polar(3.9,a+12)],.92,.2,scarlet)
        sector("Inner red rim",20+turn,140+turn,2.65,3.1,.72,.28,scarlet,8)
        for angle in (38,82,120):
            a=angle+turn
            x,z=polar(3.68,a)
            disc("Silver hex fastener",x,.97,z,.56,.19,silver)
            disc("Fastener recess",x,1.08,z,.27,.06,dark)

    plate("Gold shield silhouette",[(0,-3.5),(1.48,-1.6),(1.2,1.55),(0,3.42),(-1.2,1.55),(-1.48,-1.6)],1.00,.34,gold)
    plate("Shield scarlet enamel",[(0,-3.19),(1.18,-1.48),(.98,1.5),(0,3.04),(-.98,1.5),(-1.18,-1.48)],1.22,.14,red)
    for side in (-1,1):
        def mirror(points):
            return [(side*x,z) for x,z in points]
        for i, (tipx,tipz,basex,basez) in enumerate([(1.2,-3.4,.45,-1.1),(1.65,-2.85,.65,-.85),(1.7,-2.15,.85,-.45)]):
            plate(f"Golden crest feather {side}/{i}",mirror([(basex-.24,basez),(tipx,tipz),(basex+.32,basez-.17)]),1.38,.22,gold)
            plate(f"Crest highlight {side}/{i}",mirror([(basex-.08,basez-.13),(tipx,tipz),(basex+.08,basez-.29)]),1.52,.07,yellow)
        plate("Gold cheek armor",mirror([(.12,-.6),(1.25,-1.25),(1.6,-.45),(.55,.3)]),1.4,.18,gold)
        plate("Lower gold flourish",mirror([(.4,.8),(1.0,1.15),(.63,2.42),(.06,2.9)]),1.42,.15,gold)
        plate("Lower flame inset",mirror([(.38,1.13),(.74,1.3),(.4,2.28)]),1.52,.06,yellow)
        x=side*3.18
        plate("Gold lateral bracket",mirror([(2.3,-.28),(3.3,-.52),(3.76,0),(3.3,.52),(2.3,.28)]),.95,.19,gold)
        disc("Gold pivot",x,1.12,0,.64,.22,gold)
        disc("Ruby pivot",x,1.26,0,.35,.10,scarlet)

    disc("Crest upper gold jewel",0,1.49,-1.25,.62,.19,gold)
    disc("Crest ruby jewel",0,1.61,-1.25,.33,.10,scarlet)
    plate("Central silver spear",[(0,-.85),(.66,0),(0,1.95),(-.66,0)],1.53,.30,silver)
    plate("Spear left facet",[(0,-.69),(-.46,.02),(0,.49)],1.72,.07,"#f8fbff")
    plate("Spear right facet",[(0,-.69),(.46,.02),(0,.49)],1.72,.07,"#718899")
    plate("Spear long facet",[(-.33,.37),(.33,.37),(0,1.75)],1.73,.08,"#edf4f7")
    disc("Center jewel setting",0,1.81,0,.5,.12,dark)
    disc("Center jewel",0,1.9,0,.30,.08,"#9ddae8")
    return {"title":"Achilles · reference study 01", "project":"Nova Frontier",
            "units":"concept", "reference_asset":"achilles", "objects":objects}
