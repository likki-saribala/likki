"""Generates the SARIBALA'S concept ground-floor plan + front elevation as a DXF
(opens in AutoCAD / LibreCAD) and a dark "AutoCAD-style" PNG preview.

Units: millimetres. CONCEPT DRAWING ONLY - not for construction.
"""
import math
import os

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext, pymupdf  # noqa: F401
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

OUT = os.path.dirname(os.path.abspath(__file__))
W, D = 40000, 24000          # plan width x depth (40 m x 24 m)
T = 300                      # wall thickness
CEIL_H = 7000                # clear ceiling height (double height hall)
TOTAL_H = 14400              # top of full-width sign wall

doc = ezdxf.new("R2010", setup=True)
doc.units = ezdxf.units.MM
msp = doc.modelspace()

for name, color in {
    "WALLS": 7, "DOORS": 3, "GLASS": 4, "FURNITURE": 2, "KITCHEN": 6,
    "BAR": 30, "DIMS": 1, "TEXT": 7, "SIGN": 2, "COLUMNS": 8, "TITLE": 7,
    "ELEVATION": 7, "HATCH": 8, "ROOMTAG": 7,
}.items():
    doc.layers.add(name, color=color)

dimstyle = doc.dimstyles.duplicate_entry("EZDXF", "ARCH")
dimstyle.dxf.dimtxt = 380
dimstyle.dxf.dimasz = 280
dimstyle.dxf.dimexe = 150
dimstyle.dxf.dimexo = 150
dimstyle.dxf.dimtad = 1
dimstyle.dxf.dimgap = 80
dimstyle.dxf.dimlfac = 1


# ---------------------------------------------------------------- helpers
def rect(x1, y1, x2, y2, layer, close=True):
    msp.add_lwpolyline([(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
                       close=close, dxfattribs={"layer": layer})


def solid(pts, layer, color=None):
    h = msp.add_hatch(color=color if color else 256,
                      dxfattribs={"layer": layer})
    h.paths.add_polyline_path(pts, is_closed=True)
    h.set_solid_fill()
    return h


def text(s, x, y, h=300, layer="TEXT", align="MIDDLE_CENTER", color=None):
    e = msp.add_text(s, height=h, dxfattribs={"layer": layer})
    if color:
        e.dxf.color = color
    e.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment[align])
    return e


def big_text(s, x0, y0, width, layer="SIGN", color=2):
    """Bold block letters as real filled geometry (true bold in any CAD viewer)."""
    fp = FontProperties(family="DejaVu Sans", weight="bold")
    tp = TextPath((0, 0), s, size=100, prop=fp)
    bb = tp.get_extents()
    k = width / bb.width
    for poly in tp.to_polygons():
        pass
    h = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    h.set_solid_fill()
    for poly in tp.to_polygons():
        pts = [((px - bb.x0) * k + x0, (py - bb.y0) * k + y0) for px, py in poly]
        h.paths.add_polyline_path(pts, is_closed=True)
    # thin outline so the letters read in wireframe mode too
    for poly in tp.to_polygons():
        pts = [((px - bb.x0) * k + x0, (py - bb.y0) * k + y0) for px, py in poly]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={"layer": layer, "color": 7})
    return bb.height * k


def wall(axis, fixed, a, b, openings=(), t=T):
    """Wall along x (axis='h', y=fixed) or y (axis='v', x=fixed) with gaps."""
    cuts = [a] + [v for o in sorted(openings) for v in o] + [b]
    for i in range(0, len(cuts), 2):
        s, e = cuts[i], cuts[i + 1]
        if e <= s:
            continue
        if axis == "h":
            pts = [(s, fixed - t / 2), (e, fixed - t / 2), (e, fixed + t / 2), (s, fixed + t / 2)]
        else:
            pts = [(fixed - t / 2, s), (fixed + t / 2, s), (fixed + t / 2, e), (fixed - t / 2, e)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "WALLS"})
        solid(pts, "HATCH", 252)


def door_swing(hx, hy, width, closed_deg, open_deg, layer="DOORS"):
    """Door leaf in its open position + swing arc, hinged at (hx, hy)."""
    o = math.radians(open_deg)
    msp.add_line((hx, hy), (hx + width * math.cos(o), hy + width * math.sin(o)),
                 dxfattribs={"layer": layer})
    a0, a1 = sorted([closed_deg % 360, open_deg % 360])
    if a1 - a0 > 180:
        a0, a1 = a1, a0 + 360
    msp.add_arc((hx, hy), width, a0, a1, dxfattribs={"layer": layer})


