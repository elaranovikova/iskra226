#!/usr/bin/env python3
"""
iskra - toolkit for Iskra-226 (Искра 226) floppy images.

The Iskra 226 loads its interpreter from disk at power-on.

  * disk geometry: IBM 3740 formats the media as 77 tracks x 26 physical
    sectors x 128 bytes, but the file system pairs them. Every catalog
    number, extent and length on these disks counts LOGICAL sectors of
    256 bytes, 1001 per side.
  * KOI-8 character set
  * detection and extraction of boot images

Three on-disk layouts turn up in the surviving images:

  * Wang-2200-style catalog (16-byte entries) -> Disk.catalog()
  * labeled text volume, an EDITOR document with a name and a date in
    sector 0 and running KOI-8 text further in -> Disk.text_label(),
    Disk.text_body()
  * flat BASIC source with no directory at all, recognized only by how
    much of the surface reads as BASIC -> Disk.is_basic_source()

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

# -- labeled text volume ---------------------------------------------------
# An EDITOR document written to a whole side. Sector 0 carries the volume
# label, sector 2 repeats name and date behind a different prefix, sectors
# 3.. hold a small chapter index, and the running text starts further in.
LABEL_MAGIC = 0x7E          # sector 0, byte 0
LABEL_NAME_OFF = 1          # eight KOI-8 characters, space padded
LABEL_NAME_LEN = 8
LABEL_CONST_OFF = 9         # the constant '111111' follows the name
LABEL_CONST = b"111111"
LABEL_DATE_OFF = 28         # six ASCII digits, DDMMYY as everywhere on this
LABEL_DATE_LEN = 6          # machine (compare the boot signatures)

# Line separators inside EDITOR text. NUL ends a line. '!' is the EDITOR's
# own line separator, but on these two volumes it turns up exactly once per
# sector and always at offset 0, where it means the opposite: the sector
# carries on the line the sector before it broke off, sometimes in the
# middle of a word. So it separates everywhere except in that one place.
LINE_BREAK = 0x21           # '!'
NUL_BREAK = 0x00

# -- text and source heuristics --------------------------------------------
MIN_TEXT_BYTES = 64         # ignore sectors that are almost empty
TEXT_SECTOR_RATIO = 0.90    # share of printable bytes that makes it text
MIN_VISIBLE_RATIO = 0.50    # and this much of it has to be visible, or a
                            # free map of NULs and a few 0xFF would pass

# Spelled out in the source, not tokenized: these disks store BASIC the way
# the EDITOR wrote it. The trailing spaces keep 'FOR' out of 'FORMAT' and
# 'IF' out of any identifier.
BASIC_KEYWORDS = (b"PRINT", b"GOTO", b"GOSUB", b"RETURN", b"THEN", b"INPUT",
                  b"NEXT", b"FOR ", b"IF ", b"REM ", b"DIM ", b"DATA ",
                  b"END")
MIN_SOURCE_SECTORS = 16     # below this a few stray words prove nothing
MIN_SOURCE_RATIO = 0.5      # of the text sectors, this many must be BASIC

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
        self._stats = None      # filled by text_stats()
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
        """
        One line naming the layout of this side.

        The order is not free. A boot image has no catalog header, a text
        volume would produce a nonsense one, and a catalogued disk full of
        BASIC would also satisfy the source heuristic, so the cheap and
        exact tests have to run before the statistical one.
        """
        if self.is_blank():
            return "blank"
        if self.is_boot():
            return "boot image: " + self.boot_signature()
        label = self.text_label()
        if label is not None:
            return "text volume '%s' of %s" % (label[0], self.label_date())
        entries = self.catalog()
        if entries is not None:
            return "data disk (%d files)" % len(entries)
        if self.is_basic_source():
            return ("BASIC source, no directory (%d of %d sectors)"
                    % self.text_stats())
        return "unknown"

    # -- labeled text volume ----------------------------------------------

    def text_label(self):
        """
        ('АСМБ', '261185') on a labeled text volume, None otherwise.

        Sector 0 opens with 0x7E, then eight KOI-8 characters of volume
        name padded with spaces, then the constant '111111', and at offset
        28 six ASCII digits of date. Sector 2 repeats name and date behind
        a different prefix; that repeat is the cross check, because a
        single magic byte would sooner or later fire on a binary side.
        """
        head = self.sector(0)
        if len(head) < LABEL_DATE_OFF + LABEL_DATE_LEN:
            return None
        if head[0] != LABEL_MAGIC:
            return None
        if head[LABEL_CONST_OFF:LABEL_CONST_OFF + len(LABEL_CONST)] != LABEL_CONST:
            return None
        raw_name = head[LABEL_NAME_OFF:LABEL_NAME_OFF + LABEL_NAME_LEN]
        if not all(b == 0x20 or 0xC0 <= b <= 0xFF or 0x21 <= b < 0x7F
                   for b in raw_name):
            return None
        name = decode(raw_name).strip()
        if not name:
            return None
        date = head[LABEL_DATE_OFF:LABEL_DATE_OFF + LABEL_DATE_LEN]
        if not date.isdigit():
            return None
        date = date.decode("ascii")
        if raw_name not in self.sector(2) or date.encode() not in self.sector(2):
            return None
        return name, date

    def is_text_volume(self):
        return self.text_label() is not None

    def label_date(self):
        """The volume date as DD.MM.YY, or None."""
        label = self.text_label()
        if label is None:
            return None
        d = label[1]
        return "%s.%s.%s" % (d[0:2], d[2:4], d[4:6])

    def is_text_sector(self, n):
        """True when sector n reads as running text rather than as code."""
        raw = self.sector(n).rstrip(b"\x00")
        if len(raw) < MIN_TEXT_BYTES:
            return False
        visible = sum(1 for b in raw if 0x20 <= b < 0x7F or 0xC0 <= b <= 0xFF)
        # Embedded NUL counts as printable, inside EDITOR text it is the
        # line break, but it must not be what carries the sector.
        printable = visible + raw.count(0x00)
        return (printable >= TEXT_SECTOR_RATIO * len(raw) and
                visible >= MIN_VISIBLE_RATIO * len(raw))

    def first_text_sector(self, skip=3):
        """
        Number of the first sector of running text, or None.

        The label, the free map and the chapter index sit in front of it and
        are skipped. A single text-looking sector is not enough, the run has
        to continue, otherwise a stray index sector would win.
        """
        for n in range(skip, len(self) - 1):
            if self.is_text_sector(n) and self.is_text_sector(n + 1):
                return n
        return None

    def text_body(self, first=None):
        """
        The running text of the volume as a list of editor lines.

        Sectors are read in order from the first text sector on and cut at
        the separators, NUL and '!', with the leading '!' of a continuation
        sector skipped so that words split across a sector boundary come
        back together. The NUL padding behind the last line of a sector is
        dropped first, otherwise every sector would end in a stack of empty
        lines. Sectors that are not text at all are skipped: the chapters
        of the manual do not touch, there is binary in between. Trailing
        blanks go, leading blanks stay, they carry the layout.
        """
        if first is None:
            first = self.first_text_sector()
        if first is None:
            return []
        lines = []
        run = bytearray()
        for n in range(first, len(self)):
            if not self.is_text_sector(n):
                continue
            raw = self.sector(n).rstrip(b"\x00")
            if raw[:1] == bytes([LINE_BREAK]):
                raw = raw[1:]           # continuation, not a break
            for b in raw:
                if b == NUL_BREAK or b == LINE_BREAK:
                    lines.append(decode(bytes(run), "").rstrip())
                    run.clear()
                else:
                    run.append(b)
        lines.append(decode(bytes(run), "").rstrip())
        return lines

    # -- flat BASIC source, no directory ----------------------------------

    def text_stats(self):
        """
        (sectors that read as BASIC source, sectors that read as text).

        Cached, because kind() and cmd_info both want it and it walks the
        whole side byte by byte.
        """
        if self._stats is None:
            source = text = 0
            for n in range(len(self)):
                if not self.is_text_sector(n):
                    continue
                text += 1
                raw = self.sector(n)
                if any(k in raw for k in BASIC_KEYWORDS):
                    source += 1
            self._stats = (source, text)
        return self._stats

    def is_basic_source(self):
        """
        True for a side that is nothing but BASIC source, no catalog.

        Two disks are held together only by this: the text has to fill a
        real part of the surface, and it has to be BASIC rather than prose.
        A binary side fails the first test, the Assembler manual fails the
        second with 2 percent.
        """
        source, text = self.text_stats()
        if source < MIN_SOURCE_SECTORS:
            return False
        return source >= MIN_SOURCE_RATIO * text

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
        if self.is_boot() or self.is_blank() or self.is_text_volume():
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
        # Sides with no catalog get a second line, because for them the
        # kind is a finding and not a lookup, and the reader deserves the
        # numbers it rests on.
        if d.is_text_volume():
            first = d.first_text_sector()
            text = d.text_stats()[1]
            lines = d.text_body(first)
            print("                 label %s, %s, text from sector %s, "
                  "%d text sectors, %d lines"
                  % (d.text_label()[0], d.label_date(),
                     "?" if first is None else first, text,
                     sum(1 for line in lines if line)))
        elif d.catalog() is None and not d.is_boot() and not d.is_blank():
            source, text = d.text_stats()
            if d.is_basic_source():
                print("                 no catalog, %d of %d text sectors "
                      "carry BASIC keywords (%.0f%%)"
                      % (source, text, 100.0 * source / text))
            else:
                # Say what little is there. A side that reaches this point
                # is usually a read that failed, not a fourth format.
                used = sum(1 for n in range(len(d))
                           if d.sector(n).count(0) != SECTOR)
                print("                 no catalog, no label, %d of %d "
                      "sectors carry data, %d of them text"
                      % (used, len(d), text))


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
    if d.is_text_volume():
        # A labeled volume is one document, so print it as one, in order,
        # instead of fishing for runs.
        print("%s: text volume '%s' of %s, from sector %s"
              % (d.name, d.text_label()[0], d.label_date(),
                 d.first_text_sector()))
        for line in d.text_body():
            print(line)
        return
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
