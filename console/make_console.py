# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore Console carrier, rev 0.2 (PoC): one slim black board that carries 4 NVIDIA Jetson T5000 (AGX Thor) modules,
128 GB each = 512 GB unified LPDDR5X, enough for DeepSeek V3.1 (671B) at 4-bit. Run with KiCad's python:
    KPY make_console.py [path/to/Jetson_Thor_Series_Pin_Descriptions_v1.0.nvxlsx]
The 699-pin map is read from NVIDIA's pin description spreadsheet (attached inside the Jetson Thor Series Modules Design
Guide DG-12084-001, free download from developer.nvidia.com). It is not stored in this repo; download it yourself and
extract the attachment (`pdfdetach -saveall`), or point the script at it.

Real in rev 0.2:
  - every module pin and the net it lands on (NVIDIA spreadsheet + design guide ch. 5 / 7)
  - module outline 87 x 100 mm, connector position, 4 standoff holes, connector body 64.70 x 22.00 mm, 11 staggered rows:
    MEASURED from NVIDIA's drawings (DG-12084 fig. 3-1, SP-12533 fig. 5-1), about +-0.05 to 0.5 mm
  - power: TI TPS546B24A bucks (12 V -> 5 V and 3.3 V, 20 A each, strap resistors from the datasheet tables),
    TI TPS25982 eFuses per module (12 V HV and 5 V MV), TI TPS22918 per module (3.3 V SV); land patterns from TI's drawings
  - MGBE reference clock: 156.25 MHz HCSL oscillator per module (SCTF pinout + land pattern), terminated as in DG-12084 fig. 7-12
  - QSFP28: TE 2170704 cage + SFF-8679 connector layout from TE's customer drawing 2170704 rev G8, sheet 15
