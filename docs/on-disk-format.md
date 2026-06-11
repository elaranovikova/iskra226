# The on-disk format, first complete pass

Written against the six sides in `disks/`, June 2026. Every claim here is
something `emulator/iskra.py` can be made to print, and where I am guessing
I say so.

## Geometry

Each file is exactly 256,256 bytes. That factors as 77 x 26 x 128, which is
IBM 3740 single density on 8-inch media: 77 tracks, 26 sectors per track,
128 bytes per sector. It also factors as 1001 x 256. Both are true and the
difference cost me an evening, see below.

One file is one *side*. The three physical disks in the archive are six
files, and the naming says so: `disk1side0`, `disk1side1`, and so on.

## The two sector sizes

The physical sector is 128 bytes. The logical sector, the one the catalog
counts in, is 256.

I did not believe this for a while because the catalog parses correctly
either way: the entries live in the first few sectors and 16-byte records
land on the same boundaries at both sizes. What does not survive is
extraction. Reading a file at 128-byte sectors gives you exactly half of it
and the half is the wrong half, interleaved.

The proof is in the header. `disk3side0` reports its catalog area as 1000
sectors. The image has 2002 physical sectors of 128 bytes. It has 1001
sectors of 256 bytes. Only one of those is near 1000.

So: address the medium in 128, address the *files* in 256.

## The catalog

Sector 0 begins with three big-endian 16-bit fields:

    0-1   number of index sectors
    2-3   last sector in use
    4-5   size of the catalog area

After those six bytes the entries start, 16 bytes each, and they continue
into the following sectors:

    0     status
    1     flags
    2-3   first sector, big endian
    4-5   last sector, big endian
    6-7   reserved, always zero in this archive
    8-15  name, space padded, KOI-8

Entries are monotone: each file's first sector is at or after the previous
file's last. A scratched file keeps its entry and its name, with the status
byte changed. `disk2side1` carries one of those, a Cyrillic name that reads
СПИСОК.
