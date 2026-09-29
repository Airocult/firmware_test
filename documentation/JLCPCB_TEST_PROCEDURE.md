# STM32N657 Flight Controller - JLCPCB programming and test procedure (firmware 0.2.1)

> **This is the intended procedure. It is NOT evidence that JLCPCB, or anyone else, has run it.
> Nothing in this package is hardware verified. No assembled board has been programmed or booted
> with these images, and the external loader is NOT HARDWARE QUALIFIED. Before this procedure goes
> to a production line, the engineering team must do three things on the first boards: bring
> them up (`BRINGUP_CHECKLIST.md`, `PHASE2_BRINGUP_CHECKLIST.md` in the source bundle), qualify
> the loader (`programming/EXTERNAL_LOADER_STATUS.md` section 6), and replace every
> "TBD - first-board qualification" below with a measured value.**

Firmware: bring-up / manufacturing-test firmware 0.2.1 only. It is **not** flight-control
firmware. It runs 20 mandatory board-local checks: boot chain, MCU, NOR, sensor identification,
motor safe state, both crystals, I2C mux, ADC reference, SD power switch, both CAN transceivers,
USB controller, ESP32-C5 ROM bootloader, and PSRAM. It prints one report. Anything that needs
external equipment either prints `[SKIP]` (SD card, CAN nodes, USB host) or is not tested at all
(GPS, cameras, telemetry/RC, external compass, ESC outputs). `PASS_FAIL_CRITERIA.md` section 5
lists what a PASS does not prove.

## 1. Safety

- No ESC, motor or propeller may be connected, at any step.
- `MOTOR_OE_N` is pulled high by R52 (motor translators U16/U18 disabled) and `MOTOR_ENABLE`
  (PA3) is pulled low by R50. The FSBL, the test application and the external loader drive PA3
  low as their first peripheral action. The application never starts TIM1/TIM2, drives PA3 low
  again every 5 s, and drives it low again in every fault handler.
- Use the bench supply with its current limit set (section 4) for every board.
- J4 pin 1 is `VIN_PERIPH`, a ~5 V supply **output**. Never connect it to the UART adapter.
- Take ESD precautions for the exposed SWD and UART connectors.

## 2. Equipment

| Item | Notes |
|---|---|
| Station PC, Windows | runs the `.bat` files of this package |
| STM32CubeProgrammer >= 2.22.0 | `STM32_Programmer_CLI.exe`: default install path, or set `FC_CUBEPROG_CLI` to the executable |
| Python 3 (standard library only) | `python` or `py -3` on the PATH; used by `diagnostics\CHECK_UART_LOG.bat` and `READ_DIAG_LOG.bat`. Without Python, see `PASS_FAIL_CRITERIA.md` section 1.5 |
| ST-LINK V2 or V3 (SWD) | to J20, section 5 |
| USB-UART adapter, **3.3 V logic** | to J4 (TELEM1), 115200 8N1, no flow control. You also need a terminal program that can log raw received text to a file |
| Bench supply, **5.00 V**, adjustable current limit, current readout | to J18, section 4 |
| Multimeter | rails and `MOTOR_OE_N` (section 4, `PASS_FAIL_CRITERIA.md` section 4) |

## 3. Station setup (every board)

| Item | Required state | Reason |
|---|---|---|
| Power input | **J18** (S2P-VH): pin 1 = `UBEC_5V_INPUT` (+), pin 2 = GND | feeds power muxes U9/U30 and eFuse U27 (`VIN_PERIPH`) |
| J1 (battery) | **nothing connected** | the power muxes would share the load, so the current reading would not be comparable |
| J2 (USB-C) | **no cable** | same reason (VBUS feeds BQ24075). USB enumeration is not tested |
| J14 (microSD) | **no card** | the card-detect sequence 0 -> 1 -> 0 of entry 13 (SD POWER) needs an empty socket |
| J15 (CAN1 termination), J16 (CAN2 termination) | **not fitted**; record the state for every board | the CAN echo test is designed for an isolated, unterminated transceiver at 50 kbit/s. Operators never change these jumpers (see below) |
| J12, J13 (CAN) | no cable | no CAN node at the station |
| J28 (BOOT1 solder jumper) | **open** | BOOT1 = PA6, pulled low by R5; BOOT0 is pulled low by R2. Needed for the boot from external flash |
| ESP32-C5 module | any flash content | only its ROM bootloader is used |
| J20 | ST-LINK (section 5) | programming, optional SWD result read |
| J4 (TELEM1) | adapter RX to pin 2 (TX out of the MCU), adapter TX to pin 3 (RX into the MCU), GND to pins 6-8; **pin 1 not connected** | console, primary result path |
| ESC / motor / propeller | none | safety |

