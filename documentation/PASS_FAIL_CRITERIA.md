# PASS / FAIL criteria - STM32N657 FC manufacturing test (firmware 0.2.1)

> Status of every criterion below: **NOT HARDWARE VERIFIED**. The expected values come from the
> device datasheets, the vendor drivers and the firmware sources. The decision logic was
> checked on the PC (host tests, `engineering/HOST_TEST_REPORT.txt`). No board has produced any
> of these results yet. Each PASS criterion below is written as the source code implements it
> (`03_MANUFACTURING_TEST/Tests/`).

## 1. Global rules

### 1.1 Three kinds of criteria

| Kind | What | Where |
|---|---|---|
| **Software-verifiable** | the report tail: RESULTS block (20 mandatory entries), `NOT-PASS MASK`, `FINAL RESULT`, and the `END OF REPORT` line with build id and CRC-32. The station tool decides from it | sections 1.3-1.5, 2 |
| **Informational** | `[INFO]` lines, `[SKIP]` lines, indented detail lines. **Never** a criterion | section 3 |
| **Bench** | input current, rails, `MOTOR_OE_N` / PA3, VERIFY exit code, LED, station setup. The firmware cannot see these | section 4 |

### 1.2 Report line types

| Line | Meaning |
|---|---|
| `[PASS] <label>` / `[FAIL] <label>` | verdict of one check. One mandatory entry can print several of these lines (MCU 3, PSRAM 4) |
| `  Reason: ...` | follows a `[FAIL]` line and says why, with the value actually read. Record it with the board |
| `[SKIP] <label>` | deliberately not tested at this station (needs external equipment). Never a PASS, never a criterion. Only the three texts of section 3.2 exist |
| `  [INFO] ...` | diagnostics only, never a verdict |
| indented plain line | detail of the line above (values read) |

The report prints more `[PASS]`/`[FAIL]` lines than there are mandatory entries. **Never count
them.** The verdict is the tail block.

### 1.3 Authoritative verdict (report tail)

```
========================================
RESULTS: 20 mandatory tests, run COMPLETE
 0 BOOT                           PASS        <t> ms
 ... one line per entry 0..19: index, fixed name, state, elapsed ms ...
19 MOTOR SAFETY (AFTER PHASE 2)   PASS        <t> ms
NOT-PASS MASK: 0x00000000
========================================
FINAL RESULT: PASS
========================================
END OF REPORT build=<build id> tests=20 crc32=0x<8 hex digits>
```

- An entry's state is `PASS`, `FAIL` or `SKIP`, taken from the test's return value. Any other
  return value counts as `FAIL`. `NOT_RUN`, `RUNNING` and `ABORTED` appear only in the SWD log of
  a run that did not finish or was aborted. Bit *i* of `NOT-PASS MASK` is set when entry *i* is
  not `PASS`.
- `FINAL RESULT: PASS` requires a completed run in which **all 20** mandatory entries are
  `PASS`. A mandatory entry in state `SKIP` is **not** a PASS, so the result is `FAIL`. The
  runner table has a fixed size of 20, set at compile time, so a mandatory test cannot drop out.
  Aggregation happens only after the last test.
- The CRC-32 (zlib/IEEE) covers every report character (LF line ends, CR removed) from the
  first character of the banner through the newline before `END OF REPORT`.
- Fatal fault (NMI, HardFault, MemManage, BusFault, UsageFault, SecureFault, Error_Handler): the
  firmware prints `FATAL FAULT: <name> test=0x... PC=0x... CFSR=0x... HFSR=0x...` and
  `FINAL RESULT: ABORTED` between rule lines. **No END line follows.** A fault after a completed
  PASS run (idle loop) withdraws that verdict in the same way.

### 1.4 Machine rule (station tool)

A board passes the software criteria only if `diagnostics\CHECK_UART_LOG.bat <capture>` prints
**`STATION VERDICT: PASS` and exits 0**. The script runs `parse_station_log.py` with
`--expect-build-id` set to `EXPECTED_BUILD_ID.txt`. The SWD fallback
`diagnostics\READ_DIAG_LOG.bat read` uses the same verdicts and exit codes.

