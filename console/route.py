# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""Routing for the CyberCore Console carrier (KiCad's python). Three steps:
  KPY route.py prep    reads console.kicad_pcb, builds the plane stack, puts vias in pads, writes console_prep.kicad_pcb
                       and console.dsn for Freerouting
  freerouting          routes the signal nets on the 5 signal layers (command below), writes console.ses
  KPY route.py import  reads console_prep.kicad_pcb + console.ses, fills every zone, writes console_routed.kicad_pcb
Freerouting (from ~/Developer/hardware-lab):
  /opt/homebrew/opt/openjdk/bin/java -Xmx3g -Djava.awt.headless=true -jar tools/freerouting-dl/freerouting-2.5.0.jar \\
     --gui.enabled=false -de cybercore/console/console.dsn -do cybercore/console/console.ses -mp 60

Stack (12 layers, 1.6 mm, HDI rules from console.kicad_pro: 0.10 mm track / clearance, 0.30 / 0.15 mm vias):
  F.Cu   signals + GND pour (parts on top: modules, fans, bucks, QSFP, connectors)
  In1    GND plane
  In2    signals (stripline between In1 and In3)
  In3    GND plane
  In4    signals
  In5    VIN_12V plane (whole board)
  In6    one SYS_VIN_HV island per module (eFuse output -> module), GND elsewhere
  In7    5V plane (whole board)
  In8    one SYS_VIN_MV island per module, GND elsewhere
  In9    3V3 plane (whole board)
  In10   signals
  B.Cu   signals + GND pour (parts under each module: eFuses, switch, clock, AC caps, M.2)
