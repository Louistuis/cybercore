# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore management board: writes mgmt.kicad_sch from parts.py (adapted from the concierge-phone generator).
Original notes: writes a real KiCad schematic from the netlists, so tools that need one (Quilter, KiCad's
'Update PCB from schematic', schematic parity DRC) can use the design. Run with KiCad's python:
    gen_sch.py <board.kicad_pcb> <out_dir>
Every part becomes one symbol whose pins are exactly the footprint's pad numbers (pin name = the net on that pad, so the
schematic reads like a pin map); every net is a global label on the pin end, every 'nc' pad a no-connect flag. Value,
footprint and DNP are read from the board so the two always agree. Writes <out_dir>/mgmt.kicad_sch and
<out_dir>/sym_uuids.json (ref -> symbol uuid; the board copy's footprint paths are set from it).
Parts are laid out in blocks per parts.py group (m0-m3, core, usb, power, sys), each IC followed by the passives whose
'near' is that IC, so the sheet is readable when printed."""
import sys, os, re, glob, json, math, uuid, importlib.util, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD, OUTD = sys.argv[1], sys.argv[2]
os.makedirs(OUTD, exist_ok=True)
_s = importlib.util.spec_from_file_location("parts", os.path.join(HERE, "parts.py")); _m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)
PARTS = [p for p in _m.PARTS if not p.get("board_only")]
BY = {p["ref"]: p for p in PARTS}
b = pcbnew.LoadBoard(BOARD)
FP = {f.GetReference(): f for f in b.GetFootprints()}
U = lambda: str(uuid.uuid4())
G = 1.27
q = lambda s: '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
def natkey(s): return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
def up(v, step=2.54): return math.ceil(v / step - 1e-9) * step
FONT = "(effects (font (size 1.27 1.27)))"
CH = 1.0   # mm per character at 1.27 mm text (generous)

ROOT = U()
lib, body, sym_uuid = {}, [], {}

def passive_kind(p, pads):
    pre = re.match(r"[A-Z]+", p["ref"]).group(0)
    return pre if pre in ("R", "C", "L", "FB") and sorted(pads) == ["1", "2"] else None

def lib_symbol(name, left, right, names_shown, refpre):
    """left/right: lists of (number, name). Returns (sexpr, top, bw)."""
    n = max(len(left), len(right), 1)
    top = (n - 1) * G
    ml = max([len(x[1]) for x in left] or [0]); mr = max([len(x[1]) for x in right] or [0])
    bw = max(5.08, up((ml + mr) * CH + 3.0)) if names_shown else 5.08
    pins = []
    for i, (num, nm) in enumerate(left):
        pins.append(f'(pin passive line (at {-bw/2-2.54:.2f} {top-i*2.54:.2f} 0) (length 2.54) (name {q(nm)} {FONT}) (number {q(num)} {FONT}))')
    for i, (num, nm) in enumerate(right):
        pins.append(f'(pin passive line (at {bw/2+2.54:.2f} {top-i*2.54:.2f} 180) (length 2.54) (name {q(nm)} {FONT}) (number {q(num)} {FONT}))')
    pn = "(pin_names (offset 0.508))" if names_shown else "(pin_names (offset 0) hide)"
    s = (f'(symbol {q("mgmt:"+name)} {pn} (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
         f'  (property "Reference" {q(refpre)} (at 0 {top+2.54:.2f} 0) {FONT})\n'
         f'  (property "Value" {q(name)} (at 0 {-top-2.54:.2f} 0) {FONT})\n'
         f'  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
         f'  (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
         f'  (property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
         f'  (symbol {q(name+"_0_1")} (rectangle (start {-bw/2:.2f} {top+G:.2f}) (end {bw/2:.2f} {-top-G:.2f}) (stroke (width 0.254) (type default)) (fill (type background))))\n'
         f'  (symbol {q(name+"_1_1")}\n    ' + "\n    ".join(pins) + "))")
    return s, top, bw

# ---------------------------------------------------------------- order: group blocks, IC then its passives
GROUPS = []
for p in PARTS:
    if p["group"] not in GROUPS: GROUPS.append(p["group"])
order = []
for g in GROUPS:
    members = [p for p in PARTS if p["group"] == g]
    heads = sorted([p for p in members if not passive_kind(p, list(p["pins"]) + list(p.get("nc", {})))], key=lambda p: natkey(p["ref"]))
    done = set()
    for h in heads:
        if h["ref"] in done: continue
        order.append(h); done.add(h["ref"])
        for p in sorted(members, key=lambda p: natkey(p["ref"])):
            if p["ref"] not in done and p.get("near") == h["ref"]: order.append(p); done.add(p["ref"])
    for p in sorted(members, key=lambda p: natkey(p["ref"])):
        if p["ref"] not in done: order.append(p); done.add(p["ref"])
assert len(order) == len(PARTS)

# ---------------------------------------------------------------- place blocks on shelves
ROW_W = 420.0
x, y, row_h, maxx = 25.4, 25.4, 0.0, 0.0
labels, ncs = [], []
for p in order:
    ref = p["ref"]; f = FP[ref]
    pads = sorted({pd.GetNumber() for pd in f.Pads() if pd.GetNumber() and pd.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH}, key=natkey)
    net_of = {n: p["pins"].get(n) for n in pads}
    kind = passive_kind(p, pads)
    if kind:
        name, left, right, shown = kind, [("1", "~")], [("2", "~")], False
    else:
        name = "P_" + ref
        half = math.ceil(len(pads) / 2)
        lst = [(n, net_of[n] or "NC") for n in pads]
        left, right, shown = lst[:half], lst[half:], True
    if name not in lib: lib[name] = lib_symbol(name, left, right, shown, re.match(r"[A-Z]+", ref).group(0))
    _, top, bw = lib[name]
    labL = max([len(net_of[n] or "") for n, _ in left] or [0]) * CH + 4
    labR = max([len(net_of[n] or "") for n, _ in right] or [0]) * CH + 4
    w = up(labL + 2.54 + bw + 2.54 + labR + 5.08); h = up(2 * top + 2 * G + 10.16)
    if x + w > ROW_W: x, y, row_h = 25.4, y + row_h, 0.0
    sx = round((x + labL + 2.54 + bw / 2) / G) * G; sy = round((y + top + G + 5.08) / G) * G
    x += w; row_h = max(row_h, h); maxx = max(maxx, x)
    su = U(); sym_uuid[ref] = su
    dnp = "yes" if f.IsDNP() else "no"; inbom = "no" if f.IsExcludedFromBOM() else "yes"
    fpid = p["fp"]   # library:name from parts.py (the board copy was loaded by path, so it has no library nickname)
    props = [("Reference", ref, sy - top - G - 1.27, False), ("Value", f.GetValue(), sy + top + G + 1.27, False),
             ("Footprint", fpid, sy, True), ("Datasheet", "~", sy, True), ("Description", "", sy, True),
             ("LCSC", p.get("lcsc", ""), sy, True)]
    ps = "\n  ".join(f'(property {q(k)} {q(v)} (at {sx:.2f} {yy:.2f} 0) (effects (font (size 1.27 1.27)){" hide" if hid else ""}))'
                     for k, v, yy, hid in props)
    pins = " ".join(f'(pin {q(n)} (uuid {q(U())}))' for n in pads)
    body.append(f'(symbol (lib_id {q("mgmt:"+name)}) (at {sx:.2f} {sy:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom {inbom}) '
                f'(on_board yes) (dnp {dnp}) (uuid {q(su)})\n  {ps}\n  {pins}\n'
                f'  (instances (project "mgmt" (path {q("/"+ROOT)} (reference {q(ref)}) (unit 1)))))')
    for side, lst in ((0, left), (1, right)):
        for i, (n, _) in enumerate(lst):
            px = sx + ((-bw / 2 - 2.54) if side == 0 else (bw / 2 + 2.54)); py = sy - (top - i * 2.54)
            if net_of[n]:
                ang, just = (180, "right") if side == 0 else (0, "left")
                labels.append(f'(global_label {q(net_of[n])} (shape passive) (at {px:.2f} {py:.2f} {ang}) (fields_autoplaced yes) '
                              f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(U())}) '
                              f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {px:.2f} {py:.2f} 0) (effects (font (size 1.27 1.27)) hide)))')
            else:
                ncs.append(f'(no_connect (at {px:.2f} {py:.2f}) (uuid {q(U())}))')
W_, H_ = up(maxx + 25.4, 10), up(y + row_h + 25.4, 10)
out = (f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")\n(uuid {q(ROOT)})\n'
       f'(paper "User" {W_:.0f} {H_:.0f})\n'
       f'(title_block (title "CyberCore management board") (rev "1.0") (comment 1 "Generated by mgmt/gen_sch.py from parts.py"))\n'
       '(lib_symbols\n' + "\n".join(v[0] for v in lib.values()) + ')\n' + "\n".join(body) + "\n" + "\n".join(labels) + "\n" +
       "\n".join(ncs) + '\n(sheet_instances (path "/" (page "1")))\n)\n')
open(os.path.join(OUTD, "mgmt.kicad_sch"), "w").write(out)
json.dump({"root": ROOT, "symbols": sym_uuid}, open(os.path.join(OUTD, "sym_uuids.json"), "w"), indent=0)
print(f"{len(body)} symbols, {len(lib)} library symbols, {len(labels)} labels, {len(ncs)} no-connects, sheet {W_:.0f} x {H_:.0f} mm")