| Exit | Verdict | Condition (UART capture) |
|---|---|---|
| 0 | PASS | exactly one report banner; no `FINAL RESULT: ABORTED`; well-formed END line; CRC-32 matches; banner build id = END build id = expected build id; `tests=20`; `RESULTS: 20 mandatory tests, run COMPLETE` with 20 lines in the fixed index/name order; mask consistent with the 20 states; exactly one `FINAL RESULT` line, and it reads `PASS` with mask 0 |
| 1 | FAIL | the same consistency checks pass, but `FINAL RESULT: FAIL` with at least one entry not PASS |
| 2 | INCOMPLETE | no banner, or no `FINAL RESULT` / END line (boot failure, hang, timeout, power loss, capture stopped). SWD: invalid log magic, or run state not COMPLETE |
| 3 | ABORTED | `FINAL RESULT: ABORTED` (fatal fault) |
| 4 | INVALID | CRC mismatch, wrong build id, more than one banner (board reset during the test), malformed or inconsistent RESULTS block |
| 10 | (script) | station problem (Python / CubeProgrammer missing, SWD read failed): not a board verdict |

**Only exit 0 accepts a board.** A log that decodes without error is not a PASS.

### 1.5 Manual rule (station PC without Python)

The capture must contain:
- exactly one banner;
- a RESULTS block with 20 lines, all `PASS`;
- `NOT-PASS MASK: 0x00000000`;
- `FINAL RESULT: PASS`;
- an `END OF REPORT build=<expected id> tests=20` line, where the expected id is the content of
  `diagnostics/EXPECTED_BUILD_ID.txt`;
- **no** `FINAL RESULT: ABORTED` line.

A person cannot check the CRC by eye. Record the result as **"manual, CRC not checked"**. The SWD
path always needs Python.

### 1.6 Station timeout and retest

- Allow **60 s** from power-on (or reset) to the END line. A run without an END line is
  INCOMPLETE. A normal run is estimated at 5-10 s, and the worst case at <= 30 s. Both are
  estimates, not measurements.
- **FAIL is final.** Retest only if engineering authorises a documented retest.
- **INCOMPLETE, ABORTED or INVALID:** take an SWD log dump, power-cycle the board, and run once
  more. If the second run is anything other than PASS, reject the board and keep both captures
  and the dump.

### 1.7 Motor safety overrides everything

A `[FAIL]` in MOTOR SAFETY (entry 8 or 19), or a low `MOTOR_OE_N` reading (section 4), means the
board is **FAIL (safety)**, whatever the other results say.

## 2. The 20 mandatory entries

A mandatory entry is PASS only when **every** `[PASS]`/`[FAIL]` line it prints is `[PASS]`. The
same label is printed for PASS and FAIL unless the table shows two labels. Shared bus
preconditions: `fc_spi_bus_init_all()` covers HAL_SPI_Init and the RCC kernel-clock selection of
SPI1 and SPI2. If it fails, entries 3-6 fail. `fc_i2c_bus_init()` covers HAL_I2C_Init, the
filters and the I2C2 kernel clock. If it fails, entries 7 and 11 fail.

