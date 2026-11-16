# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore Console carrier, rev 0.1 (PoC): one slim black board that carries 4 NVIDIA Jetson T5000 (AGX Thor) modules,
128 GB each = 512 GB unified LPDDR5X, enough for DeepSeek V3.1 (671B) at 4-bit. Run with KiCad's python:
    KPY make_console.py [path/to/Jetson_Thor_Series_Pin_Descriptions_v1.0.nvxlsx]
The 699-pin map is read from NVIDIA's pin description spreadsheet (attached inside the Jetson Thor Series Modules Design
Guide DG-12084-001, free download from developer.nvidia.com). It is not stored in this repo; download it yourself and
extract the attachment (`pdfdetach -saveall`), or point the script at it.

What is real here: every module pin and the net it lands on (from NVIDIA's spreadsheet and design guide chapter 5 / 7),
the board-level architecture, the stock connectors (M.2, USB-C, Mini-Fit Sr, fan headers, mgmt headers).
What is a placeholder: the Molex Mirror Mezz footprint geometry (1.30 mm column pitch from Molex's listing, row pitch and
the connector's position inside the module outline assumed), module standoff positions, the QSFP28 footprint, and the
five power blocks (sized, not designed). Nothing is routed. See README.md for the list to clear before any order."""
import os, sys, re, glob, math, zipfile, xml.etree.ElementTree as ET, pcbnew
from pcbnew import FromMM, VECTOR2I, EDA_ANGLE, DEGREES_T
HERE = os.path.dirname(os.path.abspath(__file__))
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
LIB = os.path.join(HERE, "Console.pretty"); os.makedirs(LIB, exist_ok=True)
W, H, RC = 240.0, 232.0, 4.0
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
def write_fp(name, descr, body_lines, pads, crt):
    cw, ch = crt
    s = [f'(footprint "{name}" (version 20240108) (generator "make_console") (layer "F.Cu")',
         f'  (descr "{descr}") (attr smd)',
         '  (property "Reference" "REF**" (at 0 %.2f 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))' % (-ch / 2 - 1.5),
         '  (property "Value" "%s" (at 0 %.2f 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % (name, ch / 2 + 1.5)]
    s += body_lines
    s.append(f'  (fp_rect (start {-cw/2:.3f} {-ch/2:.3f}) (end {cw/2:.3f} {ch/2:.3f}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))')
    s += pads
    s.append(")")
    open(os.path.join(LIB, name + ".kicad_mod"), "w").write("\n".join(s) + "\n")

def rect(layer, w, h, x=0, y=0, width=0.1):
    return f'  (fp_rect (start {x-w/2:.3f} {y-h/2:.3f}) (end {x+w/2:.3f} {y+h/2:.3f}) (stroke (width {width}) (type solid)) (fill none) (layer "{layer}"))'
def ftext(s, x, y, layer="F.Fab", size=1.0):
    return f'  (fp_text user "{s}" (at {x:.2f} {y:.2f} 0) (layer "{layer}") (effects (font (size {size} {size}) (thickness {size*0.15:.2f}))))'

# 1) Jetson Thor 699-pin Mirror Mezz, carrier side. Column pitch 1.30 mm (Molex 203456 listing). Row pitch ASSUMED 1.30 mm.
#    Carrier pin orientation per DG-12084 fig. 3-2: row L on top (low y), row A at the bottom, column 1 on the left.
#    The module outline (100 x 87 mm) is drawn on F.Fab and courtyard around the connector; with the 2.5 mm connector
#    the design guide allows NO parts under the module, so make_console keeps that area clear on the top side.
CP, RP = 1.30, 1.30
pads = []
for pin in PINS:
    r, c = pin[0], int(pin[1:])
    x = (c - 33) * CP; y = (ROWS.index(r) - 5) * -RP
    pads.append(f'  (pad "{pin}" smd circle (at {x:.3f} {y:.3f}) (size 0.65 0.65) (layers "F.Cu" "F.Paste" "F.Mask"))')
body = [rect("F.Fab", 87.0, 16.0), rect("F.SilkS", 87.4, 16.4, width=0.12), rect("F.Fab", 100.0, 87.0, width=0.15),
        ftext("Jetson T5000 module outline 100 x 87 (position inside it ASSUMED)", 0, -41.0),
        ftext("L1", -33 * CP + CP, -7.2, "F.SilkS", 0.8)]
write_fp("Jetson_Thor_699_MirrorMezz_P1.30mm_Placeholder",
         "Molex Mirror Mezz 699-pin (65 x 11), carrier side, Jetson Thor. PLACEHOLDER geometry: verify vs Molex 203456 drawing + NVIDIA reference layout",
         body, pads, (88.5, 17.5))

# 2) QSFP28 host connector (SFF-8679 38-pin), PLACEHOLDER geometry: 2 rows of 19 at 0.8 mm, cage outline approximate.
q = []
for i in range(19):
    q.append(f'  (pad "{i+1}" smd roundrect (at {(i-9)*0.8:.2f} -1.6) (size 0.45 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))')
    q.append(f'  (pad "{38-i}" smd roundrect (at {(i-9)*0.8:.2f} 1.6) (size 0.45 1.6) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))')
write_fp("QSFP28_Host_38P_Cage_Placeholder", "QSFP28 host connector + cage, PLACEHOLDER geometry (SFF-8679 pin numbers)",
         [rect("F.Fab", 18.75, 52.0, 0, 18.0), rect("F.SilkS", 19.2, 52.4, 0, 18.0, 0.12), ftext("QSFP28 cage, mouth at board edge", 0, 40)], q, (19.5, 53.0))

# 3) power blocks: sized pads only (IN / OUT / GND / EN / PG), PLACEHOLDER for a real converter or eFuse design
def pwr_block(name, w, h, descr):
    """IN on the left, OUT on the right, GND in the middle, EN + PG along the bottom edge (all scaled to the body)."""
    pw = w * 0.22; gw = w * 0.3; sh = h * 0.18
    p = [f'  (pad "IN" smd rect (at {-w/2+pw/2:.3f} {-sh/2:.3f}) (size {pw:.3f} {h-sh-0.6:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"))',
         f'  (pad "OUT" smd rect (at {w/2-pw/2:.3f} {-sh/2:.3f}) (size {pw:.3f} {h-sh-0.6:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"))',
         f'  (pad "GND" smd rect (at 0 {-sh/2:.3f}) (size {gw:.3f} {h-sh-0.6:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"))',
         f'  (pad "EN" smd rect (at {-w/4:.3f} {h/2-sh/2:.3f}) (size {w*0.18:.3f} {sh:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"))',
         f'  (pad "PG" smd rect (at {w/4:.3f} {h/2-sh/2:.3f}) (size {w*0.18:.3f} {sh:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"))']
    write_fp(name, descr, [rect("F.Fab", w, h), rect("F.SilkS", w + 0.6, h + 0.6, width=0.12)], p, (w + 1, h + 1))
pwr_block("PWR_eFuse12V15A_8x6_Placeholder", 8, 6, "12 V 15 A eFuse per module (e.g. TI TPS2598x class), PLACEHOLDER")
pwr_block("PWR_Buck5V20A_22x16_Placeholder", 22, 16, "12 V -> 5 V 20 A buck for SYS_VIN_MV, PLACEHOLDER")
pwr_block("PWR_Buck3V3A15_22x16_Placeholder", 22, 16, "12 V -> 3.3 V 15 A buck for SYS_VIN_SV + 4 x M.2, PLACEHOLDER")
pwr_block("PWR_LoadSw5V5A_4x4_Placeholder", 5.0, 5.0, "5 V load switch per module (MV gating for power sequencing), PLACEHOLDER")
pwr_block("PWR_LoadSw3V3_3x3_Placeholder", 4.0, 4.0, "3.3 V load switch per module (SV gating), PLACEHOLDER")

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

# modules: 2 x 2, centres
MOD = [(58.0, 52.0), (182.0, 52.0), (58.0, 148.0), (182.0, 148.0)]
PEERS = {m: [n for n in range(4) if n != m] for m in range(4)}
used = {m: set() for m in range(4)}
def mpin(m, name):
    used[m].add(name); return BYNAME[name]

def module_nets(m):
    p = {}
    for pin, name in PINS.items():
        base = re.sub(r"_\d+$", "", name)
        if base == "GND": p[pin] = "GND"
        elif base == "SYS_VIN_HV": p[pin] = f"M{m}_VIN_HV"
        elif base == "SYS_VIN_MV": p[pin] = f"M{m}_VIN_MV"
    p[BYNAME["SYS_VIN_SV"]] = f"M{m}_VIN_SV"
    return p

MGMT = ["MODULE_POWER_ON", "CARRIER_POWER_ON", "SYS_RESET_N", "MODULE_POWER_GOOD", "VDDIN_PWR_BAD_N", "FORCE_RECOVERY_N",
        "MODULE_SHDN_N", "THERM_ALERT_N", "THERM_SHDN_REQ_N", "PRSNT0", "PRSNT1", "UART3_TX_DEBUG", "UART3_RX_DEBUG",
        "I2C3_CLK", "I2C3_DAT"]
mod_pins = {m: module_nets(m) for m in range(4)}
for m in range(4):
    P = mod_pins[m]
    for s in MGMT: P[BYNAME[s]] = f"M{m}_{s}"
    # PCIe C5 x4 (UPHY1 config #2 lanes 0-3) -> this module's own M.2 NVMe
    for k in range(4):
        P[BYNAME[f"UPHY_TX{8+k}_P"]] = f"M{m}_PCIE_TX{k}_P_AC"; P[BYNAME[f"UPHY_TX{8+k}_N"]] = f"M{m}_PCIE_TX{k}_N_AC"
        P[BYNAME[f"UPHY_RX{8+k}_P"]] = f"M{m}_PCIE_RX{k}_P"; P[BYNAME[f"UPHY_RX{8+k}_N"]] = f"M{m}_PCIE_RX{k}_N"
    P[BYNAME["UPHY_REFCLK3_P"]] = f"M{m}_PCIE_REFCLK_P"; P[BYNAME["UPHY_REFCLK3_N"]] = f"M{m}_PCIE_REFCLK_N"
    P[BYNAME["PEX_C5_RST_N"]] = f"M{m}_PCIE_PERST_N"; P[BYNAME["PEX_C5_CLKREQ_N"]] = f"M{m}_PCIE_CLKREQ_N"
    P[BYNAME["PEX_WAKE_N"]] = f"M{m}_PCIE_WAKE_N"
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
    add("Console", "Jetson_Thor_699_MirrorMezz_P1.30mm_Placeholder", f"U{m+1}", cx, cy, 0, "Jetson T5000 (AGX Thor) 128 GB", P)

# AC coupling caps (0201, 100 nF), back side, rows beside each module's connector. PCIe TX (host side) + mesh TX.
cap_i = [100]
def accap(a, bnet, x, y):
    ref = f"C{cap_i[0]}"; cap_i[0] += 1
    add("Capacitor_SMD", "C_0201_0603Metric", ref, x, y, 90, "100nF", {"1": a, "2": bnet}, back=True)
for m in range(4):
    cx, cy = MOD[m]
    row = 0
    for k in range(4):
        for pol in "PN":
            accap(f"M{m}_PCIE_TX{k}_{pol}_AC", f"M{m}_PCIE_TX{k}_{pol}", cx - 10 + row * 1.2, cy + 11.0); row += 1
    row = 0
    for peer in PEERS[m]:
        for pol in "PN":
            accap(f"MESH_{m}{peer}_{pol}_AC", f"MESH_{m}{peer}_{pol}", cx + 2 + row * 1.2, cy + 11.0); row += 1

# M.2 2280 M-key NVMe per module, on the back under its module (PCIe Gen4/5 x4). Standard M-key pin map.
M2 = {"3": "GND", "9": "GND", "15": "GND", "21": "GND", "27": "GND", "33": "GND", "39": "GND", "45": "GND", "51": "GND",
      "57": "GND", "71": "GND", "73": "GND", "75": "GND", "MP": "GND",
      "2": "3V3", "4": "3V3", "12": "3V3", "14": "3V3", "16": "3V3", "18": "3V3", "70": "3V3", "72": "3V3", "74": "3V3"}
for m in range(4):
    cx, cy = MOD[m]
    p = dict(M2)
    for k, (rn, rp, tn, tp) in enumerate([("41", "43", "47", "49"), ("29", "31", "35", "37"), ("17", "19", "23", "25"), ("5", "7", "11", "13")]):
        p[rn] = f"M{m}_PCIE_TX{k}_N"; p[rp] = f"M{m}_PCIE_TX{k}_P"     # SSD PER (its receive) <- host TX after the AC caps
        p[tn] = f"M{m}_PCIE_RX{k}_N"; p[tp] = f"M{m}_PCIE_RX{k}_P"     # SSD PET (its transmit) -> host RX
    p.update({"53": f"M{m}_PCIE_REFCLK_N", "55": f"M{m}_PCIE_REFCLK_P", "50": f"M{m}_PCIE_PERST_N",
              "52": f"M{m}_PCIE_CLKREQ_N", "54": f"M{m}_PCIE_WAKE_N"})
    add("Connector_PCBEdge", "TE_M.2_M_2x38-1MP_P0.5mm", f"J{10+m}", cx - 30, cy - 38, 180, "M.2 2280 NVMe 4 TB", p, back=True)
    add("MountingHole", "MountingHole_2.2mm_M2_Pad_Via", f"H{10+m}", cx - 30, cy - 38 + 80.5, 0, "M.2 standoff", {"1": "GND"})

# module standoffs: 4 per module at the outline corners inset 4 mm (ASSUMED positions)
hi = 20
for m, (cx, cy) in enumerate(MOD):
    for dx in (-47, 47):
        for dy in (-40.5, 40.5):
            add("MountingHole", "MountingHole_2.7mm_M2.5_Pad_Via", f"H{hi}", cx + dx, cy + dy, 0, "module standoff", {"1": "GND"}); hi += 1

# ------------------------------------------------------------------ bottom strip: power, I/O, management
Y = 210.0
# 12 V in: Molex Mini-Fit Sr 2x4 (as on CyberCore rev 0.2), pins 1-4 GND, 5-8 12 V. 4 x ~130 W + NVMe + fans ~ 600 W = 50 A.
# 12 V in: 2 x Molex Mini-Fit Jr 2x4 (EPS-12V style: 1-4 GND, 5-8 +12 V). With HCS terminals ~13 A per pin = ~100 A total
# for ~50 A peak (4 x 130 W modules + NVMe + fans ~ 600 W), so either cable alone carries the board.
for j, x in (("J1", 16.0), ("J5", 40.0)):
    add("Connector_Molex", "Molex_Mini-Fit_Jr_5566-08A_2x04_P4.20mm_Vertical", j, x, Y + 2, 0, "12V IN (EPS 8-pin)",
        {**{str(i): "GND" for i in range(1, 5)}, **{str(i): "VIN_12V" for i in range(5, 9)}})
add("Console", "PWR_Buck5V20A_22x16_Placeholder", "PS1", 69, Y, 0, "12V->5V 20A", {"IN": "VIN_12V", "OUT": "5V", "GND": "GND", "EN": "BUCK5_EN", "PG": "BUCK5_PG"})
add("Console", "PWR_Buck3V3A15_22x16_Placeholder", "PS2", 94, Y, 0, "12V->3V3 15A", {"IN": "VIN_12V", "OUT": "3V3", "GND": "GND", "EN": "BUCK3_EN", "PG": "BUCK3_PG"})
for m, (cx, cy) in enumerate(MOD):          # per-module power gating, at the module's lower edge, outside its outline
    ys = 100.0 if m < 2 else 196.5                # the gap between the module rows / below the lower row
    add("Console", "PWR_eFuse12V15A_8x6_Placeholder", f"PS{10+m}", cx - 39, ys, 0, "eFuse 12V 15A",
        {"IN": "VIN_12V", "OUT": f"M{m}_VIN_HV", "GND": "GND", "EN": f"M{m}_HV_EN", "PG": f"M{m}_HV_PG"})
    add("Console", "PWR_LoadSw5V5A_4x4_Placeholder", f"PS{20+m}", cx - 29, ys, 0, "5V switch",
        {"IN": "5V", "OUT": f"M{m}_VIN_MV", "GND": "GND", "EN": f"M{m}_MV_EN", "PG": f"M{m}_MV_PG"})
    add("Console", "PWR_LoadSw3V3_3x3_Placeholder", f"PS{30+m}", cx - 22, ys, 0, "3V3 switch",
        {"IN": "3V3", "OUT": f"M{m}_VIN_SV", "GND": "GND", "EN": f"M{m}_SV_EN", "PG": f"M{m}_SV_PG"})
    # management header 2x20 1.27 mm: odd pins = this module's control signals, even pins = GND
    sig = MGMT + ["HV_EN", "HV_PG", "MV_EN", "SV_EN", "3V3_STBY"]
    hp = {str(2 * i + 1): (f"M{m}_{s}" if s != "3V3_STBY" else "3V3") for i, s in enumerate(sig)}
    hp.update({str(2 * i + 2): "GND" for i in range(20)})
    add("Connector_PinHeader_1.27mm", "PinHeader_2x20_P1.27mm_Vertical_SMD", f"J{20+m}", cx + 12, ys, 90, f"MGMT M{m}", hp)
    # fan header per module (module drives its own blower): 1 GND, 2 +12V, 3 TACH, 4 PWM
    add("Connector", "FanPinHeader_1x04_P2.54mm_Vertical", f"J{30+m}", cx + 33, ys - 1.3, 90, f"FAN M{m}",
        {"1": "GND", "2": "VIN_12V", "3": f"M{m}_FAN_TACH", "4": f"M{m}_FAN_PWM"})
# rear I/O along the bottom edge: QSFP28 uplink, 4 x USB-C recovery, status panel
QS = {"1": "GND", "4": "GND", "7": "GND", "13": "GND", "16": "GND", "19": "GND", "20": "GND", "23": "GND", "26": "GND",
      "32": "GND", "35": "GND", "38": "GND", "10": "3V3", "29": "3V3", "30": "3V3",
      "36": "Q_TX1_P", "37": "Q_TX1_N", "3": "Q_TX2_P", "2": "Q_TX2_N", "33": "Q_TX3_P", "34": "Q_TX3_N", "6": "Q_TX4_P", "5": "Q_TX4_N",
      "17": "Q_RX1_P", "18": "Q_RX1_N", "22": "Q_RX2_P", "21": "Q_RX2_N", "14": "Q_RX3_P", "15": "Q_RX3_N", "25": "Q_RX4_P", "24": "Q_RX4_N",
      "8": "QSFP_MODSEL_N", "9": "QSFP_RESET_N", "11": "QSFP_SCL", "12": "QSFP_SDA", "27": "QSFP_MODPRS_N", "28": "QSFP_INT_N", "31": "QSFP_LPMODE"}
add("Console", "QSFP28_Host_38P_Cage_Placeholder", "J2", 120, H - 44.6, 0, "QSFP28 4x25G uplink", QS)   # in the gap between modules 2 and 3, mouth at the rear edge
for m in range(4):
    add("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", f"J{40+m}", 162 + m * 13, H - 4.2, 0, f"USB-C M{m} recovery",
        {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "SH": "GND", "A6": f"M{m}_USB0_P", "B6": f"M{m}_USB0_P",
         "A7": f"M{m}_USB0_N", "B7": f"M{m}_USB0_N", "A5": f"M{m}_CC1", "B5": f"M{m}_CC2",
         "A4": f"M{m}_USB_VBUS", "B9": f"M{m}_USB_VBUS", "A9": f"M{m}_USB_VBUS", "B4": f"M{m}_USB_VBUS"})
    add("Resistor_SMD", "R_0402_1005Metric", f"R{10+2*m}", 162 + m * 13 - 2, H - 12, 0, "5.1k", {"1": f"M{m}_CC1", "2": "GND"})
    add("Resistor_SMD", "R_0402_1005Metric", f"R{11+2*m}", 162 + m * 13 + 2, H - 12, 0, "5.1k", {"1": f"M{m}_CC2", "2": "GND"})
# status panel cable (the black CyberCore status panel): JST PH 4-pin: 1 5V, 2 D-, 3 D+, 4 GND
add("Connector_JST", "JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "J3", 140, Y + 4, 0, "STATUS PANEL",
    {"1": "5V", "2": "PANEL_USB_N", "3": "PANEL_USB_P", "4": "GND"})
# system management header: bucks, MV/SV power-good, QSFP sideband (odd pins), GND (even pins)
SYS = ["BUCK5_EN", "BUCK5_PG", "BUCK3_EN", "BUCK3_PG"] + [f"M{m}_MV_PG" for m in range(4)] + [f"M{m}_SV_PG" for m in range(4)] + \
      ["QSFP_MODSEL_N", "QSFP_RESET_N", "QSFP_SCL", "QSFP_SDA", "QSFP_MODPRS_N", "QSFP_INT_N", "QSFP_LPMODE", "3V3"]
sp = {str(2 * i + 1): s for i, s in enumerate(SYS)}; sp.update({str(2 * i + 2): "GND" for i in range(20)})
add("Connector_PinHeader_1.27mm", "PinHeader_2x20_P1.27mm_Vertical_SMD", "J4", 94, 224, 90, "SYS MGMT", sp)

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
for m, (cx, cy) in enumerate(MOD): text(f"THOR {m}", cx + 30, cy - 30, 2.5)
text("CyberCore", 52.0, 224.0, 4.0, thick=0.7)
text("CONSOLE rev 0.1 PoC | 4 x Jetson T5000 | 512 GB | DeepSeek V3.1", 60.0, 229.0, 1.1)
text("CyberCore Console rev 0.1 PoC (unrouted)  |  open hardware  |  github.com/Louistuis/cybercore", 120, 205, 1.6, pcbnew.B_SilkS)

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
# Design rules (HDI class for the 1.3 mm module connector) live in console.kicad_pro, which is kept in the repo as a
# source file: min clearance 0.10, min track 0.09, via 0.30/0.15, copper-edge 0.25.
single = [n for n in nets if sum(1 for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == n) < 2]
print(f"wrote {out}: {len(b.GetFootprints())} footprints, {len(nets)} nets; one-pad nets: {single}")