Still placeholder or unverified (see README.md): the exact Mirror Mezz pad size / pitch (no Molex 203456 drawing),
the QSFP28 contact pad size (drawn, not dimensioned, on TE's sheet), buck compensation and
the 5 V MV current limit. Nothing is routed."""
import os, sys, re, glob, math, zipfile, xml.etree.ElementTree as ET, pcbnew
from pcbnew import FromMM, VECTOR2I, EDA_ANGLE, DEGREES_T
HERE = os.path.dirname(os.path.abspath(__file__))
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
LIB = os.path.join(HERE, "Console.pretty"); os.makedirs(LIB, exist_ok=True)
W, H, RC = 240.0, 256.0, 4.0
OX, OY = 100.0, 100.0
pt = lambda x, y: VECTOR2I(FromMM(OX + x), FromMM(OY + y))

# ------------------------------------------------------------------ NVIDIA pin map
def find_pinmap():
    if len(sys.argv) > 1: return sys.argv[1]
    hits = glob.glob(os.path.join(HERE, "datasheets", "**", "Jetson_Thor_Series_Pin_Descriptions*.nvxlsx"), recursive=True)
    if not hits: sys.exit("Pin map not found: download NVIDIA's Jetson Thor design guide and extract its attachments (see docstring)")
    return hits[0]
def read_pins(path):
    NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = zipfile.ZipFile(path)
    ss = ["".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))
          for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    pins = {}
    for r in ET.fromstring(z.read(sheet)).iter("{%s}row" % NS["m"]):
        cells = {}
        for c in r.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0); v = c.find("m:v", NS)
            if v is None: continue
            cells[col] = ss[int(v.text)] if c.get("t") == "s" else v.text
        if re.fullmatch(r"[A-L]\d+", cells.get("A", "") or "") and cells.get("B"): pins[cells["A"]] = cells["B"]
    return pins
PINS = read_pins(find_pinmap())
assert len(PINS) == 699, f"expected 699 pins, got {len(PINS)}"
BYNAME = {v: k for k, v in PINS.items()}
ROWS = "ABCDEFGHJKL"

# ------------------------------------------------------------------ custom footprints (text .kicad_mod)
for old in glob.glob(os.path.join(LIB, "*.kicad_mod")): os.remove(old)     # rebuilt from scratch every run
def write_fp(name, descr, body_lines, pads, crt, attr="smd", crt_xy=(0, 0)):
    cw, ch = crt; cx0, cy0 = crt_xy
    s = [f'(footprint "{name}" (version 20240108) (generator "make_console") (layer "F.Cu")',
         f'  (descr "{descr}") (attr {attr})',
         '  (property "Reference" "REF**" (at %.2f %.2f 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))' % (cx0, cy0 - ch / 2 - 1.5),
         '  (property "Value" "%s" (at %.2f %.2f 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % (name, cx0, cy0 + ch / 2 + 1.5)]
    s += body_lines
    s.append(f'  (fp_rect (start {cx0-cw/2:.3f} {cy0-ch/2:.3f}) (end {cx0+cw/2:.3f} {cy0+ch/2:.3f}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))')
    s += pads
    s.append(")")
    open(os.path.join(LIB, name + ".kicad_mod"), "w").write("\n".join(s) + "\n")

def rect(layer, w, h, x=0, y=0, width=0.1):
    return f'  (fp_rect (start {x-w/2:.3f} {y-h/2:.3f}) (end {x+w/2:.3f} {y+h/2:.3f}) (stroke (width {width}) (type solid)) (fill none) (layer "{layer}"))'
def ftext(s, x, y, layer="F.Fab", size=1.0):
    return f'  (fp_text user "{s}" (at {x:.2f} {y:.2f} 0) (layer "{layer}") (effects (font (size {size} {size}) (thickness {size*0.15:.2f}))))'
def dot(x, y, layer="F.SilkS"):
    return f'  (fp_circle (center {x:.3f} {y:.3f}) (end {x+0.1:.3f} {y:.3f}) (stroke (width 0.2) (type solid)) (fill none) (layer "{layer}"))'
def smd(num, x, y, w, h, shape="roundrect", paste=True):
    lay = '"F.Cu" "F.Paste" "F.Mask"' if paste else '"F.Cu" "F.Mask"'
    rr = " (roundrect_rratio 0.25)" if shape == "roundrect" else ""
    return f'  (pad "{num}" smd {shape} (at {x:.4f} {y:.4f}) (size {w:.3f} {h:.3f}) (layers {lay}){rr})'

# 1) Jetson T5000 module, carrier side: 87 x 100 mm outline, 699-pin Molex Mirror Mezz, 4 standoff holes.
#    Footprint origin = module centre (= centre of the 4 holes). All numbers measured from NVIDIA's drawings:
#      DG-12084 fig. 3-1: connector body 64.70 x 22.00 mm, 11 rows, alternate rows offset by half a column pitch,
#                         contacts are rectangles longer across the row than along it.
#      SP-12533 fig. 5-1 (carrier top view, scaled at ~13.77 px/mm): rows run along the 87 mm side; 11 rows over 15.1 mm
#                         = 1.50 mm row pitch; a full 65-pin row spans 61.9 mm = 0.96 mm column pitch; connector centre
#                         2.0 mm right of and 24.0 mm above the module centre; holes 80.7 x 93.4 mm apart.
#    Carrier pin orientation per DG-12084 fig. 3-2 (mirror of the module view): row L at the top, row A at the bottom,
#    column 1 on the left. Rows A, B, K, L use columns 3-63, rows C-J use 1-65 (699 pins).
#    With the 2.5 mm connector (5 mm stack) the design guide allows NO parts under the module on this side, so the
#    whole outline is a top-side keepout (rule area below); everything that belongs under a module is on the back.
CP, RP, CONN = 0.96, 1.50, (2.0, -24.0)
HOLES = [(sx * 40.35, sy * 46.7) for sx in (-1, 1) for sy in (-1, 1)]
pads = []
for pin in PINS:
    r, c = pin[0], int(pin[1:]); ri = ROWS.index(r)
    x = CONN[0] + (c - 33) * CP + (CP / 4 if ri % 2 else -CP / 4)      # stagger: odd rows half a pitch right of even rows
    y = CONN[1] + (ri - 5) * -RP
    pads.append(smd(pin, x, y, 0.45, 0.90))
for hx, hy in HOLES:
    pads.append(f'  (pad "MH" thru_hole circle (at {hx:.2f} {hy:.2f}) (size 5.0 5.0) (drill 2.7) (layers "*.Cu" "*.Mask"))')
# top-side "no parts" area over the whole module: a rule area inside the footprint (KiCad does not apply it to its own
# footprint), so any other top-side part placed under the module fails DRC. Back-side parts are allowed.
KEEPOUT = ('  (zone (net 0) (net_name "") (layers "F.Cu") (name "no parts under module") (hatch edge 0.5) (connect_pads (clearance 0))'
           ' (min_thickness 0.25) (filled_areas_thickness no)'
           ' (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints not_allowed))'
           ' (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))'
           ' (polygon (pts (xy -43.5 -50) (xy 43.5 -50) (xy 43.5 50) (xy -43.5 50))))')
body = [rect("F.Fab", 87.0, 100.0, width=0.15), rect("F.Fab", 64.70, 22.00, *CONN),
        rect("F.SilkS", 64.9, 22.2, *CONN, width=0.12), rect("F.SilkS", 87.3, 100.3, width=0.12),
        ftext("Jetson T5000 module 87 x 100 (measured from NVIDIA drawings)", 0, 40.0),
        ftext("L1", CONN[0] - 34.4, CONN[1] - 7.5, "F.SilkS", 0.8),
        ftext("A1", CONN[0] - 34.4, CONN[1] + 7.5, "F.SilkS", 0.8)]
write_fp("Jetson_T5000_Module_MirrorMezz699_Carrier",
         "NVIDIA Jetson T5000 (AGX Thor) on a 699-pin Molex Mirror Mezz, carrier side, with the 4 module standoff holes. "
         "Measured from NVIDIA DG-12084 fig 3-1 and SP-12533 fig 5-1 (+-0.05-0.5 mm): confirm against the Molex 203456 "
         "drawing and NVIDIA's reference layout before ordering",
         body + [KEEPOUT], pads, (65.2, 22.5), attr="smd", crt_xy=CONN)

# 2) TI TPS25982 eFuse, VQFN-24 RGE0024M (4 x 4 mm, 0.5 mm pitch), land pattern from TI's RGE0024M drawing.
#    Two exposed pads: 25 = IN (upper), 26 = GND (lower). Pin 1 top-left, counter-clockwise.
def qfn_side(first, n, side, pitch, span, w, h):
    """n pads numbered from `first`, on one side of a QFN, placed counter-clockwise starting top-left."""
    out = []
    for i in range(n):
        o = (i - (n - 1) / 2) * pitch
        if side == "L": out.append(smd(first + i, -span, o, h, w))           # top -> bottom
        if side == "B": out.append(smd(first + i, o, span, w, h))            # left -> right
        if side == "R": out.append(smd(first + i, span, -o, h, w))           # bottom -> top
        if side == "T": out.append(smd(first + i, -o, -span, w, h))          # right -> left
    return out
p = []
for first, side in ((1, "L"), (7, "B"), (13, "R"), (19, "T")): p += qfn_side(first, 6, side, 0.5, 1.9125, 0.24, 0.575)
p += [smd(25, 0, -0.625, 2.7, 1.45, "rect"), smd(26, 0, 0.925, 2.7, 0.85, "rect")]
write_fp("TI_RGE0024M_VQFN-24_4x4mm_P0.5mm_SplitPad",
         "TI RGE0024M VQFN-24 with split exposed pad (TPS25982): pad 25 = IN, pad 26 = GND. TI land pattern",
         [rect("F.Fab", 4.0, 4.0), dot(-2.55, -1.95)], p, (4.9, 4.9))

# 3) TI TPS546B24A buck, LQFN-CLIP-40 RVF0040A (5 x 7 mm, 0.5 mm pitch), land pattern from TI's RVF0040A drawing.
#    Pins 1-12 left (top -> bottom), 13-20 bottom, 21-32 right (bottom -> top), 33-40 top (right -> left), 41 = thermal pad.
p = []
for i in range(12): p.append(smd(1 + i, -2.4, -2.75 + i * 0.5, 0.6, 0.25))
for i in range(8): p.append(smd(13 + i, -1.75 + i * 0.5, 3.4, 0.25, 0.6))
for i in range(12): p.append(smd(21 + i, 2.4, 2.75 - i * 0.5, 0.6, 0.25))
for i in range(8): p.append(smd(33 + i, 1.75 - i * 0.5, -3.4, 0.25, 0.6))
p.append(smd(41, 0, 0, 3.3, 5.3, "rect"))
write_fp("TI_RVF0040A_LQFN-CLIP-40_5x7mm_P0.5mm_EP3.3x5.3mm",
         "TI RVF0040A LQFN-CLIP-40 (TPS546B24A), pad 41 = thermal pad / PGND. TI land pattern",
         [rect("F.Fab", 5.0, 7.0), dot(-3.1, -3.5)], p, (5.9, 7.9))

# 4) QSFP28 host connector + press-fit cage, from TE customer drawing 2170704 rev G8, sheet 15 ("Recommended PCB
#    layout, single type of 2 rear holes of legs", single-sided board, PCB tolerance +-0.05). Datums -L- / -K- are the
#    connector's two 1.55 mm alignment holes; every number below is relative to -L-, x to the right, y towards the
#    connector rear (away from the bezel). Values read from the drawing's dimensions and checked against its CAD geometry:
#      connector holes   L (0, 0), K (16.80, 0), 1.55 +-0.05 non-plated
#      12 x 1.05 +-0.05 compliant (press-fit) cage holes:
#        left  x -1.10 at y +3.10, -7.60, -16.60, -25.60, -34.60
#        right x 17.90 at y +7.60, -3.10, -12.10, -21.10, -30.10
#        rear  y 12.79 at x 3.40 and 10.60
#      cage on the board: x -2.675 .. 19.475 (22.15 wide), y -37.00 (bezel end, max) .. 13.49 (rear, min)
#      connector body (parts keep-out, traces allowed): 19.20 wide, y 12.49 down to -1.69, centre notch 15.02 wide to -3.10
#      the rest of the cage area: no parts and no traces (chassis ground excepted)
#    Contacts (SFF-8679 numbering), 0.80 mm pitch: pins 1-19 along the bezel-side row (y 7.37, x 1.40 .. 15.80 left to
#    right), pins 20-38 along the rear row (y 9.88, x 15.40 .. 1.00 right to left), half a pitch offset.
#    The contact pads are drawn but not dimensioned on the sheet: 0.35 x 1.80 mm is their drawn outline. Check against
#    SFF-8679's host pad table before ordering. Board must be at least 1.57 mm thick (note 6); ours is 1.6 mm.
#    Footprint origin = midway between L and K. KiCad y points to the bezel, so y_kicad = -y_drawing.
QX = 8.40
qd = lambda x, y: (x - QX, -y)
q = []
for n in range(1, 20):
    q.append(smd(n, *qd(1.40 + (n - 1) * 0.80, 7.369), 0.35, 1.80, shape="oval"))
for n in range(20, 39):
    q.append(smd(n, *qd(15.40 - (n - 20) * 0.80, 9.878), 0.35, 1.80, shape="oval"))
for hx in (0.0, 16.80):
    x, y = qd(hx, 0)
    q.append(f'  (pad "" np_thru_hole circle (at {x:.3f} {y:.3f}) (size 1.55 1.55) (drill 1.55) (layers "*.Cu" "*.Mask"))')
CAGE_HOLES = [(-1.10, y) for y in (3.10, -7.60, -16.60, -25.60, -34.60)] + \
             [(17.90, y) for y in (7.60, -3.10, -12.10, -21.10, -30.10)] + [(3.40, 12.79), (10.60, 12.79)]
for hx, hy in CAGE_HOLES:
    x, y = qd(hx, hy)
    q.append(f'  (pad "SH" thru_hole circle (at {x:.3f} {y:.3f}) (size 1.45 1.45) (drill 1.05) (layers "*.Cu" "*.Mask"))')
def poly(pts): return " ".join("(xy %.3f %.3f)" % qd(x, y) for x, y in pts)
CAGE = [(-2.675, 13.49), (19.475, 13.49), (19.475, -37.0), (-2.675, -37.0)]
BODY = [(-1.20, 12.49), (18.00, 12.49), (18.00, -1.69), (15.91, -1.69), (15.91, -3.10), (0.89, -3.10), (0.89, -1.69), (-1.20, -1.69)]
U = [(-2.675, 13.49), (-1.20, 13.49), (-1.20, -1.69), (0.89, -1.69), (0.89, -3.10), (15.91, -3.10), (15.91, -1.69),
     (18.00, -1.69), (18.00, 13.49), (19.475, 13.49), (19.475, -37.0), (-2.675, -37.0)]
CAGE_KEEPOUT = ('  (zone (net 0) (net_name "") (layers "F.Cu") (name "QSFP cage: no parts, no traces") (hatch edge 0.5)'
                ' (connect_pads (clearance 0)) (min_thickness 0.25) (filled_areas_thickness no)'
                ' (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints not_allowed))'
                ' (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))'
                f' (polygon (pts {poly(U)})))')
fab = lambda pts, layer, w: f'  (fp_poly (pts {poly(pts)}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))'
SILK = [(-2.8, 13.62), (19.6, 13.62), (19.6, -36.6), (-2.8, -36.6)]   # stops short of the board edge
write_fp("TE_2170704_QSFP28_Cage_SFF8679_38P",
         "TE 2170704 QSFP28 press-fit cage + 38-pin SFF-8679 host connector, layout from TE customer drawing 2170704 rev G8 "
         "sheet 15 (single-sided, 2 rear legs). Contact pad size is the drawn outline, confirm against SFF-8679",
         [fab(CAGE, "F.Fab", 0.15), fab(BODY, "F.Fab", 0.1), fab(SILK, "F.SilkS", 0.12),
          dot(*qd(1.40, 5.9)), ftext("QSFP28 cage (TE 2170704), bezel this end", 0, 30), CAGE_KEEPOUT],
         q, (22.4, 50.75), attr="smd", crt_xy=(0, 11.755))

# 5) SCTF 5Z-series 5.0 x 3.2 mm 6-pad oscillator (SX5DF156.250B20F30HNN), land pattern from SCTF's 5Z spec sheet
#    ("Solder pad layout"): 0.9 x 1.2 mm pads, 1.27 mm pitch (2.54 outer), rows 2.1 mm apart centre to centre.
#    Top view: pins 1-2-3 along the bottom row left to right, 4-5-6 along the top row right to left.
#    Pins: 1 tri-state (high or open = running, low = output off), 2 NC, 3 GND, 4 OUT, 5 OUT-bar, 6 VDD.
p = [smd(n, x, 1.05, 0.9, 1.2) for n, x in ((1, -1.27), (2, 0), (3, 1.27))] + \
    [smd(n, x, -1.05, 0.9, 1.2) for n, x in ((4, 1.27), (5, 0), (6, -1.27))]
write_fp("SCTF_5Z_SMD5032-6P_5.0x3.2mm", "SCTF 5Z series 5.0 x 3.2 mm differential XO (LVPECL/LVDS/HCSL), SCTF land pattern",
         [rect("F.Fab", 5.0, 3.2), dot(-2.65, 1.75)], p, (5.5, 4.0))

# ------------------------------------------------------------------ board
b = pcbnew.BOARD()
b.SetCopperLayerCount(12)
ds = b.GetDesignSettings(); ds.SetBoardThickness(FromMM(1.6))
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
    return nets[name]
fps = {}
def add(lib, name, ref, x, y, rot=0, value=None, pins=None, back=False, default=None):
    path = LIB if lib == "Console" else STOCK + lib + ".pretty"
    f = pcbnew.FootprintLoad(path, name)
    assert f, f"{lib}:{name} missing"
    assert ref not in fps, f"duplicate {ref}"
    f.SetReference(ref); f.SetValue(value or name); f.Value().SetVisible(False)
    f.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); f.Reference().SetTextThickness(FromMM(0.12))
    f.SetPosition(pt(x, y)); f.SetOrientation(EDA_ANGLE(rot, DEGREES_T))
    pins = pins or {}
    for pad in f.Pads():
        n = pad.GetNumber()
        if n in pins: pad.SetNet(net(pins[n]))
        elif default and n: pad.SetNet(net(default(n)))
    if name.startswith("USB_C_Receptacle"):
        for g in list(f.GraphicalItems()):
            if g.GetLayer() == pcbnew.F_SilkS: f.Remove(g)
    f.Reference().SetLayer(pcbnew.F_Fab)       # Flip() moves it to B.Fab for back-side parts
    b.Add(f); fps[ref] = f
    if back: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)   # must be on the board first (crashes otherwise)
    return f

C0201, C0402, C0603, C0805, C1210 = (("Capacitor_SMD", f"C_{s}") for s in
                                     ("0201_0603Metric", "0402_1005Metric", "0603_1608Metric", "0805_2012Metric", "1210_3225Metric"))
R0402 = ("Resistor_SMD", "R_0402_1005Metric")
def C(ref, val, a, x, y, rot=90, bnet="GND", fp=C0402, back=False):
    return add(*fp, ref, x, y, rot, val, {"1": a, "2": bnet}, back=back)
def R(ref, val, a, bnet, x, y, rot=90, back=False):
    return add(*R0402, ref, x, y, rot, val, {"1": a, "2": bnet}, back=back)

# modules: 2 x 2. Each module is 87 (x) x 100 (y); row 0 spans y 5-105, row 1 y 114-214, the 37 mm channel between the
# columns carries the mesh lanes, the fan headers and (at the rear edge) the QSFP28 cage.
MOD = [(58.0, 55.0), (182.0, 55.0), (58.0, 164.0), (182.0, 164.0)]
PEERS = {m: [n for n in range(4) if n != m] for m in range(4)}

def module_nets(m):
    p = {}
    for pin, name in PINS.items():
        base = re.sub(r"_\d+$", "", name)
        if base == "GND": p[pin] = "GND"
        elif base == "SYS_VIN_HV": p[pin] = f"M{m}_VIN_HV"
        elif base == "SYS_VIN_MV": p[pin] = f"M{m}_VIN_MV"
    p[BYNAME["SYS_VIN_SV"]] = f"M{m}_VIN_SV"
    p["MH"] = "GND"
    return p

MGMT = ["MODULE_POWER_ON", "CARRIER_POWER_ON", "SYS_RESET_N", "MODULE_POWER_GOOD", "VDDIN_PWR_BAD_N", "FORCE_RECOVERY_N",
        "MODULE_SHDN_N", "THERM_ALERT_N", "THERM_SHDN_REQ_N", "PRSNT0", "PRSNT1", "UART3_TX_DEBUG", "UART3_RX_DEBUG",
        "I2C3_CLK", "I2C3_DAT"]
for m in range(4):
    P = module_nets(m)
    for s in MGMT: P[BYNAME[s]] = f"M{m}_{s}"
    # PCIe C5 x4 (UPHY1 config #2 lanes 0-3) -> this module's own M.2 NVMe
    for k in range(4):
        P[BYNAME[f"UPHY_TX{8+k}_P"]] = f"M{m}_PCIE_TX{k}_P_AC"; P[BYNAME[f"UPHY_TX{8+k}_N"]] = f"M{m}_PCIE_TX{k}_N_AC"
        P[BYNAME[f"UPHY_RX{8+k}_P"]] = f"M{m}_PCIE_RX{k}_P"; P[BYNAME[f"UPHY_RX{8+k}_N"]] = f"M{m}_PCIE_RX{k}_N"
    P[BYNAME["UPHY_REFCLK3_P"]] = f"M{m}_PCIE_REFCLK_P"; P[BYNAME["UPHY_REFCLK3_N"]] = f"M{m}_PCIE_REFCLK_N"
    P[BYNAME["PEX_C5_RST_N"]] = f"M{m}_PCIE_PERST_N"; P[BYNAME["PEX_C5_CLKREQ_N"]] = f"M{m}_PCIE_CLKREQ_N"
    P[BYNAME["PEX_WAKE_N"]] = f"M{m}_PCIE_WAKE_N"
    # MGBE reference clock (UPHY_REFCLK2, F28/F29): 156.25 MHz HCSL from this module's own oscillator (below)
    P[BYNAME["UPHY_REFCLK2_P"]] = f"M{m}_MGBE_REFCLK_P"; P[BYNAME["UPHY_REFCLK2_N"]] = f"M{m}_MGBE_REFCLK_N"
    # MGBE C0..C2 (UPHY lanes 12-14): direct 25G links to the three other modules (a PCB trace instead of a DAC cable)
    for k, peer in enumerate(PEERS[m]):
        P[BYNAME[f"UPHY_TX{12+k}_P"]] = f"MESH_{m}{peer}_P_AC"; P[BYNAME[f"UPHY_TX{12+k}_N"]] = f"MESH_{m}{peer}_N_AC"
        P[BYNAME[f"UPHY_RX{12+k}_P"]] = f"MESH_{peer}{m}_P"; P[BYNAME[f"UPHY_RX{12+k}_N"]] = f"MESH_{peer}{m}_N"
    # MGBE C3 (UPHY lane 15) -> one lane of the QSFP28 uplink (4 x 25G breakout = one port per module)
    P[BYNAME["UPHY_TX15_P"]] = f"Q_TX{m+1}_P"; P[BYNAME["UPHY_TX15_N"]] = f"Q_TX{m+1}_N"
    P[BYNAME["UPHY_RX15_P"]] = f"Q_RX{m+1}_P"; P[BYNAME["UPHY_RX15_N"]] = f"Q_RX{m+1}_N"
    # USB 2.0 port 0 = recovery / flashing port -> rear USB-C;  module 0 USB1 -> the status panel
    P[BYNAME["USB0_P"]] = f"M{m}_USB0_P"; P[BYNAME["USB0_N"]] = f"M{m}_USB0_N"
    if m == 0: P[BYNAME["USB1_P"]] = "PANEL_USB_P"; P[BYNAME["USB1_N"]] = "PANEL_USB_N"
    P[BYNAME["FAN_PWM"]] = f"M{m}_FAN_PWM"; P[BYNAME["FAN_TACH"]] = f"M{m}_FAN_TACH"
    cx, cy = MOD[m]
    add("Console", "Jetson_T5000_Module_MirrorMezz699_Carrier", f"U{m+1}", cx, cy, 0, "Jetson T5000 (AGX Thor) 128 GB", P)

# ------------------------------------------------------------------ under each module (back side)
for m, (cx, cy) in enumerate(MOD):
    B = 100 * (m + 1)          # refs: module 0 = x1xx, module 1 = x2xx, ...
    # AC coupling caps (0201, 100 nF) just below the connector: PCIe TX (host side) + mesh TX
    i = 0
    for k in range(4):
        for pol in "PN":
            C(f"C{B+50+i}", "100nF", f"M{m}_PCIE_TX{k}_{pol}_AC", cx - 11 + i * 1.2, cy - 12, bnet=f"M{m}_PCIE_TX{k}_{pol}", fp=C0201, back=True); i += 1
    for j, peer in enumerate(PEERS[m]):
        for pol in "PN":
            C(f"C{B+50+i}", "100nF", f"MESH_{m}{peer}_{pol}_AC", cx + 2 + (i - 8) * 1.2, cy - 12, bnet=f"MESH_{m}{peer}_{pol}", fp=C0201, back=True); i += 1

    # M.2 2280 M-key NVMe (PCIe Gen4/5 x4), card along y on the left half. Standard M-key pin map.
    p = {"3": "GND", "9": "GND", "15": "GND", "21": "GND", "27": "GND", "33": "GND", "39": "GND", "45": "GND", "51": "GND",
         "57": "GND", "71": "GND", "73": "GND", "75": "GND", "MP": "GND",
         "2": "3V3", "4": "3V3", "12": "3V3", "14": "3V3", "16": "3V3", "18": "3V3", "70": "3V3", "72": "3V3", "74": "3V3"}
    for k, (rn, rp, tn, tp) in enumerate([("41", "43", "47", "49"), ("29", "31", "35", "37"), ("17", "19", "23", "25"), ("5", "7", "11", "13")]):
        p[rn] = f"M{m}_PCIE_TX{k}_N"; p[rp] = f"M{m}_PCIE_TX{k}_P"     # SSD PER (its receive) <- host TX after the AC caps
        p[tn] = f"M{m}_PCIE_RX{k}_N"; p[tp] = f"M{m}_PCIE_RX{k}_P"     # SSD PET (its transmit) -> host RX
    p.update({"53": f"M{m}_PCIE_REFCLK_N", "55": f"M{m}_PCIE_REFCLK_P", "50": f"M{m}_PCIE_PERST_N",
              "52": f"M{m}_PCIE_CLKREQ_N", "54": f"M{m}_PCIE_WAKE_N"})
    add("Connector_PCBEdge", "TE_M.2_M_2x38-1MP_P0.5mm", f"J{10+m}", cx - 25, cy - 43, 180, "M.2 2280 NVMe 4 TB", p, back=True)
    add("MountingHole", "MountingHole_2.2mm_M2_Pad_Via", f"H{10+m}", cx - 25, cy - 43 + 80.5, 0, "M.2 standoff", {"1": "GND"}, back=True)

    # MGBE refclk: 156.25 MHz HCSL oscillator, SCTF SX5DF156.250B20F30HNN (LCSC C5830692). Pinout and land pattern from
    # SCTF's 5Z spec sheet. Pin 1 tied to 3V3 = always running. SCTF specifies the same HCSL load (Rs 33, RL 50).
    # Termination per DG-12084 fig. 7-12: 33.2 R in series at the source, 49.9 R to GND on each leg.
    add("Console", "SCTF_5Z_SMD5032-6P_5.0x3.2mm", f"X{m+1}", cx + 20, cy - 6, 0, "156.25MHz HCSL",
        {"1": "3V3", "3": "GND", "4": f"M{m}_OSC_P", "5": f"M{m}_OSC_N", "6": "3V3"}, back=True)
    C(f"C{B+40}", "100nF", "3V3", cx + 25, cy - 6, back=True)
    R(f"R{B+40}", "33.2", f"M{m}_OSC_P", f"M{m}_MGBE_REFCLK_P", cx + 15, cy - 11, back=True)
    R(f"R{B+41}", "33.2", f"M{m}_OSC_N", f"M{m}_MGBE_REFCLK_N", cx + 16.2, cy - 11, back=True)
    R(f"R{B+42}", "49.9", f"M{m}_MGBE_REFCLK_P", "GND", cx + 17.4, cy - 11, back=True)
    R(f"R{B+43}", "49.9", f"M{m}_MGBE_REFCLK_N", "GND", cx + 18.6, cy - 11, back=True)

    # Power gating, so a module only sees its rails when management says so (DG-12084 ch. 5 sequencing: SV first,
    # then HV and MV; VDDIN_PWR_BAD_N held low until HV is valid).
    # HV: TPS259827ONRGER (LCSC C2155761) eFuse on 12 V. ILIM = 1470 / RILIM -> 110 R = 13.4 A (T5000 ~130 W / 12 V
    # = 11 A). IMON 246 uA/A into 470 R = 1.16 V at 10 A. dVdt 10 nF. RETRY_DLY to GND = latch off after a fault.
    def efuse(ref, x, y, vin, vout, en, pg, imon, rilim, rimon, cdvdt, rb, cb):
        add("Console", "TI_RGE0024M_VQFN-24_4x4mm_P0.5mm_SplitPad", ref, x, y, 0, "TPS259827ONRGER (C2155761)",
            {**{str(n): vin for n in (1, 2, 3, 16, 25)}, **{str(n): vout for n in range(17, 25)},
             **{str(n): "GND" for n in (4, 5, 14, 26, 10, 11, 12)},
             "6": en, "8": f"{ref}_ILIM", "9": imon, "13": pg, "15": f"{ref}_DVDT"}, back=True)
        C(f"C{cb}", "22uF", vin, x - 5, y - 1.2, rot=90, fp=C0805, back=True)
        C(f"C{cb+1}", "100nF", vin, x - 3.2, y - 1.2, back=True)
        C(f"C{cb+2}", cdvdt, f"{ref}_DVDT", x + 3.4, y + 0.8, back=True)
        R(f"R{rb}", rilim, f"{ref}_ILIM", "GND", x - 1.2, y + 4, back=True)
        R(f"R{rb+1}", rimon, imon, "GND", x, y + 4, back=True)
        R(f"R{rb+2}", "100k", en, "GND", x - 2.4, y + 4, back=True)       # off unless management drives EN high
        R(f"R{rb+3}", "10k", "3V3", pg, x + 1.2, y + 4, back=True)          # PG is open drain
    efuse(f"U{B+1}", cx + 10, cy + 12, "VIN_12V", f"M{m}_VIN_HV", f"M{m}_HV_EN", f"M{m}_HV_PG", f"M{m}_HV_IMON",
          "110", "470", "10nF", B + 1, B + 1)
    # MV: the same eFuse on 5 V. NVIDIA gives no SYS_VIN_MV current, so the limit is an assumption: 182 R = 8.1 A.
    efuse(f"U{B+2}", cx + 28, cy + 12, "5V", f"M{m}_VIN_MV", f"M{m}_MV_EN", f"M{m}_MV_PG", f"M{m}_MV_IMON",
          "182", "1k", "3.3nF", B + 11, B + 11)
    # SV (3.3 V safety-logic rail, L53): TPS22918DBVR (LCSC C131941) load switch. 1 VIN, 2 GND, 3 ON, 4 CT, 5 QOD, 6 VOUT.
    # QOD tied to VOUT = quick output discharge through the internal resistor (SV must fall after HV and MV).
    add("Package_TO_SOT_SMD", "SOT-23-6", f"U{B+3}", cx + 10, cy + 28, 0, "TPS22918DBVR (C131941)",
        {"1": "3V3", "2": "GND", "3": f"M{m}_SV_EN", "4": f"U{B+3}_CT", "5": f"M{m}_VIN_SV", "6": f"M{m}_VIN_SV"}, back=True)
    C(f"C{B+21}", "1uF", "3V3", cx + 6, cy + 28, back=True)
    C(f"C{B+22}", "1nF", f"U{B+3}_CT", cx + 14, cy + 28, back=True)
    R(f"R{B+21}", "100k", f"M{m}_SV_EN", "GND", cx + 15.2, cy + 28, back=True)

    # management header 2x20 1.27 mm (back): odd pins = this module's control signals, even pins = GND
    sig = MGMT + ["HV_EN", "HV_PG", "MV_EN", "SV_EN", "3V3_STBY"]
    hp = {str(2 * i + 1): (f"M{m}_{s}" if s != "3V3_STBY" else "3V3") for i, s in enumerate(sig)}
    hp.update({str(2 * i + 2): "GND" for i in range(20)})
    add("Connector_PinHeader_1.27mm", "PinHeader_2x20_P1.27mm_Vertical_SMD", f"J{20+m}", cx + 20, cy + 42, 90, f"MGMT M{m}", hp, back=True)

    # fan header per module (top side, in the centre channel): 1 GND, 2 +12V, 3 TACH, 4 PWM
    fx = 107.0 if m % 2 == 0 else 127.5
    add("Connector", "FanPinHeader_1x04_P2.54mm_Vertical", f"J{30+m}", fx, cy - 25, 0, f"FAN M{m}",
        {"1": "GND", "2": "VIN_12V", "3": f"M{m}_FAN_TACH", "4": f"M{m}_FAN_PWM"})

# ------------------------------------------------------------------ bottom strip (y 214-256): power in, bucks, rear I/O
# 12 V in: 2 x Molex Mini-Fit Jr 2x4 (EPS-12V style: 1-4 GND, 5-8 +12 V). With HCS terminals ~13 A per pin = ~100 A total
# for ~50 A peak (4 x 130 W modules + NVMe + fans ~ 600 W), so either cable alone carries the board.
for j, x in (("J1", 16.0), ("J5", 40.0)):
    add("Connector_Molex", "Molex_Mini-Fit_Jr_5566-08A_2x04_P4.20mm_Vertical", j, x, 240.0, 0, "12V IN (EPS 8-pin)",
        {**{str(i): "GND" for i in range(1, 5)}, **{str(i): "VIN_12V" for i in range(5, 9)}})

# Two TI TPS546B24ARVFR (LCSC C3189423) 20 A PMBus bucks from 12 V. Pin straps (TI datasheet tables 7-x, Rtop to BP1V5,
# Rbot to AGND, 1 %): VSEL sets Vout, MSEL1 = 550 kHz + compensation 19, MSEL2 = 3 ms soft start + stand-alone + 20/26 A
# OC, ADRSEL = PMBus address. The compensation choice still has to be checked in TI's design tool for this LC filter.
# Power stage: Coilcraft XAL7070-102MEC 1 uH (LCSC C6609502), 6 x 47 uF 10 V 1210 out, 4 x 22 uF 25 V 0805 + 10 nF in.
def buck(base, gx, vout, en, pg, straps, en_parts):
    u = f"U{base}"
    pins = {str(n): "GND" for n in (*range(13, 21), 36, 37, 39, 40, 41)}   # PGND, NC, AGND, BCX_CLK/DAT (stand-alone), pad
    pins.update({str(n): "VIN_12V" for n in range(21, 26)})
    pins.update({str(n): f"{u}_SW" for n in range(8, 13)})
    pins.update({"1": pg, "2": "PMBUS_DAT", "3": "PMBUS_CLK", "4": f"{u}_BP1V5", "5": f"{u}_DRTN", "6": "PMBUS_ALERT_N",
                 "7": f"{u}_BOOT", "26": f"{u}_AVIN", "27": en, "28": f"{u}_VDD5", "29": f"{u}_MSEL2", "30": f"{u}_VSEL",
                 "31": f"{u}_ADRSEL", "32": f"{u}_MSEL1", "33": vout, "34": "GND"})      # 35 VSHARE + 38 SYNC float
    add("Console", "TI_RVF0040A_LQFN-CLIP-40_5x7mm_P0.5mm_EP3.3x5.3mm", u, gx + 5, 224, 0, "TPS546B24ARVFR (C3189423)", pins)
    for i in range(4): C(f"C{base+i}", "22uF", "VIN_12V", gx + 10, 219 + i * 2.2, rot=0, fp=C0805)
    C(f"C{base+4}", "10nF", "VIN_12V", gx + 10, 227.8, rot=0)
    add("Inductor_SMD", "L_Coilcraft_XAL7070-XXX", f"L{base}", gx + 5, 236, 0, "XAL7070-102MEC 1uH (C6609502)",
        {"1": f"{u}_SW", "2": vout})
    for i in range(6): C(f"C{base+10+i}", "47uF", vout, gx + 2 + i * 3.6, 246, rot=90, fp=C1210)
    # small parts grid right of the inductor: 5 columns x 3 rows of 0402 + one 0603 row
    grid = [(gx + 12 + 2 * c, 230 + 3 * r) for r in range(3) for c in range(5)]
    small = [("C", "1uF", f"{u}_BP1V5", f"{u}_DRTN"),         # BP1V5 bypass returns to DRTN only (datasheet: DRTN not to PGND/AGND)
             ("C", "100nF", f"{u}_BOOT", f"{u}_SW"),
             ("R", "10", "VIN_12V", f"{u}_AVIN"), ("C", "1uF", f"{u}_AVIN", "GND"),     # AVIN RC filter (10 us)
             ("R", "10k", "3V3", pg)] + en_parts
    for name, (rt, rb) in straps.items():
        if rt: small.append(("R", rt, f"{u}_BP1V5", f"{u}_{name}"))
        small.append(("R", rb, f"{u}_{name}", "GND"))
    assert len(small) <= len(grid), (u, len(small))
    ci = ri = 0
    for (kind, val, a, bn), (x, y) in zip(small, grid):
        if kind == "C": C(f"C{base+20+ci}", val, a, x, y, bnet=bn); ci += 1
        else: R(f"R{base+ri}", val, a, bn, x, y); ri += 1
    C(f"C{base+30}", "4.7uF", f"{u}_VDD5", gx + 16, 239.5, rot=0, fp=C0603)           # VDD5 >= 4.7 uF, 10 V
#              VSEL (Rtop, Rbot)   MSEL1          MSEL2              ADRSEL
buck(501, 58, "5V", "BUCK5_EN", "BUCK5_PG",
     {"VSEL": ("1.87k", "12.1k"), "MSEL1": (None, "31.6k"), "MSEL2": ("11.5k", "4.64k"), "ADRSEL": (None, "4.64k")},   # 5.0 V, PMBus 0x10
     [("R", "100k", "BUCK5_EN", "GND")])                                                                    # on when management says so
buck(601, 84, "3V3", "BUCK3_EN", "BUCK3_PG",
     {"VSEL": ("12.1k", "21.5k"), "MSEL1": (None, "31.6k"), "MSEL2": ("11.5k", "4.64k"), "ADRSEL": (None, "5.62k")},   # 3.32 V, PMBus 0x11
     [("R", "100k", "VIN_12V", "BUCK3_EN"), ("R", "15k", "BUCK3_EN", "GND")])  # always-on standby rail: EN/UVLO 1.1 V -> starts at ~8.4 V in
# PMBus pull-ups (one set for both bucks)
R("R701", "4.7k", "3V3", "PMBUS_CLK", 150, 226); R("R702", "4.7k", "3V3", "PMBUS_DAT", 151.2, 226); R("R703", "10k", "3V3", "PMBUS_ALERT_N", 152.4, 226)

# rear I/O along the bottom edge: QSFP28 uplink, 4 x USB-C recovery, status panel
QS = {"SH": "GND", "1": "GND", "4": "GND", "7": "GND", "13": "GND", "16": "GND", "19": "GND", "20": "GND", "23": "GND", "26": "GND",
      "32": "GND", "35": "GND", "38": "GND", "10": "3V3", "29": "3V3", "30": "3V3",
      "36": "Q_TX1_P", "37": "Q_TX1_N", "3": "Q_TX2_P", "2": "Q_TX2_N", "33": "Q_TX3_P", "34": "Q_TX3_N", "6": "Q_TX4_P", "5": "Q_TX4_N",
      "17": "Q_RX1_P", "18": "Q_RX1_N", "22": "Q_RX2_P", "21": "Q_RX2_N", "14": "Q_RX3_P", "15": "Q_RX3_N", "25": "Q_RX4_P", "24": "Q_RX4_N",
      "8": "QSFP_MODSEL_N", "9": "QSFP_RESET_N", "11": "QSFP_SCL", "12": "QSFP_SDA", "27": "QSFP_MODPRS_N", "28": "QSFP_INT_N", "31": "QSFP_LPMODE"}
add("Console", "TE_2170704_QSFP28_Cage_SFF8679_38P", "J2", 120, H - 37.0, 0, "QSFP28 4x25G uplink", QS)   # centre channel, cage end at the rear edge
for m in range(4):
    add("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", f"J{40+m}", 162 + m * 13, H - 4.2, 0, f"USB-C M{m} recovery",
        {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "SH": "GND", "A6": f"M{m}_USB0_P", "B6": f"M{m}_USB0_P",
         "A7": f"M{m}_USB0_N", "B7": f"M{m}_USB0_N", "A5": f"M{m}_CC1", "B5": f"M{m}_CC2",
         "A4": f"M{m}_USB_VBUS", "B9": f"M{m}_USB_VBUS", "A9": f"M{m}_USB_VBUS", "B4": f"M{m}_USB_VBUS"})
    R(f"R{10+2*m}", "5.1k", f"M{m}_CC1", "GND", 162 + m * 13 - 2, H - 12, rot=0)
    R(f"R{11+2*m}", "5.1k", f"M{m}_CC2", "GND", 162 + m * 13 + 2, H - 12, rot=0)
# status panel cable (the black CyberCore status panel): JST PH 4-pin: 1 5V, 2 D-, 3 D+, 4 GND
add("Connector_JST", "JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "J3", 140, 246, 0, "STATUS PANEL",
    {"1": "5V", "2": "PANEL_USB_N", "3": "PANEL_USB_P", "4": "GND"})
# system management header: buck control + PMBus, MV power-good, HV current monitors, QSFP sideband (odd), GND (even)
SYS = ["BUCK5_EN", "BUCK5_PG", "PMBUS_CLK", "PMBUS_DAT"] + [f"M{m}_MV_PG" for m in range(4)] + [f"M{m}_HV_IMON" for m in range(4)] + \
      ["QSFP_MODSEL_N", "QSFP_RESET_N", "QSFP_SCL", "QSFP_SDA", "QSFP_MODPRS_N", "QSFP_INT_N", "QSFP_LPMODE", "3V3"]
assert len(SYS) == 20
sp = {str(2 * i + 1): s for i, s in enumerate(SYS)}; sp.update({str(2 * i + 2): "GND" for i in range(20)})
add("Connector_PinHeader_1.27mm", "PinHeader_2x20_P1.27mm_Vertical_SMD", "J4", 190, 228, 90, "SYS MGMT", sp)

# corner mounting holes (case)
for i, (x, y) in enumerate([(4.5, 4.5), (W - 4.5, 4.5), (4.5, H - 4.5), (W - 4.5, H - 4.5)]):
    add("MountingHole", "MountingHole_3.2mm_M3_Pad_Via", f"H{1+i}", x, y, 0, "case", {"1": "GND"})

# ------------------------------------------------------------------ outline, planes, silk
def edge_line(a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pt(*a)); s.SetEnd(pt(*c)); s.SetWidth(FromMM(0.1)); b.Add(s)
def edge_arc(cx, cy, a0):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1))
    s.SetArcGeometry(*(pt(cx + RC * math.cos(math.radians(a0 + k * 45)), cy + RC * math.sin(math.radians(a0 + k * 45))) for k in range(3))); b.Add(s)
edge_line((RC, 0), (W - RC, 0)); edge_line((W, RC), (W, H - RC)); edge_line((W - RC, H), (RC, H)); edge_line((0, H - RC), (0, RC))
edge_arc(W - RC, RC, 270); edge_arc(W - RC, H - RC, 0); edge_arc(RC, H - RC, 90); edge_arc(RC, RC, 180)
for layer, nm in ((pcbnew.In1_Cu, "GND"), (pcbnew.In2_Cu, "VIN_12V"), (pcbnew.In3_Cu, "GND"), (pcbnew.In10_Cu, "GND")):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net(nm)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetLocalClearance(FromMM(0.2)); ol = z.Outline(); ol.NewOutline()
    for x, y in [(1, 1), (W - 1, 1), (W - 1, H - 1), (1, H - 1)]: ol.Append(*pt(x, y))
    b.Add(z)
def text(s, x, y, size, layer=pcbnew.F_SilkS, thick=None):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetLayer(layer); t.SetPosition(pt(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(thick or max(0.15, size * 0.15)))
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    b.Add(t)
for m, (cx, cy) in enumerate(MOD): text(f"THOR {m}", cx, cy + 20, 2.5)
text("CyberCore", 30.0, 222.0, 4.0, thick=0.7)
text("CONSOLE rev 0.2 PoC | 4 x T5000 | 512 GB", 30.0, 228.0, 1.0)
text("CyberCore Console rev 0.2 PoC (unrouted)  |  open hardware  |  github.com/Louistuis/cybercore", 120, 109.5, 1.6, pcbnew.B_SilkS)

out = os.path.join(HERE, "console.kicad_pcb")
b.Save(out)
# black mask, white silk, ENIG (same stackup block as the status panel)
s = open(out).read()
stack = ['\t\t(stackup', '\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))', '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
         '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "#060606F5") (thickness 0.01))']
cu = ["F.Cu"] + [f"In{i}.Cu" for i in range(1, 11)] + ["B.Cu"]
for i, l in enumerate(cu):
    stack.append(f'\t\t\t(layer "{l}" (type "copper") (thickness 0.035))')
    if i < len(cu) - 1:
        stack.append(f'\t\t\t(layer "dielectric {i+1}" (type "{"core" if i % 2 == 0 else "prepreg"}") (color "FR4 natural") (thickness 0.1) (material "FR4") (epsilon_r 4.1) (loss_tangent 0.008))')
stack += ['\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "#060606F5") (thickness 0.01))', '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))',
          '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))', '\t\t\t(copper_finish "ENIG")', '\t\t\t(dielectric_constraints no)', '\t\t)']
if "(stackup" not in s:
    i = s.index("(setup") + len("(setup"); s = s[:i] + "\n" + "\n".join(stack) + "\n" + s[i:]; open(out, "w").write(s)
# Design rules (HDI class for the fine-pitch module connector) live in console.kicad_pro, which is kept in the repo as a
# source file: min clearance 0.10, min track 0.09, via 0.30/0.15, copper-edge 0.25.
single = [n for n in nets if sum(1 for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == n) < 2]
print(f"wrote {out}: {len(b.GetFootprints())} footprints, {len(nets)} nets; one-pad nets: {single}")
