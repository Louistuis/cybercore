# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""Routing for the management board (KiCad's python):
  route.py export  -> adds the In1.Cu GND plane, writes mgmt.dsn for Freerouting
  route.py import  -> reads mgmt.ses, pours GND on F.Cu / B.Cu and 3V3 on In2.Cu, stitches the GND pours, saves
                      mgmt_routed.kicad_pcb (+ black stackup)
Freerouting (from ~/Developer/hardware-lab; one instance at a time, it needs ~2-3 GB):
  /opt/homebrew/opt/openjdk/bin/java -Xmx3g -Djava.awt.headless=true -jar tools/freerouting-dl/freerouting-2.5.0.jar \
     --gui.enabled=false -de cybercore/mgmt/mgmt.dsn -do cybercore/mgmt/mgmt.ses --router.autorouter.max_passes=200 --router.automatic_neckdown=false"""
import os, sys, pcbnew
from pcbnew import FromMM, VECTOR2I
HERE = os.path.dirname(os.path.abspath(__file__))
OX, OY, W, H = 100.0, 100.0, 132.0, 72.0
POWER = ["GND", "3V3", "1V8", "5V_AO"] + [f"M{m}_VIO" for m in range(4)]
USB = ["USB1_DP", "USB1_DN", "USB2_DP", "USB2_DN"]

def rules(b):
    """JLCPCB standard 6-layer rules (their minimum is 0.09 mm track / space; 0.25 mm via drill is within the standard
    multilayer process). 0.127 mm signal tracks and gaps leave room between the TSSOP pins; Freerouting necks down to
    ~0.11 mm in a few places, so the hard minimum is 0.10 mm."""
    ds = b.GetDesignSettings(); ds.SetCopperLayerCount(6); ds.SetBoardThickness(FromMM(1.6))
    for L in (pcbnew.In1_Cu, pcbnew.In4_Cu): b.SetLayerType(L, pcbnew.LT_POWER)       # GND and 3V3 planes
    for L in (pcbnew.In2_Cu, pcbnew.In3_Cu): b.SetLayerType(L, pcbnew.LT_SIGNAL)
    ds.m_MinClearance = FromMM(0.1); ds.m_TrackMinWidth = FromMM(0.1); ds.m_ViasMinSize = FromMM(0.45)
    ds.m_MinThroughDrill = FromMM(0.25); ds.m_HoleClearance = FromMM(0.2); ds.m_CopperEdgeClearance = FromMM(0.3)
    ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass(); d.SetClearance(FromMM(0.127)); d.SetTrackWidth(FromMM(0.127))
    d.SetViaDiameter(FromMM(0.5)); d.SetViaDrill(FromMM(0.25))
    for name, width, clr, nl in (("Power", 0.3, 0.15, POWER), ("USB", 0.25, 0.15, USB)):
        nc = pcbnew.NETCLASS(name); nc.SetClearance(FromMM(clr)); nc.SetTrackWidth(FromMM(width))
        nc.SetViaDiameter(FromMM(0.5)); nc.SetViaDrill(FromMM(0.25)); ns.SetNetclass(name, nc)
        for n in nl: ns.SetNetclassPatternAssignment(n, name)
    ns.RecomputeEffectiveNetclasses(); b.SynchronizeNetsAndNetClasses(True)

STACKUP = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (color "#060606F5") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "prepreg") (color "FR4 natural") (thickness 0.1) (material "FR4") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "In1.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 2" (type "core") (color "FR4 natural") (thickness 0.55) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In2.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 3" (type "prepreg") (color "FR4 natural") (thickness 0.2) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
			(layer "In3.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 4" (type "core") (color "FR4 natural") (thickness 0.55) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
			(layer "In4.Cu" (type "copper") (thickness 0.0152))
			(layer "dielectric 5" (type "prepreg") (color "FR4 natural") (thickness 0.1) (material "FR4") (epsilon_r 4.1) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (color "#060606F5") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
"""

def black_stackup(path):
    """Black solder mask, white silk, ENIG, a JLC 6-layer 1.6 mm stack: written into the board so renders and
    the fab notes agree (same look as the status panel)."""
    s = open(path).read()
    if "(stackup" in s: return
    i = s.index("(setup") + len("(setup")
    open(path, "w").write(s[:i] + "\n" + STACKUP + s[i:])

def zone(b, layer, netname, clearance=0.3, thermal=True):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(netname))
    z.SetLocalClearance(FromMM(clearance)); z.SetMinThickness(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(FromMM(0.3)); z.SetThermalReliefSpokeWidth(FromMM(0.4))
    ol = z.Outline(); ol.NewOutline()
    for x, y in [(0, 0), (W, 0), (W, H), (0, H)]: ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(z); return z

def free_spot(b, x, y):
    """True if a 0.6 mm GND via at (x, y) stays clear of every pad, track and keep-out (plus 0.35 mm)"""
    p = VECTOR2I(FromMM(OX + x), FromMM(OY + y)); r = FromMM(0.3 + 0.35)
    for f in b.GetFootprints():
        for z in f.Zones():
            if z.GetIsRuleArea() and z.Outline().Collide(p, r): return False
        for pad in f.Pads():
            if pad.HitTest(p, r): return False
    for t in b.GetTracks():
        if t.HitTest(p, r): return False
    return True

if __name__ == "__main__":
    src = os.path.join(HERE, "mgmt.kicad_pcb")
    b = pcbnew.LoadBoard(src)
    rules(b)
    if sys.argv[1] == "export":
        if not any(z.GetLayer() == pcbnew.In1_Cu for z in b.Zones()): zone(b, pcbnew.In1_Cu, "GND", 0.2, thermal=False)
        if not any(z.GetLayer() == pcbnew.In4_Cu for z in b.Zones()): zone(b, pcbnew.In4_Cu, "3V3", 0.2, thermal=False)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(src)
        print("dsn:", pcbnew.ExportSpecctraDSN(b, os.path.join(HERE, "mgmt.dsn")))
    else:
        print("ses:", pcbnew.ImportSpecctraSES(b, os.path.join(HERE, "mgmt.ses")))
        zone(b, pcbnew.F_Cu, "GND"); zone(b, pcbnew.B_Cu, "GND")
        n, y = 0, 3.0       # stitching vias every 5 mm wherever there is room: the pours and the In1 plane act as one ground
        while y < H - 2:
            x = 3.0
            while x < W - 2:
                if free_spot(b, x, y):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y)))
                    v.SetWidth(FromMM(0.6)); v.SetDrill(FromMM(0.3)); v.SetNet(b.FindNet("GND")); b.Add(v); n += 1
                x += 5.0
            y += 5.0
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        out = os.path.join(HERE, "mgmt_routed.kicad_pcb")
        b.Save(out)
        black_stackup(out)
        pro = os.path.join(HERE, "mgmt.kicad_pro")      # rules live in the .kicad_pro; saving under a new name skips it
        if os.path.exists(pro):
            open(os.path.join(HERE, "mgmt_routed.kicad_pro"), "w").write(open(pro).read().replace('"mgmt.kicad_pro"', '"mgmt_routed.kicad_pro"'))
        print("tracks+vias:", len(b.GetTracks()), "stitching vias:", n)
