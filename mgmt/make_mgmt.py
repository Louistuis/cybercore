# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore management board rev 1.0: places every part from parts.py, assigns nets, draws the outline and silkscreen,
sets JLCPCB rules (route.py makes it 6 layers), writes mgmt.kicad_pcb. Run with KiCad's python:  KPY make_mgmt.py
Then: route.py export -> Freerouting -> route.py import (see README.md).

Board 132 x 72 mm, 6 layers after route.py (F.Cu, In1 GND, In2 + In3 signal, In4 3V3, B.Cu), 1.6 mm,
all parts on the front. Coordinates: mm from the board's top-left corner, y down, shifted by ORIGIN when placed.
Layout: the four module headers (J20-J23) along the top edge, each with its own block of logic underneath in the same
30 mm column; ESP32 (antenna at the bottom edge), the two USB-C ports, power and the SYS header (J4) along the bottom.
ICs have fixed positions below; passives are placed by a greedy search next to the pad they connect to."""
import os, sys, math, importlib.util, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, EDA_ANGLE, DEGREES_T
HERE = os.path.dirname(os.path.abspath(__file__))
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
spec = importlib.util.spec_from_file_location("parts", os.path.join(HERE, "parts.py"))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
W, H, RC = 132.0, 72.0, 3.0
OX, OY = 100.0, 100.0
pt = lambda x, y: VECTOR2I(FromMM(OX + x), FromMM(OY + y))
BY = {p["ref"]: p for p in P.PARTS}

# ------------------------------------------------------------------ fixed placement (x, y, rotation deg)
POS = {}
for m in range(4):
    x0 = 6.0 + 30.0 * m; b = 100 * (m + 1)
    POS[f"J{20+m}"] = (x0 + 2.9, 4.5, 90)        # pin 1 left, odd (signal) row towards the logic, GND row at the edge
    POS[f"U{b+2}"] = (x0 + 4.0, 13.0, 90)        # readers A: SYS_RESET_N, MODULE_POWER_GOOD, VDDIN_PWR_BAD_N, SHDN
    POS[f"U{b+4}"] = (x0 + 10.6, 13.0, 90)       # 74LVC07 open-drain pull-downs
    POS[f"U{b+3}"] = (x0 + 17.2, 13.0, 90)       # readers B: THERM_ALERT_N, THERM_SHDN_REQ_N, UART3_TX
    POS[f"U{b+9}"] = (x0 + 23.0, 12.0, 90)       # PCA9306
    POS[f"U{b+7}"] = (x0 + 27.0, 12.0, 90)       # UART3_RX driver on VIO
    POS[f"U{b+6}"] = (x0 + 3.0, 22.0, 0)         # MODULE_POWER_ON gate (5 V)
    POS[f"U{b+8}"] = (x0 + 8.4, 22.0, 0)         # VIO load switch
    POS[f"U{b+5}"] = (x0 + 25.0, 21.0, 0)        # PCA9306 enable
    POS[f"U{b+1}"] = (x0 + 15.5, 31.0, 90)       # TCA9535
POS.update({
    "U1": (66.0, H - 13.05, 180),                # ESP32, antenna at the bottom edge (module edge 0.3 mm inside)
    "J2": (13.0, H - 3.7, 0), "U4": (13.0, 60.0, 0), "U2": (17.0, 48.5, 180),     # consoles USB-C + CH344Q
    "J1": (33.0, H - 3.7, 0), "U3": (33.0, 60.0, 0),                              # MCU USB-C
    "U5": (86.0, 39.5, 0), "U6": (93.0, 39.5, 0), "L1": (93.0, 43.0, 0),          # 1V8 LDO, 5V boost
    "C26": (79.0, 38.5, 90), "C27": (81.5, 38.5, 90),
    "SW1": (84.0, 52.0, 0), "SW2": (84.0, 59.0, 0), "D1": (79.5, 47.5, 180),
    "U7": (109.0, 53.0, 90),                     # SYS expander
    "J4": (121.0, H - 4.5, 270),                 # SYS header: pin 1 right, pins run left, GND row at the edge
    "J3": (W - 3.6, 42.0, 90),                   # Qwiic, mouth at the right edge
    "H1": (3.5, 3.5, 0), "H2": (W - 3.5, 3.5, 0), "H3": (3.5, H - 3.5, 0), "H4": (W - 3.5, H - 3.5, 0),
})

b = pcbnew.BOARD()
ds = b.GetDesignSettings()
b.SetCopperLayerCount(4)
b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)          # solid GND plane: Freerouting drops vias into it
ds.SetBoardThickness(FromMM(1.6))
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
    return nets[name]

# ------------------------------------------------------------------ footprints
problems, fps = [], {}
for p in P.PARTS:
    lib, name = p["fp"].split(":")
    f = pcbnew.FootprintLoad(STOCK + lib + ".pretty", name)
    if f is None: problems.append(f"{p['ref']}: footprint {p['fp']} missing"); continue
    f.SetReference(p["ref"]); f.SetValue(p["value"])
    if p.get("board_only"): f.SetBoardOnly(True); f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
    elif p["fp"].startswith("TestPoint"): f.SetExcludedFromBOM(True); f.SetExcludedFromPosFiles(True)
    f.Value().SetVisible(False)
    f.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); f.Reference().SetTextThickness(FromMM(0.12))
    f.Reference().SetLayer(pcbnew.F_Fab)
    seen = set()
    for pad in f.Pads():
        # the ESP32 footprint's thermal vias are 0.2 mm; JLC's standard minimum is 0.3 mm (same fix as the panel)
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetDrillSize().x < FromMM(0.3):
            pad.SetDrillSize(VECTOR2I(FromMM(0.3), FromMM(0.3)))
            if pad.GetSize(pcbnew.F_Cu).x < FromMM(0.6): pad.SetSize(pcbnew.F_Cu, VECTOR2I(FromMM(0.6), FromMM(0.6)))
        n = pad.GetNumber()
        if not n: continue
        seen.add(n)
        if n in p["pins"]: pad.SetNet(net(p["pins"][n]))
        elif n not in p["nc"]: problems.append(f"{p['ref']}: pad {n} not assigned")
    for n in list(p["pins"]) + list(p["nc"]):
        if n not in seen: problems.append(f"{p['ref']}: pad {n} not in footprint")
    if name.startswith("USB_C_Receptacle"):        # silk outline runs over the board edge at the plug mouth
        for g in list(f.GraphicalItems()):
            if g.GetLayer() == pcbnew.F_SilkS: f.Remove(g)
    fps[p["ref"]] = f

count = {}
for p in P.PARTS:
    for n in p["pins"].values(): count[n] = count.get(n, 0) + 1
for n, c in count.items():
    if c < 2: problems.append(f"net {n} has only one pad")

# ------------------------------------------------------------------ placement
def bbox(f, margin=0.12):
    f.BuildCourtyardCaches()
    c = f.GetCourtyard(pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (ToMM(bb.GetX()) - OX - margin, ToMM(bb.GetY()) - OY - margin,
            ToMM(bb.GetRight()) - OX + margin, ToMM(bb.GetBottom()) - OY + margin)
taken = []
def hit(r, edge=True):
    if edge and (r[0] < 0.6 or r[1] < 0.6 or r[2] > W - 0.6 or r[3] > H - 0.6): return True
    return any(r[0] < t[2] and r[2] > t[0] and r[1] < t[3] and r[3] > t[1] for t in taken)
def put(f, x, y, rot):
    f.SetPosition(pt(x, y)); f.SetOrientation(EDA_ANGLE(rot, DEGREES_T))
for ref, (x, y, rot) in POS.items():
    f = fps[ref]; put(f, x, y, rot)
    if ref == "U1":     # module body + antenna keep-out band at the board edge (the courtyard bbox is the whole T shape)
        taken.append((x - 10.6, y - 13.6, x + 10.6, y + 13.6)); taken.append((x - 24.2, H - 6.3, x + 24.2, H))
    elif ref.startswith("H"): taken.append((x - 3.6, y - 3.6, x + 3.6, y + 3.6))
    else:
        r = bbox(f)
        if hit(r, edge=not ref.startswith('J')): problems.append(f"{ref}: fixed position overlaps {[round(v,2) for v in r]} with {[ [round(v,2) for v in t] for t in taken if r[0] < t[2] and r[2] > t[0] and r[1] < t[3] and r[3] > t[1]]}")
        taken.append(r)

for m in range(4):        # room for the "J2x MODULE m" silk label under each header
    taken.append((6.0 + 30.0 * m + 9.0, 6.6, 6.0 + 30.0 * m + 21.0, 8.3))

taken.append((25.0, 36.6, 55.0, 45.0))   # front title
taken.append((7.0, 55.0, 19.0, 56.8)); taken.append((27.0, 55.0, 39.0, 56.8))   # USB labels

def target(p):
    """where a free part wants to be: the pad of its 'near' part that shares a signal net, else that part's centre"""
    nf = fps.get(p.get("near") or "")
    if nf is None: return (W / 2, 38.0)
    mine = [n for n in p["pins"].values() if n not in ("GND",)]
    best = None
    for pad in nf.Pads():
        if pad.GetNetname() in mine:
            pos = (ToMM(pad.GetPosition().x) - OX, ToMM(pad.GetPosition().y) - OY)
            if best is None or pad.GetNetname() not in ("3V3",): best = pos
            if pad.GetNetname() not in ("3V3", "5V_AO", "1V8"): break
    if best: return best
    c = nf.GetPosition(); return (ToMM(c.x) - OX, ToMM(c.y) - OY)

