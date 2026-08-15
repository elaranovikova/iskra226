#!/usr/bin/env python3
"""
The flat listing format, read and write.

Some sides in the archive carry no catalog at all. iskra.py reports them
as unknown, and for a while I took that to mean the read had failed. It
had not. What is on them is the output of BASIC's own LIST DC statement:
plain source text written straight to the surface, one program after
another, with no directory in front of it.

REGION line 2 says so itself:

    2 SCRATCH R/1C,"REGION":SAVE DC R/1C,T("REGION")"REGION":LIST DC R/1C,"R":END

That line is the author's own tooling. It wipes the work area, saves the
tokenised program, then lists the source next to it. Line 1 is GOTO 3, so
line 2 never runs unless you ask for it.

Layout, worked out from the bytes and verified by round trip:

    01 <name:8> <flag:1>    header sector, and nothing else in it. The name
                            is space padded. The flag is 0x20 on the three
                            programs here and 0x21 on SIG1, which I have
                            not explained.
    02 80                   first text sector
    8F 80                   middle text sector
    03 80                   last text sector
    1C 00 78                end record, its own sector
    85                      line separator
    00                      unused tail of a sector

No source line is ever split across a sector. When the next line does not
fit whole, the writer leaves the rest of the sector as zeros and starts
the next one, which is why 120 sectors hold 23,500 characters that would
fit in 95. That rule is what makes a byte-exact rebuild possible.

Usage:
    python3 listing_format.py read  <image.dsk> <NAME>          > out.bas
    python3 listing_format.py write <out.dsk> <NAME> <in.bas>
    python3 listing_format.py names <image.dsk>
"""

import re
import sys

SECTOR = 256
SECTORS = 1001
IMAGE_SIZE = SECTOR * SECTORS

HEADER_MARK = 0x01
NAME_LEN = 8
FIRST_PREFIX = b"\x02\x80"
MIDDLE_PREFIX = b"\x8f\x80"
LAST_PREFIX = b"\x03\x80"
PREFIXES = (FIRST_PREFIX, MIDDLE_PREFIX, LAST_PREFIX)
END_RECORD = b"\x1c\x00\x78"
LINE_BREAK = 0x85
END_MARK = 0x1C


def program_starts(data):
    """Sectors that begin with a program header, in order."""
    found = []
    for s in range(len(data) // SECTOR):
        base = s * SECTOR
        if data[base] != HEADER_MARK:
            continue
        raw = data[base + 1:base + 1 + NAME_LEN]
        try:
            name = raw.decode("koi8-r").rstrip()
        except UnicodeDecodeError:
            continue
        if re.fullmatch(r"[A-Z0-9]{2,8}", name):
            found.append((s, name))
    return found


def read_listing(data, name):
    """Return the source lines of one program as a list of strings."""
    starts = program_starts(data)
    names = [n for _, n in starts]
    if name not in names:
        raise KeyError(f"{name} not on this side, found {names}")
    i = names.index(name)
    first = starts[i][0]
    last = starts[i + 1][0] if i + 1 < len(starts) else len(data) // SECTOR

    body = bytearray()
    for s in range(first, last):
        sec = data[s * SECTOR:(s + 1) * SECTOR]
        if sec[0] == HEADER_MARK:
            continue                            # header sector carries no text
        if sec[:len(END_RECORD)] == END_RECORD or sec[0] == END_MARK:
            break
        if sec[:2] in PREFIXES:
            sec = sec[2:]
        body += sec.rstrip(b"\x00") + bytes([LINE_BREAK])

    lines = []
    for chunk in bytes(body).split(bytes([LINE_BREAK])):
        chunk = chunk.replace(b"\x00", b"")
        if not chunk.strip():
            continue
        # Trailing spaces are kept. Several lines carry one, and dropping
        # them would break a byte-exact rebuild.
        lines.append(chunk.decode("koi8-r"))
    return lines


def pack(lines):
    """Group lines into sector payloads, never splitting a line."""
    room = SECTOR - 2
    groups, current, used = [], [], 0
    for line in lines:
        chunk = line.encode("koi8-r") + bytes([LINE_BREAK])
        if len(chunk) > room:
            raise ValueError(f"line does not fit in one sector: {line[:40]}")
        if used + len(chunk) > room:
            groups.append(current)
            current, used = [], 0
        current.append(chunk)
        used += len(chunk)
    if current:
        groups.append(current)
    return groups


def write_listing(lines, name, sectors=SECTORS, start=0):
    """Build a full side image holding one program in the same format."""
    if len(name) > NAME_LEN:
        raise ValueError(f"name longer than {NAME_LEN}")
    groups = pack(lines)
    image = bytearray(sectors * SECTOR)

    base = start * SECTOR
    image[base] = HEADER_MARK
    image[base + 1:base + 1 + NAME_LEN] = name.ljust(NAME_LEN).encode("koi8-r")
    image[base + 1 + NAME_LEN] = 0x20

    for i, group in enumerate(groups):
        prefix = (FIRST_PREFIX if i == 0
                  else LAST_PREFIX if i == len(groups) - 1
                  else MIDDLE_PREFIX)
        base = (start + 1 + i) * SECTOR
        if base + SECTOR > len(image):
            raise ValueError("listing does not fit on one side")
        image[base:base + 2] = prefix
        payload = b"".join(group)
        image[base + 2:base + 2 + len(payload)] = payload

    base = (start + 1 + len(groups)) * SECTOR
    image[base:base + len(END_RECORD)] = END_RECORD
    return bytes(image)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    mode = argv[1]
    if mode == "names":
        data = open(argv[2], "rb").read()
        for s, n in program_starts(data):
            print(f"sector {s:4d}  {n}")
    elif mode == "read":
        data = open(argv[2], "rb").read()
        for line in read_listing(data, argv[3]):
            print(line)
    elif mode == "write":
        lines = open(argv[4], encoding="utf-8").read().splitlines()
        lines = [ln for ln in lines if ln.strip()]
        open(argv[2], "wb").write(write_listing(lines, argv[3]))
        print(f"{argv[2]}: {len(lines)} lines as {argv[3]}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
