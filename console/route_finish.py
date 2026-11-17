# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""Cleanup after `route.py import` (KiCad's python, needs kicad-cli on PATH):
  KPY route_finish.py
Freerouting necks some tracks down to 0.05-0.075 mm where they leave a fine-pitch pad. This widens every such track to
the board minimum (0.09 mm), runs DRC, and puts back the original width of any track that now breaks clearance. It
repeats that once at 0.075 mm for the thinnest ones. It also gives the two buck GND pads (U302/U402 pad 14) a solid zone
connection; they already reach the planes through their in-pad vias. Rewrites console_routed.kicad_pcb in place."""
import os, sys, json, subprocess, tempfile, pcbnew
from pcbnew import FromMM
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "console_routed.kicad_pcb")
TMP = tempfile.mkdtemp()

def tracks(b):
    return [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]

def clashing(b):
    p, j = os.path.join(TMP, "t.kicad_pcb"), os.path.join(TMP, "drc.json")
    pcbnew.SaveBoard(p, b)
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", j, p], check=True, capture_output=True)
    d = json.load(open(j))
    return {i["uuid"] for v in d["violations"] if v["type"] == "clearance" for i in v["items"]}

def widen(b, below, to):
    old = {t.m_Uuid.AsString(): t.GetWidth() for t in tracks(b) if t.GetWidth() < FromMM(below)}
    for t in tracks(b):
        if t.m_Uuid.AsString() in old: t.SetWidth(FromMM(to))
    for _ in range(3):                      # a put-back can expose a neighbour that was hidden behind it
        bad = clashing(b) & old.keys()
        if not bad: break
        for t in tracks(b):
            if t.m_Uuid.AsString() in bad: t.SetWidth(old[t.m_Uuid.AsString()])
    return len(old)

b = pcbnew.LoadBoard(OUT)
print("0.09 mm:", widen(b, 0.09, 0.09), "candidates")
print("0.075 mm:", widen(b, 0.075, 0.075), "candidates")
for ref in ("U302", "U402"):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == "14": p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(OUT, b)
print("thinner than 0.09 mm left:", sum(1 for t in tracks(b) if t.GetWidth() < FromMM(0.09)))
