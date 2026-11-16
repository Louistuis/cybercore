"""CyberCore status panel rev 1.0: the netlist (one dict per part). make_panel.py places these, gen_sch.py draws the
schematic from them, jlc_files.py writes the BOM. Every LCSC number was looked up in the JLC parts API on 2026-11-16
(stock that day in brackets); pin tables come from the KiCad symbol / footprint and the datasheets named per part.

What the board does: an ESP32-S3 module shows CyberCore's live numbers (tok/s, power, temperatures) on a plug-in SPI
display and on a 16-LED RGB bar along the bottom edge. Data arrives over USB from the server itself (a small agent in the
OS writes to the USB serial port) or over Wi-Fi from the server's BMC (Redfish). Power: 5 V from the same USB-C cable.

Power tree:  J1 USB-C VBUS -> F1 1.5 A PTC -> 5V -> U2 AMS1117-3.3 -> 3V3 (module, display, Qwiic)
                                              5V -> U4 74AHCT1G125 (3.3 V -> 5 V level shift) + LED bar D1-D16
LED current: up to 60 mA per LED at full white = ~1 A. Firmware caps the total at ~400 mA (USB 2.0 ports give 500 mA).
"""
C0402, C0603, C0805 = "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
CAP = {"100nF": ("C1525", C0402),   # CL05B104KO5NNNC 16 V X7R, basic (37.3M)
       "1uF": ("C52923", C0402),    # CL05A105KA5NQNC 25 V X5R, basic (9.6M)
       "10uF": ("C19702", C0603),   # CL10A106KP8NNNC 10 V X5R, basic (11.3M)
       "22uF": ("C45783", C0805)}   # CL21A226MAQNNNE 25 V X5R, basic (4.0M)
RES = {"10k": "C25744",             # 0402WGF1002TCE 1 %, basic (20.6M)
       "5.1k": "C25905",            # 0402WGF5101TCE 1 %, basic (3.8M)
       "330": "C25104"}             # 0402WGF3300TCE 1 %, basic (1.45M)

PARTS = []
def part(ref, fp, value, lcsc, pins, nc=(), note="", group="core"):
    PARTS.append({"ref": ref, "fp": fp, "value": value, "lcsc": lcsc, "pins": pins, "nc": {n: "nc" for n in nc},
                  "note": note, "group": group, "side": "F"})
def cap(ref, val, a, b="GND", group="power"):
    part(ref, CAP[val][1], val, CAP[val][0], {"1": a, "2": b}, group=group)
def res(ref, val, a, b, group="core"):
    part(ref, R0402, val, RES[val], {"1": a, "2": b}, group=group)

# ---------------------------------------------------------------- brain: ESP32-S3-WROOM-1-N16R8
# Pin numbers = KiCad symbol RF_Module:ESP32-S3-WROOM-1 (= Espressif datasheet table 2-1). Left free on purpose:
# IO3 / IO45 / IO46 (strapping pins), IO35-37 (wired to the octal PSRAM on the R8 variant).
U1 = {"1": "GND", "40": "GND", "41": "GND", "2": "3V3", "3": "EN",
      "4": "BTN_USER",      # IO4
      "13": "USB_DN", "14": "USB_DP",          # IO19 / IO20 native USB (flashing + serial data from the server)
      "17": "DISP_DC",      # IO9
      "18": "DISP_CS",      # IO10
      "19": "DISP_DIN",     # IO11 (SPI MOSI)
      "20": "DISP_CLK",     # IO12
      "12": "DISP_RST",     # IO8
      "11": "DISP_BUSY",    # IO18: e-paper BUSY in, or LCD backlight PWM out
      "27": "IO0",          # BOOT strap
      "31": "LED_DATA_3V3", # IO38
      "39": "I2C_SDA", "38": "I2C_SCL",        # IO1 / IO2 to the Qwiic port
      "37": "UART_TX", "36": "UART_RX"}
nc = [str(n) for n in range(1, 42) if str(n) not in U1]
part("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8", "C2913202", U1, nc,
     "Espressif module, 16 MB flash + 8 MB PSRAM, extended (15.0k). Antenna at the top board edge, keep-out from the footprint.")
res("R1", "10k", "3V3", "EN"); cap("C3", "1uF", "EN", group="core")      # EN delay RC (Espressif reference: 10k + 1uF)
res("R2", "10k", "3V3", "IO0")
res("R3", "10k", "3V3", "BTN_USER")
SW = "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A"   # XKB TS-1187A-B-A-B 5.1 x 5.1 mm, basic (841k)
part("SW1", SW, "RESET", "C318884", {"1": "EN", "2": "GND"})
part("SW2", SW, "BOOT", "C318884", {"1": "IO0", "2": "GND"})
part("SW3", SW, "PAGE", "C318884", {"1": "BTN_USER", "2": "GND"}, note="front button: next display page")
cap("C6", "100nF", "3V3", group="core"); cap("C7", "10uF", "3V3", group="core")   # at the module's 3V3 pin
for i, (net, lab) in enumerate([("UART_TX", "TX"), ("UART_RX", "RX"), ("GND", "GND"), ("3V3", "3V3")]):
    part(f"TP{i+1}", "TestPoint:TestPoint_Pad_D1.0mm", lab, "", {"1": net}, note="bare test pad, nothing to place")

