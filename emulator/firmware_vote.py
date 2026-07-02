#!/usr/bin/env python3
"""
firmware_vote - recover an error-corrected interpreter master from a boot side.

Every boot side carries the interpreter four times over, back to back, 498
sectors of 128 bytes each, so 63744 bytes per copy and 254976 of the 256256
bytes on the side. The four copies are not identical: against the voted
result, copy 0 differs in 75 bytes and copies 1 to 3 in 1320, 1805 and 1841
bytes on the BASIC 02 side. Read errors, and not in the same places, which
is the whole point of writing it four times.

Taking the most common value at each offset gives a master that no single
copy on the disk provides.

Usage:
    python3 firmware_vote.py <bootimage.dsk> <out.bin>
    python3 firmware_vote.py <bootimage.dsk> --report
"""

import sys
from collections import Counter

COPY_LEN = 498 * 128     # 63744 bytes, one interpreter image
COPIES = 4


def copies_of(image):
    return [image[k * COPY_LEN:(k + 1) * COPY_LEN] for k in range(COPIES)]


def vote(copies):
    """Most common byte per offset. Returns (master, votes per offset)."""
    master = bytearray()
    tally = []
    for i in range(COPY_LEN):
        counts = Counter(c[i] for c in copies)
        value, votes = counts.most_common(1)[0]
        master.append(value)
        tally.append(votes)
    return bytes(master), tally


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1

    with open(argv[1], "rb") as fh:
        image = fh.read()
    if len(image) < COPIES * COPY_LEN:
        print("%s is %d bytes, needs at least %d"
              % (argv[1], len(image), COPIES * COPY_LEN), file=sys.stderr)
        return 1

    copies = copies_of(image)
    master, tally = vote(copies)

    if argv[2] == "--report":
        print("copy   offset   bytes differing from the master")
        for k, c in enumerate(copies):
            diff = sum(1 for a, b in zip(c, master) if a != b)
            print("  %d  %8d   %5d" % (k, k * COPY_LEN, diff))
        split = Counter(tally)
        print("\nvote margin over %d offsets:" % COPY_LEN)
        for votes in sorted(split, reverse=True):
            print("  %d of %d ... %6d offsets" % (votes, COPIES, split[votes]))
        if min(tally) <= COPIES // 2:
            print("\nwarning: at least one offset has no majority")
        return 0

    with open(argv[2], "wb") as fh:
        fh.write(master)
    print("%s -> %s (%d bytes)" % (argv[1], argv[2], len(master)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
