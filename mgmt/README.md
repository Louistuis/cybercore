# CyberCore management board (rev 1.0)

The console's power and reset controller: a small black board that plugs into the **CyberCore Console** carrier with five 40-way ribbon cables.
- It switches each Jetson T5000 module on and off in NVIDIA's order.
- It holds modules in reset or recovery, and watches power-good, current and temperature.
- It gives you all four module debug consoles over one USB-C cable.

The console carrier has no logic of its own; this board is its brain.

![management board](shots/mgmt_angle.png)

## What it does
| Block | Parts | What it does |
|---|---|---|
| Brain | ESP32-S3-WROOM-1-N16R8 (C2913202) | Runs the sequencing in [SEQUENCING.md](SEQUENCING.md). Wi-Fi status page, USB-C (MCU) for firmware and a serial console |
| Control outputs | 5 × TCA9535PWR I/O expanders (C130204), 0x20-0x23 one per module, 0x24 system | Hold every enable and request. An ESP32 reset or firmware update never drops a running module, because the expanders stay powered and keep their outputs |
| Power-bad | 74LVC07A (C7809) per module, wired-AND | `VDDIN_PWR_BAD_N` is released only when the module's HV eFuse PG **and** MV eFuse PG **and** the firmware all agree. A dropping eFuse flags power-bad in hardware, with no firmware in the loop |
| Power-on | SN74AHCT1G08 (C113521) per module on a 5 V always-on rail | Drives `MODULE_POWER_ON` at 5 V like NVIDIA's reference (DG-12084 fig 5-7), and only while `VDDIN_PWR_BAD_N` is high |
| Reset, recovery, thermal request | 74LVC07A open-drain channels, 74LVC1G07 (C7829) | Pull `SYS_RESET_N`, `FORCE_RECOVERY_N`, `THERM_SHDN_REQ_N` low. They can only pull down, never drive a level |
| Reading the module | 2 × SN74LV4T125PWR (C90755) per module | Input-only buffers with a 1.35 V threshold and 5.5 V-tolerant inputs: they read the 1.8 V, 3.3 V and 5 V module outputs, and never feed current into a powered-down module |
| 1.8 V I/O guard | TPS22918 (C131941) per module, driven by that module's own `SYS_RESET_N` | Makes `M<m>_VIO`, the only 1.8 V source that touches the module. It is off whenever the module is in reset (NVIDIA DS-11945 table 6-2) |
| Debug UARTs | CH344Q (C2988084) on USB-C (CONSOLES) + SN74LV1T34 (C100024) per module | 4 module consoles as 4 serial ports, no firmware involved. The ESP32 listens on all four for its log |
| Module I2C | PCA9306DCUR (C33196) per module | 1.8 V module I2C3 ↔ the 3.3 V system bus (PMBus + QSFP28). Each module can be switched off the bus |
| Current | ESP32 ADC1 × 4, 10k + 100 nF per channel | HV eFuse current monitors: 1.16 V at 10 A, 1.55 V at the 13.4 A limit |
| Power | TLV75518 (C2877863) 1.8 V, TPS61222 (C116461) 5 V, both from the console's 3.3 V standby | The board takes nothing from USB, so it can never back-feed the console |
| Extras | Qwiic port (inlet temperature sensor), RESET / BOOT buttons, heartbeat LED, 4 × M3 holes | |

## Connections to the console
- **Headers:** 5 × 2×20 1.27 mm (C71827, through-hole), with the same reference designators as on the console:
  - J20-J23: modules 0-3
  - J4: SYS
- **Cables:** IDC ribbon, pin 1 to pin 1, so the pinout is identical on both ends. Odd pins carry the signals listed in `parts.py` (`MGMT` and `SYS`, copied from `console/make_console.py`); even pins are GND.
- **Power:** the board runs from the console's 3.3 V standby rail on pin 39 of every header (about 0.4 A peak with Wi-Fi transmitting).

