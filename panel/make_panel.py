"""CyberCore status panel rev 1.0: places every part from parts.py, assigns nets, draws the outline and silkscreen,
sets JLCPCB 2-layer rules, writes panel.kicad_pcb. Run with KiCad's python:  KPY make_panel.py
Then: route.py export -> Freerouting -> route.py import (see ../README.md / PANEL.md).

Board 150 x 50 mm, 2 layers, 1.6 mm, all parts on the front (the side that faces you through the server bezel).
Coordinates below: mm from the board's top-left corner, y down (KiCad's own direction), shifted by ORIGIN when placed."""
import os, sys, math, importlib.util, pcbnew
from pcbnew import FromMM, VECTOR2I, EDA_ANGLE, DEGREES_T
HERE = os.path.dirname(os.path.abspath(__file__))
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
spec = importlib.util.spec_from_file_location("parts", os.path.join(HERE, "parts.py"))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
W, H, RC = 150.0, 50.0, 3.0
OX, OY = 100.0, 100.0
pt = lambda x, y: VECTOR2I(FromMM(OX + x), FromMM(OY + y))

# ------------------------------------------------------------------ placement (x, y, rotation deg)
POS = {
    "U1": (112.0, 13.05, 0),          # module top edge 0.3 mm inside the board edge; antenna keep-out comes with the footprint
    "C6": (99.5, 9.0, 0), "C7": (99.5, 11.5, 0),
    "R1": (97.0, 24.5, 0), "C3": (97.0, 26.5, 0), "R2": (100.0, 24.5, 90),
    "SW1": (90.0, 31.0, 0), "SW2": (99.0, 31.0, 0),
    "TP1": (93.0, 12.0, 0), "TP2": (93.0, 15.0, 0), "TP3": (93.0, 18.0, 0), "TP4": (93.0, 21.0, 0),
    "J1": (146.3, 22.0, 90), "U3": (138.6, 22.0, 0), "R5": (138.6, 17.5, 0), "R6": (138.6, 26.5, 0),
    "F1": (140.5, 32.0, 90), "C1": (137.0, 31.5, 90), "U2": (130.0, 31.0, 0), "C2": (123.0, 31.0, 90),
    "U4": (118.0, 31.0, 0), "C8": (114.5, 31.0, 90), "R4": (118.0, 35.5, 0),
    "C4": (75.0, 33.0, 0), "C5": (40.0, 33.0, 0),
    "SW3": (12.0, 30.0, 0), "R3": (12.0, 25.5, 0),
    "J2": (52.0, 6.0, 90),            # pin 1 at (52, 6), pins run to the right
    "J3": (80.0, 3.6, 180), "R7": (77.0, 8.6, 0), "R8": (83.0, 8.6, 0),
    "H1": (4.0, 4.0, 0), "H2": (146.0, 4.0, 0), "H3": (4.0, 46.0, 0), "H4": (146.0, 46.0, 0),
}
for i in range(16):                   # LED bar, D1 at the right (next to U4) to D16 at the left
    x = 137.0 - i * 124.0 / 15
    POS[f"D{i+1}"] = (x, 44.0, 0); POS[f"C{10+i}"] = (x, 38.8, 0)

b = pcbnew.BOARD()
ds = b.GetDesignSettings()
b.SetCopperLayerCount(2)
ds.SetBoardThickness(FromMM(1.6))
# JLCPCB standard 2-layer with margin
ds.m_MinClearance = FromMM(0.15); ds.m_TrackMinWidth = FromMM(0.15); ds.m_ViasMinSize = FromMM(0.6)
ds.m_MinThroughDrill = FromMM(0.3); ds.m_HoleClearance = FromMM(0.25); ds.m_CopperEdgeClearance = FromMM(0.3)
ns = ds.m_NetSettings
d = ns.GetDefaultNetclass(); d.SetClearance(FromMM(0.15)); d.SetTrackWidth(FromMM(0.2))
d.SetViaDiameter(FromMM(0.6)); d.SetViaDrill(FromMM(0.3))
for name, width, nets in (("Power", 0.5, ["GND", "VBUS", "5V", "3V3"]), ("USB", 0.3, ["USB_DP", "USB_DN"])):
    nc = pcbnew.NETCLASS(name); nc.SetClearance(FromMM(0.2)); nc.SetTrackWidth(FromMM(width))
    nc.SetViaDiameter(FromMM(0.6 if name == "USB" else 0.8)); nc.SetViaDrill(FromMM(0.3 if name == "USB" else 0.4))
    ns.SetNetclass(name, nc)
    for n in nets: ns.SetNetclassPatternAssignment(n, name)

nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
    return nets[name]