free = [p for p in P.PARTS if p["ref"] not in POS]
free.sort(key=lambda p: (0 if p["fp"].startswith(("Package", "Crystal", "LED", "Inductor")) else 1, p["ref"]))
for p in free:
    f = fps[p["ref"]]; tx, ty = target(p); done = False
    for rad in [i * 0.25 for i in range(0, 120)]:
        steps = max(1, int(rad * 8))
        for k in range(steps):
            a = 2 * math.pi * k / steps
            x, y = round((tx + rad * math.cos(a)) * 4) / 4, round((ty + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90):
                put(f, x, y, rot); r = bbox(f)
                if not hit(r): taken.append(r); done = True; break
            if done: break
        if done: break
    if not done: problems.append(f"{p['ref']}: no free spot near {p.get('near')}")

for f in fps.values(): b.Add(f)

# ------------------------------------------------------------------ outline: rounded rectangle
def edge_line(a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pt(*a)); s.SetEnd(pt(*c)); s.SetWidth(FromMM(0.1)); b.Add(s)
def edge_arc(cx, cy, a0):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1))
    ang = [math.radians(a0 + k * 45) for k in range(3)]
    s.SetArcGeometry(*(pt(cx + RC * math.cos(t), cy + RC * math.sin(t)) for t in ang)); b.Add(s)
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
for m in range(4):
    x0 = 6.0 + 30.0 * m
    text(f"J{20+m}  MODULE {m}", x0 + 15.0, 7.4, 1.0)
    text("1", x0 + 1.4, 4.5, 0.9)
