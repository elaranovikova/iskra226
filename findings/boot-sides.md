# The boot sides

Each of the three uncatalogued sides carries the same 32-byte header
four times over, at 0, 63744, 127488 and 191232. That is a stride of
498 sectors of 128 bytes. Four copies fill 254,976 of the 256,256
bytes on the side.

The copies are not identical. On disk1side1 they differ from each
other in between 492 and 3,634 bytes.

## Correction, 6 August 2026

The word "copies" above is wrong and it cost me a month.

The four slots are not four writings of one interpreter. They are four
different interpreters. Each carries its own 18-character signature with
its own build date, and across the three boot sides there are eight
distinct builds spanning 1981 to 1986. A boot side is a version library.

The measured spread of 492 to 3,634 bytes on disk1side1 is real. It is
the distance between successive revisions of BASIC 02, which is exactly
the size you would expect four dated builds of one interpreter to differ
by, and that is why it read as damage.

Reading them as copies had a consequence. I majority-voted them into two
"error-corrected masters", and on disk1side0 the vote lost outright: slot 0
is PL5 and slots 1 to 3 are BASIC 01, a different program, so the vote
carried BASIC 01 three times and wrote it out under the PL5 name, 58,587
of 63,744 bytes away from the real thing. Both vote artifacts also came out
carrying build dates that never existed, because the vote averaged the date
digits as well.

No correction is needed in the first place. Every build is byte-identical
wherever it occurs. `emulator/firmware_extract.py` now writes the eight out
by signature, and `firmware/` holds them under their real dates.