problems = []
for p in P.PARTS:
    lib, name = p["fp"].split(":")
    f = pcbnew.FootprintLoad(STOCK + lib + ".pretty", name)
    if f is None: problems.append(f"{p['ref']}: footprint {p['fp']} missing"); continue
    f.SetReference(p["ref"]); f.SetValue(p["value"])
    x, y, rot = POS[p["ref"]]
    f.SetPosition(pt(x, y)); f.SetOrientation(EDA_ANGLE(rot, DEGREES_T))
    if p.get("board_only"): f.SetBoardOnly(True); f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
    elif p["fp"].startswith("TestPoint"): f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
    f.Value().SetVisible(False)
    f.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); f.Reference().SetTextThickness(FromMM(0.12))
    f.Reference().SetLayer(pcbnew.F_Fab)   # the front face is the product: refs go on the assembly (fab) layer
    seen = set()
    for pad in f.Pads():
        # the module footprint's thermal vias are 0.2 mm; JLC's standard 2-layer minimum is 0.3 mm
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetDrillSize().x < FromMM(0.3):
            pad.SetDrillSize(VECTOR2I(FromMM(0.3), FromMM(0.3)))
            if pad.GetSize(pcbnew.F_Cu).x < FromMM(0.6): pad.SetSize(pcbnew.F_Cu, VECTOR2I(FromMM(0.6), FromMM(0.6)))
        n = pad.GetNumber()
        if not n: continue
        seen.add(n)
        if n in p["pins"]:
            pad.SetNet(net(p["pins"][n]))
            if p["ref"] == "J1" and p["pins"][n] == "GND": pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        elif n not in p["nc"]: problems.append(f"{p['ref']}: pad {n} not assigned")
    for n in list(p["pins"]) + list(p["nc"]):
        if n not in seen: problems.append(f"{p['ref']}: pad {n} not in footprint")
    if p["ref"] == "J1":   # its silk outline runs along the board edge at the plug mouth; the label says what it is
        for g in list(f.GraphicalItems()):
            if g.GetLayer() == pcbnew.F_SilkS: f.Remove(g)
    b.Add(f)

# one-pin nets are wiring mistakes (except the LED chain end, which is an nc pad)
count = {}
for p in P.PARTS:
    for n in p["pins"].values(): count[n] = count.get(n, 0) + 1
for n, c in count.items():
    if c < 2: problems.append(f"net {n} has only one pad")

# ------------------------------------------------------------------ outline: rounded rectangle
def edge_line(a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pt(*a)); s.SetEnd(pt(*c)); s.SetWidth(FromMM(0.1)); b.Add(s)
def edge_arc(cx, cy, a0):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1))
    r = RC; ang = [math.radians(a0 + k * 45) for k in range(3)]
    s.SetArcGeometry(*(pt(cx + r * math.cos(t), cy + r * math.sin(t)) for t in ang)); b.Add(s)
edge_line((RC, 0), (W - RC, 0)); edge_line((W, RC), (W, H - RC)); edge_line((W - RC, H), (RC, H)); edge_line((0, H - RC), (0, RC))
edge_arc(W - RC, RC, 270); edge_arc(W - RC, H - RC, 0); edge_arc(RC, H - RC, 90); edge_arc(RC, RC, 180)

# ------------------------------------------------------------------ silkscreen
def text(s, x, y, size, layer=pcbnew.F_SilkS, thick=None, rot=0, just=None):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetLayer(layer); t.SetPosition(pt(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(thick or max(0.15, size * 0.15)))
    t.SetTextAngle(EDA_ANGLE(rot, DEGREES_T))
    if just == "left": t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    b.Add(t)
text("CyberCore", 30.0, 15.0, 7.0, thick=1.1)
text("STATUS PANEL   rev 1.0", 30.0, 21.5, 1.8, thick=0.3)
text("DISPLAY", 61.0, 2.2, 1.0)
for i, lab in enumerate(["3V3", "GND", "DIN", "CLK", "CS", "DC", "RST", "BUSY"]):
    text(lab, 52.0 + i * 2.54, 10.6, 0.9, rot=90)
text("QWIIC", 80.0, 10.6, 0.9)
for i, lab in enumerate(["TX", "RX", "GND", "3V3"]):
    text(lab, 89.2, 12.0 + 3 * i, 0.9)
text("RESET", 90.0, 35.2, 1.0); text("BOOT", 99.0, 35.2, 1.0); text("PAGE", 12.0, 34.4, 1.0)
text("USB-C 5V", 147.6, 34.0, 1.0, rot=90)
text("CyberCore status panel rev 1.0  |  Louis Studios hardware-lab  |  2026-11-16", 75.0, 25.0, 1.5, layer=pcbnew.B_SilkS)
text("ESP32-S3  |  USB-C 5 V  |  16 x RGB  |  SPI display  |  Qwiic", 75.0, 29.0, 1.2, layer=pcbnew.B_SilkS)

out = os.path.join(HERE, "panel.kicad_pcb")
b.Save(out)
for x in problems: print("PROBLEM:", x)
print(f"wrote {out}: {len(b.GetFootprints())} footprints, {len(nets)} nets, {len(problems)} problem(s)")
j2 = b.FindFootprintByReference("J2"); j1 = b.FindFootprintByReference("J1")
print("J2 pads:", [(p.GetNumber(), round(pcbnew.ToMM(p.GetPosition().x) - OX, 2), round(pcbnew.ToMM(p.GetPosition().y) - OY, 2)) for p in j2.Pads()][:3])
print("J1 A5 at:", [(round(pcbnew.ToMM(p.GetPosition().x) - OX, 2), round(pcbnew.ToMM(p.GetPosition().y) - OY, 2)) for p in j1.Pads() if p.GetNumber() == "A5"])
sys.exit(1 if problems else 0)