J15/J16: first-board qualification may show that the echo needs termination. In that case
engineering changes the production state to "both fitted" for every board. The two states are
never mixed.

## 4. Power-up and bench checks (current limited)

1. Set the supply to **5.00 V** and the current limit to **0.5 A** (a conservative start value
   for the first power-up of each board; production value TBD - first-board qualification),
   with the output off. Connect J18.
2. Switch the output on. Record the input current. If the supply reaches the current limit, the
   board is **FAIL (power)**. Switch off and do not program it.
3. Measure the rails and record the values. They are **bench** criteria: the firmware cannot
   see them (it checks VDDA only indirectly, through entry 12, ADC VREFINT). Nominal values come from the
   netlist feedback dividers, with V_FB = 0.8 V (TPS62130 datasheet p5). The measurement points
   are pads on the rail nets in the netlist.

| Rail | Source | Nominal | Where to measure | Acceptance window |
|---|---|---|---|---|
| VDD3V3 | U35 TPS62130, R93 316k / R94 100k | 0.8 x (1 + 316/100) = 3.33 V | J20 pin 1 or TP3 (GND: J20 pin 2 or TP1) | TBD - first-board qualification |
| VDDIO | U37 TPS62130, R99 316k / R98 100k | 3.33 V | R99 pin 2 | TBD - first-board qualification |
| VDD1V8 | U34 TPS62130, R13 124k / R15 100k | 0.8 x (1 + 124/100) = 1.79 V | R13 pin 2 | TBD - first-board qualification |
| VDDA1V8_AON | U36 TPS62130, R95 124k / R96 100k | 1.79 V | R95 pin 2 | TBD - first-board qualification |
| VDDA1V8 | U4 ETA5055V180 LDO (fixed) | 1.8 V | C10 pin 1 or R7 pin 2 | TBD - first-board qualification |
| VIN | U9 TPS2121 output (from `UBEC_5V_INPUT`) | ~5 V (mux drop TBD) | R11 pin 1 | TBD - first-board qualification |
| VIN_PERIPH | U27 TPS259535 eFuse output | ~5 V (TBD) | J4 pin 1 | TBD - first-board qualification |

Until engineering fills in the windows: record every value. A board with a missing rail or a
current-limit trip is **FAIL (power)** and is not programmed. The idle and run current windows
are TBD too: engineering sets them from reference boards, so record both values for every board
of the first lots (section 11).

## 5. SWD connection - J20

| J20 pin | Net | Function | MCU ball | ST-LINK signal |
|---|---|---|---|---|
| 1 | VDD3V3 | target voltage reference | - | T_VCC / VDD |
| 2 | GND | ground | - | GND |
| 3 | DEBUG_DAT | SWDIO (PA13) | P7 | SWDIO |
| 4 | DEBUG_CLK | SWCLK (PA14) | P6 | SWCLK |
| 5 | NC | not connected | - | - |
| 6 | NRST | reset | E4 | NRST |

Drawing: `SWD_CONNECTION_DIAGRAM.svg` in this folder (`.png` too, when it was generated).

## 6. Programming

| File | NOR address | Loaded to | Note |
|---|---|---|---|
| `firmware/FC_FSBL_LRUN_Trusted.bin` | `0x70000000` | SRAM 0x34180000 by the BootROM | STM32 header v2.3 at 0x70000000, code at 0x70000400 |
| `firmware/FC_Manufacturing_Test_Trusted.bin` | `0x70100000` | SRAM 0x34000000 by the FSBL (0x40000-byte copy) | vector table at 0x34000400 |

Each programmed range runs from its start address to start + file size - 1. For the exact ranges
and the loader limits, see `programming/EXTERNAL_LOADER_STATUS.md` section 4.

