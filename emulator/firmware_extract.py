#!/usr/bin/env python3
"""
firmware_extract - recover the interpreter builds from an Iskra boot side.

A boot side is not one interpreter written four times. It is four slots of
498 sectors each, 63744 bytes per slot, and the slots hold *different
builds*. Every slot carries its own 32-byte header: the entry vector, then
an 18-character signature such as 'BASIC 02  22.04.84'.

Across the three boot sides in this archive the slots hold eight distinct
builds spanning five years:

    BASIC 01  15.12.81   disk1side0 slot 3
    BASIC 01  12.07.82   disk1side0 slot 1
    BASIC 01  27.12.82   disk1side0 slot 2
    BASIC 02  16.12.83   disk1side1 slot 3
    BASIC 02  22.04.84   disk1side1 slot 0
    BASIC 02  10.10.84   disk1side1 slot 1
    BASIC PL5 30.09.84   disk1side0 slot 0, and all four slots of disk2side0
    BASIC 02  10.09.86   disk1side1 slot 2

Each build appears byte-identical wherever it appears, so nothing has to be
error corrected and nothing has to be guessed. PL5 30.09.84 is present five
times over, all five identical.

Do not majority-vote the slots. Voting them mixes builds that are two to
five years apart and yields a file that never existed on any machine. On
disk1side0 it is worse than that: slot 0 is PL5 and slots 1 to 3 are BASIC
01, a different program with a different entry vector, so the vote returns
BASIC 01 under a PL5 label, 58587 of 63744 bytes away from actual PL5.

The BASIC 02 10.09.86 build matters beyond completeness: it is the revision
the BAM database suite on disk2side1 declares it was written for.

Usage:
    python3 firmware_extract.py <bootimage.dsk> [outdir]
    python3 firmware_extract.py <bootimage.dsk> --report
"""

import sys
import os
import re
import hashlib
import struct

SLOT_LEN = 498 * 128     # 63744 bytes, one interpreter build
SLOTS = 4
HEADER_LEN = 32


def slots_of(image):
    return [image[k * SLOT_LEN:(k + 1) * SLOT_LEN] for k in range(SLOTS)]


def signature(slot):
    """The 18-character build signature, or None if the header is not one."""
    text = slot[6:24].decode("ascii", "replace")
    return text.strip() if re.match(r"^[ -~]{18}$", text) else None


def entry_vector(slot):
    return struct.unpack("<HHH", slot[0:6])


def filename_for(sig):
    """'BASIC 02  22.04.84' -> 'basic02_220484.bin'"""
    parts = sig.split()
    name = "".join(parts[:-1]).lower().replace(".", "")
    date = parts[-1].replace(".", "")
    return "%s_%s.bin" % (name, date)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1

    with open(argv[1], "rb") as fh:
        image = fh.read()
    if len(image) < SLOTS * SLOT_LEN:
        print("%s is %d bytes, needs at least %d"
              % (argv[1], len(image), SLOTS * SLOT_LEN), file=sys.stderr)
        return 1

    slots = slots_of(image)
    report = len(argv) > 2 and argv[2] == "--report"
    outdir = argv[2] if len(argv) > 2 and not report else "."

    if report:
        print("slot   offset  entry vector        signature            sha1")
        for k, s in enumerate(slots):
            v = entry_vector(s)
            print("  %d  %8d  %04X %04X %04X   %-19s  %s"
                  % (k, k * SLOT_LEN, v[0], v[1], v[2],
                     signature(s) or "(no signature)",
                     hashlib.sha1(s).hexdigest()[:16]))
        distinct = {hashlib.sha1(s).digest() for s in slots}
        print("\n%d slot(s), %d distinct build(s)" % (SLOTS, len(distinct)))
        return 0

    os.makedirs(outdir, exist_ok=True)
    for k, s in enumerate(slots):
        sig = signature(s)
        if sig is None:
            print("slot %d: no signature, skipped" % k)
            continue
        target = os.path.join(outdir, filename_for(sig))
        with open(target, "wb") as fh:
            fh.write(s)
        print("slot %d  %-19s -> %s" % (k, sig, target))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