| # | RESULTS name | Section | Line(s) printed | PASS criterion (as coded) | Source of the expected value |
|---|---|---|---|---|---|
| 0 | `BOOT` | BOOT | `Application reached (running from SRAM 0x34000400)` | `SCB->VTOR == 0x34000400` **and** the header copied to 0x34000000 starts with the **bytes** `53 54 4D 32` ("STM2"; read as a little-endian word this is `0x324D5453`), has header version (offset 0x68) `0x00020300`, and has an entry point (offset 0x70) equal to the running image's reset vector (word at 0x34000404) | STM32 Signing Tool v2.22 header v2.3 layout (`04_DRIVERS/board/fc_image_header.h`, host-tested against the real signed images); FSBL LRUN layout |
| 1 | `MCU` | MCU | `Device identification`; `Clock configuration`; `Console UART (USART1, J4 TELEM1)` | all three PASS. Identification: DEVID != 0x000 and != 0xFFF (REVID/UID printed only). Clocks, exact and computed by the HAL from the RCC registers: SystemCoreClock == 600000000 **and** HCLK == PCLK1 == PCLK2 == PCLK4 == PCLK5 == 200000000 **and** the USART1 kernel-clock selection in HAL_UART_MspInit did not fail. Console: USART1 HAL_UART_Init and FIFO configuration succeeded, and no transmit has timed out | FSBL `SystemClock_Config` (HSI 64 MHz -> PLL1 1200 MHz; CPU = IC1 = /2; IC2 = /3 = 400 MHz; AHB /2; APB /1), `fc_clock_check.h` |
| 2 | `NOR` | NOR | `External NOR initialization` | the FSBL's XSPI2 mapping is quiesced (final CR.EN = 0 and SR.BUSY = 0; BUSY on entry is normal and only `[INFO]`); HAL_XSPI_Init, HAL_XSPIM_Config, `EXTMEM_Init(EXTMEMORY_1) == EXTMEM_OK` and EXTMEM_GetInfo succeed; the RCC XSPI2 kernel-clock selection did not fail; ManufacturerID == 0xC2 and FlashSize == 2^25; `EXTMEM_Read(0x00100000, 128 B)` returns header bytes `53 54 4D 32`, version `0x00020300` and entry == running reset vector, and the 128 bytes equal the FSBL copy at 0x34000000; memory-mapped base == 0x70000000; the 4096 bytes at 0x70100400 (D-cache invalidated) equal the running image at 0x34000400 | MX25UM25645G datasheet (Macronix ID 0xC2, 256 Mbit = 2^25 bytes); header v2.3 as entry 0 |
| 3 | `IMU1 ICM-45686` | IMU1 | `ICM-45686 identification` | SPI bus init OK; WHO_AM_I (reg 0x72) == 0xE9 over SPI1, CS PB10 | TDK driver `inv_imu.h` (INV_IMU_WHOAMI 0xE9), `inv_imu_regmap_le.h` (WHO_AM_I 0x72) |
| 4 | `IMU2 BMI088 ACC` | IMU2 | `BMI088 accelerometer identification` | SPI bus init OK; ACC_CHIP_ID (0x00) == 0x1E over SPI2, CS PD10 (a dummy read first switches the accelerometer to SPI; one dummy byte per read) | BMI088 datasheet, register map (ACC_CHIP_ID 0x1E) |
| 5 | `IMU2 BMI088 GYR` | IMU2 | `BMI088 gyroscope identification` | SPI bus init OK; GYRO_CHIP_ID (0x00) == 0x0F over SPI2, CS PB12 | BMI088 datasheet, register map (GYRO_CHIP_ID 0x0F) |
| 6 | `BARO BMP581` | BAROMETER | `BMP581 identification` | SPI bus init OK; CHIP_ID (0x01) == 0x50 over SPI2, CS PG13 (after the dummy read) | BMP581 datasheet, register map (CHIP_ID reset 0x50) |
| 7 | `MAG BMM350` | MAGNETOMETER | `BMM350 identification` | I2C2 bus init OK; address 0x14 acknowledges; CHIP_ID (0x00) == 0x33 (2 dummy bytes discarded) | BMM350 datasheet 5.10.1, Table 10 (address 0x14) |
| 8 | `MOTOR SAFETY` | MOTOR SAFETY | `MOTOR_ENABLE inactive` | PA3: MODER = output, ODR = 0, IDR = 0; TIM1 and TIM2 RCC clock-enable bits clear; none of PB2, PA9, PE13, PA11 (TIM1) or PA0, PA1, PA2, PB11 (TIM2) in output or alternate-function mode (input or analog = non-driving) | netlist motor chain U15/Q2/R52, `fc_board_pins.h` |
| 9 | `OSC HSE` | OSCILLATORS | PASS: `HSE 48 MHz crystal (Y1) ready in <n> ms`; FAIL: `HSE 48 MHz crystal (Y1) start-up` | `HAL_RCC_OscConfig(HSE ON, PLL1-4 unchanged) == HAL_OK` and RCC SR.HSERDY = 1 (wait bounded by HSE_STARTUP_TIMEOUT); system clock unchanged; HSE stays on for the USB test | ST HAL RCC; Y1 48 MHz crystal on PH0/PH1 (netlist) |
| 10 | `OSC LSE` | OSCILLATORS | PASS: `LSE 32.768 kHz crystal (Y2) ready in <n> ms`; FAIL: `LSE 32.768 kHz crystal (Y2) start-up` | HAL_PWR_EnableBkUpAccess, then `HAL_RCC_OscConfig(LSE ON) == HAL_OK` and SR.LSERDY = 1 (wait bounded by RCC_LSE_TIMEOUT_VALUE) | ST HAL RCC; Y2 32.768 kHz crystal on PC14/PC15 (netlist) |
| 11 | `I2C MUX TCA9548A` | I2C MUX | `TCA9548A I2C mux control register (0x70)` | I2C2 bus init OK; address 0x70 acknowledges; control-register write 0x00 OK; read-back OK and == 0x00 (all channels off) | TCA9548A datasheet (A0/A1/A2 = GND -> 0x70) |
| 12 | `ADC VREFINT` | ADC / POWER | `ADC1 internal reference (VREFINT)` | ADC init OK (RCC ADC kernel-clock selection TIMG/6 in HAL_ADC_MspInit, HAL_ADC_Init, calibration); VREFINT conversion OK; raw != 0 and VREFINT_CAL != 0; VDDA = 1800 mV x VREFINT_CAL / raw (8-sample average) within **1620..1980 mV** | `stm32n6xx_ll_adc.h` (VREFINT_CAL_ADDR 0x460091B8 = BSEC fuse 110, VREFINT_CAL_VREF 1800 mV); limits from `PHASE2_IMPLEMENTATION_SPEC.md` (1.8 V +/- 10 %) |
| 13 | `SD POWER` | SD POWER | `SD power switch (TPS22917 U14) + card-detect pull-up` | SD_CARD_DET (PD2) = 0 with SD_PWR_EN (PC13) = 0; = 1 20 ms after PC13 = 1; = 0 20 ms after PC13 = 0. Precondition: **no card** in J14. SD power left off | netlist U14 / R39 (10k to switched SD_3V3) / U17 / J14 |
| 14 | `CAN1` | CAN1 | `CAN1 TCAN332G U24 TX->bus->RX echo (FDCAN1 PD1/PH9, 50 kbit/s)` | the RCC FDCAN kernel-clock selection did not fail **and** the FDCAN kernel clock is exactly 200000000 Hz (otherwise no frame is sent: FAIL); HAL init/filter/start/TX OK; one frame (ID 0x123, DLC 8) in **normal mode** at 50 kbit/s (prescaler 200, 1+15+4 tq, no automatic retransmission) ends with LEC = ACK error (no other node, every bit up to the ACK slot echoed through TXD -> transceiver -> CANH/CANL -> RXD) **or** is acknowledged by another node (LEC none, TXBTO). A frame still pending (bus never idle) or any other LEC (bit0, bit1, stuff, form ...) = FAIL | M_CAN protocol: bit monitoring, LEC in PSR, TXBTO (`04_DRIVERS/fdcan/fc_fdcan_test.c`); TCAN332G datasheet; netlist U24; the bit timing assumes the 200 MHz PCLK1 kernel clock |
| 15 | `CAN2` | CAN2 | `CAN2 TCAN332G U25 TX->bus->RX echo (FDCAN3 PE11/PE12, 50 kbit/s)` | same as entry 14, through FDCAN3 and U25 | same, netlist U25 |
| 16 | `USB` | USB | `USB1 OTG HS controller + PHY init` | HSE ready (RCC HSERDY); OTG/PHY kernel-clock selection (`HAL_RCCEx_PeriphCLKConfig` in HAL_PCD_MspInit) == HAL_OK; `HAL_PCD_Init == HAL_OK`; GSNPSID != 0x00000000 and != 0xFFFFFFFF | ST CubeN6 example `Ux_Device_HID` (usb_otg.c) init sequence; CMSIS `USB_OTG_GlobalTypeDef.GSNPSID` |
| 17 | `ESP32-C5 SYNC` | ESP32 | `ESP32-C5 ROM bootloader SYNC` | USART6 init OK (kernel clock, HAL_UART_Init, FIFO). After a reset into download mode (PG2 reset, PF10 strap low), up to 5 SYNC requests with 100 ms windows must give **at least one VALID_OK response**: exactly 12 decoded bytes `01 08 04 00 v0 v1 v2 v3 00 00 r0 r1` (direction 0x01, command 0x08, declared size 4 == bytes present, status 0, error 0). There must also be **no VALID_ERROR_STATUS response** (status != 0 or error != 0) in any window. Our own request echoed back (direction 0x00) can never PASS | Espressif esptool serial-protocol document (ROM SYNC response = 4 status bytes); `04_DRIVERS/esp32c5/esp32c5_proto.h` |
| 18 | `PSRAM` | PSRAM | `APS51208N identification`; `PSRAM walking-bit (sampled: 8 addresses x 32 bits)`; `PSRAM address pattern (sampled: 16384 words, 4 KiB stride over 64 MiB)`; `PSRAM block pattern (3 x 1 MiB blocks)` | all four PASS. **Identification:** NOR mapping quiesced (final EN = 0, BUSY = 0); XSPI2/XSPIM init and `EXTMEM_Init(EXTMEMORY_2)` OK; Global Reset (FFh) HAL_OK, then >= 1 ms wait; MR0/1/2/3/4/8 read OK; RCC XSPI2 kernel-clock selection OK; and MR1[4:0] = 0b01101 (vendor APM), MR2[2:0] = 0b110 (512 Mb), MR2[7:5] = 0b110 (known-good die), MR0[5:2] = 0b0010 (variable latency, LC 5), MR0[1:0] = 0b00 (reset-default drive), MR4[7:5] = 0b010 (WLC 5), MR4[2:0] = 0b000 (PASR full array). MR3/MR8 are reported only. If identification fails, no memory-mapped access takes place. **Memory tests** run only after mapping at base 0x70000000, and only if XSPI2 is not BUSY after mapping and the CE#-low protection read back from the registers passes: CR.TCEN = 1; 0 < LPTR < REFRESH; DCR3.CSBOUND in 1..11; DCR4.REFRESH != 0; memory clock = kernel / (PRESCALER + 1) in (0, 133 MHz]; worst-case CE# low (REFRESH + 4 + 4 + LPTR) cycles <= 3500 ns. The configuration is REFRESH 120, LPTR 32, CSBOUND 256 B, which gives 160 cycles = 3.20 us at 50 MHz. Otherwise each memory line prints `[FAIL]` with `Reason: not executed (...)`. Each memory test must show no mismatch within the shared 5000 ms budget. Coverage is **sampled** (section 5) | APS51208N datasheet Rev 1.2 Tables 3-17 (mode registers), Table 28 (tCEM 4 us, standard temperature); RM0486 (XSPI REFRESH/LPTR/CSBOUND); `04_DRIVERS/psram/fc_psram_check.h` |
| 19 | `MOTOR SAFETY (AFTER PHASE 2)` | MOTOR SAFETY (AFTER PHASE 2) | `MOTOR_ENABLE inactive` | same as entry 8, repeated after all Phase-2 drivers ran | netlist motor chain |