1. Run `programming\PROGRAM_JLCPCB.bat`. It connects, writes and verifies the FSBL, writes and
   verifies the application, then resets the board. It uses `programming\external_loader.stldr`.
   Exit codes:

   | Exit | Meaning | Action |
   |---|---|---|
   | 0 | programmed | step 2 |
   | 2 | CubeProgrammer, loader or image file missing | fix the station |
   | 10 | no SWD connection | see "If the SWD connection fails" below |
   | 11 / 12 | FSBL / application programming failed | **FAIL (programming)** |
   | 13 | images written, reset command failed | power-cycle the board, then step 2 |

2. Run `programming\VERIFY_JLCPCB.bat`. It reads both ranges back through the loader and
   compares them byte for byte with the shipped files. **Exit 0 is required.** Any other exit
   code is **FAIL (programming)**: 11/13 = no read-back file, 12/14 = the content differs,
   10 = no SWD connection, 2 = missing file. VERIFY proves only the NOR content, not the board.

Connect mode: both scripts connect **under reset** by default (`FC_CONNECT_OPTS=mode=UR`). Do not
change `FC_CONNECT_OPTS` at the station unless engineering specifies it after loader
qualification. `programming/EXTERNAL_LOADER_STATUS.md` section 5 explains why.

Loader status: the packaged loader (`MX25UM25645G_STM32N657_FC`) is built and structurally
verified, and **NOT HARDWARE QUALIFIED**. Until the qualification in
`programming/EXTERNAL_LOADER_STATUS.md` section 6 has passed on first boards, only engineering may
program boards, under its supervision. This package is not a production release.

**If the SWD connection fails (exit 10):**
1. Check the J20 wiring and orientation, VDD3V3 on J20 pin 1, and NRST.
2. Retry once.
3. Do not change J28/BOOT1 or the connect mode yourself. Engineering has not yet established
   (TBD - first-board qualification) whether a blank board connects with BOOT1 = 0 (J28 open)
   and `mode=UR`, or needs development boot (BOOT1 = 1). That result decides the station
   fixture.
4. If it still fails, record **FAIL (SWD)** and hand the board to engineering.

## 7. Test run and result capture

### 7.1 Cold start

After VERIFY, switch the supply off for **>= 5 s**. The loader leaves the NOR in octal mode, and
the loader qualification covers only a boot after a cold power cycle. Disconnect the ST-LINK
from J20 or switch it off, as in the loader qualification. Whether the probe may stay connected
during the run is TBD - first-board qualification.

### 7.2 UART capture (primary)

1. Connect the UART adapter as in section 3: 115200 8N1, no flow control. Start logging raw text
   to a new file **before** power-on.
2. Switch the supply on, with the current limit still set.
3. Wait until the line `END OF REPORT ...` appears, or until **60 s after power-on**, whichever
   comes first. Record the input current after the END line (window TBD, section 4). Stop
   logging.
4. Run `diagnostics\CHECK_UART_LOG.bat <capture file>`. Record the `STATION VERDICT:` line and
   the exit code (section 8).

Do not edit, cut or join capture files. A capture that contains two report banners (the board
reset during the test) is INVALID. The FSBL lines before the banner are expected and are
ignored.

### 7.3 SWD read (fallback)

Use it when no UART adapter is available, or to diagnose an INCOMPLETE/ABORTED run:
`diagnostics\READ_DIAG_LOG.bat start`, wait 60 s, then `diagnostics\READ_DIAG_LOG.bat read`.
It prints the same `STATION VERDICT:` and exit codes. `start` resets the board over SWD instead
of power-cycling it. The details are in `DIAGNOSTIC_RETRIEVAL.md`. The SWD path is NOT HARDWARE
VERIFIED: the hot-plug read must be confirmed on the first boards.

### 7.4 Heartbeat LED (secondary indication only)

`SAFETY_SWITCH_LED` is on J7 pin 7. The LED sits on the external safety-switch module, so you
see it only if that module or a probe is connected. It toggles every 500 ms after FINAL RESULT
PASS, every 100 ms after FAIL, and stays steady (not blinking) after a fatal fault (ABORTED). The
verdict always comes from the report, never from the LED.