def glass(x1, y1, x2, y2):
    msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "GLASS"})
    dx, dy = (x2 - x1), (y2 - y1)
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * 60, dx / L * 60
    msp.add_line((x1 + nx, y1 + ny), (x2 + nx, y2 + ny), dxfattribs={"layer": "GLASS"})
    msp.add_line((x1 - nx, y1 - ny), (x2 - nx, y2 - ny), dxfattribs={"layer": "GLASS"})


def chair(cx, cy, ang):
    pts = [(-220, -220), (220, -220), (220, 220), (-220, 220)]
    c, s = math.cos(ang), math.sin(ang)
    msp.add_lwpolyline([(cx + px * c - py * s, cy + px * s + py * c) for px, py in pts],
                       close=True, dxfattribs={"layer": "FURNITURE"})


def table4(cx, cy, round_=False):
    if round_:
        msp.add_circle((cx, cy), 550, dxfattribs={"layer": "FURNITURE"})
    else:
        rect(cx - 450, cy - 450, cx + 450, cy + 450, "FURNITURE")
    for ang in (0, 90, 180, 270):
        r = math.radians(ang)
        chair(cx + 880 * math.cos(r), cy + 880 * math.sin(r), r)


def table_long(cx, cy, n=3):
    """Banquet table seating n on each long side."""
    L = 900 * n
    rect(cx - L / 2, cy - 450, cx + L / 2, cy + 450, "FURNITURE")
    for i in range(n):
        x = cx - L / 2 + 450 + i * 900
        chair(x, cy + 680, math.pi / 2)
        chair(x, cy - 680, -math.pi / 2)


# ============================================================ FLOOR PLAN
# --- outer walls (front facade is the TOP wall, y = D)
ENTRY = (17000, 23000)
EXIT_R = (20500, 21700)
SERVICE = (33000, 35000)
wall("h", D, 0, W, openings=[ENTRY])
wall("h", 0, 0, W, openings=[SERVICE])
wall("v", 0, 0, D)
wall("v", W, 0, D, openings=[EXIT_R])

# --- interior walls: back-of-house strip y 0..8000
BOH = 8000
wall("h", BOH, 0, W, openings=[(2500, 3500), (7000, 8000), (10000, 11000),
                               (14000, 15200), (18000, 26000), (34000, 35000)])
for x in (6000, 12000, 32000):
    wall("v", x, 0, BOH)
wall("v", 9000, 0, BOH)

# --- glazed entrance (double doors with swing + side glass)
glass(ENTRY[0], D, ENTRY[1], D)
door_swing(17000, D, 1500, 0, 270)
door_swing(20000, D, 1500, 180, 270)
door_swing(20000, D, 1500, 0, 270)
door_swing(23000, D, 1500, 180, 270)
text("MAIN ENTRANCE", 20000, D + 1100, 380, "ROOMTAG")
# emergency exit (right wall) + service door (bottom wall)
door_swing(W, EXIT_R[0], 1200, 90, 180)
text("FIRE EXIT", W + 1900, 21100, 300, "ROOMTAG", "MIDDLE_LEFT")
door_swing(SERVICE[0], 0, 2000, 0, 90)
text("SERVICE / DELIVERY", 34000, -900, 320, "ROOMTAG")
# interior door swings
door_swing(2500, BOH, 1000, 0, 90)
door_swing(7000, BOH, 1000, 0, 90)
door_swing(10000, BOH, 1000, 0, 90)
door_swing(14000, BOH, 1200, 0, 90)
door_swing(34000, BOH, 1000, 0, 90)

# --- structural columns on an aisle grid
col_x = [15650, 22250, 28850, 35450]
for cx in col_x:
    rect(cx - 250, 15000 - 250, cx + 250, 15000 + 250, "COLUMNS")
    solid([(cx - 250, 14750), (cx + 250, 14750), (cx + 250, 15250), (cx - 250, 15250)],
          "COLUMNS", 8)

# --- main dining: tables on a regular grid, banquet tables on the right
xs = [14000 + 3300 * i for i in range(8)]
for row, y in enumerate([10500, 13500, 16500]):
    for i, x in enumerate(xs):
        if row == 2 and i >= 5:
            continue
        table4(x, y, round_=(i + row) % 2 == 0)
for x in (31200, 35400):
    table_long(x, 18900, 2)
# booths along the right wall
for y in (9400, 11200):
    rect(W - 1500, y, W - 300, y + 1500, "FURNITURE")
text("BOOTHS", W - 900, 8650, 260, "ROOMTAG")

# --- bar / lounge (left)
rect(3000, 11500, 4300, 20500, "BAR")                 # counter
rect(300, 11500, 1500, 20500, "BAR")                  # back bar
for i in range(10):
    msp.add_circle((5300, 11900 + i * 900), 220, dxfattribs={"layer": "BAR"})