## Signal levels: every decision and its source
| Module pin | NVIDIA says | This board | Source |
|---|---|---|---|
| MODULE_POWER_ON | Input, CMOS 5.0 V, driven low first | 5 V AND gate (5V_AO) + 100 Ω, 100k pull-down | DG-12084 table 5-1, fig 5-2 note 2, fig 5-7 / table 5-2 (5V_AO gate, PP) |
| CARRIER_POWER_ON | Output, open drain 3.3 V, 10k pull-up on module | Read directly by the expander (3.3 V), 100k pull-down | DG table 5-1 |
| SYS_RESET_N | Bidir, open drain 1.8 V, 10k to 1.8 V on module | Read via LV4T125; pulled low by a 74LVC07; drives the VIO switch; 470k pull-down | DG table 5-1, DS table 3-1 |
| VDDIN_PWR_BAD_N | Open drain 5.0 V, 10k to 5 V on module | Three 74LVC07 outputs wired-AND (HV_PG, MV_PG, firmware); read via LV4T125 (5.5 V tolerant) | DG table 5-1, 5.1.1, 5.1.4 |
| FORCE_RECOVERY_N | Input, CMOS 1.8 V, 20k to 1.8 V on module | 74LVC07 open drain only | DG table 5-1, fig 18-1, ch 18 |
| MODULE_SHDN_N | Output, CMOS 1.8 V, 10k to 1.8 V on module | Read via LV4T125 | DG table 5-1 |
| THERM_ALERT_N | Open drain "3.3 V" (DG, DS), but the schematic checklist lists a 10k pull-up to 1.8 V on the module | Read via LV4T125 (works for either level), 100k to M<m>_VIO | DG table 5-1, DS table 3-1, Schematic Checklist v1.1 "Module_Signal_Term" |
| THERM_SHDN_REQ_N | **Not described** (only in the pin spreadsheet, G59) | Read via LV4T125 + 74LVC07 pull-down, 100k to VIO; firmware leaves it alone | Pin Descriptions v1.0 only |
| MODULE_POWER_GOOD | **Not described** (only in the pin spreadsheet, L59) | Read only via LV4T125, 100k pull-down | Pin Descriptions v1.0 only |
| PRSNT0 / PRSNT1 | Tied together on the module | PRSNT0 = GND, PRSNT1 10k to 3.3 V, read (low = seated) | DG table 5-1, fig 5-7 (PRSNT1 to 3V3_AO) |
| UART3_TX_DEBUG | Output, CMOS 1.8 V | Read via LV4T125 into the CH344Q, 100k to VIO | DG 17.2.2, table 17-3 |
| UART3_RX_DEBUG | Input, 1.8 V | SN74LV1T34 powered from VIO (off in reset, Ioff), 100 Ω; 100k pull-up on the 3.3 V side | DG table 17-3 |
| I2C3_CLK / DAT | Open drain 1.8 V, 1k to 1.8 V on module | PCA9306, VREF1 = VIO, enable through 74LVC1G07 | DG table 12-2, SP-12533 |
| HV_EN, MV_EN, SV_EN, BUCK5_EN | eFuse EN/UVLO 1.2 V (max 7 V), TPS22918 ON 1.0 V, TPS546B24A EN (max 5.5 V); 100k pull-downs on the console | 3.3 V push-pull from the expanders | TPS25982, TPS22918, TPS546B24A data sheets |
| HV_PG, MV_PG, BUCK5_PG | Open drain, 10k to 3.3 V on the console | Read directly + feed the power-bad AND | console/make_console.py |
| HV_IMON | 246 uA/A × 470 Ω | 10k + 100 nF into ESP32 ADC1 (0-3.1 V at 12 dB) | TPS25982 7.3.5 (10k series recommended) |
| QSFP sideband | 3.3 V LVTTL | Direct; 10k host pull-ups on ModPrsL and IntL | SFF-8679 |

**The one rule behind the table:** no 1.8 V module input is ever driven high while that module's `SYS_RESET_N` is low (DS-11945 table 6-2, VM_PIN).
- The only push-pull driver into a 1.8 V module input, and every 1.8 V pull-up, sit on `M<m>_VIO`.
- A load switch turns `M<m>_VIO` on from the module's own `SYS_RESET_N`, and off within ~15 µs when it falls.

## Board
- 132 × 72 mm, **6 layers** (F.Cu signal + GND, In1.Cu GND plane, In2.Cu and In3.Cu signal, In4.Cu 3V3 plane, B.Cu signal + GND), 1.6 mm, **black solder mask, white silk, ENIG**, all parts on top. It started as 4 layers, but Freerouting could not finish that at this size.
- **Rules:** JLCPCB standard 6-layer (0.127 mm track and space, 0.5 / 0.25 mm vias).
- **Routing:** Freerouting.
- **DRC:** see `drc.rpt`. **ERC:** see `erc.rpt`. Results are listed under "State" below.