## 8. Station verdicts, timeout and retest

| Exit | STATION VERDICT | Meaning | Action |
|---|---|---|---|
| 0 | PASS | complete report, 20/20 mandatory tests PASS, CRC intact, expected build | accept (together with the bench checks) |
| 1 | FAIL | complete report, at least one mandatory test not PASS | **reject**; copy the `Reason:` lines into the record |
| 2 | INCOMPLETE | no banner, or no FINAL RESULT / END line: boot failure, hang, timeout, power loss, capture stopped | retest rule below |
| 3 | ABORTED | the firmware reported a fatal fault (`FATAL FAULT: ...`, `FINAL RESULT: ABORTED`, no END line) | retest rule below |
| 4 | INVALID | corrupt or inconsistent capture: CRC mismatch, wrong build id (wrong firmware programmed), two banners in one capture, malformed RESULTS block | check the capture setup, then the retest rule below |
| 10 | (script) | station problem: Python or CubeProgrammer missing, SWD read failed | fix the station and repeat; this is not a board verdict |

**Only exit code 0 / `STATION VERDICT: PASS` accepts a board.** A log that decodes without error
is not a PASS.

**Station timeout: 60 s from power-on (or reset) to the `END OF REPORT` line.** A normal all-PASS
run is estimated at 5-10 s after reset. The worst case, with every bounded wait expiring, is
estimated at <= 30 s. Both figures are **estimates, not measurements**: record the per-test
milliseconds of the RESULTS block on the first boards (TBD - first-board qualification). The
firmware cannot end every failure itself. A stalled bus access, such as a memory-mapped PSRAM
read that never completes, raises no fault. A lock-up, a power loss, or a boot failure before the
application produces no END line either. The station timeout is what catches these runs.

Retest rule:
- **FAIL is final.** Retest only if engineering authorises a documented retest.
- **INCOMPLETE, ABORTED or INVALID:**
  1. Take an SWD log dump (`READ_DIAG_LOG.bat read`) **before** power-cycling.
  2. Power-cycle the board.
  3. Capture a new file and run once more.
  4. If the second run is anything other than PASS, **reject** the board. Keep both captures
     and the SWD dump for engineering.

## 9. Illustrative expected console output (all PASS)

This listing is **derived from the firmware source**: the report labels in
`03_MANUFACTURING_TEST/Tests/*.c` and the FSBL trace in `02_CUSTOM_FSBL`. It was **not captured
from a board**. Values in `<>` vary by board and build. `...` marks text shortened here. The
UART sends CRLF line endings. The station tool evaluates only the report from the banner to the
END line.

