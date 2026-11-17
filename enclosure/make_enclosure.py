# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore Console enclosure, rev 0.1 (concept). Builds the case around the console carrier in Blender, exports the
printable / sheet-metal reference parts as STL and renders a preview. Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender -b -P make_enclosure.py
Units: 1 Blender unit = 1 mm. Board coordinates: x right, y towards the rear (KiCad's y), so Blender y = -board y.
The front of the box is +y (status panel), the rear is -y (QSFP28, USB-C, power, exhaust fans).

Stack (from the floor up, mm):
  floor 2.0 | standoffs 8.0 (M.2 drives + back-side parts) | carrier 1.6 | Mirror Mezz 2.5 mm part = 5.0 board-to-module
  | Jetson T5000 15.29 (incl. thermal transfer plate) | heatsink fins 28 | 2 mm air gap | lid 2.0
Outer size: 252 x 300 x 64 mm (about 4.8 litres)."""
import bpy, bmesh, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
T = 2.0                                   # wall / floor / lid thickness
BW, BH = 240.0, 256.0                     # carrier board
X0, X1 = -6.0, 246.0                      # outer x
YR, YF = -262.0, 38.0                     # outer y: rear, front (front leaves room for the panel and intake)
ZT = 64.0                                 # outer height
Z_BOARD = T + 8.0                         # board underside
Z_MOD = Z_BOARD + 1.6 + 5.0               # module underside
MOD_H, FIN_H = 15.29, 28.0
MOD = [(58.0, 55.0), (182.0, 55.0), (58.0, 164.0), (182.0, 164.0)]   # module centres (board coords)
FAN = 40.0                                # 40 x 40 x 28 mm exhaust fans, 4 on the rear wall
FAN_X = [24.0, 66.0, 136.0, 178.0]        # left edges (board x); QSFP28 cage sits between the pairs (x 109-131)
FAN_Z = 18.0
PANEL = (45.0, 195.0, 8.0, 58.0)          # status panel window on the front: x0, x1, z0, z1

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene; s.unit_settings.system = 'METRIC'; s.unit_settings.scale_length = 0.001

def box(name, x0, x1, y0, y1, z0, z1, col=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1; v.co.y = y0 if v.co.y < 0 else y1; v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    if col: ob.data.materials.append(mat(col))
    return ob

def cyl(name, x, y, z0, z1, r, col=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=z1 - z0, location=(x, y, (z0 + z1) / 2))
    ob = bpy.context.active_object; ob.name = name
    if col: ob.data.materials.append(mat(col))
    return ob

_mats = {}
def mat(rgba):
    if rgba not in _mats:
        m = bpy.data.materials.new(f"m{len(_mats)}"); m.diffuse_color = rgba; _mats[rgba] = m
    return _mats[rgba]

def cut(target, cutters):
    for c in cutters:
        md = target.modifiers.new("cut", 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = c
        bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(c, do_unlink=True)

def union(target, parts):
    for p in parts:
        md = target.modifiers.new("add", 'BOOLEAN'); md.operation = 'UNION'; md.solver = 'EXACT'; md.object = p
        bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(p, do_unlink=True)

def slots(x0, x1, y0, y1, z0, z1, n, axis):
    """n vent slots, 2 mm wide, spread along `axis` ('x' or 'z') inside the given box."""
    out = []
    for i in range(n):
        if axis == 'x':
            a = x0 + (x1 - x0) * (i + 0.5) / n; out.append(box("slot", a - 1.0, a + 1.0, y0, y1, z0, z1))
        else:
            a = z0 + (z1 - z0) * (i + 0.5) / n; out.append(box("slot", x0, x1, y0, y1, a - 1.0, a + 1.0))
    return out

def build():
    clear()
    BLACK, DARK, GREY, ALU = (0.03, 0.03, 0.035, 1), (0.09, 0.09, 0.1, 1), (0.35, 0.36, 0.38, 1), (0.62, 0.63, 0.66, 1)
    # ---- tray: floor + 4 walls, open top
    tray = box("tray", X0, X1, YR, YF, 0, ZT - T, DARK)
    cut(tray, [box("inside", X0 + T, X1 - T, YR + T, YF - T, T, ZT)])
    # rear wall (y = YR): 4 fan openings, QSFP28 window, 4 USB-C slots, power cable gland
    rear = [box("fan", x, x + FAN, YR - 1, YR + T + 1, FAN_Z, FAN_Z + FAN) for x in FAN_X]
    rear += [box("qsfp", 107.5, 132.5, YR - 1, YR + T + 1, Z_BOARD + 1.6, Z_BOARD + 1.6 + 10.5)]
    rear += [box("usbc", 162 + 13 * m - 5.0, 162 + 13 * m + 5.0, YR - 1, YR + T + 1, Z_BOARD + 1.6, Z_BOARD + 1.6 + 4.0) for m in range(4)]
    g = cyl("gland", 0, 0, -4, 4, 6.5); g.rotation_euler = (math.pi / 2, 0, 0); g.location = (10.0, YR + T / 2, 30.0)
    rear += [g]
    cut(tray, rear)
    # front wall (y = YF): panel window in the middle, intake slots either side
    front = [box("panel", PANEL[0], PANEL[1], YF - T - 1, YF + 1, PANEL[2], PANEL[3])]
    front += slots(X0 + 8, PANEL[0] - 6, YF - T - 1, YF + 1, 8, ZT - 10, 6, 'x')
    front += slots(PANEL[1] + 6, X1 - 8, YF - T - 1, YF + 1, 8, ZT - 10, 6, 'x')
    cut(tray, front)
    # board standoffs (M3, at the carrier's 4 case holes)
    for i, (x, y) in enumerate([(4.5, 4.5), (BW - 4.5, 4.5), (4.5, BH - 4.5), (BW - 4.5, BH - 4.5)]):
        s = cyl(f"standoff{i}", x, -y, T, Z_BOARD, 3.5); union(tray, [s])
        cut(tray, [cyl("m3", x, -y, -1, Z_BOARD + 1, 1.25)])
    # ---- lid: plate with intake slots above the front half of each module column
    lid = box("lid", X0, X1, YR, YF, ZT - T, ZT, DARK)
    lid_slots = []
    for cx, cy in MOD[:2]:
        lid_slots += slots(cx - 40, cx + 40, -(cy + 30), -(cy - 45), ZT - T - 1, ZT + 1, 14, 'x')
    cut(lid, lid_slots)
    for i, (x, y) in enumerate([(X0 + 6, YR + 6), (X1 - 6, YR + 6), (X0 + 6, YF - 6), (X1 - 6, YF - 6)]):
        cut(lid, [cyl("lidscrew", x, y, ZT - T - 1, ZT + 1, 1.7)])
    # ---- contents (reference only, not exported): carrier, modules, heatsinks, fans, status panel
    box("carrier", 0, BW, -BH, 0, Z_BOARD, Z_BOARD + 1.6, BLACK)
    for i, (cx, cy) in enumerate(MOD):
        box(f"thor{i}", cx - 43.5, cx + 43.5, -(cy + 50), -(cy - 50), Z_MOD, Z_MOD + MOD_H, GREY)
        hs = box(f"fins{i}", cx - 43.5, cx + 43.5, -(cy + 46), -(cy - 46), Z_MOD + MOD_H, Z_MOD + MOD_H + FIN_H, ALU)
        cut(hs, slots(cx - 42, cx + 42, -(cy + 47), -(cy - 47), Z_MOD + MOD_H + 3, Z_MOD + MOD_H + FIN_H + 1, 28, 'x'))
    for x in FAN_X:
        f = box("fan", x, x + FAN, YR + T, YR + T + 28, FAN_Z, FAN_Z + FAN, BLACK)
        h = cyl("hub", 0, 0, -16, 16, 18.5); h.rotation_euler = (math.pi / 2, 0, 0)
        h.location = (x + FAN / 2, YR + T + 14, FAN_Z + FAN / 2); cut(f, [h])
    box("status_panel", PANEL[0] + 0.5, PANEL[1] - 0.5, YF - T - 6, YF - T - 4.4, PANEL[2] + 0.5, PANEL[3] - 0.5, BLACK)
    # ---- export the two manufactured parts
    for ob in (tray, lid):
        bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.wm.stl_export(filepath=os.path.join(HERE, f"enclosure_{ob.name}.stl"), export_selected_objects=True,
                              global_scale=1.0, apply_modifiers=True)
    return tray, lid

def render(tray, lid, name, lid_on):
    lid.hide_render = not lid_on
    s = bpy.context.scene
    s.render.engine = 'BLENDER_WORKBENCH'; s.display.shading.light = 'STUDIO'; s.display.shading.color_type = 'MATERIAL'
    s.display.shading.show_shadows = True; s.display.shading.show_cavity = True
    s.render.resolution_x, s.render.resolution_y = 1600, 1000; s.render.film_transparent = False
    w = bpy.data.worlds.new("w"); w.color = (0.92, 0.92, 0.93); s.world = w
    cam = bpy.data.cameras.new("cam"); cam.lens = 55; cam.clip_end = 5000
    co = bpy.data.objects.new("cam", cam); s.collection.objects.link(co); s.camera = co
    co.location = (620, 420, 420); target = (120, -110, 20)
    d = [target[i] - co.location[i] for i in range(3)]
    co.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    s.render.filepath = os.path.join(HERE, "shots", name)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(co, do_unlink=True)

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "shots"), exist_ok=True)
    tray, lid = build()
    render(tray, lid, "enclosure_open.png", False)
    render(tray, lid, "enclosure_closed.png", True)
    print("enclosure done")