## State
**Real:**
- Every pin of every part, from its maker's data sheet (TI, WCH, Espressif). The pin tables are quoted in `parts.py`.
- The console interface, copied from `console/make_console.py`.
- Every signal level, checked against NVIDIA's documents (table above).
- Every part was in stock at JLCPCB on 2026-11-17 (`jlc/stock.csv`).

**Routing is not finished.** After three Freerouting runs, 84 connections are still open and about 40 tracks are necked to 0.095 mm (JLC's minimum is 0.09). `mgmt_routed.kicad_pcb` is the work in progress: finish it by hand in KiCad, or give the board more room.

**Not verified (check before ordering):**
- `THERM_SHDN_REQ_N` and `MODULE_POWER_GOOD` are only names in NVIDIA's pin spreadsheet. The board treats them safely (read, plus an optional pull-down), but their function is unknown.
- `THERM_ALERT_N`: the design guide says 3.3 V open drain, the checklist says a 1.8 V pull-up. Both levels work here.
- `MODULE_POWER_ON` VIH is not published. The board drives 5 V as NVIDIA's reference does, so the number does not matter.
- **Cable polarity.** The console and this board both use plain (unkeyed) 1.27 mm pin headers. A ribbon plugged in rotated puts 3.3 V (pin 39) onto GND (pin 2). Use keyed IDC cables, or change both ends to shrouded headers.
- USB lines are 0.25 mm tracks with 0.15 mm gaps (about 90 Ω differential by the microstrip formula over JLC's thin outer prepreg), routed by Freerouting as single tracks, not as coupled pairs, and not ordered impedance-controlled. The CH344Q runs USB 2.0 high speed (480 Mbps): the runs are short (under ~15 mm), but this is not verified.
- **No firmware yet.** [SEQUENCING.md](SEQUENCING.md) is the specification.
- CPL rotations: check every polarised part in JLC's placement preview.

## Files
| File | What |
|---|---|
| `parts.py` | Netlist: every part, pin, LCSC number and data-sheet note |
| `make_mgmt.py` | Places parts (ICs fixed, passives by a greedy search) and writes `mgmt.kicad_pcb` |
| `route.py` | `export` → Freerouting → `import` → `mgmt_routed.kicad_pcb` (+ black stackup, GND / 3V3 pours) |
| `gen_sch.py` | Writes `mgmt.kicad_sch` from parts.py (one symbol per part, pins named by net) |
| `jlc_files.py` | `jlc/BOM.csv`, `jlc/CPL.csv`, `jlc/gerbers.zip` |
| `stock_check.py` | Live JLC stock for the BOM → `jlc/stock.csv` |
| `SEQUENCING.md` | The power-on / power-off / fault sequence the firmware must run, with NVIDIA section references |

## Rebuild
```
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KPY make_mgmt.py                      # mgmt.kicad_pcb
$KPY route.py export                   # mgmt.dsn
java -Xmx3g -Djava.awt.headless=true -jar freerouting-2.5.0.jar --gui.enabled=false \
     -de mgmt.dsn -do mgmt.ses --router.autorouter.max_passes=100
$KPY route.py import                   # mgmt_routed.kicad_pcb
$KPY gen_sch.py mgmt.kicad_pcb . && rm sym_uuids.json
$CLI pcb drc --severity-all -o drc.rpt mgmt_routed.kicad_pcb
$CLI sch erc -o erc.rpt mgmt.kicad_sch
$KPY jlc_files.py && python3 stock_check.py 5 jlc/BOM.csv
```

Data sheets are not in the repo. Download the TI, WCH and Espressif ones named in `parts.py` into `datasheets/` (git-ignored).

## Before ordering
1. Order settings: 6 layers, 1.6 mm, black mask, ENIG.
2. Use keyed 1.27 mm IDC cables (see cable polarity above). Check pin 1 on both ends.
3. In JLC's placement preview, check every IC, Y1, D1, the USB-C ports and the headers.
4. Bring-up order:
   1. Bench supply on 3V3 (pin 39) only.
   2. Flash the firmware.
   3. Plug the board into a console **with no modules fitted**, and check every enable with a scope.
   4. Then fit one module.