## 3. Informational lines (never a criterion)

### 3.1 `[INFO]` and detail lines

| Section | Content |
|---|---|
| MCU | VDDIO3_HSLV fuse bit (expected 0 = not programmed; never programmed by this firmware) |
| NOR | FSBL hand-over state: CR.EN, BUSY on entry (normal), ABORT issued, quiesce time |
| IMU1 | PWR_MGMT0, INT1_STATUS0 |
| BAROMETER | REV_ID / STATUS bits; one forced measurement (temperature, pressure): not judged |
| MAGNETOMETER | ERR_REG, PMU_CMD_STATUS_0; probe of I2C 0x30 (MMC5603, named in the original task statement, not on the BOM: `NACK` expected) |
| MOTOR SAFETY | detail line with SAFETY_SWITCH (PD6) level |
| ADC / POWER | VREFINT_CAL source (fuse 110 reload) and ADC kernel clock; VIN and VBAT from the dividers; PGOOD (BQ24075). VIN and VBAT are **not** rail criteria |
| SD POWER | SD power left off |
| CAN1 / CAN2 | internal loopback result (1 Mbit/s, controller only), kernel clock, bit timing, RX pin level. After an echo failure an `[INFO]` suggests fitting J15/J16. That hint is for engineering during first-board qualification only: operators never change the termination jumpers (`JLCPCB_TEST_PROCEDURE.md` section 3) |
| USB | kernel clocks, USBPHYC_CR, HAL_PCD_Init time, HAL_PCD_DeInit status; VBUS present (from PGOOD; no cable at the station); HSE switched off |
| ESP32 | first valid response, including the value field (information only); frame class counts; first non-valid frame; SLIP statistics; attempts, bytes and RX overruns; normal-boot console capture (byte count, first 96 printable characters, whether `ESP-ROM` was seen); module held in reset afterwards |
| PSRAM | Global Reset; decoded MR0/MR1/MR2/MR3/MR4/MR8; NOR release; XSPI2 kernel clock; CE# protection registers read back and the computed CE# bound (arithmetic, not a measurement); release state |

