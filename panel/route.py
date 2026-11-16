"""Routing for the status panel (KiCad's python):
  route.py export  -> panel.dsn for Freerouting
  route.py import  -> reads panel.ses, pours GND on both layers, stitches the pours, saves panel_routed.kicad_pcb
Freerouting (from ~/Developer/hardware-lab):
  /opt/homebrew/opt/openjdk/bin/java -Djava.awt.headless=true -jar tools/freerouting-dl/freerouting-2.5.0.jar \
     --gui.enabled=false -de cybercore/panel/panel.dsn -do cybercore/panel/panel.ses --router.autorouter.max_passes=100"""
import os, sys, pcbnew
from pcbnew import FromMM, VECTOR2I
HERE = os.path.dirname(os.path.abspath(__file__))
OX, OY, W, H = 100.0, 100.0, 150.0, 50.0

def rules(b):
    """JLCPCB standard 2-layer rules with margin. They live in the .kicad_pro, so they are set on every load + save."""
    ds = b.GetDesignSettings(); ds.SetCopperLayerCount(2); ds.SetBoardThickness(FromMM(1.6))
    ds.m_MinClearance = FromMM(0.15); ds.m_TrackMinWidth = FromMM(0.12)   # Freerouting necks USB_DN to 0.125 mm between U3's pads; JLC 2-layer min is 0.10; ds.m_ViasMinSize = FromMM(0.6)
    ds.m_MinThroughDrill = FromMM(0.3); ds.m_HoleClearance = FromMM(0.25); ds.m_CopperEdgeClearance = FromMM(0.3)
    ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass(); d.SetClearance(FromMM(0.15)); d.SetTrackWidth(FromMM(0.2))
    d.SetViaDiameter(FromMM(0.6)); d.SetViaDrill(FromMM(0.3))
    for name, width, clr, via, drill, nets in (("Power", 0.5, 0.15, 0.8, 0.4, ["GND", "VBUS", "5V", "3V3"]),
                                               ("USB", 0.25, 0.15, 0.6, 0.3, ["USB_DP", "USB_DN"])):
        nc = pcbnew.NETCLASS(name); nc.SetClearance(FromMM(clr)); nc.SetTrackWidth(FromMM(width))
        nc.SetViaDiameter(FromMM(via)); nc.SetViaDrill(FromMM(drill)); ns.SetNetclass(name, nc)
        for n in nets: ns.SetNetclassPatternAssignment(n, name)
    ns.RecomputeEffectiveNetclasses(); b.SynchronizeNetsAndNetClasses(True)

STACKUP = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (color "#060606F5") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "core") (color "FR4 natural") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (color "#060606F5") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
"""

def black_stackup(path):
    """Black solder mask, white silk, ENIG (gold) finish: written into the board's stackup so renders and the fab notes agree.
    (2026-11-16: black board, not green.)"""
    s = open(path).read()
    if "(stackup" in s: return
    i = s.index("(setup") + len("(setup")
    open(path, "w").write(s[:i] + "\n" + STACKUP + s[i:])

def gnd_pour(b, layer):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet("GND"))
    z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.3)); z.SetThermalReliefSpokeWidth(FromMM(0.4))
    ol = z.Outline(); ol.NewOutline()
    for x, y in [(0, 0), (W, 0), (W, H), (0, H)]: ol.Append(FromMM(OX + x), FromMM(OY + y))
    b.Add(z)

def free_spot(b, x, y):
    """True if a 0.8 mm GND via at (x, y) stays clear of every pad, track and keep-out (plus 0.35 mm)"""
    p = VECTOR2I(FromMM(OX + x), FromMM(OY + y)); r = FromMM(0.4 + 0.35)
    for f in b.GetFootprints():
        for z in f.Zones():
            if z.GetIsRuleArea() and z.Outline().Collide(p, r): return False
        for pad in f.Pads():
            if pad.HitTest(p, r): return False
    for t in b.GetTracks():
        if t.HitTest(p, r): return False
    return True

if sys.argv[1] == "export":
    b = pcbnew.LoadBoard(os.path.join(HERE, "panel.kicad_pcb"))
    rules(b); b.Save(os.path.join(HERE, "panel.kicad_pcb"))
    print("dsn:", pcbnew.ExportSpecctraDSN(b, os.path.join(HERE, "panel.dsn")))
else:
    b = pcbnew.LoadBoard(os.path.join(HERE, "panel.kicad_pcb"))
    rules(b)
    print("ses:", pcbnew.ImportSpecctraSES(b, os.path.join(HERE, "panel.ses")))
    gnd_pour(b, pcbnew.F_Cu); gnd_pour(b, pcbnew.B_Cu)
    # stitching vias every 6 mm wherever there is room, so the two pours act as one ground
    n = 0
    y = 3.0
    while y < H - 2:
        x = 3.0
        while x < W - 2:
            if free_spot(b, x, y):
                v = pcbnew.PCB_VIA(b); v.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y)))
                v.SetWidth(FromMM(0.8)); v.SetDrill(FromMM(0.4)); v.SetNet(b.FindNet("GND")); b.Add(v); n += 1
            x += 6.0
        y += 6.0
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    out = os.path.join(HERE, "panel_routed.kicad_pcb")
    b.Save(out)
    black_stackup(out)
    # KiCad keeps the rules in the .kicad_pro, and saving under a new name does not write one: copy it
    pro = open(os.path.join(HERE, "panel.kicad_pro")).read().replace('"panel.kicad_pro"', '"panel_routed.kicad_pro"')
    open(os.path.join(HERE, "panel_routed.kicad_pro"), "w").write(pro)
    print("tracks+vias:", len(b.GetTracks()), "stitching vias:", n)
