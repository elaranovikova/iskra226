#!/usr/bin/env python3
"""
iskra - toolkit for Iskra-226 (Искра 226) floppy images.

The Iskra 226 loads its interpreter from disk at power-on. Before any of
that can be looked at, the image has to be addressable as sectors.

IBM 3740 geometry: 77 tracks x 26 sectors x 128 bytes. That comes out to
exactly 256256 bytes, which is the size of every file in the archive. So
the geometry is right, or at least it is not wrong.

Usage:
    python3 iskra.py info <images...>
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


USAGE = __doc__


def main(argv):
    if len(argv) < 3:
        print(USAGE)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "info":
        cmd_info(args)
    else:
        print(USAGE)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
