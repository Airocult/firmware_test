#!/usr/bin/env python3
"""
parse_station_log.py - station verdict from a USART1 (J4 TELEM1, 115200 8N1)
capture of the STM32N657 FC manufacturing test.  This is the PRIMARY station
result path (JLCPCB_TEST_PROCEDURE.md).  Standard library only.

Usage:
  parse_station_log.py CAPTURE.txt [--expect-build-id ID] [--quiet]

The capture may contain anything before the report (FSBL trace, noise).  The
report must appear exactly once and be complete:
  banner  ->  test sections  ->  RESULTS block (20 lines)  ->  NOT-PASS MASK
  ->  FINAL RESULT: PASS|FAIL  ->  END OF REPORT build=<id> tests=20 crc32=0x...
The CRC-32 in the END line covers every character of the report (CR removed)
from the first banner character through the newline before "END".
A fatal fault prints "FATAL FAULT: ..." and "FINAL RESULT: ABORTED" instead
and no END line (verdict ABORTED).

Verdict / exit code (fc_station_common.py):
  0 PASS | 1 FAIL | 2 INCOMPLETE | 3 ABORTED | 4 INVALID
Only exit code 0 accepts the board.  [INFO] and [SKIP] lines are never
verdicts; per-check [PASS]/[FAIL] lines are listed for diagnosis only - the
RESULTS block + FINAL RESULT + END line are authoritative.
NOT HARDWARE VERIFIED: validated against output of the real runner/report
code on the PC (05_TOOLS/host_tests/station_tools), not against a board.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fc_station_common as sc  # noqa: E402

RESULT_LINE = re.compile(r"^\s*(\d+) (.{30}) (\S+)\s+(\d+) ms$")
END_LINE = re.compile(r"^END OF REPORT build=(\S+) tests=(\d+) crc32=0x([0-9A-Fa-f]{8})$")
MASK_LINE = re.compile(r"^NOT-PASS MASK: 0x([0-9A-Fa-f]{8})$")
RESULTS_HDR = re.compile(r"^RESULTS: (\d+) mandatory tests, run (\S+)$")


def normalise(raw: bytes) -> str:
    # latin-1 keeps every byte 1:1 so the CRC is computed over the exact bytes
    return raw.decode("latin-1").replace("\r\n", "\n").replace("\r", "")


def find_banners(text):
    """Start offsets of every banner (rule line immediately followed by the title line)."""
    starts = []
    needle = sc.BANNER_RULE + "\n" + sc.BANNER_TITLE + "\n"
    pos = text.find(needle)
    while pos >= 0:
        if pos == 0 or text[pos - 1] == "\n":
            starts.append(pos)
        pos = text.find(needle, pos + 1)
    return starts


def evaluate(text, expect_build=None, out=print):
    reasons = []
    banners = find_banners(text)
    if not banners:
        return sc.finish("INCOMPLETE", ["no report banner in the capture: the test application did not "
                                        "start (boot/programming problem), wrong UART/baud, or no capture"], out)
    if len(banners) > 1:
        return sc.finish("INVALID", ["%d report banners in one capture: the board reset/restarted during "
                                     "the test - power-cycle and run once more" % len(banners)], out)
    body = text[banners[0]:]
    lines = body.split("\n")

    m = re.search(r"^Firmware version: (\S+)$", body, re.M)
    fw = m.group(1) if m else "?"
    m = re.search(r"^Build: (\S+) (\S+)$", body, re.M)
    banner_build = m.group(1) if m else None
    out("firmware : %s   build : %s" % (fw, banner_build or "?"))

    fails = [l for l in lines if l.startswith("[FAIL]")]
    for l in fails:
        out("  " + l)

    if re.search(r"^FINAL RESULT: ABORTED$", body, re.M):
        for l in lines:
            if l.startswith("FATAL FAULT:"):
                out("  " + l)
        return sc.finish("ABORTED", ["the firmware published a fatal fault (FINAL RESULT: ABORTED); "
                                     "power-cycle and repeat once, a second ABORTED rejects the board"], out)

    end_idx = None
    for i, l in enumerate(lines):
        if l.startswith("END OF REPORT"):
            end_idx = i
            break
    if end_idx is None:
        if re.search(r"^FINAL RESULT: ", body, re.M):
            reasons.append("report truncated after FINAL RESULT (no END OF REPORT line)")
        else:
            last = next((l for l in reversed(lines) if l.strip()), "")
            reasons.append("run did not finish: no FINAL RESULT / END line (last line: %r) - "
                           "hang, reset or capture stopped early" % last[:80])
        return sc.finish("INCOMPLETE", reasons, out)

    m = END_LINE.match(lines[end_idx])
    if not m:
        return sc.finish("INVALID", ["malformed END line: %r" % lines[end_idx][:100]], out)
    end_build, end_tests, end_crc = m.group(1), int(m.group(2)), int(m.group(3), 16)
    covered = "\n".join(lines[:end_idx]) + "\n"
    crc = sc.crc32(covered.encode("latin-1"))
    if crc != end_crc:
        return sc.finish("INVALID", ["report CRC mismatch: END line 0x%08X, computed 0x%08X - corrupted or "
                                     "incomplete capture; capture again" % (end_crc, crc)], out)
    if banner_build is not None and banner_build != end_build:
        return sc.finish("INVALID", ["build id in banner (%s) != END line (%s)" % (banner_build, end_build)], out)
    if expect_build is not None and end_build != expect_build:
        return sc.finish("INVALID", ["board runs build %s, the station expects %s - wrong firmware "
                                     "programmed" % (end_build, expect_build)], out)
    if end_tests != sc.N_MANDATORY:
        return sc.finish("INVALID", ["END line reports %d tests, expected %d" % (end_tests, sc.N_MANDATORY)], out)

    hdr = None
    for i in range(end_idx):
        if RESULTS_HDR.match(lines[i]):
            hdr = i
    if hdr is None:
        return sc.finish("INVALID", ["no RESULTS block before the END line"], out)
    mh = RESULTS_HDR.match(lines[hdr])
    if int(mh.group(1)) != sc.N_MANDATORY or mh.group(2) != "COMPLETE":
        return sc.finish("INVALID", ["RESULTS header %r" % lines[hdr]], out)
    states = []
    for k in range(sc.N_MANDATORY):
        li = hdr + 1 + k
        mr = RESULT_LINE.match(lines[li]) if li < end_idx else None
        if not mr:
            return sc.finish("INVALID", ["RESULTS line %d malformed or missing: %r"
                                         % (k, lines[li][:80] if li < end_idx else "")], out)
        idx, name, state = int(mr.group(1)), mr.group(2).strip(), mr.group(3)
        if idx != k or name != sc.MANDATORY_TESTS[k]:
            return sc.finish("INVALID", ["RESULTS line %d is %d %r, expected %d %r (firmware/tool mismatch)"
                                         % (k, idx, name, k, sc.MANDATORY_TESTS[k])], out)
        if state not in sc.TEST_STATES.values():
            return sc.finish("INVALID", ["RESULTS line %d: unknown state %r" % (k, state)], out)
        states.append(state)
    mm = MASK_LINE.match(lines[hdr + 1 + sc.N_MANDATORY])
    if not mm:
        return sc.finish("INVALID", ["NOT-PASS MASK line missing after the RESULTS lines"], out)
    mask = int(mm.group(1), 16)
    expect_mask = sum(1 << i for i, s in enumerate(states) if s != "PASS")
    if mask != expect_mask:
        return sc.finish("INVALID", ["NOT-PASS MASK 0x%08X inconsistent with the states (0x%08X)" % (mask, expect_mask)], out)
    finals = [l for l in lines[hdr:end_idx] if l.startswith("FINAL RESULT: ")]
    if len(finals) != 1:
        return sc.finish("INVALID", ["%d FINAL RESULT lines in the result block" % len(finals)], out)
    final = finals[0][len("FINAL RESULT: "):].strip()

    for i, s in enumerate(states):
        if s != "PASS":
            reasons.append("mandatory test %2d %-30s %s" % (i, sc.MANDATORY_TESTS[i], s))
    if final == "PASS":
        if mask != 0:
            return sc.finish("INVALID", ["FINAL RESULT: PASS but mask 0x%08X" % mask], out)
        return sc.finish("PASS", ["20/20 mandatory tests PASS, report complete, CRC 0x%08X OK, build %s"
                                  % (crc, end_build)], out)
    if final == "FAIL":
        if mask == 0:
            return sc.finish("INVALID", ["FINAL RESULT: FAIL with an all-PASS RESULTS block"], out)
        return sc.finish("FAIL", reasons, out)
    return sc.finish("INVALID", ["unexpected FINAL RESULT %r in a complete report" % final], out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", help="UART capture file (raw bytes, CRLF or LF)")
    ap.add_argument("--expect-build-id", default=None,
                    help="build id the station expects (firmware/VERSION.txt 'build id')")
    ap.add_argument("--quiet", action="store_true", help="print only the verdict line")
    a = ap.parse_args(argv)
    p = Path(a.capture)
    out = (lambda s: None) if a.quiet else print
    if not p.is_file():
        print("ERROR: capture file not found: %s" % p)
        return sc.finish("INCOMPLETE", ["no capture file"], print)
    rc = evaluate(normalise(p.read_bytes()), a.expect_build_id, out)
    if a.quiet:
        print("STATION VERDICT: %s" % {v: k for k, v in sc.VERDICT_EXIT.items()}[rc])
    return rc


if __name__ == "__main__":
    sys.exit(main())
