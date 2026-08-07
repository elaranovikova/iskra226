#!/usr/bin/env python3
"""
iskra - toolkit for Iskra-226 (Искра 226) floppy images.

The Iskra 226 loads its interpreter from disk at power-on.

  * disk geometry: IBM 3740 formats the media as 77 tracks x 26 physical
    sectors x 128 bytes, but the file system pairs them. Every catalog
    number, extent and length on these disks counts LOGICAL sectors of
    256 bytes, 1001 per side.
  * Wang-2200-style catalog (16-byte entries)
  * KOI-8 character set
  * detection and extraction of boot images

What is NOT in here: a CPU core. The Iskra has no microprocessor, it has
K589 bit slices (Intel 3000 clones).

Usage:
    python3 iskra.py info    <images...>
    python3 iskra.py cat     <image>
    python3 iskra.py extract <image> [outdir]
    python3 iskra.py text    <image>
"""

import sys
import os
import struct
import math
from collections import Counter

PHYS_SECTOR = 128       # what the IBM 3740 format writes
PHYS_PER_TRACK = 26
TRACKS = 77
IMAGE_SIZE = TRACKS * PHYS_PER_TRACK * PHYS_SECTOR      # 256256

# The file system addresses pairs of physical sectors. Every number in a
# catalog entry refers to one of these, so this is the unit the rest of
# the module works in.
SECTOR = 2 * PHYS_SECTOR                                # 256
SECTORS = IMAGE_SIZE // SECTOR                          # 1001
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
        return len(self.data) // SECTOR

    def sector(self, n):
        return self.data[n * SECTOR:(n + 1) * SECTOR]

    def sectors(self, first, last):
        """Logical sectors first..last, inclusive."""
        return self.data[first * SECTOR:(last + 1) * SECTOR]

    def chs(self, n):
        """Logical sector -> (track, first physical sector), for messages."""
        p = n * 2
        return p // PHYS_PER_TRACK, p % PHYS_PER_TRACK + 1

    # -- content detection ------------------------------------------------

    BOOT_MAGIC = bytes([0x06, 0x90, 0x09, 0x90, 0x07, 0x90])

    def is_boot(self):
        return self.data.startswith(self.BOOT_MAGIC)

    def boot_signature(self):
        """Version string of the boot image, e.g. 'BASIC 02  22.04.84'."""
        if not self.is_boot():
            return None
        return self.data[6:24].decode("ascii", "replace").strip()

    def is_blank(self):
        return self.data.count(0) == len(self.data)

    def kind(self):
        if self.is_blank():
            return "blank"
        if self.is_boot():
            return "boot image: " + self.boot_signature()
        if self.catalog() is not None:
            return "data disk (%d files)" % len(self.catalog())
        return "unknown"

    # -- catalog ----------------------------------------------------------

    def catalog_header(self):
        """(index sectors, last used sector, size of the catalog area)."""
        return struct.unpack(">HHH", self.sector(0)[0:6])

    def catalog(self, max_index_sectors=32):
        """
        Wang-style catalog. Each entry is 16 bytes:
            0     status
            1     flags
            2-3   first sector (big endian)
            4-5   last sector
            6-7   reserved
            8-15  name, space padded

        Returns None when the side has no plausible catalog.
        """
        if self.is_boot() or self.is_blank():
            return None
        try:
            index_sectors, used_to, area = self.catalog_header()
        except struct.error:
            return None
        if not (0 < index_sectors <= max_index_sectors and
                0 < used_to <= len(self) and area <= len(self)):
            return None

        entries = []
        # The index can run longer than the header field claims, so keep
        # reading while entries keep turning up.
        #
        # An entry is real when byte 0 says so: 0x10 active, 0x11 scratched.
        # Nothing else identifies one. An earlier version of this method
        # instead required the extents to ascend, which held on the BAM
        # side by luck and lost four of the five files on disk3side0,
        # where the catalog lists 132 (178-738) before S2 (83-177).
        for sec in range(0, max_index_sectors):
            block = self.sector(sec)
            start_off = 16 if sec == 0 else 0
            found_any = False
            for off in range(start_off, SECTOR, 16):
                raw = block[off:off + 16]
                status, flags = raw[0], raw[1]
                if status not in (0x10, 0x11):
                    continue
                first, last = struct.unpack(">HH", raw[2:6])
                if not (0 <= first <= last < len(self)):
                    continue
                name = decode(raw[8:16]).rstrip()
                if not name:
                    continue
                entries.append(CatalogEntry(name, status, flags, first, last))
                found_any = True
            if sec >= index_sectors and not found_any:
                break
        return entries or None


class CatalogEntry:
    def __init__(self, name, status, flags, first, last):
        self.name = name
        self.status = status
        self.flags = flags
        self.first = first
        self.last = last

    @property
    def sector_count(self):
        return self.last - self.first + 1

    @property
    def size(self):
        return self.sector_count * SECTOR

    def safe_name(self):
        return "".join(c if c.isalnum() else "_" for c in self.name) or "unnamed"

    def __str__(self):
        return ("%-10s %02x/%02x  sector %4d-%-4d  %6.1f KB"
                % (self.name, self.status, self.flags,
                   self.first, self.last, self.size / 1024))


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_info(paths):
    for p in paths:
        d = Disk(p)
        blank = d.data.count(0) / len(d.data)
        print("%-16s %7d bytes  %3d tracks  %5.1f%% zero   %s"
              % (d.name, len(d.data), TRACKS, blank * 100, d.kind()))


def cmd_cat(path):
    d = Disk(path)
    entries = d.catalog()
    if entries is None:
        print("%s: no catalog (%s)" % (d.name, d.kind()))
        return
    idx, used, area = d.catalog_header()
    print("%s  index %d sectors, used up to %d of %d"
          % (d.name, idx, used, area))
    for e in entries:
        print("   " + str(e))
    print("   = %d files, %.1f KB" %
          (len(entries), sum(e.size for e in entries) / 1024))


def cmd_extract(path, outdir="."):
    d = Disk(path)
    os.makedirs(outdir, exist_ok=True)

    if d.is_boot():
        target = os.path.join(outdir, d.name.replace(".dsk", "") + ".ucode")
        with open(target, "wb") as fh:
            fh.write(d.data[BOOT_HEADER_LEN:])
        print("boot image '%s' -> %s" % (d.boot_signature(), target))
        return

    entries = d.catalog()
    if not entries:
        print("%s: nothing to extract" % d.name)
        return
    for e in entries:
        target = os.path.join(outdir, e.safe_name() + ".bin")
        with open(target, "wb") as fh:
            fh.write(d.sectors(e.first, e.last))
        print("%-10s -> %s (%d bytes)" % (e.name, target, e.size))


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
    elif cmd == "cat":
        cmd_cat(args[0])
    elif cmd == "extract":
        cmd_extract(args[0], args[1] if len(args) > 1 else ".")
    elif cmd == "text":
        cmd_text(args[0])
    else:
        print(USAGE)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
