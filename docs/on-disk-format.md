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