```
FSBL: reached, SystemCoreClock=600000000
FSBL: HSLV fuse(124.15)=0 XSPI2 clk=50000000 Hz
FSBL: NOR OK, loading app 0x70100000 -> 0x34000000 (0x40000 bytes)
========================================
STM32N657 FC MANUFACTURING TEST
========================================
Firmware version: 0.2.1
Build: <build id> <build date>
MCU: STM32N657 (target STM32N657I0H3Q)
Boot: FSBL_LRUN
Console: USART1 (J4 TELEM1) 115200 8N1

BOOT
[PASS] Application reached (running from SRAM 0x34000400)
  VTOR=0x34000400 header @0x34000000: magic bytes 53 54 4D 32, version 0x00020300, entry 0x<entry> = reset vector

MCU
[PASS] Device identification
  DEVID=0x<devid> REVID=0x<revid> UID=<uid0>-<uid1>-<uid2>
[PASS] Clock configuration
  SystemCoreClock=600000000 Hz HCLK=200000000 PCLK1=200000000 PCLK2=200000000 PCLK4=200000000 PCLK5=200000000
  expected CPU=600000000 Hz, HCLK/PCLK1/2/4/5=200000000 Hz; MSP kernel-clock error mask=0x00 (USART1 bit=0)
  [INFO] VDDIO3_HSLV fuse(124.15)=0 (not programmed, XSPI 50 MHz mode)
[PASS] Console UART (USART1, J4 TELEM1)

NOR
[PASS] External NOR initialization
  MX25UM25645G SFDP OK, ManufacturerID=0xC2, size=2^25 bytes, app header "STM2" v2.3 entry 0x<entry>, readback = FSBL copy
  XSPI2 kernel clock=<hz> Hz, memory-mapped compare 4096 B @0x70100400 OK, page size=<n>
  [INFO] FSBL hand-over: XSPI2 CR.EN was <0|1>, BUSY on entry <0|1>, ABORT issued <0|1>, quiesced in <n> ms

IMU1
[PASS] ICM-45686 identification
  Bus: SPI1 CS: PB10 WHO_AM_I(0x72)=0xE9
  [INFO] PWR_MGMT0(0x10)=0x<v> accel_mode=<n> gyro_mode=<n> (0=OFF)
  [INFO] INT1_STATUS0(0x19)=0x<v> reset_done=<0|1>

IMU2
[PASS] BMI088 accelerometer identification
  Bus: SPI2 CS: PD10 ACC_CHIP_ID(0x00)=0x1E
[PASS] BMI088 gyroscope identification
  Bus: SPI2 CS: PB12 GYRO_CHIP_ID(0x00)=0x0F

BAROMETER
[PASS] BMP581 identification
  Bus: SPI2 CS: PG13 CHIP_ID(0x01)=0x50 REV_ID=0x<v> STATUS=0x<v>
  [INFO] STATUS(0x28) core_rdy=<n> nvm_rdy=<n> nvm_err=<n>
  [INFO] forced measurement T=<n> mdegC P=<n> Pa INT_STATUS(0x27)=0x<v>

MAGNETOMETER
[PASS] BMM350 identification
  Bus: I2C2 Address: 0x14 CHIP_ID(0x00)=0x33
  [INFO] ERR_REG(0x02)=0x<v> pmu_cmd_error=<n> PMU_CMD_STATUS_0(0x07)=0x<v> pmu_cmd_busy=<n>
  [INFO] I2C 0x30 (MMC5603, not on BOM): NACK

MOTOR SAFETY
[PASS] MOTOR_ENABLE inactive
  PA3 mode=output ODR=0 IDR=0; SAFETY_SWITCH(PD6)=<0|1>; TIM1 clk=off TIM2 clk=off; PWM pins non-driving (input or analog mode)

OSCILLATORS
[PASS] HSE 48 MHz crystal (Y1) ready in <n> ms
  HAL_RCC_OscConfig HSE ON (PLL1-4 unchanged, system clock unchanged) HAL_OK, RCC SR.HSERDY=1, ...
[PASS] LSE 32.768 kHz crystal (Y2) ready in <n> ms
  HAL_PWR_EnableBkUpAccess + HAL_RCC_OscConfig LSE ON (PLL unchanged) HAL_OK, RCC SR.LSERDY=1, ...

I2C MUX
[PASS] TCA9548A I2C mux control register (0x70)
  write 0x00 read-back 0x00; all channels off

ADC / POWER
[PASS] ADC1 internal reference (VREFINT)
  VREFINT raw=<n> cal=<n> -> VDDA=<mV> mV (limits 1620..1980)
  [INFO] VREFINT_CAL: BSEC fuse 110 reload OK word=0x<v>; ...
  [INFO] VIN_SENSE raw=<n> -> VIN=<mV> mV (divider 100k/43k)
  [INFO] VBATSEN raw=<n> -> VBAT=<mV> mV (divider 100k/39k)
  [INFO] PGOOD (BQ24075)=<0|1> (PG14 open-drain: 0 = input power valid)

SD POWER
[PASS] SD power switch (TPS22917 U14) + card-detect pull-up
  SD_PWR_EN PC13=0: SD_CARD_DET PD2=0; PC13=1 (+20 ms): PD2=1; PC13=0 (+20 ms): PD2=0 (expected 0/1/0; ...)
  [INFO] SD power left OFF (PC13=0)
[SKIP] SD card read/write (removable card, external)

CAN1
[PASS] CAN1 TCAN332G U24 TX->bus->RX echo (FDCAN1 PD1/PH9, 50 kbit/s)
  frame ID=0x123 DLC=8 sent in normal mode, LEC=ack as expected (no other node; every bit up to the ACK slot echoed) after <n> ms, TEC=<n> REC=<n>
  [INFO] internal loopback ok (ID=0x<id> DLC=<n> data=AA 55 AA 55 F0 0F FF 00, <n> ms)
  [INFO] FDCAN kernel clock=200000000 Hz (PCLK1), echo prescaler 200, 20 tq/bit -> 50000 bit/s (target 50000), sample point 80 %; RX pin PH9 level after the echo=<0|1> (1 = recessive)
[SKIP] CAN communication with external nodes (requires CAN node / fixture)

CAN2
[PASS] CAN2 TCAN332G U25 TX->bus->RX echo (FDCAN3 PE11/PE12, 50 kbit/s)
  ... (same lines as CAN1; RX pin PE12)
[SKIP] CAN communication with external nodes (requires CAN node / fixture)

USB
[PASS] USB1 OTG HS controller + PHY init
  GSNPSID=0x<id> (Synopsys core ID register)
  [INFO] kernel clocks OTG=HSE direct, PHY=HSE/2 (Y1 48 MHz, clock cfg status=0); USBPHYC_CR=0x<v>; ...
  [INFO] VBUS present=<0|1> (BQ24075 PGOOD PG14=<0|1>, low = valid input)
  [INFO] HSE 48 MHz switched off after USB test (HAL_RCC_OscConfig HSE OFF status=<n>, HSERDY=<0|1>)
[SKIP] USB enumeration (requires USB host)

ESP32
[PASS] ESP32-C5 ROM bootloader SYNC
  Bus: USART6 (PC6/PC7) 115200; valid SYNC responses=<n> (12 bytes, status 0, error 0) after <n> attempt(s)
  [INFO] first valid SYNC response: len 12 size=4 status=0x00 error=0x00 value=0x<v> (value: information only, ROM non-zero / stub 0)
  [INFO] frames=<n>: VALID_OK=<n> VALID_ERROR_STATUS=0 ...
  [INFO] ... (SLIP statistics, SYNC attempts, boot console capture)
  [INFO] ESP32 held in reset (PG2=1) after test

PSRAM
[PASS] APS51208N identification
  Bus: XSPI2 NCS2 (PN12), after Global Reset: MR0=0x<v> MR1=0x<v> MR2=0x<v> MR3=0x<v> MR4=0x<v> MR8=0x<v>
  [INFO] Global Reset (FFh + 4 SDR address clocks = 5 CLK, >= 4 clocked CE# lows) sent, waited >= 1 ms before the MR reads (tRST >= 2 us)
  [INFO] MR0: ... (one decoded line each for MR0, MR1, MR2, MR3, MR4, MR8)
  [INFO] NOR memory-mapped mode released for the PSRAM test (...)
  [INFO] XSPI2 kernel clock=<hz> Hz (IC3, nominal 50 MHz; octal DDR on NCS2)
  [INFO] CE# protection read-back: CR=0x<v> (TCEN=1), LPTR=<n> cycles, DCR2=0x<v> (PRESCALER=<n>), DCR3=0x<v> (CSBOUND=<n> -> <n> bytes), DCR4 REFRESH=<n> cycles
  [INFO] memory clock <hz> Hz = kernel <hz> Hz / (PRESCALER + 1); worst-case CE# low (REFRESH + 4 + 4 + LPTR) = <n> cycles = <n> ns (budget 3500 ns, tCEM 4000 ns standard temp)
  [INFO] CE# bound computed from register values only; first-board CE# (PN12) scope measurement required
[PASS] PSRAM walking-bit (sampled: 8 addresses x 32 bits)
  8 addresses (offsets 0,0x1000,...,0x3FFFFFC) x 32 bits, walking 1 and walking 0, 32-bit accesses @0x70000000, <n> ms
[PASS] PSRAM address pattern (sampled: 16384 words, 4 KiB stride over 64 MiB)
  16384 words (one per 4 KiB), word = address ^ 0xA5A5A5A5, write all then read all, <n> ms
[PASS] PSRAM block pattern (3 x 1 MiB blocks)
  3 MiB of 64 MiB: blocks @0x70000000 0x72000000 0x73F00000, xorshift32 LFSR (seed = offset|1) then inverse, read back each, <n> ms

MOTOR SAFETY (AFTER PHASE 2)
[PASS] MOTOR_ENABLE inactive
  PA3 mode=output ODR=0 IDR=0; ...

========================================
RESULTS: 20 mandatory tests, run COMPLETE
 0 BOOT                           PASS        <t> ms
 1 MCU                            PASS        <t> ms
 2 NOR                            PASS        <t> ms
 3 IMU1 ICM-45686                 PASS        <t> ms
 4 IMU2 BMI088 ACC                PASS        <t> ms
 5 IMU2 BMI088 GYR                PASS        <t> ms
 6 BARO BMP581                    PASS        <t> ms
 7 MAG BMM350                     PASS        <t> ms
 8 MOTOR SAFETY                   PASS        <t> ms
 9 OSC HSE                        PASS        <t> ms
10 OSC LSE                        PASS        <t> ms
11 I2C MUX TCA9548A               PASS        <t> ms
12 ADC VREFINT                    PASS        <t> ms
13 SD POWER                       PASS        <t> ms
14 CAN1                           PASS        <t> ms
15 CAN2                           PASS        <t> ms
16 USB                            PASS        <t> ms
17 ESP32-C5 SYNC                  PASS        <t> ms
18 PSRAM                          PASS        <t> ms
19 MOTOR SAFETY (AFTER PHASE 2)   PASS        <t> ms
NOT-PASS MASK: 0x00000000
========================================
FINAL RESULT: PASS
========================================
END OF REPORT build=<build id> tests=20 crc32=0x<8 hex digits>
```