### 3.2 `[SKIP]` lines

Firmware 0.2.1 prints exactly these `[SKIP]` texts, and nothing else prints `[SKIP]`:

| Section | Line |
|---|---|
| SD POWER | `[SKIP] SD card read/write (removable card, external)` |
| CAN1 and CAN2 (once each) | `[SKIP] CAN communication with external nodes (requires CAN node / fixture)` |
| USB | `[SKIP] USB enumeration (requires USB host)` |

Each `[SKIP]` line is printed in addition to the entry's own `[PASS]`/`[FAIL]` line and does not
change it. A mandatory entry whose RESULTS state is `SKIP` is not PASS.

## 4. Bench criteria (station operator; not visible to the firmware)

| Observation | Criterion | Status |
|---|---|---|
| Input current at power-up (5.00 V on J18, limit 0.5 A) | no current-limit trip; value recorded | window TBD - first-board qualification |
| Input current after the END line (idle loop) | value recorded | window TBD - established on reference boards |
| Rails VDD3V3, VDDIO, VDD1V8, VDDA1V8_AON, VDDA1V8, VIN, VIN_PERIPH | present; values recorded (nominal values: `JLCPCB_TEST_PROCEDURE.md` section 4) | windows TBD - first-board qualification |
| `MOTOR_OE_N` (R52 pull-up; /OE pins 14/15 of U16 and U18) | high (VDD3V3 level) during programming, the test run and idle. Any low reading is **FAIL (safety)** | measurement recommended |
| `MOTOR_ENABLE` PA3 (R50, or U15 pin 1) | low at all times | optional |
| `VERIFY_JLCPCB.bat` | exit code 0 (NOR content = shipped files) | required |
| Heartbeat LED, J7 pin 7 (visible only with the external safety-switch module or a probe) | 500 ms toggle after `FINAL RESULT: PASS`; 100 ms after FAIL; steady after ABORTED | secondary indication only; never overrides the report |
| Station setup (`JLCPCB_TEST_PROCEDURE.md` section 3) | met and recorded: no J1 battery, no J2 cable, no SD card, J15/J16 not fitted, J28 open | required |
| CE# (PN12) low time during the PSRAM test | **not a station criterion.** First-board qualification with a scope: the firmware computes a bound of 3.20 us against tCEM 4 us. Several shorter stalls inside one CE# period are not bounded by any documentation | engineering |
| External loader | **not a station criterion.** Qualification: `programming/EXTERNAL_LOADER_STATUS.md` section 6 | engineering, before production |

