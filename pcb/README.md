# CyberCore XL (rev 0.2 concept, 2026-11-16): the dream board

AI inference server board: 4 of our own CC-G1 GPUs and 2 AMD EPYC CPUs, all sharing one 3.2 TB unified memory space.
The memory is soldered right next to each chip (memory-down). It is built to hold a 5-trillion-parameter model at 4-bit.

**This board is a concept and can't be built.** For the CyberCore that can actually be bought and run
(an 8-GPU AMD Instinct server), see [REAL-BUILD.md](../REAL-BUILD.md), or the [CyberCore Console](../console/) for the slim build.

## Files
| File | What |
|---|---|
| `make_board.py` | Builds `cybercore.kicad_pcb` and the custom footprints in `CyberCore.pretty/` (run with KiCad's Python) |
| `make_schematic.py` | Builds `cybercore.kicad_sch`, the top-level block diagram (any python3) |
| `cybercore.kicad_pro` | Open this in KiCad 10 |
| `cybercore_blocks.pdf` | Block diagram as a PDF |
| `shots/` | 3D renders (top, angled) + block diagram PNG |
| `drc.rpt`, `erc.rpt` | Latest checks |

Rebuild:
```
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 make_board.py
python3 make_schematic.py
kicad-cli pcb drc --refill-zones -o drc.rpt cybercore.kicad_pcb
```

## Architecture
- **4 x CC-G1 GPU (our own chip).** Each one is a 70 x 70 mm package that owns 12 LPDDR5X x64 packages: 768 GB at 9600 MT/s = 922 GB/s.
  The GPUs do all the model math, so they sit on the memory. Total: 3,072 GB at ~3.7 TB/s.
- **2 x AMD EPYC 9005 (SP5 socket).** Each CPU has 64 GB of its own DDR5-6400, memory-down (4 channels x 5 x16 chips, ECC).
  It boots and runs the OS, storage, networking, the API and batching.
- **Unified memory.** Each CPU links to two GPUs over a coherent CXL x16 link (CPU0: GPU 0 + 2, CPU1: GPU 1 + 3).
  CPUs and GPUs then see one 3.2 TB address space with no copies.
  - GPU to its own memory: 922 GB/s
  - GPU to another GPU's memory, through the CC-F1 fabric: 800 GB/s
  - CPU to GPU memory, or GPU to CPU memory, over CXL: ~64 GB/s each way
- **CC-F1 fabric switch.** All-to-all switch between the GPUs, plus 2 x 800G Ethernet to link two CyberCores.
- **CPU-to-CPU:** 3 xGMI links. That leaves 80 PCIe 5.0 lanes per CPU: 2 x CXL x16, 2 slots and 4 M.2.

## Board
- 440 x 640 mm custom form factor (4U 19-inch, deep chassis), 22 copper layers, 2.4 mm thick, HDI rules (0.1 mm clearance)
- 4 x PCIe 5.0 x16 slots, 8 x M.2 NVMe (64 TB model store), 2 x QSFP-DD 800G, RJ45 BMC + 10GbE, USB-C console
- BMC with 64 MB SPI flash, host boot flash, clock generator, RTC battery, 8 PWM fan/pump headers, front panel header
- Power: 12 V in through 3 x Molex Mini-Fit Sr 2x4 (~5.7 kW budget)
  - Each GPU has a 16-phase VR (~0.8 kW), each CPU a 12-phase VR (~0.5 kW). Peak is ~4.6 kW, so it needs direct liquid cooling.
  - 12 V plane on In2, GND on In1 + In3

## Model math
- 5T params x 4 bit = 2.5 TB of weights. KV cache and runtime need roughly 0.4 TB more, which fits in 3.2 TB. 8-bit (5 TB) does NOT fit.
- Speed comes from GPU memory bandwidth, because every token has to read the active weights:
  - Mixture-of-experts with ~150B active params: 75 GB per token, so a ceiling of ~49 tok/s and ~25-30 tok/s in practice.
  - Dense 5T: ~1.5 tok/s at best.
- The AMD CPUs do not make tokens faster. They make it a complete server, and unified memory removes the copies between CPU and GPU.
- Loading the model from 8 Gen5 NVMe drives (~110 GB/s) takes ~25 s.

## Build status (honest)
Real now:
- Board outline, layer count, power planes and mounting holes
- Every stock-library connector with real 12 V / GND nets
- DRC: 0 errors, 0 unconnected. 34 warnings: silkscreen text overlaps, plus the QSFP cages crossing the rear edge on purpose.
- ERC: 0 violations

Placeholders (right size and pitch class, but no pin map):
- **CC-G1 GPU.** It is a chip we would have to design and tape out. That is a silicon project costing many millions, not a PCB job.
- **AMD SP5 socket.** AMD only gives the land pattern, frame drawing and pinout to partners under NDA.
- **CC-F1 fabric switch, BMC, and the LPDDR5X / DDR5 ballouts.**

Assumptions to check:
- 64 GB x64 LPDDR5X packages. That is at the top end of what memory makers ship.
- CPU-to-GPU coherency needs EPYC support for CXL Type 2 devices (accelerators with their own memory). Confirm this with AMD.
  Otherwise the CPUs see GPU memory as plain CXL memory, without full coherency.
- AMD's own off-the-shelf version of this idea is the Instinct MI300A: CPU + GPU in one package with 128 GB of unified HBM3.
  That is too small per package for a 5T model.
- Approximate footprints: the PCIe x16 slot and the QSFP-DD cage. Replace them with vendor drawings before any order.

Not done:
- No routing, which needs the real pin maps
- No parts-level schematic
- No SI/PI simulation and no thermal design