text("J4  SYS", 108.9, H - 7.4, 1.0); text("1", 122.6, H - 4.5, 0.9)
text("CONSOLES", 13.0, 55.9, 1.0); text("MCU USB", 33.0, 55.9, 1.0)
text("RESET", 89.5, 52.0, 0.9, rot=90); text("BOOT", 89.5, 59.0, 0.9, rot=90)
text("QWIIC", W - 7.6, 42.0, 0.9, rot=90)
text("CyberCore", 40.0, 39.0, 4.0, thick=0.65)
text("MANAGEMENT  rev 1.0", 40.0, 44.0, 1.3, thick=0.2)
text("CyberCore management board rev 1.0  |  Louis Studios hardware-lab  |  2026-11-17", W / 2, 38.0, 1.4, layer=pcbnew.B_SilkS)
text("ESP32-S3  |  power sequencing for 4 x Jetson T5000  |  CERN-OHL-S-2.0", W / 2, 41.0, 1.2, layer=pcbnew.B_SilkS)
text("github.com/Louistuis/cybercore", W / 2, 44.0, 1.2, layer=pcbnew.B_SilkS)

out = os.path.join(HERE, "mgmt.kicad_pcb")
b.Save(out)
for x in problems: print("PROBLEM:", x)
print(f"wrote {out}: {len(b.GetFootprints())} footprints, {len(nets)} nets, {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
