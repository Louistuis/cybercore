# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore XL rev 0.2: floorplan board for a 4-GPU + 2-CPU, 3.2 TB unified-memory AI inference server.

Architecture: four CC-G1 GPUs (our own design) each own 768 GB of memory-down LPDDR5X. Two AMD EPYC 9005 CPUs
(SP5) each attach to two GPUs over CXL x16 links, so CPUs and GPUs share one cache-coherent address space
(3 TB GPU pool + 2 x 64 GB CPU-local DDR5 memory-down). GPUs talk to each other through the CC-F1 fabric.

What is real here: board size, 22-layer stackup setting, power planes, and every stock-library connector
(M.2, RJ45, USB-C, Mini-Fit Sr power, fan headers, front panel, RTC battery, mounting holes) with its
12 V / GND nets. What is a placeholder: the CC-G1 GPUs, the CC-F1 fabric switch, the BMC, the AMD SP5 socket
and the memory ballouts. Their footprints have the right size and pitch class, but no pin map, because
these pin maps are under NDA (AMD SP5) or do not exist yet (CC-G1 is a chip we would have to design). See ../README.md.

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 make_board.py
"""
import os, pcbnew
from pcbnew import FromMM, VECTOR2I, EDA_ANGLE, DEGREES_T

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "CyberCore.pretty")
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
M3D = "${KICAD10_3DMODEL_DIR}/"
W, H = 440.0, 640.0                 # board, mm (custom "CyberCore XL" form factor, 4U / 19 inch rack, deep chassis)
OX, OY = 50.0, 50.0                 # sheet offset
LAYERS = 22

# --------------------------------------------------------------------------- custom footprints (text .kicad_mod)
def fp_text(name, descr, body, crt, pads, model=None, scale=(1, 1, 1), offset=(0, 0, 0), silk=True, attr="smd",
            ref_y=None):
    bw, bh = body; cw, ch = crt
    ry = ref_y if ref_y is not None else -bh / 2 - 1.5
    out = [f'(footprint "{name}"', '\t(version 20260206)', '\t(generator "pcbnew")', '\t(generator_version "10.0")',
           '\t(layer "F.Cu")', f'\t(descr "{descr}")',
           f'\t(property "Reference" "REF**" (at 0 {ry:.2f} 0) (layer "F.SilkS") (effects (font (size 1.5 1.5) (thickness 0.2))))',
           f'\t(property "Value" "{name}" (at 0 {bh/2+1.5:.2f} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
           f'\t(attr {attr})']
    def rect(layer, w, h, wd):
        out.append(f'\t(fp_rect (start {-w/2:.3f} {-h/2:.3f}) (end {w/2:.3f} {h/2:.3f}) (stroke (width {wd}) (type solid)) (fill no) (layer "{layer}"))')
    rect("F.Fab", bw, bh, 0.1); rect("F.CrtYd", cw, ch, 0.05)
    if silk:
        rect("F.SilkS", bw + 0.4, bh + 0.4, 0.15)
        # pin-1 corner mark
        x, y = -bw / 2 - 0.2, -bh / 2 - 0.2
        out.append(f'\t(fp_line (start {x-1.2:.3f} {y:.3f}) (end {x:.3f} {y-1.2:.3f}) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))')
    out += pads
    if model:
        out.append(f'\t(model "{model}" (offset (xyz {offset[0]} {offset[1]} {offset[2]})) '
                   f'(scale (xyz {scale[0]} {scale[1]} {scale[2]})) (rotate (xyz 0 0 0)))')
    out.append(')')
    with open(os.path.join(LIB, name + ".kicad_mod"), "w") as f:
        f.write("\n".join(out) + "\n")

ROWS = "ABCDEFGHJKLMNPRTUVWY"           # JEDEC ball rows skip I O Q S X Z
def rowname(i):
    return ROWS[i] if i < len(ROWS) else ROWS[i // len(ROWS) - 1] + ROWS[i % len(ROWS)]

def bga(name, descr, body, n, pitch, ball, model, model_mm, crt_margin=0.5, crt=None, zscale=1.0, pad_shape="circle"):
    nx, ny = n if isinstance(n, tuple) else (n, n)
    px, py = pitch if isinstance(pitch, tuple) else (pitch, pitch)
    pads = []
    for r in range(ny):
        for c in range(nx):
            x, y = -(nx - 1) * px / 2 + c * px, -(ny - 1) * py / 2 + r * py
            pads.append(f'\t(pad "{rowname(r)}{c+1}" smd {pad_shape} (at {x:.3f} {y:.3f}) (size {ball} {ball}) '
                        f'(property pad_prop_bga) (layers "F.Cu" "F.Mask" "F.Paste"))')
    s = (body[0] / model_mm[0], body[1] / model_mm[1], zscale)
    fp_text(name, descr, body, crt or (body[0] + 2 * crt_margin, body[1] + 2 * crt_margin), pads, model, s)

BGA35 = M3D + "Package_BGA.3dshapes/BGA-1156_35.0x35.0mm_Layout34x34_P1.0mm.step"
BGA21 = M3D + "Package_BGA.3dshapes/BGA-625_21.0x21.0mm_Layout25x25_P0.8mm.step"
BGA9 = M3D + "Package_BGA.3dshapes/BGA-64_9.0x9.0mm_Layout10x10_P0.8mm.step"
bga("CC-G1_GPU_BGA-4624_70x70mm_P1.0mm",
    "PLACEHOLDER CyberCore CC-G1 GPU (our own design), 68x68 balls at 1.0 mm: 1024-bit LPDDR5X, CXL x16 host link, "
    "fabric links. No pin map until the chip exists.", (70, 70), 68, 1.0, 0.5, BGA35, (35, 35), 1.0)
# AMD SP5 is LGA6096, 75.4 x 72 mm package. The socket pin map and keep-outs are AMD NDA material, so this is a
# size placeholder: 78 x 78 land grid, courtyard = approximate socket + retention frame.
bga("AMD_SP5_LGA6096_75.4x72mm_Placeholder",
    "PLACEHOLDER AMD EPYC 9005 SP5 socket. Real land pattern and frame drawing are under AMD NDA.",
    (75.4, 72.0), (78, 78), (0.92, 0.88), 0.5, BGA35, (35, 35), crt=(92.0, 104.0), zscale=2.0, pad_shape="rect")
bga("DDR5_x16_FBGA-102_8x13mm_P0.8mm",
    "DDR5 x16 SDRAM, 102-ball FBGA (6 x 17 at 0.8 x 0.75 mm). Ballout per JEDEC JESD79-5, not filled in.",
    (8.0, 13.0), (6, 17), (0.8, 0.75), 0.4, BGA9, (9, 9), 0.5)
bga("CC-F1_Fabric_BGA-1849_45x45mm_P1.0mm",
    "PLACEHOLDER node-to-node fabric + PCIe 5.0 switch, 43x43 balls. No pin map.", (45, 45), 43, 1.0, 0.5, BGA35, (35, 35))
bga("LPDDR5X_x64_BGA-441_14x15mm_P0.65mm",
    "LPDDR5X x64 package (4 x16 channels), 21x21 ball grid at 0.65 mm. Ballout not filled in (JEDEC JESD209-5C).",
    (14, 15), 21, 0.65, 0.35, BGA21, (21, 21), 0.5)
bga("BMC_BGA-529_19x19mm_P0.8mm", "PLACEHOLDER baseboard management controller (AST2600 size class). No pin map.",
    (19, 19), 23, 0.8, 0.4, BGA21, (21, 21))

# PCIe 5.0 x16 CEM slot, through hole. APPROXIMATE: 164 pins at 1.0 mm effective pitch per side (two staggered rows of
# 2.0 mm per side), key after pin 11. Replace with the connector vendor's drawing before any real order.
pads = []
def slot_x(i):                         # i = 1..82
    return (i - 1) * 1.0 + (1.6 if i > 11 else 0.0) - 41.3
for side, ys in (("B", (-2.5, -1.5)), ("A", (1.5, 2.5))):
    for i in range(1, 83):
        y = ys[0] if i % 2 else ys[1]
        pads.append(f'\t(pad "{side}{i}" thru_hole circle (at {slot_x(i):.3f} {y:.3f}) (size 0.9 0.9) (drill 0.55) '
                    f'(layers "*.Cu" "*.Mask"))')
for x in (-45.0, 46.0):
    pads.append(f'\t(pad "" np_thru_hole circle (at {x:.3f} 0) (size 2.4 2.4) (drill 2.4) (layers "*.Cu" "*.Mask"))')
fp_text("PCIe_CEM_x16_Slot_THT_Approx", "PCIe 5.0 x16 CEM slot, approximate footprint (see make_board.py)",
        (95.0, 7.5), (96.0, 8.5), pads, attr="through_hole")

# QSFP-DD 1x1 cage, outline + press-fit pegs only. APPROXIMATE (SFF-TA-8000 class), no signal pads drawn.
pads = [f'\t(pad "" np_thru_hole circle (at {x} {y}) (size 1.6 1.6) (drill 1.6) (layers "*.Cu" "*.Mask"))'
        for x, y in ((-8, -18), (8, -18), (-8, 12), (8, 12))]
fp_text("QSFP-DD_Cage_1x1_Outline_Approx", "QSFP-DD 800G cage outline, approximate, signal pads not drawn",
        (19.0, 50.0), (20.0, 51.0), pads, attr="through_hole")

# --------------------------------------------------------------------------- board
b = pcbnew.NewBoard(os.path.join(HERE, "cybercore.kicad_pcb"))
ds = b.GetDesignSettings(); ds.SetCopperLayerCount(LAYERS); ds.SetBoardThickness(FromMM(2.4))
# HDI server-class rules: 0.1 mm copper clearance, 0.15 mm hole clearance
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.1)); ds.m_HoleClearance = FromMM(0.15)
P = lambda x, y: VECTOR2I(FromMM(OX + x), FromMM(OY + y))
nets = {}
def net(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    return nets[n]

R = 4.0
def seg(a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(a); s.SetEnd(c); s.SetWidth(FromMM(0.1)); b.Add(s)
def arc(c, st):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetCenter(c); s.SetStart(st); s.SetArcAngleAndEnd(EDA_ANGLE(90, DEGREES_T)); s.SetWidth(FromMM(0.1)); b.Add(s)
seg(P(R, 0), P(W - R, 0)); seg(P(W, R), P(W, H - R)); seg(P(W - R, H), P(R, H)); seg(P(0, H - R), P(0, R))
for cx, cy, sx, sy in ((W - R, R, W - R, 0), (W - R, H - R, W, H - R), (R, H - R, R, H), (R, R, 0, R)):
    arc(P(cx, cy), P(sx, sy))

def add(lib, name, ref, x, y, rot=0, value=None, pads=None):
    path = LIB if lib == "CyberCore" else STOCK + lib + ".pretty"
    f = pcbnew.FootprintLoad(path, name)
    if f is None:
        raise SystemExit(f"footprint not found: {lib}:{name}")
    f.SetReference(ref); f.SetValue(value or name)
    f.SetPosition(P(x, y)); f.SetOrientation(EDA_ANGLE(rot, DEGREES_T)); b.Add(f)
    for pn, nn in (pads or {}).items():
        for p in f.Pads():
            if p.GetNumber() == str(pn): p.SetNet(net(nn))
    return f

def silk(text, x, y, size=2.0, rot=0, layer=pcbnew.F_SilkS, bold=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(text); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(size * (0.2 if bold else 0.13)))
    t.SetTextAngle(EDA_ANGLE(rot, DEGREES_T)); b.Add(t)

# --------------------------------------------------------------------------- 4 GPU nodes, memory down
NODES = [(85, 140), (245, 140), (85, 320), (245, 320)]
CC = "CC-G1_GPU_BGA-4624_70x70mm_P1.0mm"
MEM = "LPDDR5X_x64_BGA-441_14x15mm_P0.65mm"
for n, (x, y) in enumerate(NODES):
    k = n + 1
    add("CyberCore", CC, f"U{k}", x, y, 0, f"CC-G1 GPU {n} (our design, placeholder)")
    m = 1
    for side in ("N", "E", "S", "W"):
        for off in (-22, 0, 22):
            d = 45.0
            mx, my, rot = {"N": (x + off, y - d, 0), "S": (x + off, y + d, 180),
                           "E": (x + d, y + off, 90), "W": (x - d, y + off, 270)}[side]
            add("CyberCore", MEM, f"U{k}{m:02d}", mx, my, rot, "LPDDR5X 64GB x64")
            m += 1
    silk(f"GPU {n}", x - 45, y - 45, 2.5, bold=True)
    silk("768 GB", x + 45, y - 45, 2.0)
    silk("922 GB/s", x - 45, y + 45, 1.8)
    silk("CC-G1", x + 45, y + 45, 2.0)

    # VRM: 16 phases (2 rows x 8) north of the memory ring, controller to the east
    for row in range(2):
        for i in range(8):
            px = x - 45.5 + i * 13
            ph = row * 8 + i + 1
            add("Package_TO_SOT_SMD", "TDSON-8-1", f"Q{k}{ph:02d}", px, y - 92 + row * 20, 0, "90A smart power stage")
            add("Inductor_SMD", "L_Bourns_SRP1038C_10.0x10.0mm", f"L{k}{ph:02d}", px, y - 81.5 + row * 20, 0, "150nH")
    for i in range(8):
        px = x - 45.5 + i * 13
        add("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", f"C{k}{i+1:02d}", px - 1.5, y - 104, 0, "470uF 16V polymer",
            {1: "P12V", 2: "GND"})
    add("Package_DFN_QFN", "QFN-48-1EP_7x7mm_P0.5mm_EP3.5x3.5mm", f"U{k}90", x + (58 if n % 2 else -58), y - 82, 0,
        "16-phase VR controller")

# --------------------------------------------------------------------------- fabric switch between the nodes
add("CyberCore", "CC-F1_Fabric_BGA-1849_45x45mm_P1.0mm", "U5", 165, 230, 0, "CC-F1 fabric switch (placeholder)")
silk("CC-F1 FABRIC", 165, 256, 2.0, bold=True)
silk("4 x 800 GB/s GPU links", 165, 260, 1.5)
silk("UNIFIED 3.2 TB", 165, 266, 2.0, bold=True)

# --------------------------------------------------------------------------- 2 x AMD EPYC 9005 (SP5), CPU-local DDR5 down
CPUS = [(85, 455), (245, 455)]
for c, (x, y) in enumerate(CPUS):
    k = 21 + c
    add("CyberCore", "AMD_SP5_LGA6096_75.4x72mm_Placeholder", f"U{k}", x, y, 0, f"AMD EPYC 9005 CPU{c} (SP5)")
    # 4 DDR5 channels x (4 data + 1 ECC) x16 chips, 4 GB each: 64 GB per CPU. Two columns each side of the socket.
    m = 1
    for dx in (-62, -52, 52, 62):
        for i in range(5):
            f = add("CyberCore", "DDR5_x16_FBGA-102_8x13mm_P0.8mm", f"U{k}{m:02d}", x + dx, y - 30 + i * 15, 0,
                    "DDR5-6400 32Gb x16" + (" (ECC)" if i == 4 else ""))
            f.Reference().SetVisible(False)          # 2 mm gaps: no room for ref text between the chips
            m += 1
    silk(f"AMD CPU{c}", x - 30, y - 56, 2.5, bold=True)
    silk("EPYC 9005  SP5", x + 26, y - 56, 1.8)
    silk("64 GB DDR5", x, y + 42, 1.8)
    gl = "GPU 0 + GPU 2" if c == 0 else "GPU 1 + GPU 3"
    silk(f"CXL x16 coherent -> {gl}", x, y - 70, 1.6)
    # VRM: 12 phases (2 x 6) south of the socket: VDDCR_CPU / SOC / VDDIO
    for row in range(2):
        for i in range(6):
            px = x - 32.5 + i * 13
            ph = row * 6 + i + 1
            add("Package_TO_SOT_SMD", "TDSON-8-1", f"Q{k}{ph:02d}", px, y + 60 + row * 20, 0, "70A smart power stage")
            add("Inductor_SMD", "L_Bourns_SRP1038C_10.0x10.0mm", f"L{k}{ph:02d}", px, y + 70.5 + row * 20, 0, "150nH")
    for i in range(6):
        add("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", f"C{k}{i+1:02d}", x - 34 + i * 13, y + 104, 0,
            "470uF 16V polymer", {1: "P12V", 2: "GND"})
    add("Package_DFN_QFN", "QFN-48-1EP_7x7mm_P0.5mm_EP3.5x3.5mm", f"U{k}90", x + (52 if c else -52), y + 75, 0,
        "12-phase SVI3 VR controller")
silk("xGMI x3  CPU0 <-> CPU1", 165, 420, 1.6, rot=90)

# --------------------------------------------------------------------------- rear I/O (top edge)
add("CyberCore", "QSFP-DD_Cage_1x1_Outline_Approx", "J13", 152, 26, 0, "QSFP-DD 800G")
add("CyberCore", "QSFP-DD_Cage_1x1_Outline_Approx", "J14", 178, 26, 0, "QSFP-DD 800G")
add("Connector_RJ", "RJ45_Amphenol_RJHSE5380", "J15", 14, 14, 180, "RJ45 BMC")
add("Connector_RJ", "RJ45_Amphenol_RJHSE5380", "J16", 34, 14, 180, "RJ45 10GbE")
add("Connector_USB", "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "J17", 128, 5, 180, "USB-C console",
    {**{p: "GND" for p in ("A1", "A12", "B1", "B12", "S1")}, **{p: "VBUS_CON" for p in ("A4", "A9", "B4", "B9")}})

# --------------------------------------------------------------------------- PCIe 5.0 x16 slots (right, front-to-back)
for i in range(4):
    add("CyberCore", "PCIe_CEM_x16_Slot_THT_Approx", f"J{i+1}", 350 + i * 20.32, 76, 90, "PCIe 5.0 x16")
silk("4x PCIe 5.0 x16", 380, 125, 2.0, bold=True)

# --------------------------------------------------------------------------- 8x M.2 NVMe (model storage, 8 x 8 TB)
for i in range(8):
    col, row = i % 4, i // 4
    x, y = 347 + col * 25, 145 + row * 95
    add("Connector_PCBEdge", "TE_M.2_M_2x38-1MP_P0.5mm", f"J{5+i}", x, y, 180, "M.2 M-key NVMe 2280")
    add("MountingHole", "MountingHole_2.2mm_M2_Pad_Via", f"H{20+i}", x, y + 80.5, 0, "M.2 standoff", {1: "GND"})
silk("8x M.2 NVMe  64 TB model store", 385, 330, 2.0, bold=True)

# --------------------------------------------------------------------------- BMC, boot flash, clocks, RTC
add("CyberCore", "BMC_BGA-529_19x19mm_P0.8mm", "U6", 360, 375, 0, "BMC (placeholder)")
add("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U8", 385, 365, 0, "BMC SPI NOR 64MB")
add("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U9", 385, 378, 0, "Host SPI NOR 64MB")
add("Package_DFN_QFN", "QFN-48-1EP_7x7mm_P0.5mm_EP3.5x3.5mm", "U10", 405, 371, 0,
    "PCIe/fabric clock generator")
add("Battery", "BatteryHolder_Keystone_3034_1x20mm", "BT1", 420, 400, 0, "CR2032 RTC")
silk("BMC", 360, 389, 2.0, bold=True)

# --------------------------------------------------------------------------- power entry + fans + front panel (front edge)
for j, x in ((18, 35), (19, 75), (29, 115)):
    add("Connector_Molex", "Molex_Mini-Fit_Sr_43915-xx08_2x04_P10.00mm_Vertical_ThermalVias", f"J{j}", x, 578, 0,
        "12V 8-pin Mini-Fit Sr (160 A)", {1: "GND", 2: "GND", 3: "GND", 4: "GND",
                                          5: "P12V", 6: "P12V", 7: "P12V", 8: "P12V"})
silk("12V IN  3 x 160 A  (5.7 kW)", 75, 622, 1.8, bold=True)
for i in range(8):
    add("Connector", "FanPinHeader_1x04_P2.54mm_Vertical", f"J{20+i}", 175 + i * 22, 624, 0, f"FAN{i}",
        {1: "GND", 2: "P12V"})
silk("FAN 0-7", 252, 631, 1.5)
add("Connector_PinHeader_2.54mm", "PinHeader_2x05_P2.54mm_Vertical", "J28", 380, 624, 90, "Front panel")

# mounting holes M4 (GND)
for i, (x, y) in enumerate(((8, 70), (432, 8), (8, 632), (432, 632), (165, 150), (165, 320), (318, 140),
                            (318, 320), (432, 135), (8, 240), (8, 455), (165, 455), (322, 455), (432, 455))):
    add("MountingHole", "MountingHole_4.3mm_M4_Pad_Via", f"H{i+1}", x, y, 0, "M4", {1: "GND"})

# --------------------------------------------------------------------------- branding
silk("CyberCore", 250, 588, 14.0, bold=True)
silk("4x CC-G1 GPU + 2x AMD EPYC   3.2 TB unified memory   3.7 TB/s   22 layers", 250, 605, 2.2)
silk("rev 0.2 concept  2026-11-16  louis-studios hardware-lab", 250, 611, 1.5)

# --------------------------------------------------------------------------- USB-C fan-out: GND vias, VBUS jumper
def padpos(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num: return p.GetPosition()
def track(a, c, nn, w=0.25):
    t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetWidth(FromMM(w)); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(net(nn)); b.Add(t)
def via(pt, nn):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pt); v.SetWidth(FromMM(0.6)); v.SetDrill(FromMM(0.3)); v.SetNet(net(nn)); b.Add(v)
for num, dx in (("A1", 1.0), ("A12", -1.0)):
    pp = padpos("J17", num); q = VECTOR2I(pp.x + FromMM(dx), pp.y + FromMM(1.6))
    track(pp, VECTOR2I(pp.x, q.y), "GND"); track(VECTOR2I(pp.x, q.y), q, "GND"); via(q, "GND")
a4, a9 = padpos("J17", "A4"), padpos("J17", "A9"); yb = a4.y + FromMM(1.4)
track(a4, VECTOR2I(a4.x, yb), "VBUS_CON"); track(VECTOR2I(a4.x, yb), VECTOR2I(a9.x, yb), "VBUS_CON")
track(VECTOR2I(a9.x, yb), a9, "VBUS_CON")

# --------------------------------------------------------------------------- planes: In1 GND, In2 12 V, In3 GND
def plane(layer, netname):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(net(netname))
    z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)):
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(z)
plane(pcbnew.In1_Cu, "GND"); plane(pcbnew.In2_Cu, "P12V"); plane(pcbnew.In3_Cu, "GND")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

b.Save(os.path.join(HERE, "cybercore.kicad_pcb"))
print("footprints:", len(b.GetFootprints()), "pads:", sum(len(f.Pads()) for f in b.GetFootprints()))
