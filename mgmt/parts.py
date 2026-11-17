# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""CyberCore management board rev 1.0: the netlist (one dict per part). make_mgmt.py places these, gen_sch.py draws the
schematic from them, jlc_files.py writes the BOM. Every LCSC number was looked up in the JLC parts API on 2026-11-17;
pin tables come from the KiCad symbol / footprint and the datasheets named per part (TI, WCH, Espressif).

What the board does: it is the console's power and reset controller (a small BMC). The console carrier has no logic of
its own; this board plugs into it with five 40-way 1.27 mm ribbon cables (J20-J23 = one per Jetson T5000 module, J4 =
system: 5 V buck, PMBus, current monitors, QSFP28 sideband) and runs DG-12084 chapter 5 power sequencing for each module.
An ESP32-S3 does the logic (Wi-Fi status page / USB console); five TCA9535 I2C expanders hold every control output, so
an ESP32 reboot or firmware update never drops a running module. A CH344Q gives the four module debug UARTs on a second
USB-C port without any firmware.

Power: 3V3 standby from the console (pin 39 on all five headers), nothing from USB.
  3V3 -> TLV75518 -> 1V8  -> one TPS22918 per module -> M<m>_VIO (on only while that module's SYS_RESET_N is high)
  3V3 -> TPS61222 -> 5V_AO (MODULE_POWER_ON is a 5 V CMOS input; NVIDIA's reference drives it from 5V_AO, DG fig 5-7)

Signal-level rules (sources in README.md / SEQUENCING.md):
  * nothing on this board ever drives a 1.8 V module input high while that module's SYS_RESET_N is low
    (DS-11945 table 6-2, VM_PIN): the only push-pull 1.8 V driver (UART3_RX) and every 1.8 V pull-up sit on M<m>_VIO,
    which a load switch derives from SYS_RESET_N itself;
  * every "assert low" into the module (SYS_RESET_N, FORCE_RECOVERY_N, VDDIN_PWR_BAD_N, THERM_SHDN_REQ_N) is an
    open-drain 74LVC07 output: it can only pull down, never drive a level;
  * every module output is read through an SN74LV4T125 (VIH 1.35 V at 3.3 V, inputs 5.5 V tolerant, Ioff), so 1.8 V,
    3.3 V and 5 V outputs read correctly and the inputs never source current into the module.
"""
C0402, C0603, C0805 = "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
CAP = {"100nF": ("C1525", C0402),   # CL05B104KO5NNNC 16 V X7R, basic
       "1uF": ("C52923", C0402),    # CL05A105KA5NQNC 25 V X5R, basic
       "22pF": ("C1555", C0402),    # 0402CG220J500NT 50 V C0G, basic
       "10uF": ("C19702", C0603),   # CL10A106KP8NNNC 10 V X5R, basic
       "22uF": ("C45783", C0805)}   # CL21A226MAQNNNE 25 V X5R, basic
RES = {"100": "C25076", "1k": "C11702", "4.7k": "C25900", "5.1k": "C25905", "10k": "C25744",   # 0402WGF 1 %, basic
       "100k": "C25741", "200k": "C25764",                                                     # basic
       "470k": "C25790"}                                                                       # 0402WGF4703TCE, extended
TSSOP24, TSSOP14 = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm"
SOT235, SOT236 = "Package_TO_SOT_SMD:SOT-23-5", "Package_TO_SOT_SMD:SOT-23-6"
HDR = "Connector_PinHeader_1.27mm:PinHeader_2x20_P1.27mm_Vertical"

PARTS = []
def part(ref, fp, value, lcsc, pins, nc=(), note="", group="core", near=None):
    PARTS.append({"ref": ref, "fp": fp, "value": value, "lcsc": lcsc, "pins": pins, "nc": {n: "nc" for n in nc},
                  "note": note, "group": group, "side": "F", "near": near})
def cap(ref, val, a, b="GND", group="core", near=None):
    part(ref, CAP[val][1], val, CAP[val][0], {"1": a, "2": b}, group=group, near=near)
def res(ref, val, a, b, group="core", near=None):
    part(ref, R0402, val, RES[val], {"1": a, "2": b}, group=group, near=near)

# ================================================================ console interface (pinout = console/make_console.py)
# 2 x 20, 1.27 mm, IDC ribbon pin 1 -> pin 1, so the pinout is identical on both ends: odd pins = signals, even = GND.
MGMT = ["MODULE_POWER_ON", "CARRIER_POWER_ON", "SYS_RESET_N", "MODULE_POWER_GOOD", "VDDIN_PWR_BAD_N", "FORCE_RECOVERY_N",
        "MODULE_SHDN_N", "THERM_ALERT_N", "THERM_SHDN_REQ_N", "PRSNT0", "PRSNT1", "UART3_TX_DEBUG", "UART3_RX_DEBUG",
        "I2C3_CLK", "I2C3_DAT", "HV_EN", "HV_PG", "MV_EN", "SV_EN", "3V3"]
SYS = ["BUCK5_EN", "BUCK5_PG", "PMBUS_CLK", "PMBUS_DAT"] + [f"M{m}_MV_PG" for m in range(4)] + \
      [f"M{m}_HV_IMON" for m in range(4)] + ["QSFP_MODSEL_N", "QSFP_RESET_N", "QSFP_SCL", "QSFP_SDA", "QSFP_MODPRS_N",
                                              "QSFP_INT_N", "QSFP_LPMODE", "3V3"]
assert len(MGMT) == 20 and len(SYS) == 20
# PMBus and the QSFP28 management bus are joined into one 3.3 V bus here (XSCL / XSDA, ESP32 I2C1). The QSFP module
# only answers while QSFP_MODSEL_N is low (SFF-8679), so it cannot disturb PMBus traffic otherwise.
SYSNET = {"PMBUS_CLK": "XSCL", "PMBUS_DAT": "XSDA", "QSFP_SCL": "XSCL", "QSFP_SDA": "XSDA"}
HDR_NOTE = "1.27 mm 2x20 vertical through-hole pin header, extended (1.5k). Keyed IDC cable recommended"
for m in range(4):
    hp = {str(2 * i + 2): "GND" for i in range(20)}
    for i, s in enumerate(MGMT):
        hp[str(2 * i + 1)] = "3V3" if s == "3V3" else "GND" if s == "PRSNT0" else f"M{m}_{s}"
    part(f"J{20+m}", HDR, f"MGMT M{m}", "C71827", hp, note=HDR_NOTE, group=f"m{m}")
sp = {str(2 * i + 2): "GND" for i in range(20)}
for i, s in enumerate(SYS): sp[str(2 * i + 1)] = SYSNET.get(s, s)
part("J4", HDR, "SYS", "C71827", sp, note=HDR_NOTE, group="sys")

# ================================================================ one block per module (refs x1xx, x2xx, x3xx, x4xx)
for m in range(4):
    b = 100 * (m + 1); M = lambda s: f"M{m}_{s}"; g = f"m{m}"
    # --- I/O expander, address 0x20 + m. TCA9535 = no internal pull-ups (unlike PCA9555), all pins are inputs after
    #     power-on reset, so every output below has its safe state set by a resistor until firmware writes it.
    #     TCA9535 TSSOP-24 (TI SCPS201 table 4-1): 1 INT, 2 A1, 3 A2, 4-11 P00-P07, 12 GND, 13-20 P10-P17, 21 A0,
    #     22 SCL, 23 SDA, 24 VCC.
    a0, a1 = ("3V3" if m & 1 else "GND"), ("3V3" if m & 2 else "GND")
    part(f"U{b+1}", TSSOP24, "TCA9535PWR", "C130204",
         {"1": "EXP_INT", "2": a1, "3": "GND", "21": a0, "22": "LSCL", "23": "LSDA", "24": "3V3", "12": "GND",
          "4": M("PWRON_REQ"),      # P00 out: request MODULE_POWER_ON (gated in hardware by VDDIN_PWR_BAD_N)
          "5": M("PWRBAD_REL"),     # P01 out: high = stop holding VDDIN_PWR_BAD_N low (HV_PG and MV_PG must agree)
          "6": M("RST_REQ_N"),      # P02 out: low = pull SYS_RESET_N low
          "7": M("RCM_REQ_N"),      # P03 out: low = pull FORCE_RECOVERY_N low
          "8": M("I2C_EN"),         # P04 out: high = connect the module's I2C3 to the XSCL/XSDA bus
          "9": M("HV_EN"), "10": M("MV_EN"), "11": M("SV_EN"),          # P05-P07 out: eFuse / load switch enables
          "13": M("CARRIER_POWER_ON"),  # P10 in (3.3 V open drain from the module, read directly)
          "14": M("RST_N_B"), "15": M("MPG_B"), "16": M("PWRBAD_N_B"), "17": M("SHDN_N_B"),   # P11-P14 in (buffered)
          "18": M("THERM_N_B"), "19": M("PRSNT1"), "20": M("TSREQ_N_B")},                     # P15-P17 in
         note=f"I2C address 0x{0x20+m:02X} on the local bus", group=g)
    cap(f"C{b+1}", "100nF", "3V3", group=g, near=f"U{b+1}")
    res(f"R{b+1}", "100k", M("PWRON_REQ"), "GND", g, f"U{b+1}")     # default: power-on not requested
    res(f"R{b+2}", "100k", M("PWRBAD_REL"), "GND", g, f"U{b+1}")    # default: VDDIN_PWR_BAD_N held low
    res(f"R{b+3}", "100k", "3V3", M("RST_REQ_N"), g, f"U{b+1}")     # default: reset not forced
    res(f"R{b+4}", "100k", "3V3", M("RCM_REQ_N"), g, f"U{b+1}")     # default: normal boot
    res(f"R{b+5}", "100k", M("I2C_EN"), "GND", g, f"U{b+1}")        # default: module I2C disconnected
    res(f"R{b+15}", "10k", "3V3", M("PRSNT1"), g, f"U{b+1}")       # PRSNT0 is GND here; module ties PRSNT0-PRSNT1
    res(f"R{b+8}", "100k", M("CARRIER_POWER_ON"), "GND", g, f"U{b+1}")  # reads low with no module fitted

    # --- readers: SN74LV4T125PWR (TI SCLS749 pin table: 1 1OE#, 2 1A, 3 1Y, 4 2OE#, 5 2A, 6 2Y, 7 GND, 8 3Y, 9 3A,
    #     10 3OE#, 11 4Y, 12 4A, 13 4OE#, 14 VCC). Powered from 3V3: VIH 1.35 V (reads 1.8 V outputs), inputs 5.5 V
    #     tolerant (reads the 5 V VDDIN_PWR_BAD_N), Ioff, input only, so no current flows into a powered-down module.
    part(f"U{b+2}", TSSOP14, "SN74LV4T125PWR", "C90755",
         {"1": "GND", "2": M("SYS_RESET_N"), "3": M("RST_N_B"), "4": "GND", "5": M("MODULE_POWER_GOOD"), "6": M("MPG_B"),
          "7": "GND", "8": M("PWRBAD_N_B"), "9": M("VDDIN_PWR_BAD_N"), "10": "GND", "11": M("SHDN_N_B"),
          "12": M("MODULE_SHDN_N"), "13": "GND", "14": "3V3"}, group=g)
    cap(f"C{b+2}", "100nF", "3V3", group=g, near=f"U{b+2}")
    part(f"U{b+3}", TSSOP14, "SN74LV4T125PWR", "C90755",
         {"1": "GND", "2": M("THERM_ALERT_N"), "3": M("THERM_N_B"), "4": "GND", "5": M("THERM_SHDN_REQ_N"),
          "6": M("TSREQ_N_B"), "7": "GND", "8": M("UTX_B"), "9": M("UART3_TX_DEBUG"), "10": "GND",
          "12": "GND", "13": "GND", "14": "3V3"}, ["11"], group=g)
    cap(f"C{b+3}", "100nF", "3V3", group=g, near=f"U{b+3}")
    res(f"R{b+9}", "470k", M("SYS_RESET_N"), "GND", g, f"U{b+2}")       # defined low with no module; 1.76 V with one
    res(f"R{b+10}", "100k", M("MODULE_POWER_GOOD"), "GND", g, f"U{b+2}")  # pin not described by NVIDIA: read only
    res(f"R{b+11}", "470k", M("VDDIN_PWR_BAD_N"), "GND", g, f"U{b+2}")
    res(f"R{b+12}", "470k", M("MODULE_SHDN_N"), "GND", g, f"U{b+2}")
    res(f"R{b+13}", "100k", M("VIO"), M("THERM_ALERT_N"), g, f"U{b+3}")     # pull-ups only on the gated rail
    res(f"R{b+14}", "100k", M("VIO"), M("THERM_SHDN_REQ_N"), g, f"U{b+3}")
    res(f"R{b+16}", "100k", M("VIO"), M("UART3_TX_DEBUG"), g, f"U{b+3}")

    # --- open-drain pull-downs: SN74LVC07APWR (TI SCAS595 pin table: 1 1A, 2 1Y, 3 2A, 4 2Y, 5 3A, 6 3Y, 7 GND, 8 4Y,
    #     9 4A, 10 5Y, 11 5A, 12 6Y, 13 6A, 14 VCC). Outputs open drain, 5.5 V tolerant, Ioff: they can only pull low.
    #     Channels 1-3 are a wired-AND on VDDIN_PWR_BAD_N: it is released only when HV_PG AND MV_PG AND firmware agree,
    #     so a failing eFuse flags power-bad to the module within ~10 ns, with no firmware in the loop (DG 5.1.4).
    part(f"U{b+4}", TSSOP14, "SN74LVC07APWR", "C7809",
         {"1": M("HV_PG"), "2": M("VDDIN_PWR_BAD_N"), "3": M("MV_PG"), "4": M("VDDIN_PWR_BAD_N"),
          "5": M("PWRBAD_REL"), "6": M("VDDIN_PWR_BAD_N"), "7": "GND", "8": M("SYS_RESET_N"), "9": M("RST_REQ_N"),
          "10": M("FORCE_RECOVERY_N"), "11": M("RCM_REQ_N"), "12": M("THERM_SHDN_REQ_N"), "13": M("TSREQ_REQ_N"),
          "14": "3V3"}, group=g)
    cap(f"C{b+4}", "100nF", "3V3", group=g, near=f"U{b+4}")
    res(f"R{b+20}", "100k", "3V3", M("TSREQ_REQ_N"), g, f"U{b+4}")   # default: thermal shutdown not requested
    # SN74LVC1G07DBVR (TI SCES296: 1 NC, 2 A, 3 GND, 4 Y, 5 VCC): disables the module's PCA9306 by pulling its EN low
    part(f"U{b+5}", SOT235, "SN74LVC1G07DBVR", "C7829",
         {"2": M("I2C_EN"), "3": "GND", "4": M("I2C_REF"), "5": "3V3"}, ["1"], group=g)
    cap(f"C{b+5}", "100nF", "3V3", group=g, near=f"U{b+5}")

    # --- MODULE_POWER_ON: CMOS 5.0 V input (DG-12084 table 5-1). NVIDIA's reference drives it from a 5V_AO gate with a
    #     100k pull-down (DG fig 5-7). SN74AHCT1G08DBVR (TI SCLS315: 1 A, 2 B, 3 GND, 4 Y, 5 VCC) at 5 V: TTL inputs
    #     (VIH 2.0 V) take the 3.3 V request; input B is VDDIN_PWR_BAD_N itself, so MODULE_POWER_ON can only be high
    #     while power-bad is released (DG 5.1.1 and the 5.3.1 note), and drops the moment it is asserted.
    part(f"U{b+6}", SOT235, "SN74AHCT1G08DBVR", "C113521",
         {"1": M("PWRON_REQ"), "2": M("VDDIN_PWR_BAD_N"), "3": "GND", "4": M("PWRON_5V"), "5": "5V_AO"}, group=g)
    cap(f"C{b+6}", "100nF", "5V_AO", group=g, near=f"U{b+6}")
    res(f"R{b+6}", "100", M("PWRON_5V"), M("MODULE_POWER_ON"), g, f"U{b+6}")   # damps the ribbon line
    res(f"R{b+7}", "100k", M("MODULE_POWER_ON"), "GND", g, f"U{b+6}")          # as in DG fig 5-7

    # --- gated 1.8 V I/O rail: TPS22918DBVR (TI SLVSDH4: 1 VIN, 2 GND, 3 ON, 4 CT, 5 QOD, 6 VOUT). ON = the module's
    #     own SYS_RESET_N (VIH 1.0 V), QOD tied to VOUT: when SYS_RESET_N falls the rail turns off in ~2 us and the
    #     internal 45-60 ohm pull-down empties 200 nF in ~12 us. CT open = fastest turn-on.
    part(f"U{b+8}", SOT236, "TPS22918DBVR", "C131941",
         {"1": "1V8", "2": "GND", "3": M("SYS_RESET_N"), "5": M("VIO"), "6": M("VIO")}, ["4"], group=g)
    cap(f"C{b+8}", "1uF", "1V8", group=g, near=f"U{b+8}")
    cap(f"C{b+9}", "100nF", M("VIO"), group=g, near=f"U{b+8}")
    # UART3_RX_DEBUG driver: SN74LV1T34DBVR (TI SCLS743: 1 NC, 2 A, 3 GND, 4 Y, 5 VCC) powered from M<m>_VIO: input
    # 5.5 V tolerant (takes the CH344Q's 3.3 V TXD), output 1.8 V, and Ioff when VIO is off, so the line is 0 V in reset.
    part(f"U{b+7}", SOT235, "SN74LV1T34DBVR", "C100024",
         {"2": M("URX_3V3"), "3": "GND", "4": M("URX_1V8"), "5": M("VIO")}, ["1"], group=g)
    cap(f"C{b+7}", "100nF", M("VIO"), group=g, near=f"U{b+7}")
    res(f"R{b+17}", "100k", "3V3", M("URX_3V3"), g, f"U{b+7}")         # DG table 17-3: 100k on the non-module side
    res(f"R{b+18}", "100", M("URX_1V8"), M("UART3_RX_DEBUG"), g, f"U{b+7}")
    # I2C3 (1.8 V, 1k pull-ups to 1.8 V on the module, DG table 12-2) <-> 3.3 V XSCL/XSDA: PCA9306DCUR (TI SCPS113
    # table 5-1: 1 GND, 2 VREF1, 3 SCL1, 4 SDA1, 5 SDA2, 6 SCL2, 7 VREF2, 8 EN). VREF1 = M<m>_VIO, so the module side
    # cannot rise while the module is in reset; EN/VREF2 through 200k to 3V3 (TI's circuit), pulled low by U<b+5> to
    # take this module off the shared bus.
    part(f"U{b+9}", "Package_SO:VSSOP-8_2.3x2mm_P0.5mm", "PCA9306DCUR", "C33196",
         {"1": "GND", "2": M("VIO"), "3": M("I2C3_CLK"), "4": M("I2C3_DAT"), "5": "XSDA", "6": "XSCL",
          "7": M("I2C_REF"), "8": M("I2C_REF")}, group=g)
    res(f"R{b+19}", "200k", "3V3", M("I2C_REF"), g, f"U{b+9}")
    cap(f"C{b+10}", "10uF", "3V3", group=g, near=f"U{b+1}")             # local bulk for the block

# ================================================================ brain: ESP32-S3-WROOM-1-N16R8
# Pin numbers = KiCad symbol RF_Module:ESP32-S3-WROOM-1 (= Espressif datasheet table). Left free on purpose: IO3/45/46
# (straps), IO35-37 (octal PSRAM on the R8 variant). Inputs only from the module side of the board: an ESP32 reset
# leaves every control output where the expanders hold it.
U1 = {"1": "GND", "40": "GND", "41": "GND", "2": "3V3", "3": "EN", "27": "IO0",
      "13": "USB1_DN", "14": "USB1_DP",
      "39": "IMON0_ADC", "38": "IMON1_ADC", "4": "IMON2_ADC", "5": "IMON3_ADC",     # IO1, IO2, IO4, IO5 = ADC1 ch 0, 1, 3, 4
      "12": "LSDA", "17": "LSCL",            # IO8 / IO9: local I2C (5 expanders, Qwiic)
      "18": "XSDA", "19": "XSCL",            # IO10 / IO11: PMBus + QSFP + module I2C3
      "20": "EXP_INT",                       # IO12: any expander input changed
      "21": "M0_HV_PG", "22": "M1_HV_PG", "23": "M2_HV_PG", "24": "M3_HV_PG",       # IO13, IO14, IO21, IO47
      "8": "M0_UTX_B", "9": "M1_UTX_B", "10": "M2_UTX_B", "11": "M3_UTX_B",         # IO15-18: listen-only console taps
      "25": "LED_HB",                        # IO48
      "36": "U0RX", "37": "U0TX"}
part("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8", "C2913202", U1,
     [str(n) for n in range(1, 42) if str(n) not in U1],
     "Espressif module, 16 MB flash + 8 MB PSRAM, extended. Antenna at the bottom board edge, keep-out from the footprint.")
res("R1", "10k", "3V3", "EN", near="U1"); cap("C1", "1uF", "EN", near="U1")       # Espressif EN RC
res("R2", "10k", "3V3", "IO0", near="U1")
cap("C2", "100nF", "3V3", near="U1"); cap("C3", "10uF", "3V3", near="U1")
SW = "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A"
part("SW1", SW, "RESET", "C318884", {"1": "EN", "2": "GND"})
part("SW2", SW, "BOOT", "C318884", {"1": "IO0", "2": "GND"})
res("R3", "1k", "LED_HB", "LED_A", near="D1")
part("D1", "LED_SMD:LED_0603_1608Metric", "KT-0603R", "C2286", {"1": "GND", "2": "LED_A"}, note="heartbeat LED, basic")
for i, (net, lab) in enumerate([("U0TX", "TX"), ("U0RX", "RX"), ("1V8", "1V8"), ("5V_AO", "5V")]):
    part(f"TP{i+1}", "TestPoint:TestPoint_Pad_D1.0mm", lab, "", {"1": net}, note="bare test pad, nothing to place")
# HV current monitors: TPS25982 IMON 246 uA/A into the console's 470 R = 1.16 V at 10 A, 1.55 V at the 13.4 A limit.
# ESP32-S3 ADC1 at 12 dB attenuation reads 0-3.1 V, so no divider. TI (TPS25982 7.3.5) recommends >= 10k in series with
# an RC filter; 10k also caps any injection into the ESP32 pin if IMON is ever pulled above 3.3 V.
for m in range(4):
    res(f"R{16+m}", "10k", f"M{m}_HV_IMON", f"IMON{m}_ADC", group="sys", near="U1")
    cap(f"C{22+m}", "100nF", f"IMON{m}_ADC", group="sys", near="U1")

# ================================================================ USB-C 1: ESP32 native USB (firmware, CDC console)
USBC = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
def usb_c(ref, n, cc_r, esd):
    part(ref, USBC, f"USB-C {'MCU' if n == 1 else 'CONSOLES'}", "C165948",
         {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "A4": f"VBUS{n}", "A9": f"VBUS{n}", "B4": f"VBUS{n}",
          "B9": f"VBUS{n}", "A5": f"CC1_{n}", "B5": f"CC2_{n}", "A6": f"USB{n}_DP", "B6": f"USB{n}_DP",
          "A7": f"USB{n}_DN", "B7": f"USB{n}_DN", "SH": "GND"}, ["A8", "B8"], group="usb")
    res(f"R{cc_r}", "5.1k", f"CC1_{n}", "GND", "usb", ref); res(f"R{cc_r+1}", "5.1k", f"CC2_{n}", "GND", "usb", ref)
    # USBLC6-2SC6 (ST: 1 I/O1, 2 GND, 3 I/O2, 4 I/O2, 5 VBUS, 6 I/O1). VBUS only feeds the clamp reference: the board
    # is powered from the console, never from USB (it would back-feed the console's 3V3 rail).
    part(esd, "Package_TO_SOT_SMD:SOT-23-6", "USBLC6-2SC6", "C7519",
         {"1": f"USB{n}_DP", "6": f"USB{n}_DP", "3": f"USB{n}_DN", "4": f"USB{n}_DN", "2": "GND", "5": f"VBUS{n}"},
         group="usb", near=ref)
usb_c("J1", 1, 4, "U3")

# ================================================================ USB-C 2: four module debug consoles (CH344Q)
# CH344Q LQFP-48 (WCH CH344DS1 v1.7 section 4): VCC 9/24/36/48, GND 8/20/23/35/47, 5 XI, 6 XO (8 MHz crystal, ~22 pF),
# 7 RESET# (internal pull-up), 42 UD-, 43 UD+ (no series resistors), 44 TEST (to GND), UART0 30 TXD / 31 RXD,
# UART1 12 / 13, UART2 21 / 22, UART3 37 / 38. Modem pins unused and left open (WCH: CTS/RTS/DTR have pull-ups or are
# outputs; RTS0 / DTRx must stay open or the strap options change). Single 3.3 V supply, 3.3 V UART levels.
usb_c("J2", 2, 6, "U4")
CH = {"9": "3V3", "24": "3V3", "36": "3V3", "48": "3V3", "8": "GND", "20": "GND", "23": "GND", "35": "GND", "47": "GND",
      "5": "XTAL_I", "6": "XTAL_O", "42": "USB2_DN", "43": "USB2_DP", "44": "GND",
      "30": "M0_URX_3V3", "31": "M0_UTX_B", "12": "M1_URX_3V3", "13": "M1_UTX_B",
      "21": "M2_URX_3V3", "22": "M2_UTX_B", "37": "M3_URX_3V3", "38": "M3_UTX_B"}
part("U2", "Package_QFP:LQFP-48_7x7mm_P0.5mm", "CH344Q", "C2988084", CH,
     [str(n) for n in range(1, 49) if str(n) not in CH], "USB 2.0 high-speed to 4 x UART, extended", group="usb")
for i in range(4): cap(f"C{10+i}", "100nF", "3V3", group="usb", near="U2")
cap("C14", "10uF", "3V3", group="usb", near="U2")
part("Y1", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "8MHz", "C5181477",
     {"1": "XTAL_I", "3": "XTAL_O", "2": "GND", "4": "GND"}, note="3225 8 MHz 20 pF 10 ppm, extended", group="usb", near="U2")
cap("C15", "22pF", "XTAL_I", group="usb", near="Y1"); cap("C16", "22pF", "XTAL_O", group="usb", near="Y1")

# ================================================================ power
# TLV75518PDBVR (TI SBVS320 table 4-1, DBV: 1 IN, 2 GND, 3 EN, 4 NC, 5 OUT), 500 mA, feeds the four VIO switches.
part("U5", SOT235, "TLV75518PDBVR", "C2877863", {"1": "3V3", "2": "GND", "3": "3V3", "5": "1V8"}, ["4"], group="power")
cap("C17", "1uF", "3V3", group="power", near="U5"); cap("C18", "1uF", "1V8", group="power", near="U5")
# 1V8 bleeder: an LDO cannot sink. A module that pulls THERM_ALERT_N / THERM_SHDN_REQ_N up to its own 3.3 V (as DG table
# 5-1 says) back-feeds a few uA into M<m>_VIO through the 100k pull-ups, and the PCA9306 reference adds ~5 uA each;
# 180 uA of load keeps the rail at 1.8 V regardless.
res("R20", "10k", "1V8", "GND", "power", "U5")
# TPS61222DCKR (TI SLVS776: 1 VIN, 2 FB, 3 GND, 4 VOUT, 5 L, 6 EN), fixed 5 V, 4.7 uH. Load: four AHCT gates and
# four 100k pull-downs, under 1 mA.
part("U6", "Package_TO_SOT_SMD:SOT-363_SC-70-6", "TPS61222DCKR", "C116461",
     {"1": "3V3", "2": "5V_AO", "3": "GND", "4": "5V_AO", "5": "BOOST_SW", "6": "3V3"}, group="power")
part("L1", "Inductor_SMD:L_1008_2520Metric", "4.7uH", "C66536", {"1": "3V3", "2": "BOOST_SW"},
     note="SWPA252010S4R7MT 4.7 uH 760 mA, extended", group="power", near="U6")
cap("C19", "10uF", "3V3", group="power", near="U6"); cap("C20", "10uF", "5V_AO", group="power", near="U6")
cap("C26", "22uF", "3V3", group="power"); cap("C27", "22uF", "3V3", group="power")

# ================================================================ system block: buck, QSFP sideband, thermal requests
# TCA9535 at 0x24 (A2 high). Holds BUCK5_EN and the QSFP outputs across ESP32 resets.
part("U7", TSSOP24, "TCA9535PWR", "C130204",
     {"1": "EXP_INT", "2": "GND", "3": "3V3", "21": "GND", "22": "LSCL", "23": "LSDA", "24": "3V3", "12": "GND",
      "4": "BUCK5_EN", "5": "BUCK5_PG", "6": "M0_MV_PG", "7": "M1_MV_PG", "8": "M2_MV_PG", "9": "M3_MV_PG",
      "10": "QSFP_MODSEL_N", "11": "QSFP_RESET_N", "13": "QSFP_LPMODE", "14": "QSFP_MODPRS_N", "15": "QSFP_INT_N",
      "16": "M0_TSREQ_REQ_N", "17": "M1_TSREQ_REQ_N", "18": "M2_TSREQ_REQ_N", "19": "M3_TSREQ_REQ_N", "20": "SYS_P17"},
     note="I2C address 0x24 on the local bus", group="sys")
cap("C21", "100nF", "3V3", group="sys", near="U7")
res("R13", "10k", "SYS_P17", "GND", "sys", "U7")                   # unused port: TI asks for ~10k to a rail
res("R14", "10k", "3V3", "QSFP_MODPRS_N", "sys", "U7")             # SFF-8679: host pull-ups on ModPrsL and IntL
res("R15", "10k", "3V3", "QSFP_INT_N", "sys", "U7")
res("R8", "4.7k", "3V3", "LSDA", "sys", "U7"); res("R9", "4.7k", "3V3", "LSCL", "sys", "U7")
res("R10", "10k", "3V3", "XSDA", "sys", "U1"); res("R11", "10k", "3V3", "XSCL", "sys", "U1")  # + 4.7k on the console
res("R12", "10k", "3V3", "EXP_INT", "sys", "U7")
# Qwiic / STEMMA QT (JST SH 4-pin: 1 GND, 2 3V3, 3 SDA, 4 SCL) on the local bus: inlet / exhaust temperature sensor.
part("J3", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", "QWIIC", "C160404",
     {"1": "GND", "2": "3V3", "3": "LSDA", "4": "LSCL", "MP": "GND"}, group="sys")
for i, ref in enumerate(("H1", "H2", "H3", "H4")):
    PARTS.append({"ref": ref, "fp": "MountingHole:MountingHole_3.2mm_M3", "value": "M3", "lcsc": "", "pins": {}, "nc": {},
                  "note": "mounting hole", "group": "mech", "side": "F", "board_only": True, "near": None})