`<build id>` has the form `src-<12 hex digits of the source digest>` for this source tree, which
is not under git. It must equal `diagnostics/EXPECTED_BUILD_ID.txt` and the `build_id` in
`firmware/VERSION.txt`. When a check fails, its line reads `[FAIL] <label>`, followed by
`  Reason: ...`. That entry then shows `FAIL` in the RESULTS block, and the report ends with
`FINAL RESULT: FAIL`. A fatal fault prints the following instead of the tail, with no END line:

```
FATAL FAULT: <name> test=0x<index> PC=0x<pc> CFSR=0x<cfsr> HFSR=0x<hfsr>
========================================
FINAL RESULT: ABORTED
========================================
```

## 10. PASS / FAIL decision

A board passes only if **all** of the following hold:
- `PROGRAM_JLCPCB.bat` completed, and `VERIFY_JLCPCB.bat` exited 0.
- `CHECK_UART_LOG.bat` (or `READ_DIAG_LOG.bat read`) printed `STATION VERDICT: PASS` with exit
  code 0. Without Python, the manual rule of `PASS_FAIL_CRITERIA.md` section 1.5 applies,
  recorded as "manual, CRC not checked".
- Bench: no current-limit trip, all rails present and recorded, no low `MOTOR_OE_N` reading
  (measurement recommended; any low reading is FAIL (safety), `PASS_FAIL_CRITERIA.md` section 4).
  Engineering fills in the acceptance windows (TBD).
- The setup of section 3 is recorded as met.

Anything else is FAIL. Every criterion is detailed in `PASS_FAIL_CRITERIA.md`.

## 11. Records to keep for each board

- Board serial / lot, date, operator, station PC.
- Package identity: the build id from `diagnostics/EXPECTED_BUILD_ID.txt`, and the `MANIFEST.txt`
  of the package used.
- Setup record (section 3): J15/J16 state, J28 open, no SD card, no battery, no USB cable.
- Input current at power-up and after the END line, and every rail voltage (section 4).
- Exit codes and console output of `PROGRAM_JLCPCB.bat` and `VERIFY_JLCPCB.bat`.
- The raw UART capture file, and the `STATION VERDICT:` line with its exit code (or "manual, CRC
  not checked").
- A copy of `diagnostics\diag_log.bin` whenever the SWD path was used (each read overwrites it).
- The `MOTOR_OE_N` measurement, if it was taken.
- For INCOMPLETE/ABORTED/INVALID runs: both captures and the SWD log dump.
- First boards: the per-test milliseconds of the RESULTS block, which confirm or correct the
  timing estimate of section 8.