Every SMD pad on a plane net gets a via in the pad (filled and capped: order "via in pad" / POFV). Every connected
pad of the 4 Mirror Mezz connectors gets one too, so their signals can leave on any layer.
What this does NOT do: impedance-controlled, coupled and length-matched routing of the 25G, PCIe Gen4, USB and QSFP
pairs. Freerouting routes each leg on its own. The result shows the board can be fully connected; the high-speed
pairs still need a manual pass in an SI-aware tool (see README)."""
import os, sys, re, math, collections, pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I
HERE = os.path.dirname(os.path.abspath(__file__))
SRC, PREP, DSN, SES, OUT = (os.path.join(HERE, n) for n in
    ("console.kicad_pcb", "console_prep.kicad_pcb", "console.dsn", "console.ses", "console_routed.kicad_pcb"))
OX, OY, W, H = 100.0, 100.0, 240.0, 256.0
VIA_D, VIA_H = 0.30, 0.15          # HDI via, also used in pads
CLR, HOLE2HOLE, EDGE = 0.10, 0.20, 0.30

SIGNAL = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In4_Cu, pcbnew.In10_Cu, pcbnew.B_Cu]
POWER = [pcbnew.In1_Cu, pcbnew.In3_Cu, pcbnew.In5_Cu, pcbnew.In6_Cu, pcbnew.In7_Cu, pcbnew.In8_Cu, pcbnew.In9_Cu]
PLANE_NET = re.compile(r"^(GND|VIN_12V|5V|3V3|M\d_VIN_(HV|MV))$")
WIDE = {"U501_SW": 0.8, "U601_SW": 0.8, **{f"M{m}_VIN_SV": 0.4 for m in range(4)},
        **{f"M{m}_USB_VBUS": 0.4 for m in range(4)}}

def mm(v): return ToMM(v)
def P(x, y): return VECTOR2I(FromMM(x), FromMM(y))

def zone(b, layer, net, pts, prio=0, clr=0.2, thermal=False):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(net)); z.SetAssignedPriority(prio)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetLocalClearance(FromMM(clr)); z.SetMinThickness(FromMM(0.15))
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(P(x, y))
    b.Add(z); return z

def rect(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
BOARD = rect(OX + 0.6, OY + 0.6, OX + W - 0.6, OY + H - 0.6)

class Space:
    """Coarse spatial hash of copper obstacles (pads as rectangles, vias as circles) for via placement checks."""
    def __init__(s): s.g = collections.defaultdict(list)
    def _cells(s, x0, y0, x1, y1):
        for i in range(int(x0 // 2), int(x1 // 2) + 1):
            for j in range(int(y0 // 2), int(y1 // 2) + 1): yield (i, j)
    def add(s, kind, net, x0, y0, x1, y1, hole=None):
        it = (kind, net, x0, y0, x1, y1, hole)
        for c in s._cells(x0, y0, x1, y1): s.g[c].append(it)
    def ok(s, net, x, y):
        r = VIA_D / 2
        if not (OX + EDGE + r < x < OX + W - EDGE - r and OY + EDGE + r < y < OY + H - EDGE - r): return False
        seen = set()
        for c in s._cells(x - 1, y - 1, x + 1, y + 1):
            for it in s.g[c]:
                if id(it) in seen: continue
                seen.add(id(it)); kind, n, x0, y0, x1, y1, hole = it
                if hole is not None:      # another via or drilled hole: hole-to-hole and copper clearance
                    hx, hy, hr = hole
                    if math.hypot(hx - x, hy - y) < hr + VIA_H / 2 + HOLE2HOLE: return False
                if n == net and kind != "hole": continue
                dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
                if math.hypot(dx, dy) < r + CLR + 0.02: return False
        return True

VIAS = []
def add_via(b, sp, net, x, y, d=VIA_D, h=VIA_H):
    VIAS.append((net, x, y)); v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(FromMM(d)); v.SetDrill(FromMM(h))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(b.FindNet(net)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    b.Add(v); sp.add("via", net, x - d / 2, y - d / 2, x + d / 2, y + d / 2, (x, y, h / 2))

def strip_zones(src, dst):
    """Copy the board without its top-level zones (removing zones through the python API breaks KiCad 10's swig types)."""
    s = open(src).read(); out = []; i = 0
    while True:
        j = s.find("\n\t(zone", i)
        if j < 0: out.append(s[i:]); break
        out.append(s[i:j]); depth = 0; k = j + 1
        while True:
            c = s[k]
            if c == "(": depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0: break
            k += 1
        i = k + 1
    open(dst, "w").write("".join(out))

def prep():
    tmp = PREP + ".tmp.kicad_pcb"; strip_zones(SRC, tmp)
    b = pcbnew.LoadBoard(tmp); os.remove(tmp)
    for L in SIGNAL: b.SetLayerType(L, pcbnew.LT_SIGNAL)
    for L in POWER: b.SetLayerType(L, pcbnew.LT_POWER)
    # net classes: HDI default (from console.kicad_pro) + wider power-ish signals
    ds = b.GetDesignSettings(); ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass(); d.SetClearance(FromMM(CLR)); d.SetTrackWidth(FromMM(0.1))
    d.SetViaDiameter(FromMM(VIA_D)); d.SetViaDrill(FromMM(VIA_H))
    for width in sorted(set(WIDE.values())):
        nc = pcbnew.NETCLASS(f"W{int(width*100)}"); nc.SetClearance(FromMM(0.15)); nc.SetTrackWidth(FromMM(width))
        nc.SetViaDiameter(FromMM(0.45)); nc.SetViaDrill(FromMM(0.2)); ns.SetNetclass(nc.GetName(), nc)
        for n, w in WIDE.items():
            if w == width: ns.SetNetclassPatternAssignment(n, nc.GetName())
    ns.RecomputeEffectiveNetclasses(); b.SynchronizeNetsAndNetClasses(True)

    # obstacle map
    sp = Space(); pads = []
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox(); x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
            hole = None
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                c = p.GetPosition(); hole = (mm(c.x), mm(c.y), mm(p.GetDrillSize().x) / 2)
            sp.add("hole" if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else "pad", p.GetNetname(), x0, y0, x1, y1, hole)
            pads.append((f, p, x0, y0, x1, y1))
    # vias in pads
    placed = collections.Counter(); missed = []
    for f, p, x0, y0, x1, y1 in pads:
        net = p.GetNetname()
        if not net or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
        is_mod = f.GetFPID().GetLibItemName().wx_str().startswith("Jetson_T5000")
        if not (PLANE_NET.match(net) or is_mod): continue
        w, h = x1 - x0, y1 - y0; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if min(w, h) >= 1.2:          # big pad: grid of vias, 1.0 mm pitch, 0.35 mm in from the edge
            nx, ny = max(1, int((w - 0.7) // 1.0) + 1), max(1, int((h - 0.7) // 1.0) + 1)
            pts = [(cx + (i - (nx - 1) / 2) * 1.0, cy + (j - (ny - 1) / 2) * 1.0) for i in range(nx) for j in range(ny)]
        else:
            pts = [(cx, cy)]
        got = 0
        for x, y in pts:
            if sp.ok(net, x, y): add_via(b, sp, net, x, y); got += 1
        placed[net if PLANE_NET.match(net) else "module signal"] += got
        if not got: missed.append(f"{f.GetReference()}.{p.GetNumber()} {net}")
    # extra current vias next to each eFuse output (8 small QFN pins carry 6.5-13.4 A)
    for f in b.GetFootprints():
        if not f.GetFPID().GetLibItemName().wx_str().startswith("TI_RGE0024M"): continue
        outs = [p for p in f.Pads() if p.GetNumber() in [str(n) for n in range(19, 25)]]
        net = outs[0].GetNetname(); ys = [mm(p.GetPosition().y) for p in outs]; xs = [mm(p.GetPosition().x) for p in outs]
        y_row = ys[0]; side = 1 if y_row > mm(f.GetPosition().y) else -1
        yv = y_row + side * 1.05
        zone(b, pcbnew.B_Cu, net, rect(min(xs) - 0.3, min(y_row, yv) - 0.35, max(xs) + 0.3, max(y_row, yv) + 0.35), prio=5, clr=0.15)
        for x in (min(xs), (min(xs) + max(xs)) / 2, max(xs)):
            if sp.ok(net, x, yv): add_via(b, sp, net, x, yv); placed[net] += 1
    print("vias placed:", dict(placed)); print("pads without a via:", len(missed), missed[:20])

    # planes
    zone(b, pcbnew.F_Cu, "GND", BOARD, 0, 0.25, thermal=True)
    zone(b, pcbnew.B_Cu, "GND", BOARD, 0, 0.25, thermal=True)
    for L in (pcbnew.In1_Cu, pcbnew.In3_Cu): zone(b, L, "GND", BOARD)
    zone(b, pcbnew.In5_Cu, "VIN_12V", BOARD); zone(b, pcbnew.In7_Cu, "5V", BOARD); zone(b, pcbnew.In9_Cu, "3V3", BOARD)
    for L, rail in ((pcbnew.In6_Cu, "HV"), (pcbnew.In8_Cu, "MV")):
        zone(b, L, "GND", BOARD, 0)
        for m in range(4):
            net = f"M{m}_VIN_{rail}"
            pts = [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == net]
            pts += [(x, y) for n, x, y in VIAS if n == net]
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            zone(b, L, net, rect(min(xs) - 1.0, min(ys) - 1.0, max(xs) + 1.0, max(ys) + 1.0), prio=10)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PREP)
    ok = pcbnew.ExportSpecctraDSN(b, DSN)
    print("wrote", PREP, "and", DSN, ok)
    s = drop_module_keepouts(open(DSN).read()); open(DSN, "w").write(s)
    print("planes in dsn:", len(re.findall(r"\(plane ", s)), "| nets in dsn:", len(re.findall(r"\(net ", s)))

def drop_module_keepouts(s):
    """The module footprint's rule area only forbids other footprints under a module (vias and tracks are allowed), but
    KiCad's Specctra export writes it as a full keepout, which would stop Freerouting from routing under the modules.
    Drop exactly those (the 87 x 100 mm polygon); the QSFP28 cage keepout stays."""
    out, i, n = [], 0, 0
    while True:
        j = s.find('(keepout "" (polygon F.Cu 0  -43500 50000', i)
        if j < 0: out.append(s[i:]); break
        out.append(s[i:j]); depth, k = 0, j
        while True:
            if s[k] == "(": depth += 1
            elif s[k] == ")":
                depth -= 1
                if depth == 0: break
            k += 1
        i = k + 1; n += 1
    print("module keepouts dropped from the dsn:", n)
    return "".join(out)

def do_import():
    b = pcbnew.LoadBoard(PREP)
    ok = pcbnew.ImportSpecctraSES(b, SES)
    print("imported", SES, ok)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    for d in b.GetDrawings():
        if isinstance(d, pcbnew.PCB_TEXT) and "(unrouted)" in d.GetText(): d.SetText(d.GetText().replace("(unrouted)", "(autorouted)"))
    b.Save(OUT); print("wrote", OUT)

if __name__ == "__main__":
    {"prep": prep, "import": do_import}[sys.argv[1]]()
