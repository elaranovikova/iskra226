#!/usr/bin/env python3
"""
iskra - toolkit for Iskra-226 (Искра 226) floppy images.

The Iskra 226 loads its interpreter from disk at power-on.

  * disk geometry (IBM 3740: 77 tracks x 26 sectors x 128 bytes)
  * KOI-8 character set

Usage:
    python3 iskra.py info <images...>
    python3 iskra.py text <image>
"""

import sys
import os
import struct
import math
from collections import Counter

SECTOR_SIZE = 128
SECTORS_PER_TRACK = 26
TRACKS = 77
IMAGE_SIZE = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE   # 256256
BOOT_HEADER_LEN = 32    # magic + version string + test pattern

# --------------------------------------------------------------------------
# Character set
# --------------------------------------------------------------------------

# KOI-8: 0xC0..0xFF carry the Cyrillic alphabet. The Iskra uses the same
# range; lowercase ASCII 0x60..0x7F is the 7-bit variant KOI-7 of the
# same characters.
_KOI8_HIGH = ("юабцдефгхийклмнопярстужвьызшэщчъ"
              "ЮАБЦДЕФГХИЙКЛМНОПЯРСТУЖВЬЫЗШЭЩЧЪ")

KOI8 = {0xC0 + i: ch for i, ch in enumerate(_KOI8_HIGH)}


def decode(data, placeholder="·"):
    """Bytes to readable text: ASCII stays, 0xC0-0xFF becomes Cyrillic."""
    out = []
    for b in data:
        if b in KOI8:
            out.append(KOI8[b])
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
        else:
            out.append(placeholder)
    return "".join(out)


# --------------------------------------------------------------------------
# Disk image
# --------------------------------------------------------------------------

class Disk:
    """One side of a floppy, as a sequence of sectors."""

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as fh:
            self.data = fh.read()
        if len(self.data) != IMAGE_SIZE:
            print("warning: %s is %d bytes, expected %d"
                  % (self.name, len(self.data), IMAGE_SIZE), file=sys.stderr)

    def __len__(self):
        return len(self.data) // SECTOR_SIZE

    def sector(self, n):
        return self.data[n * SECTOR_SIZE:(n + 1) * SECTOR_SIZE]

    def sectors(self, first, last):
        """Sectors first..last, inclusive."""
        return self.data[first * SECTOR_SIZE:(last + 1) * SECTOR_SIZE]

    def chs(self, n):
        """Sector number -> (track, sector), for error messages."""
        return n // SECTORS_PER_TRACK, n % SECTORS_PER_TRACK + 1
# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_info(paths):
    for p in paths:
        d = Disk(p)
        zero = d.data.count(0) / len(d.data)
        print("%-16s %7d bytes  %4d sectors  %5.1f%% zero"
              % (d.name, len(d.data), len(d), zero * 100))


def cmd_text(path, min_len=12):
    """Print runs of KOI-8 text."""
    d = Disk(path)
    run = bytearray()
    seen = set()
    printable = set(range(0xC0, 0x100)) | set(b" ,.?()-/0123456789:;=")
    for b in d.data:
        if b in printable:
            run.append(b)
            continue
        if len(run) >= min_len:
            t = decode(bytes(run)).strip()
            if t not in seen and any(c in _KOI8_HIGH for c in t):
                seen.add(t)
                print("  " + t)
        run.clear()


USAGE = __doc__


def main(argv):
    if len(argv) < 3:
        print(USAGE)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "info":
        cmd_info(args)
    elif cmd == "text":
        cmd_text(args[0])
    else:
        print(USAGE)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