for cy in (12500, 16000, 19500):
    msp.add_circle((8800, cy), 650, dxfattribs={"layer": "FURNITURE"})
    for ang in (0, 120, 240):
        r = math.radians(ang)
        msp.add_circle((8800 + 1050 * math.cos(r), cy + 1050 * math.sin(r)), 260,
                       dxfattribs={"layer": "FURNITURE"})
text("BAR & LOUNGE", 2300, 22000, 450, "ROOMTAG", "MIDDLE_LEFT")

# --- host stand + waiting area at the entrance
rect(18200, 21400, 21800, 22300, "FURNITURE")
text("HOST", 20000, 21850, 280, "ROOMTAG")
rect(23800, 22600, 26200, 23700, "FURNITURE")  # waiting bench
text("WAITING", 25000, 22150, 260, "ROOMTAG")

# --- back of house
# kitchen (x 12000..32000)
rect(12600, 6600, 31400, 7400, "KITCHEN")                       # cold pass / counter
text("PASS COUNTER", 22000, 7000, 300, "ROOMTAG")
rect(18000, 6400, 26000, 7600, "KITCHEN")                       # pass window ledge
for i in range(5):                                              # cook line
    x = 13000 + i * 2200
    rect(x, 4300, x + 2000, 5300, "KITCHEN")
    msp.add_circle((x + 500, 4800), 180, dxfattribs={"layer": "KITCHEN"})
    msp.add_circle((x + 1500, 4800), 180, dxfattribs={"layer": "KITCHEN"})
text("COOK LINE - RANGES / GRILLS / FRYERS", 18000, 3600, 300, "ROOMTAG")
rect(25500, 3600, 30500, 5000, "KITCHEN")                       # prep island
text("PREP", 28000, 4300, 300, "ROOMTAG")
rect(12600, 500, 17600, 2500, "KITCHEN")                        # walk-in cooler
text("WALK-IN COOLER", 15100, 1500, 300, "ROOMTAG")
rect(25000, 500, 31400, 2200, "KITCHEN")                        # dish wash
text("DISH WASH", 28200, 1350, 300, "ROOMTAG")
text("KITCHEN", 22000, 5800, 600, "ROOMTAG")
# dry store, restrooms, office
text("DRY STORE", 3000, 4000, 420, "ROOMTAG")
text("MEN", 7500, 4000, 420, "ROOMTAG")
text("WOMEN", 10500, 4000, 420, "ROOMTAG")
text("OFFICE / STAFF", 36000, 4000, 420, "ROOMTAG")
rect(33000, 5600, 35200, 7000, "FURNITURE")                    # desk
text("DINING HALL  -  240 SEATS", 31500, 21700, 520, "ROOMTAG")

# --- dimensions
msp.add_linear_dim(base=(0, -2800), p1=(0, 0), p2=(W, 0), dimstyle="ARCH",
                   override={"dimtxt": 520}).render()
msp.add_linear_dim(base=(-3200, 0), p1=(0, 0), p2=(0, D), angle=90, dimstyle="ARCH",
                   override={"dimtxt": 520}).render()
msp.add_linear_dim(base=(-1600, 0), p1=(0, 0), p2=(0, BOH), angle=90,
                   dimstyle="ARCH").render()
msp.add_linear_dim(base=(0, D + 2200), p1=(0, D), p2=(ENTRY[0], D), dimstyle="ARCH").render()
msp.add_linear_dim(base=(0, D + 2200), p1=(ENTRY[0], D), p2=(ENTRY[1], D), dimstyle="ARCH").render()
msp.add_linear_dim(base=(0, D + 2200), p1=(ENTRY[1], D), p2=(W, D), dimstyle="ARCH").render()

# ---------------------------------------------- BANNER: name across the top
SIGN_Y = D + 4200
sign_h = big_text("SARIBALA'S", 0, SIGN_Y, W, "SIGN", 2)
text("R E S T A U R A N T   &   B A R   -   G R O U N D   F L O O R   P L A N",
     W / 2, SIGN_Y + sign_h + 1200, 650, "TITLE")

# ================================================== FRONT ELEVATION (below)
EY = -21500                        # elevation ground line
rect(0, EY, W, EY + TOTAL_H, "ELEVATION")
rect(0, EY + CEIL_H - 600, W, EY + TOTAL_H, "ELEVATION")        # sign / parapet band
msp.add_line((-2500, EY), (W + 2500, EY), dxfattribs={"layer": "ELEVATION", "lineweight": 70})
big_text("SARIBALA'S", 800, EY + CEIL_H + 200, W - 1600, "SIGN", 2)
# storefront glazing: pilasters + tall glass bays
bays = 10
pw = 700
bay_w = (W - pw * (bays + 1)) / bays
for i in range(bays + 1):
    x = i * (bay_w + pw)
    rect(x, EY, x + pw, EY + CEIL_H - 600, "ELEVATION")
    solid([(x, EY), (x + pw, EY), (x + pw, EY + CEIL_H - 600), (x, EY + CEIL_H - 600)],
          "HATCH", 252)
