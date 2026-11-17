# Management board: power sequencing the firmware must run

This is the contract between the management board hardware and its firmware. The firmware is not written yet. Every step names the document and section it comes from.

**Sources:**
- **DG** = NVIDIA Jetson Thor Series Modules Design Guide, DG-12084-001 v1.2, chapter 5 (and 12, 17, 18 where named)
- **DS** = NVIDIA Jetson Thor Series Modules Data Sheet, DS-11945-001 v1.4
- **TPS25982** = TI eFuse data sheet (SLVSEI3D), used on the console for HV and MV
- **TPS546B24A** = TI PMBus buck data sheet, used on the console for 5 V (0x10) and 3.3 V (0x11)
- **TCA9535** = TI I/O expander data sheet (SCPS201F)

Times marked "NVIDIA" are hard requirements. Times marked "ours" are firmware choices with margin; change them only with a reason.

## 1. What the hardware already does on its own

The firmware sits on top of a few things that work with no firmware at all:

| Hardware | Effect | Why |
|---|---|---|
| U<m>04 channels 1-3, wired-AND on `VDDIN_PWR_BAD_N` | Power-bad is held low unless `HV_PG` **and** `MV_PG` **and** `PWRBAD_REL` are all high | DG 5.1.1 (power-bad until HV and MV are valid), DG 5.1.4 (power-bad on a supply droop) |
| U<m>06, 5 V AND gate on `MODULE_POWER_ON` | `MODULE_POWER_ON` is high only while `PWRON_REQ` is high **and** `VDDIN_PWR_BAD_N` is high | DG 5.3.1 note, DG fig 5-7 (NVIDIA's own gate from 5V_AO) |
| U<m>08, load switch on `SYS_RESET_N` | `M<m>_VIO` (all 1.8 V pull-ups, the UART RX driver, the I2C translator reference) is on only while that module's `SYS_RESET_N` is high | DS table 6-2, VM_PIN: no I/O pin above 0.5 V while SYS_RESET* is low |
| TCA9535 expanders on the always-on 3V3 | Outputs keep their state through an ESP32 reset, crash or firmware update | TCA9535 6.4.1: registers reset only on a power cycle |
| Pull resistors on every expander output | Before firmware writes anything, every module is off and safe (table below) | |

**Safe state** (after a cold power-up of the console's 3V3 standby rail, before any firmware write):

| Signal | State | Set by |
|---|---|---|
| `SV_EN`, `MV_EN`, `HV_EN`, `BUCK5_EN` | low (off) | 100k pull-downs on the console |
| `PWRON_REQ` -> `MODULE_POWER_ON` | low | R<m>01 / R<m>07 (100k) |
| `PWRBAD_REL` -> `VDDIN_PWR_BAD_N` | held low | R<m>02 |
| `RST_REQ_N`, `RCM_REQ_N`, `TSREQ_REQ_N` | not asserted | R<m>03 / R<m>04 / R<m>20 |
| `I2C_EN` | module I2C off the shared bus | R<m>05 |
| QSFP `MODSEL_N`, `RESET_N`, `LPMODE` | not driven (module pull-ups) | SFF-8679 |

## 2. Start-up of the firmware itself

1. **Do not assume a cold start.** After an ESP32 reset the expanders still hold the last outputs and modules may be running. For each TCA9535 (0x20-0x24), read the Output (02h/03h) and Configuration (06h/07h) registers first, and adopt that state.
2. **Write Output registers before Configuration registers.** The TCA9535 Output register resets to `1` on every pin (TCA9535 table 6-5). If a pin is switched to output first, it drives **high** for a moment, and `HV_EN`, `MV_EN` or `SV_EN` high powers a module. Order: write the wanted output values, then clear the configuration bits.
3. Outputs per module expander (address 0x20 + m): P00 `PWRON_REQ`, P01 `PWRBAD_REL`, P02 `RST_REQ_N`, P03 `RCM_REQ_N`, P04 `I2C_EN`, P05 `HV_EN`, P06 `MV_EN`, P07 `SV_EN`. Inputs: P10 `CARRIER_POWER_ON`, P11 `SYS_RESET_N`, P12 `MODULE_POWER_GOOD`, P13 `VDDIN_PWR_BAD_N`, P14 `MODULE_SHDN_N`, P15 `THERM_ALERT_N`, P16 `PRSNT1` (low = module present), P17 `THERM_SHDN_REQ_N`.
4. System expander (0x24): P00 `BUCK5_EN` (out), P01 `BUCK5_PG`, P02-P05 `M0..M3_MV_PG`, P06 `QSFP_MODSEL_N` (out), P07 `QSFP_RESET_N` (out), P10 `QSFP_LPMODE` (out), P11 `QSFP_MODPRS_N`, P12 `QSFP_INT_N`, P13-P16 `M0..M3_TSREQ_REQ_N` (out), P17 unused.
5. ESP32 direct inputs: `M0..M3_HV_PG` (IO13, IO14, IO21, IO47), `EXP_INT` (IO12, any expander input changed: read the Input registers to clear it), HV current monitors on ADC1 (IO1, IO2, IO4, IO5).

## 3. System power: the 5 V buck

The console's 5 V buck (TPS546B24A, PMBus 0x10) feeds all four MV eFuses. The 3.3 V buck (0x11) is the standby rail that powers **this board and every module's SV rail**.

1. Turn the 5 V buck on before the first module's `MV_EN`: `BUCK5_EN` high, wait for `BUCK5_PG` high. The console straps a 3 ms soft start (console/make_console.py, MSEL2). Timeout (ours): 50 ms.
2. Check it over PMBus (address 0x10 on XSCL/XSDA): `STATUS_WORD` (79h) = 0, `READ_VOUT` (8Bh) within 4.75-5.25 V (DS table 6-1, SYS_VIN_MV).
3. Turn it off only after the last module's MV is off.
4. **Never** send `OPERATION` (01h) off or change `ON_OFF_CONFIG` (02h) on the 3.3 V buck at 0x11: it would switch off this board and every SV rail at once. Read-only use of 0x11 (`READ_VIN` 88h for the 12 V input, temperatures, status) is fine.

## 4. Module power-on

Per module m. DG 5.1.1 and fig 5-2 (power-on sequence), DG 5.3.1 (auto power-on).

| Step | Action | Wait / check | Source |
|---|---|---|---|
| 0 | Check `PRSNT1` low (module seated, both connector corners) | otherwise refuse | DG table 5-1 PRSNT0/1, DG 5.3.1 |
| 1 | 5 V buck on (section 3) | `BUCK5_PG` high | |
| 2 | `SV_EN` high (TPS22918 on the console, 3.3 V) | wait **at least 20 ms** (no PG on SV) | DG fig 5-2: SV stable 20 ms or more before MV/HV; DG 5.1.1 "SYS_VIN_SV must be powered up first" |
| 3 | `MV_EN` high, then `HV_EN` high (`PWRBAD_REL` still low) | `MV_PG` (0x24 P02+m) and `HV_PG` (ESP32 GPIO) high, timeout (ours) 100 ms | DG fig 5-2 (MV and HV come up together after SV) |
| 4 | Read the HV current monitor once (idle baseline) | | TPS25982 7.3.5 |
| 5 | `PWRBAD_REL` high: the hardware now releases `VDDIN_PWR_BAD_N` | `VDDIN_PWR_BAD_N` reads high (P13) within 5 ms (ours) | DG 5.1.1: power-bad active until SYS_VIN_HV is valid |
| 6 | Wait **at least 50 ms** | | DG fig 5-2: VDDIN_PWR_BAD_N high to MODULE_POWER_ON 50 ms or more |
| 7 | (Recovery boot only) `RCM_REQ_N` low now | | DG 17.1, DG 18 |
| 8 | `PWRON_REQ` high: `MODULE_POWER_ON` goes to 5 V | | DG 5.1.1, fig 5-2 note 2 (must have been low first) |
| 9 | Wait `CARRIER_POWER_ON` high (P10) | NVIDIA: within 13 ms of module power; timeout (ours) 200 ms | DG fig 5-2 |
| 10 | Wait `SYS_RESET_N` high (P11) | NVIDIA: 15-50 ms after CARRIER_POWER_ON; timeout (ours) 200 ms | DG fig 5-2 |
| 11 | `M<m>_VIO` comes up by itself (load switch on SYS_RESET_N) | nothing to do | DS table 6-2 |
| 12 | (Recovery boot only) keep `RCM_REQ_N` low for 100 ms (ours) after `SYS_RESET_N` rose, then high | NVIDIA: strap valid for 12.5 us or more after SYS_RESET_N rises | DG 18 (table 18-1 RCM0) |
| 13 | Optional: `I2C_EN` high to reach the module on XSCL/XSDA | one module at a time unless their I2C addresses differ | DG table 12-2 (I2C3 = SoC I2C12, 1k to 1.8 V on the module) |

Any timeout in steps 3-10: stop, log which step, and run the **forced power-off** (section 5.2). Do not retry more than once without a user command.

The carrier has no 1.8 V / 3.3 V I/O rails of its own that wait for `CARRIER_POWER_ON` (the console carrier's 3.3 V is always on), so `PERIPHERAL_RESET_N` (fig 5-2 note 1) is not needed and is not wired on the console.

## 5. Module power-off

### 5.1 Software shutdown (the OS powers off)
DG 5.1.3 and fig 5-4. The module drops `SYS_RESET_N` first, then `CARRIER_POWER_ON`.

1. On `CARRIER_POWER_ON` falling (expander interrupt): `PWRON_REQ` low. DG 5.1.3 item 3: MODULE_POWER_ON goes low **after** CARRIER_POWER_ON.
2. Then `PWRBAD_REL` low. DG fig 5-4: VDDIN_PWR_BAD_N must de-assert after CARRIER_POWER_ON goes low.
3. `HV_EN` low, then `MV_EN` low. DG fig 5-4: either order, NVIDIA recommends HV before MV.
4. Wait for `HV_PG` and `MV_PG` low, then **1 s** (ours) so SYS_VIN_MV is below 100 mV before any new power-on (DG fig 5-3/5-4 note 3). The board cannot measure MV directly; the time is a margin until the bench shows the real discharge time.
5. `SV_EN` low. DG fig 5-4: SV goes low after HV and MV.
6. If no other module needs MV: 5 V buck off (section 3).

### 5.2 Forced power-off (user command, timeout, fault)
DG 5.1.2 and fig 5-3 (the "power button" case; this board plays the button).

1. `PWRON_REQ` low. The module's sequencer starts the power-down at once: `SYS_RESET_N` low within 25 us, module rails down and `CARRIER_POWER_ON` low within 3 ms.
2. Wait for `CARRIER_POWER_ON` low, timeout (ours) 100 ms, then wait **at least 10 ms** more (fig 5-3: 10 ms or more before HV/MV go down).
3. Steps 2-6 of 5.1.
4. If `CARRIER_POWER_ON` never falls (hung sequencer): drop `HV_EN` and `MV_EN` anyway. `HV_PG` / `MV_PG` fall and the hardware asserts `VDDIN_PWR_BAD_N` with no firmware involved, then finish steps 4-6 of 5.1.

### 5.3 Shutdown by an event
DG 5.1.4, fig 5-5, and the DG 5.3.1 note. Triggers, any of:
- `MODULE_SHDN_N` low (on-module thermal, hardware or software shutdown, DS table 3-3 note),
- `VDDIN_PWR_BAD_N` low while running (an eFuse dropped PG, or the module itself pulled it, DS table 3-1 "can also be driven by module"),
- `CARRIER_POWER_ON` low while `PWRON_REQ` is still high.

Action:
1. `PWRON_REQ` low immediately. (If power-bad caused it, the AND gate has already pulled `MODULE_POWER_ON` low in hardware; fig 5-5: MODULE_POWER_ON must de-assert before CARRIER_POWER_ON goes low.)
2. **Latch the module off** in firmware: it stays off until a user command, even if the cause clears. DG fig 5-5 note 4: otherwise the system can power on again by itself.
3. Then 5.2 steps 2-4.

## 6. Faults

### 6.1 eFuse trip (HV or MV)
The console's TPS25982 eFuses tie RETRY_DLY to GND, so they **latch off** after a fault (TPS25982 table 7-3).
- **Symptom:** `HV_PG` or `MV_PG` low while its `_EN` is high.
- **Already done by hardware:** power-bad asserted, `MODULE_POWER_ON` dropped.
- **Firmware:** run 5.3. Store the last few seconds of the HV current monitor for the log.
- **Latch reset:** drive the `_EN` low (below VSD = 0.59 V, TPS25982 "fault latch can be externally reset", EN/UVLO driven low) for at least 10 ms (ours), and leave it low until the next power-on.
- **Retry:** at most once, after 5 s (ours). A second trip keeps the module off until a user command.

### 6.2 5 V buck fault
- **Symptom:** `BUCK5_PG` low while `BUCK5_EN` is high. Every module's `MV_PG` falls, and the hardware asserts power-bad on all of them.
- **Firmware:** run 5.3 on every running module, then read `STATUS_WORD` (79h) and the `STATUS_VOUT` / `STATUS_IOUT` / `STATUS_TEMPERATURE` bytes over PMBus, `CLEAR_FAULTS` (03h), `BUCK5_EN` low.
- **Retry:** at most once.

### 6.3 Over-current trend
- **What it is:** the HV current monitor is 1.16 V at 10 A, 1.55 V at the 13.4 A eFuse limit (console: 246 uA/A into 470 R).
- **Firmware:** warn above 11 A for 1 s (ours, about 130 W at 12 V).
- **The eFuse is the protection.** The firmware only reports.

### 6.4 Thermal
- **`THERM_ALERT_N` low:** the module is near thermal shutdown (DS table 3-1, THERMAL_ALERT_N). The module drives its own fan (`FAN_PWM` on the console). The firmware logs it, shows it on the status page and, if the inlet sensor on the Qwiic port reads high, can ask the OS to throttle over I2C.
- **`MODULE_SHDN_N` low:** handled as an event shutdown (5.3).
- **`THERM_SHDN_REQ_N`:** NVIDIA's spreadsheet lists this pin (G59) but no document describes it yet. The board can read it (P17) and pull it low (0x24 P13+m through an open-drain buffer). **Firmware must not pull it low** until NVIDIA documents its direction and meaning.
- **`MODULE_POWER_GOOD` (L59):** the same problem: it is in the pin list but not described. It is read only, and used only for logging.

## 7. Reset and recovery
- **Warm reset:** `RST_REQ_N` low for 100 ms (ours), then high. This resets the SoC and boot devices, not the module's power sequencer (DG table 5-1, SYS_RESET_N). `M<m>_VIO` drops and returns with it.
- **Recovery mode** (flashing over the module's USB0, the console's rear USB-C per module):
  1. `RCM_REQ_N` low.
  2. A warm reset, or a full power-on (section 4, step 7).
  3. Keep `RCM_REQ_N` low 100 ms after `SYS_RESET_N` rises, then release it.

  Sources: DG 17.1 and DG 18 (12.5 us minimum hold). The module has a 20k pull-up to 1.8 V on `FORCE_RECOVERY_N` (DG fig 18-1), so releasing it means normal boot.

## 8. Debug consoles and I2C
- **The four UART3 debug consoles** go to the CH344Q on the CONSOLES USB-C as four serial ports, with no firmware involved. The ESP32 also listens on all four (IO15-IO18) to keep a log, but never transmits.
- **Each module's I2C3** reaches the shared 3.3 V bus (XSCL/XSDA) through its own PCA9306. The bus also carries PMBus and the QSFP28 management interface.
  - Enable one module at a time unless the modules use different target addresses.
  - Talk to the QSFP (0x50/0x51) only while `QSFP_MODSEL_N` is low.
  - If a module holds SDA low, `I2C_EN` low takes it off the bus, and the 9-clock bus recovery handles the rest.

## 9. Timing summary

| From | To | Time | Kind |
|---|---|---|---|
| SV on | MV / HV on | 20 ms or more | NVIDIA (DG fig 5-2) |
| VDDIN_PWR_BAD_N high | MODULE_POWER_ON high | 50 ms or more | NVIDIA (DG fig 5-2) |
| module power up | CARRIER_POWER_ON high | 13 ms or less | NVIDIA (DG fig 5-2) |
| CARRIER_POWER_ON high | SYS_RESET_N high | 15-50 ms | NVIDIA (DG fig 5-2) |
| SYS_RESET_N high | FORCE_RECOVERY_N released | 12.5 us or more (we use 100 ms) | NVIDIA (DG 18) |
| MODULE_POWER_ON low | SYS_RESET_N low | 0-25 us | NVIDIA (DG fig 5-3) |
| module rails down | CARRIER_POWER_ON low | 3 ms or less | NVIDIA (DG fig 5-3) |
| CARRIER_POWER_ON low | HV / MV off | 10 ms or more | NVIDIA (DG fig 5-3, 5-5) |
| HV and MV off | SV off | after both | NVIDIA (DG fig 5-3 to 5-5) |
| MV off | next power-on | MV below 100 mV (we wait 1 s) | NVIDIA (DG fig 5-3 note 3) |
| SYS_RESET_N low | M<m>_VIO below 0.5 V | about 2 us + 12 us | this board (TPS22918 tOFF, 45-60 ohm QOD x 200 nF) |
| eFuse EN low (latch reset) | EN high | 10 ms (ours) | TPS25982 fault latch reset |
