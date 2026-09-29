#!/usr/bin/env python3
"""
fc_station_common.py - shared definitions of the station tools
(parse_station_log.py = UART capture, decode_diag_log.py = SWD dump).

Standard library only.  Must stay identical to the firmware:
  runner order / names  03_MANUFACTURING_TEST/Tests/test_runner.c (s_tests[].name)
  states / encodings    03_MANUFACTURING_TEST/Tests/fc_result.h
  log layout v2         04_DRIVERS/console/fc_console.h
  report format         03_MANUFACTURING_TEST/Tests/test_report.c
(host test 05_TOOLS/host_tests/station_tools checks both tools against output
of the real runner/report code.)

STATION VERDICT and exit code (identical for both tools):
  0 PASS        complete run, all 20 mandatory tests PASS, consistent, intact
  1 FAIL        complete run with at least one mandatory test not PASS
  2 INCOMPLETE  no report / no final verdict / truncated (timeout, hang, power loss)
  3 ABORTED     the firmware published a fatal fault (FINAL RESULT: ABORTED)
  4 INVALID     corrupt or inconsistent evidence: CRC mismatch, wrong build,
                more than one report (unexpected reset), malformed RESULTS block
Only 0 means the board passed.  Successfully decoding a log is NOT a PASS.
"""
import zlib

MANDATORY_TESTS = [
    "BOOT", "MCU", "NOR", "IMU1 ICM-45686", "IMU2 BMI088 ACC", "IMU2 BMI088 GYR",
    "BARO BMP581", "MAG BMM350", "MOTOR SAFETY",
    # Phase 2, bits 9-19
    "OSC HSE", "OSC LSE", "I2C MUX TCA9548A", "ADC VREFINT", "SD POWER",
    "CAN1", "CAN2", "USB", "ESP32-C5 SYNC", "PSRAM", "MOTOR SAFETY (AFTER PHASE 2)",
]
N_MANDATORY = len(MANDATORY_TESTS)          # 20

TEST_STATES = {0: "NOT_RUN", 1: "RUNNING", 2: "PASS", 3: "FAIL", 4: "SKIP", 5: "ABORTED"}
RUN_STATES = {0: "NOT_STARTED", 1: "IN_PROGRESS", 2: "COMPLETE", 3: "ABORTED"}
FINAL_RESULTS = {0: "NONE", 1: "PASS", 2: "FAIL", 3: "ABORTED"}
FAULT_CODES = {0: "none", 1: "NMI", 2: "HardFault", 3: "MemManage", 4: "BusFault",
               5: "UsageFault", 6: "SecureFault", 7: "Error_Handler"}

VERDICT_EXIT = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2, "ABORTED": 3, "INVALID": 4}

BANNER_RULE = "=" * 40
BANNER_TITLE = "STM32N657 FC MANUFACTURING TEST"


def crc32(data: bytes) -> int:
    """CRC-32 as in fc_result_crc32_update (zlib, IEEE 802.3)."""
    return zlib.crc32(data) & 0xFFFFFFFF


def finish(verdict, reasons, out=print):
    """Print the verdict block and return the exit code."""
    out("-" * 78)
    for r in reasons:
        out("  - " + r)
    out("STATION VERDICT: %s" % verdict)
    if verdict != "PASS":
        out("  (only STATION VERDICT: PASS / exit code 0 accepts the board)")
    return VERDICT_EXIT[verdict]