for i in range(bays):
    x0 = pw + i * (bay_w + pw)
    rect(x0, EY + 100, x0 + bay_w, EY + CEIL_H - 700, "GLASS")
    for k in range(1, 3):
        msp.add_line((x0 + bay_w * k / 3, EY + 100), (x0 + bay_w * k / 3, EY + CEIL_H - 700),
                     dxfattribs={"layer": "GLASS"})
    msp.add_line((x0, EY + 4200), (x0 + bay_w, EY + 4200), dxfattribs={"layer": "GLASS"})
# entrance double door (bays 5/6 centre)
ex0, ex1 = ENTRY
rect(ex0, EY, ex1, EY + 4600, "DOORS")
msp.add_line((20000, EY), (20000, EY + 4600), dxfattribs={"layer": "DOORS"})
text("MAIN ENTRANCE", 20000, EY - 900, 380, "ROOMTAG")
text("FRONT ELEVATION  (NORTH)", W / 2, EY - 2200, 650, "TITLE")
# height dims
msp.add_linear_dim(base=(-3200, EY), p1=(0, EY), p2=(0, EY + CEIL_H), angle=90,
                   dimstyle="ARCH", override={"dimtxt": 520}).render()
msp.add_linear_dim(base=(W + 3200, EY), p1=(W, EY), p2=(W, EY + TOTAL_H), angle=90,
                   dimstyle="ARCH", override={"dimtxt": 520}).render()
text(f"CLEAR CEILING HEIGHT {CEIL_H/1000:.1f} m  (DOUBLE-HEIGHT HALL)", -5400, EY + CEIL_H / 2,
     380, "ROOMTAG", "MIDDLE_CENTER").dxf.rotation = 90
text(f"OVERALL {TOTAL_H/1000:.1f} m (SIGN WALL)", W + 4300, EY + TOTAL_H / 2, 380,
     "ROOMTAG", "MIDDLE_CENTER").dxf.rotation = 90

# ================================================ FRAME + TITLE BLOCK
FX0, FX1 = -9000, W + 9000
FY0, FY1 = EY - 7500, SIGN_Y + sign_h + 3600
rect(FX0, FY0, FX1, FY1, "TITLE")
rect(FX0 - 600, FY0 - 600, FX1 + 600, FY1 + 600, "TITLE")
tb_x0, tb_y1 = FX1 - 16000, FY0 + 4200
rect(tb_x0, FY0, FX1, tb_y1, "TITLE")
text("PROJECT: SARIBALA'S RESTAURANT & BAR", tb_x0 + 500, FY0 + 3300, 500, "TITLE", "MIDDLE_LEFT")
text("SHEET: GROUND FLOOR PLAN + FRONT ELEVATION", tb_x0 + 500, FY0 + 2400, 420, "TITLE", "MIDDLE_LEFT")
text("PLAN 40.0 m x 24.0 m  |  UNITS: MM  |  SCALE 1:100 @ A0", tb_x0 + 500, FY0 + 1500, 380,
     "TITLE", "MIDDLE_LEFT")
text("CONCEPT ONLY - NOT FOR CONSTRUCTION. NEEDS LICENSED ARCHITECT REVIEW.",
     tb_x0 + 500, FY0 + 650, 300, "TITLE", "MIDDLE_LEFT")
# north arrow
na = (FX1 - 4000, FY1 - 5000)
msp.add_circle(na, 1500, dxfattribs={"layer": "TITLE"})
solid([(na[0], na[1] + 1500), (na[0] - 500, na[1] - 600), (na[0], na[1] - 200),
       (na[0] + 500, na[1] - 600)], "TITLE", 7)
text("N", na[0], na[1] + 2100, 600, "TITLE")

# ----------------------------------------------------------------- output
dxf_path = os.path.join(OUT, "saribalas_floorplan.dxf")
doc.saveas(dxf_path)

fig = plt.figure(figsize=(32, 30), dpi=110)
ax = fig.add_axes([0, 0, 1, 1])
ctx = RenderContext(doc)
ctx.set_current_layout(msp)
fig.patch.set_facecolor("#1b1f24")
ax.set_facecolor("#1b1f24")
backend = MatplotlibBackend(ax)
Frontend(ctx, backend).draw_layout(msp, finalize=True)
ax.set_xlim(FX0 - 1500, FX1 + 1500)
ax.set_ylim(FY0 - 1500, FY1 + 1500)
png_path = os.path.join(OUT, "saribalas_floorplan_preview.png")
fig.set_size_inches(32, 30)
fig.savefig(png_path, dpi=110, facecolor=fig.get_facecolor())
print(dxf_path)
print(png_path)
