# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore top-level block diagram as a KiCad schematic (A3). Blocks + buses only: the parts-level schematic
needs pin maps for the CC-G1 GPU (not designed yet), the AMD SP5 socket (NDA), the fabric switch and the BMC.
See ../README.md. Run with any python3."""
import os, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
out = []
U = lambda: f'(uuid "{uuid.uuid4()}")'

def text(x, y, s, size=1.8, bold=False):
    s = s.replace('"', '\\"')
    out.append(f'\t(text "{s}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size})'
               f'{" (bold yes)" if bold else ""}) (justify left bottom)) {U()})')

def box(x, y, w, h, title, lines, width=0.35, size=1.7):
    out.append(f'\t(rectangle (start {x} {y}) (end {x+w} {y+h}) (stroke (width {width}) (type default)) '
               f'(fill (type none)) {U()})')
    text(x + 2, y + 4.5, title, 2.2, bold=True)
    for i, l in enumerate(lines):
        text(x + 2, y + 9 + i * 3.3, l, size)

def bus(pts, width=0.6):
    p = " ".join(f"(xy {x} {y})" for x, y in pts)
    out.append(f'\t(polyline (pts {p}) (stroke (width {width}) (type default)) {U()})')

text(15, 17, "CyberCore XL  rev 0.2  block diagram", 4.0, bold=True)
text(15, 23.5, "4 x CC-G1 GPU (our design) + 2 x AMD EPYC 9005, 3.2 TB unified memory, 3.7 TB/s GPU memory bandwidth. "
               "Board: cybercore.kicad_pcb (22 layers, 440 x 640 mm)", 1.9)

GPU = ["768 GB LPDDR5X memory-down, 1024 bit, 922 GB/s", "FP4 / FP8 matrix engines (target ~1 PFLOP FP4)",
       "800 GB/s fabric link + CXL x16 to its CPU", "16-phase VR, ~0.8 kW"]
gpus = {0: (15, 30), 1: (275, 30), 2: (15, 122), 3: (275, 122)}
for n, (x, y) in gpus.items():
    box(x, y, 130, 26, f"GPU {n}: CC-G1 (our own chip, placeholder)", GPU)

box(160, 30, 100, 26, "EXPANSION + STORAGE + NETWORK",
    ["J1-J4 PCIe 5.0 x16 slots (2 per CPU)", "J5-J12 M.2 NVMe 8 x 8 TB = 64 TB (4 per CPU)",
     "J13-J14 QSFP-DD 800G (from CC-F1)", "J16 RJ45 10GbE"])

box(160, 62, 100, 54, "CC-F1 GPU FABRIC (placeholder)",
    ["All-to-all switch between the 4 GPUs", "800 GB/s per GPU link", "Expert-parallel MoE traffic",
     "Lets any GPU read any other GPU's memory", "2 x 800G Ethernet to QSFP-DD", "(CyberCore-to-CyberCore scale-out)",
     "PCIe x4 management link to BMC"])
for n, (x, y) in gpus.items():
    cx = x + 130 if x < 100 else x
    cy = y + 13
    fx = 160 if x < 100 else 260
    fy = 80 if y < 100 else 100
    mx = (cx + fx) / 2
    bus([(cx, cy), (mx, cy), (mx, fy), (fx, fy)])
    text(mx - 6 if x < 100 else 261.5, cy - 1, "800 GB/s", 1.5)
bus([(210, 56), (210, 62)])

box(15, 62, 130, 54, "POWER (12 V single rail)",
    ["J18, J19, J29 Molex Mini-Fit Sr 2x4, 160 A each", "  budget 3 x 1.9 kW = 5.7 kW",
     "GPUs 4 x 0.8 kW = 3.2 kW", "CPUs 2 x 0.5 kW = 1.0 kW (12-phase VR each)",
     "Fabric, NVMe, BMC, fans ~0.35 kW", "  peak ~4.6 kW: direct liquid cooling needed",
     "In2.Cu P12V plane, In1 / In3 GND planes", "PMBus telemetry + sequencing from BMC"])

box(275, 62, 130, 54, "BMC + PLATFORM (placeholder BMC)",
    ["U6 AST2600-class BMC, U8 64 MB SPI NOR", "U9 host boot SPI NOR (64 MB)",
     "J15 RJ45 BMC network (Redfish / IPMI)", "J17 USB-C serial console",
     "J20-J27 8 x 4-pin PWM fans / pumps", "J28 front panel, BT1 CR2032 RTC",
     "U10 PCIe / CXL / fabric clock generator", "Temps + power -> telemetry dashboard"])

CPU = ["Up to 192 Zen 5 cores: OS, scheduler, tokenizer, API", "64 GB DDR5-6400 memory-down (4 ch, ECC)",
       "80 PCIe 5.0 lanes: 2 x CXL x16 + 2 slots + 4 M.2"]
box(15, 158, 130, 30, "AMD CPU0: EPYC 9005 (SP5)", CPU + ["CXL x16 coherent to GPU 0 and GPU 2"])
box(275, 158, 130, 30, "AMD CPU1: EPYC 9005 (SP5)", CPU + ["CXL x16 coherent to GPU 1 and GPU 3"])
bus([(80, 148), (80, 158)]); text(82, 155, "CXL x16 (to GPU 2; GPU 0 the same)", 1.5)
bus([(340, 148), (340, 158)]); text(342, 155, "CXL x16 (to GPU 3; GPU 1 the same)", 1.5)
bus([(145, 173), (275, 173)]); text(185, 172, "xGMI x3  CPU0 <-> CPU1", 1.6)

box(160, 122, 100, 30, "UNIFIED MEMORY  3.2 TB, one address space",
    ["GPU own pool: 922 GB/s", "GPU -> other GPU pool: 800 GB/s (fabric)", "CPU -> GPU pool: ~64 GB/s each way (CXL)",
     "GPU -> CPU DDR5: ~64 GB/s (CXL)"], size=1.6)

box(15, 196, 280, 52, "BUILD STATUS (read before ordering anything)",
    ["REAL: outline, 22-layer setting, power planes, stock connectors with 12 V / GND nets. DRC 0 errors, ERC 0.",
     "PLACEHOLDER: CC-G1 GPU (a chip we would have to design and tape out), AMD SP5 socket (land pattern is AMD NDA),",
     "  CC-F1 fabric, BMC, memory ballouts. Right size and pitch class, no pin maps. Not routed, not orderable yet.",
     "CHECK: CPU <-> GPU coherency needs CXL Type 2 device support on EPYC. AMD's own ready-made version of this idea",
     "  is the Instinct MI300A (CPU + GPU, 128 GB unified HBM3 per package).",
     "Model math: 5T params x 4 bit = 2.5 TB + ~0.4 TB KV/runtime -> fits. MoE ~150B active: 75 GB/token over",
     "  3.7 TB/s -> ceiling ~49 tok/s, expect ~25-30. The CPUs do not add speed: GPU memory bandwidth sets it."],
    width=0.5, size=1.6)

box(300, 196, 105, 52, "WHY THIS LAYOUT",
    ["The memory sits on the GPUs because tokens/s", "comes from memory bandwidth, and the GPUs", "do the math.",
     "The CPUs map that memory over CXL, so the", "OS and the model share one pool: no copies.",
     "CPUs run the server around the model:", "OS, storage, network, API, batching."], size=1.6)

body = "\n".join(out)
sch = f"""(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "9.0")
\t(uuid "{uuid.uuid4()}")
\t(paper "A3")
\t(title_block
\t\t(title "CyberCore XL - AI inference server board")
\t\t(date "2026-11-16")
\t\t(rev "0.2 concept")
\t\t(company "Louis Studios hardware-lab")
\t)
\t(lib_symbols)
{body}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""
open(os.path.join(HERE, "cybercore.kicad_sch"), "w").write(sch)
print("wrote cybercore.kicad_sch")