# ---------------------------------------------------------------- USB-C power + data in
# HRO TYPE-C-31-M-12 (C165948, extended, 521k). 5.1k on each CC = "sink, give me 5 V". SBU not used.
part("J1", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB-C 5V + data", "C165948",
     {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
      "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN", "SH": "GND"},
     ["A8", "B8"], group="power")
res("R5", "5.1k", "CC1", "GND", group="power"); res("R6", "5.1k", "CC2", "GND", group="power")
# USBLC6-2SC6 (ST DS: 1 I/O1, 2 GND, 3 I/O2, 4 I/O2, 5 VBUS, 6 I/O1; pins 1+6 and 3+4 are the same line). C7519 extended (34.8k)
part("U3", "Package_TO_SOT_SMD:SOT-23-6", "USBLC6-2SC6", "C7519",
     {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "2": "GND", "5": "VBUS"}, group="power")
part("F1", "Fuse:Fuse_1206_3216Metric", "PTC 1.5A", "C20802", {"1": "VBUS", "2": "5V"},
     note="SMD1206P150TF 1.5 A hold / 3 A trip, 6 V, extended (11.3k)", group="power")

# ---------------------------------------------------------------- 3.3 V
# AMS1117-3.3 SOT-223: 1 GND, 2 VOUT (= tab), 3 VIN. C6186 basic (1.42M). ESP32-S3 peaks ~355 mA on Wi-Fi TX.
part("U2", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "AMS1117-3.3", "C6186", {"1": "GND", "2": "3V3", "3": "5V"}, group="power")
cap("C1", "10uF", "5V"); cap("C2", "22uF", "3V3")

# ---------------------------------------------------------------- LED bar
# SN74AHCT1G125 SOT-23-5 (TI: 1 OE#, 2 A, 3 GND, 4 Y, 5 VCC): AHCT input high = 2.0 V, so 3.3 V in -> clean 5 V data out.
part("U4", "Package_TO_SOT_SMD:SOT-23-5", "SN74AHCT1G125", "C7484",
     {"1": "GND", "2": "LED_DATA_3V3", "3": "GND", "4": "LED_DATA_5V", "5": "5V"}, group="leds")
cap("C8", "100nF", "5V", group="leds")
res("R4", "330", "LED_DATA_5V", "LED_DIN1", group="leds")
cap("C4", "22uF", "5V", group="leds"); cap("C5", "22uF", "5V", group="leds")
# XINGLIGHT XL-5050RGBC-2812B (WS2812B clone, 5050, 4 pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN). C2843785 extended (1.20M).
# Chain runs right to left: D1 (next to U4) -> D16.
for i in range(16):
    din = "LED_DIN1" if i == 0 else f"LED_D{i}_{i+1}"
    dout = f"LED_D{i+1}_{i+2}" if i < 15 else None
    part(f"D{i+1}", "LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm", "XL-5050RGBC-2812B", "C2843785",
         {"1": "5V", "3": "GND", "4": din, **({"2": dout} if dout else {})}, [] if dout else ["2"], group="leds")
    cap(f"C{10+i}", "100nF", "5V", group="leds")

# ---------------------------------------------------------------- display + expansion
# 8-pin 2.54 mm header in Waveshare's module order: VCC GND DIN CLK CS DC RST BUSY. The same order fits Waveshare's SPI
# e-Paper modules (pin 8 = BUSY) and their SPI LCD modules (pin 8 = BL backlight), using the PH2.0-to-jumper cable they ship.
part("J2", "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical", "DISPLAY", "C32713274",
     {"1": "3V3", "2": "GND", "3": "DISP_DIN", "4": "DISP_CLK", "5": "DISP_CS", "6": "DISP_DC", "7": "DISP_RST", "8": "DISP_BUSY"},
     note="HX PZ2.54-1x8P ZZ through-hole, extended (15.0k); JLC THT assembly or hand-solder", group="io")
# Qwiic / STEMMA QT (JST SH 4-pin: 1 GND, 2 3V3, 3 SDA, 4 SCL) for a temperature or air-flow sensor later.
part("J3", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", "QWIIC", "C160404",
     {"1": "GND", "2": "3V3", "3": "I2C_SDA", "4": "I2C_SCL", "MP": "GND"}, group="io")
res("R7", "10k", "3V3", "I2C_SDA", group="io"); res("R8", "10k", "3V3", "I2C_SCL", group="io")
for i, ref in enumerate(("H1", "H2", "H3", "H4")):
    PARTS.append({"ref": ref, "fp": "MountingHole:MountingHole_3.2mm_M3", "value": "M3", "lcsc": "", "pins": {}, "nc": {},
                  "note": "mounting hole", "group": "mech", "side": "F", "board_only": True})
