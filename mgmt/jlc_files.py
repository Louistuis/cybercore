# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""JLCPCB files for the management board (KiCad's python):  jlc_files.py  ->  jlc/BOM.csv, jlc/CPL.csv, jlc/gerbers.zip
BOM + CPL come from parts.py (LCSC numbers) and the routed board (positions). Test pads and mounting holes are not parts.
Board order settings: 6 layers, 1.6 mm, BLACK solder mask, white silk, ENIG.
CPL rotation = KiCad's angle with no package correction: check every polarised part (all U, D1, Y1, J1-J4, J20-J23) in JLC's
placement preview before paying; their library origins differ per part. Stock check: python3 stock_check.py 5 jlc/BOM.csv"""
import os, csv, shutil, subprocess, importlib.util, collections, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "jlc"); os.makedirs(OUT, exist_ok=True)
s = importlib.util.spec_from_file_location("parts", os.path.join(HERE, "parts.py")); P = importlib.util.module_from_spec(s); s.loader.exec_module(P)
SPEC = {p["ref"]: p for p in P.PARTS}
BOARD = os.path.join(HERE, "mgmt_routed.kicad_pcb")
b = pcbnew.LoadBoard(BOARD)
bom, cpl, skipped = collections.OrderedDict(), [], []
for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    ref = f.GetReference(); sp = SPEC[ref]
    if not sp.get("lcsc"): skipped.append(ref); continue
    fpname = f.GetFPID().GetLibItemName().wx_str()
    bom.setdefault((sp["value"], fpname, sp["lcsc"]), []).append(ref)
    pos = f.GetPosition()
    cpl.append((ref, f"{pcbnew.ToMM(pos.x):.3f}mm", f"{-pcbnew.ToMM(pos.y):.3f}mm", "top", f"{f.GetOrientationDegrees() % 360:.1f}"))
with open(os.path.join(OUT, "BOM.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, lcsc), refs in bom.items(): w.writerow([val, ",".join(refs), fp, lcsc])
with open(os.path.join(OUT, "CPL.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); w.writerows(cpl)
g = os.path.join(OUT, "gerbers"); shutil.rmtree(g, ignore_errors=True); os.makedirs(g)
z = os.path.join(OUT, "gerbers.zip")
if os.path.exists(z): os.remove(z)
cli = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
subprocess.run([cli, "pcb", "export", "gerbers", "--check-zones", "-o", g + "/", "-l",
                "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts", "--subtract-soldermask", BOARD], check=True, capture_output=True)
subprocess.run([cli, "pcb", "export", "drill", "-o", g + "/", "--format", "excellon", "--excellon-separate-th", BOARD], check=True, capture_output=True)
files = sorted(os.listdir(g)); subprocess.run(["zip", "-jq", z] + [os.path.join(g, x) for x in files], check=True)
print(f"BOM lines {len(bom)}, placed parts {len(cpl)}, not placed (pads/holes) {len(skipped)}: {' '.join(skipped)}; gerbers.zip {len(files)} files")
