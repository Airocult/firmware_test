# Diagnostic retrieval - STM32N657 FC manufacturing test (firmware 0.2.1)

> **NOT HARDWARE VERIFIED.** The tools below were validated on the PC against output of the real
> firmware runner/report code (host tests, `engineering/HOST_TEST_REPORT.txt`), not on a board.
> The SWD hot-plug read and SWD access while a test is stalled must be confirmed on the first
> boards.

The board publishes its result in two places at the same time:

| Path | What | When to use | Tool (folder `diagnostics/`) |
|---|---|---|---|
| **UART (primary)** | report text on J4 TELEM1, 115200 8N1 | every board | `CHECK_UART_LOG.bat <capture file>` |
| SWD (fallback) | the same report + a machine-readable header in RAM (`fc_diag_log`, 16512 bytes) | UART adapter missing/suspect, or to diagnose an INCOMPLETE/ABORTED run | `READ_DIAG_LOG.bat start` / `READ_DIAG_LOG.bat read` |

Both tools print `STATION VERDICT: <X>` and return an exit code:

| Exit | Verdict | Meaning | Station action |
|---|---|---|---|
| 0 | PASS | complete run, 20/20 mandatory tests PASS, consistent, intact (CRC), expected build | accept |
| 1 | FAIL | complete run, at least one mandatory test not PASS | reject; keep the capture |
| 2 | INCOMPLETE | no report, no FINAL RESULT/END line, run still in progress, log never written | power-cycle and run once more; second time -> reject |
| 3 | ABORTED | the firmware reported a fatal fault (`FINAL RESULT: ABORTED`) | power-cycle and run once more; second time -> reject |
| 4 | INVALID | corrupted or inconsistent evidence: CRC mismatch, wrong firmware build, two reports in one capture (board reset during the test), malformed result block | check the capture setup, power-cycle, run once more; second time -> reject |
| 10 | (script) | tool problem: Python/CubeProgrammer missing, SWD connection or read failed | fix the station, repeat |

**Only exit code 0 / `STATION VERDICT: PASS` accepts a board.** A log that decodes without error
is not a PASS - the verdict is decided from the result block, not from the fact that decoding
worked.

## 1. UART capture (primary)

1. Connect the 3.3 V USB-UART adapter to J4 (pin 2 = TX out of the MCU -> adapter RX, pin 3 = RX
   into the MCU -> adapter TX, pins 6-8 = GND). 115200 8N1, no flow control.
2. Start logging to a file in the terminal program (raw text; CRLF or LF are both fine) BEFORE
   the board is powered or reset. The FSBL prints a few lines before the report; they are ignored.
3. Power the board (or reset it). Wait until the line `END OF REPORT ...` appears or the station
   timeout (60 s from power-on) expires, whichever comes first. Stop logging.
4. Run `diagnostics\CHECK_UART_LOG.bat <file>` and record the verdict line and exit code.

The capture must contain the report exactly once. If the board resets during the test the capture
contains two banners and is rejected as INVALID - never cut a capture by hand.

## 2. SWD read (fallback)

The log lives in SRAM that the firmware maps non-cacheable, so a debugger always reads current
data (no cache flush needed). SRAM keeps its content over a reset without power loss, so the old
result of a previous run could still be there - the `start` step removes that risk:

1. `diagnostics\READ_DIAG_LOG.bat start` - connects over SWD, writes 0 to the log's magic word
   (invalidates any old log) and resets the board: the test starts.
2. Wait for the station timeout (60 s) or the LED heartbeat.
3. `diagnostics\READ_DIAG_LOG.bat read` - hot-plug connect (`mode=HOTPLUG`: no reset, no halt),
   reads 16512 bytes at the address in `App_diag_addr.txt` into `diagnostics\diag_log.bin`, decodes
   it and prints the verdict. `EXPECTED_BUILD_ID.txt` makes a board running a different firmware
   fail as INVALID.

If a run was powered off in between, the SRAM content is lost: the decoder reports INCOMPLETE
(invalid magic), never a stale PASS.

The decoded output lists every mandatory test with its state (NOT_RUN / RUNNING / PASS / FAIL /
SKIP / ABORTED), the test that was running when the board stopped (`current`), the fault details
(fault type, PC, CFSR, HFSR, fault address) after an ABORTED run, and the full report text.

Environment variables: `FC_CUBEPROG_CLI` (path of `STM32_Programmer_CLI.exe`), `FC_CONNECT_OPTS`
(replaces the default `mode=HOTPLUG` of the read step; also added to the start step).

## 3. Without Python on the station PC

Apply the manual rule of `PASS_FAIL_CRITERIA.md` section 1.5 to the UART capture and record the
result as "manual, CRC not checked". The SWD path requires Python.

## 4. What to keep for each board

- The raw UART capture file (and `diag_log.bin` if the SWD path was used).
- The verdict line and exit code of the tool.
- For INCOMPLETE/ABORTED/INVALID: both runs' captures and an SWD log dump (`READ_DIAG_LOG.bat read`
  taken without power-cycling first) - the `current` test and the fault fields tell engineering
  where the board stopped.
