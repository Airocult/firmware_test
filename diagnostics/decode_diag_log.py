#!/usr/bin/env python3
"""
decode_diag_log.py - decode the SWD-read RAM diagnostic log (fc_diag_log_t v2)
and give a STATION VERDICT.  SWD is the FALLBACK result path; the primary path
is the UART capture (parse_station_log.py).  Standard library only.

Layout v2 (04_DRIVERS/console/fc_console.h, little-endian, 128-byte header):
   0 magic 0x47444346 ("FCDG")   4 version (2)      8 length      12 capacity (16384)
  16 final_result (0 none, 1 PASS, 2 FAIL, 3 ABORTED)   20 not-pass mask (bit i)
  24 fw_version (maj<<16|min<<8|patch)   28 run_state (0 not started, 1 in progress,
  2 complete, 3 aborted)   32 test_count (20)   36 current_test (0xFFFFFFFF none)
  40 fault_code   44 fault_pc   48 fault_cfsr   52 fault_hfsr   56 fault_addr
  60 report_crc32   64 test_state[32] (0 NOT_RUN 1 RUNNING 2 PASS 3 FAIL 4 SKIP
  5 ABORTED)   96 build_id[32]   128 text[16384]          sizeof = 16512 bytes
The log is in MPU-non-cacheable SRAM (coherent SWD reads, no cache maintenance).

Usage: decode_diag_log.py DUMP.bin [--expect-build-id ID]
Verdict / exit code: 0 PASS | 1 FAIL | 2 INCOMPLETE | 3 ABORTED | 4 INVALID
(fc_station_common.py).  Exit 0 ONLY for a complete, consistent all-PASS run
of the expected build; a merely decodable log is not a PASS.
NOT HARDWARE VERIFIED: validated against logs produced by the real
runner/report code on the PC (05_TOOLS/host_tests/station_tools).
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fc_station_common as sc  # noqa: E402

FC_DIAG_LOG_MAGIC = 0x47444346
FC_DIAG_LOG_VERSION = 2
FC_DIAG_LOG_CAPACITY = 16384
HEADER_FMT = "<16I32s32s"
HEADER_SIZE = struct.calcsize(HEADER_FMT)          # 128
TOTAL_SIZE = HEADER_SIZE + FC_DIAG_LOG_CAPACITY    # 16512
NO_TEST = 0xFFFFFFFF


def evaluate(data, expect_build=None, out=print):
    out("dump   : %d bytes (log size %d)" % (len(data), TOTAL_SIZE))
    if len(data) < HEADER_SIZE:
        return sc.finish("INVALID", ["dump shorter than the 128-byte header: SWD read failed/truncated"], out)
    (magic, version, length, capacity, final, mask, fw, run, count, cur, fcode, fpc, fcfsr, fhfsr,
     faddr, rcrc, states_raw, build_raw) = struct.unpack_from(HEADER_FMT, data, 0)
    if magic != FC_DIAG_LOG_MAGIC:
        return sc.finish("INCOMPLETE", ["magic 0x%08X is not 0x%08X: the test application never initialised "
                                        "the log (did not boot / reset without re-run / power cycle / wrong "
                                        "address)" % (magic, FC_DIAG_LOG_MAGIC)], out)
    if version != FC_DIAG_LOG_VERSION:
        return sc.finish("INVALID", ["log version %d, this decoder reads version %d (firmware/tool mismatch)"
                                     % (version, FC_DIAG_LOG_VERSION)], out)
    if capacity != FC_DIAG_LOG_CAPACITY or length > capacity:
        return sc.finish("INVALID", ["corrupt header: length %d capacity %d" % (length, capacity)], out)
    build = build_raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
    states = list(states_raw)
    out("fw     : %d.%d.%d   build : %s" % ((fw >> 16) & 0xFF, (fw >> 8) & 0xFF, fw & 0xFF, build))
    out("run    : %s   final : %s   tests : %d   current : %s"
        % (sc.RUN_STATES.get(run, "INVALID(%d)" % run), sc.FINAL_RESULTS.get(final, "INVALID(%d)" % final),
           count, "none" if cur == NO_TEST else cur))
    out("mask   : 0x%08X   report crc32 : 0x%08X   text : %d / %d bytes" % (mask, rcrc, length, capacity))
    n_show = min(max(count, sc.N_MANDATORY), 32)
    for i in range(n_show):
        name = sc.MANDATORY_TESTS[i] if i < sc.N_MANDATORY else "(entry %d)" % i
        out("  %2d %-30s %s" % (i, name, sc.TEST_STATES.get(states[i], "INVALID(%d)" % states[i])))
    avail = min(length, max(0, len(data) - HEADER_SIZE))
    text = data[HEADER_SIZE:HEADER_SIZE + avail].decode("latin-1")
    out("-" * 36 + " log text " + "-" * 32)
    out(text if text.endswith("\n") or not text else text + "\n")

    if expect_build is not None and build != expect_build:
        return sc.finish("INVALID", ["board ran build %s, the station expects %s" % (build, expect_build)], out)
    if run == 3 or final == 3:
        return sc.finish("ABORTED", ["fatal fault %s during test %s: PC=0x%08X CFSR=0x%08X HFSR=0x%08X addr=0x%08X"
                                     % (sc.FAULT_CODES.get(fcode, str(fcode)),
                                        "none" if cur == NO_TEST else cur, fpc, fcfsr, fhfsr, faddr)], out)
    if run != 2:
        where = ("test %d %s" % (cur, sc.MANDATORY_TESTS[cur])) if cur < sc.N_MANDATORY else "startup"
        return sc.finish("INCOMPLETE", ["run state %s (stopped in %s): hang, power loss or read taken too early"
                                        % (sc.RUN_STATES.get(run, run), where)], out)
    if final not in (1, 2):
        return sc.finish("INVALID" if final != 0 else "INCOMPLETE",
                         ["run COMPLETE but final_result %d" % final], out)
    if count != sc.N_MANDATORY:
        return sc.finish("INVALID", ["test_count %d, expected %d" % (count, sc.N_MANDATORY)], out)
    if len(data) < TOTAL_SIZE:
        return sc.finish("INVALID", ["dump has %d bytes, the complete log is %d: read the full log"
                                     % (len(data), TOTAL_SIZE)], out)
    bad = [i for i in range(sc.N_MANDATORY) if states[i] not in sc.TEST_STATES]
    if bad:
        return sc.finish("INVALID", ["invalid state value(s) at entries %s" % bad], out)
    expect_mask = sum(1 << i for i in range(sc.N_MANDATORY) if states[i] != 2)
    if mask != expect_mask:
        return sc.finish("INVALID", ["mask 0x%08X inconsistent with the per-test states (0x%08X)" % (mask, expect_mask)], out)
    # report CRC (only checkable when the text was not truncated at capacity)
    end = text.find("\nEND OF REPORT ")
    if length < capacity:
        if end < 0:
            return sc.finish("INVALID", ["complete run but no END line in the (untruncated) log text"], out)
        crc = sc.crc32(text[:end + 1].encode("latin-1"))
        if crc != rcrc:
            return sc.finish("INVALID", ["log text CRC 0x%08X != header report_crc32 0x%08X" % (crc, rcrc)], out)
        out("report CRC 0x%08X verified" % crc)
    else:
        out("NOTE: log text filled its capacity (truncated); CRC not checkable, header fields used")
    reasons = ["mandatory test %2d %-30s %s" % (i, sc.MANDATORY_TESTS[i], sc.TEST_STATES[states[i]])
               for i in range(sc.N_MANDATORY) if states[i] != 2]
    if final == 1:
        if mask != 0:
            return sc.finish("INVALID", ["final PASS with mask 0x%08X" % mask], out)
        return sc.finish("PASS", ["20/20 mandatory tests PASS, run COMPLETE, build %s" % build], out)
    if mask == 0:
        return sc.finish("INVALID", ["final FAIL with all states PASS"], out)
    return sc.finish("FAIL", reasons, out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", nargs="?", default=str(Path(__file__).resolve().parents[1] / "build" / "diag_log.bin"))
    ap.add_argument("--expect-build-id", default=None)
    a = ap.parse_args(argv)
    p = Path(a.dump)
    if not p.is_file():
        print("ERROR: dump file not found: %s" % p)
        return sc.finish("INCOMPLETE", ["no SWD dump (read failed?)"], print)
    return evaluate(p.read_bytes(), a.expect_build_id)


if __name__ == "__main__":
    sys.exit(main())
