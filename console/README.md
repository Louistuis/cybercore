# CyberCore Console (rev 0.2, proof of concept)

A slim, black, console-sized box that runs **DeepSeek V3.1 (671B)** locally, on our own carrier board with
**4 × NVIDIA Jetson T5000 (AGX Thor) modules**. Each module has 128 GB of memory, so there is **512 GB in total**.

![console carrier, angled](shots/console_angle.png)

## What's on the board
| Block | What | Status |
|---|---|---|
| Compute | 4 × Jetson T5000 module (87 × 100 mm), 699-pin Molex Mirror Mezz, 2.5 mm connector = **5 mm** between board and module | Pin map **real** (NVIDIA). Outline, connector position, row layout and standoffs **measured** from NVIDIA's drawings |
| Memory | 4 × 128 GB LPDDR5X = 512 GB (273 GB/s per module, per NVIDIA's spec) | On the modules |
| Module-to-module | Full mesh: each module's MGBE C0-C2 (UPHY lanes 12-14) wired straight to the 3 others, 6 links, AC caps on the back | Nets real, not routed |
| Network clock | One 156.25 MHz HCSL oscillator per module into UPHY_REFCLK2, terminated as in DG-12084 fig. 7-12 (33.2 Ω series, 49.9 Ω to GND) | Real part; its pinout is **assumed** (see below) |
| Uplink | Each module's MGBE C3 → one lane of a QSFP28 cage (4 × 25G breakout = one port per module) | **Placeholder footprint** |
| Storage | 1 × M.2 2280 NVMe per module on the back (PCIe C5 x4, UPHY lanes 8-11), each holding its share of the model | Nets real, stock footprint |
| Power | 12 V in through 2 × EPS-style Mini-Fit Jr 8-pin (~600 W). See the power section | Real TI parts and land patterns |
| Management | Per module: 2×20 1.27 mm header (sequencing, reset, recovery, thermal, debug UART, I2C, eFuse enables). One system header: buck enable, PMBus, power-good, current monitors, QSFP sideband | Real connectors. The BMC board that plugs in is not designed yet |
| Service | 4 × USB-C on the rear (each module's USB0, used for recovery and flashing) | Real |
| Front | The black **CyberCore status panel** (`../panel/`) plugs into J3 (module 0's USB1 + 5 V) | Panel is finished and orderable |
| Cooling | 4 fan headers, each module driving its own blower (FAN_PWM / FAN_TACH) | Real connectors; the thermal design is not done |

Board: 240 × 256 mm, 12 layers (HDI rules: 0.10 mm clearance), 1.6 mm, **black solder mask, ENIG**.
With the 2.5 mm connector, NVIDIA allows **no parts under a module** on the top side. The module footprint carries a keep-out rule area, so DRC fails if anything lands there.
Everything that belongs to a module (eFuses, load switch, clock, AC caps, M.2 drive, management header) sits on the **back**, right under it.

## Power
| Rail | Part | Setting |
|---|---|---|
| 12 V → 5 V, 20 A | TI **TPS546B24A** (LQFN-CLIP-40, LCSC C3189423) + Coilcraft XAL7070 1 µH, 6 × 47 µF out | Pin straps: 5.0 V, 550 kHz, 3 ms soft start, PMBus 0x10. Enabled by management |
| 12 V → 3.3 V, 20 A | TI **TPS546B24A**, same power stage | Pin straps: 3.32 V, PMBus 0x11. Always on (standby rail), starts at ~8.4 V in |
| Module SYS_VIN_HV (12 V) | TI **TPS25982** eFuse per module (VQFN-24, LCSC C2155761) | 13.4 A limit (T5000 ≈ 130 W ≈ 11 A), latch-off on fault, current monitor to the system header |
| Module SYS_VIN_MV (5 V) | TI **TPS25982** per module | 8.1 A limit (**assumed**, NVIDIA gives no MV current) |
| Module SYS_VIN_SV (3.3 V) | TI **TPS22918** load switch per module (SOT-23-6, LCSC C131941) | Quick output discharge on, so SV falls after HV and MV |

Each converter's footprint was drawn from TI's own land-pattern drawing (RVF0040A, RGE0024M). The strap resistor values come from the TPS546B24A datasheet tables.

## The model math (DeepSeek V3.1)
- **Size:** 671B parameters at 4-bit ≈ 380-400 GB.
  - 512 GB minus each module's OS share leaves ~460 GB, so it fits with ~50 GB for context cache.
  - 8-bit (~700 GB) does **not** fit.
- **Per token:** 37B active parameters ≈ 18.5 GB read per token.
- **Speed:**
  - Layers split across the 4 modules (pipeline): one module works at a time, so the ceiling is 273 GB/s ÷ 18.5 GB ≈ **15 tok/s**.
  - Experts split across all 4 modules working at once over the 25G mesh: the ceiling is ~1.1 TB/s ÷ 18.5 GB ≈ **59 tok/s**. Mesh latency on every layer eats into that.
  - **Estimate: about 10-25 tok/s for one user.** Measure it before believing it.
  - For scale: a 512 GB Apple Mac Studio does ~17-25 tok/s on this model, and hosted datacenter services ~200.
- **Power:** ~520 W for the modules at full power + NVMe + fans ≈ 600 W.
- **Module cost:** NVIDIA lists the T5000 at $4,999 each (1,000-unit price), so ~$20k for 4 before the board and case.

## Build status (honest)
**Real now:**
- Board outline and the 12-layer black stackup
- Every connection the board makes to each module's 699 pins, taken from NVIDIA's pin description spreadsheet: power, GND, PCIe, MGBE, MGBE clock, USB, management
- Module outline, connector position, row layout and the 4 standoff holes, measured from NVIDIA's drawings
- Power: TI bucks, eFuses and load switches with their real land patterns and set-up resistors
- Stock connectors (M.2, USB-C, Mini-Fit Jr, fan headers, management headers)
- DRC: 0 violations (with 499 unrouted connections, because nothing is routed yet)

**Still to confirm before ordering:**
1. **Mirror Mezz pad size and pitch.** Measured from NVIDIA's drawings: 0.96 mm column pitch, 1.50 mm row pitch, alternate rows offset by half a pitch, ±0.05-0.5 mm. Molex's 1.30 mm "pitch" listing doesn't fit the 64.7 mm body, so that number was dropped.
   - Confirm against Molex's 203456 drawing and NVIDIA's reference layout. Which rows carry the half-pitch offset is also measured, not documented.
2. **QSFP28 footprint (still a placeholder).** Pin numbers follow SFF-8679, but the TE and U-MAX drawings couldn't be downloaded (their sites block automated downloads). Candidate part: U-MAX UMAX95202101 (connector + cage, LCSC C42434130).
3. **Oscillator pinout.** HCSL oscillator SX5DF156.250B20F30HNN (LCSC C5830692). Its datasheet couldn't be downloaded, so the standard 6-pin layout is assumed: 1 OE, 2 NC, 3 GND, 4 OUT+, 5 OUT−, 6 VDD.
4. **Buck compensation.** Compensation setting 19 is a starting point; check it in TI's design tool for the 1 µH + 282 µF filter.
5. **MV current limit.** 8.1 A is an assumption until NVIDIA's power numbers for SYS_VIN_MV are known.
6. **MV_LSW_MON (pin L42).** NVIDIA's documents don't describe it, so it is left unconnected.

**Open questions:**
- **The direct MGBE-to-MGBE mesh.** XFI is meant to drive an SFP+ module. A short PCB link acts like a passive copper cable, but it must be checked against design guide section 7.3.
- **25 GbE speed.** NVIDIA says it is "being validated", so plan on 10G per link until it is confirmed.
- **Sequencing.** Every module has its own SYS_VIN_SV → MV/HV → MODULE_POWER_ON sequence (DG-12084 chapter 5). The eFuses and switches are on the board now, but the logic that drives them runs on the management board, which isn't designed yet.
- **Cooling.** ~600 W in a slim box needs vapor chambers on the modules' thermal plates and 4 blowers. That's the hardest part of "slim".

**Not done:** routing (12-layer HDI, with length-matched 25G and PCIe Gen4 pairs), the BMC board, the enclosure, and power/thermal simulation.

## Rebuild
1. Download NVIDIA's *Jetson Thor Series Modules Design Guide* (DG-12084-001, free from developer.nvidia.com).
2. Extract its attachments: `pdfdetach -saveall -o datasheets/nv_attach <guide.pdf>`.
3. Run the build script with KiCad's Python:
```
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 make_console.py
kicad-cli pcb drc -o drc.rpt console.kicad_pcb
```
NVIDIA's documents and the pin spreadsheet are **not** in this repo; the script reads them from your own download. The TI datasheets used for the power stage are free on ti.com (TPS546B24A, TPS25982, TPS22918).