## 5. Coverage limits: what a PASS does not prove

- **PSRAM:** the memory tests are **sampled**, not every byte. They cover walking 1/0 at 8
  addresses, an address pattern on 16384 words (one per 4 KiB) across 64 MiB, and three 1 MiB
  blocks (pattern and inverse). The CE# timing is a computed bound; the scope measurement is
  still open.
- **I2C mux:** a write/read of 0x00 in the control register only (all channels stay off). The
  channel paths are not tested.
- **CAN:** a local transceiver echo only. No external node, no connector continuity, no check of
  termination quality or of the bit rate of a real network.
- **USB:** controller and PHY initialisation plus the core ID only. No device stack and no
  enumeration (`[SKIP]`). D+/D- continuity and protection are not tested.
- **SD:** the power switch and the card-detect pull-up only. No card access (`[SKIP]`).
- **ESP32-C5:** the ROM bootloader SYNC only. Nothing is flashed, and there is no Wi-Fi, BLE or
  application test.
- **Sensors:** identification registers only, plus one BMP581 measurement as `[INFO]`. No
  accuracy, calibration, interrupt or streaming test.
- **MCU clocks:** CPU 600 MHz and HCLK/PCLK1/2/4/5 200 MHz as the HAL computes them from the RCC
  registers. Nothing is measured with an instrument. DEVID is only checked to be valid, not
  matched to an expected value.
- **Crystals:** start-up and ready flag only, not frequency accuracy.
- **Power:** the firmware sees VDDA only (through VREFINT). The rails and currents are bench
  measurements (section 4).
- **Motor safety:** the MCU-side state only. The `MOTOR_OE_N` chain (U15/Q2/U16/U18) is a bench
  measurement.
- **NOR:** identification, the application header and a 4 KiB mapped compare.
  `VERIFY_JLCPCB.bat` checks the full programmed ranges.
- **External interfaces are NOT tested** and do not appear as results: GPS, cameras,
  telemetry/RC, external compass, motor/ESC outputs.
- **Not caught by the firmware itself:** a bus access that never completes, a lock-up, a power
  loss, a boot failure before the application. The station timeout (section 1.6) catches them.
