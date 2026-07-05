# The boot sides

Each of the three uncatalogued sides carries the same 32-byte header
four times over, at 0, 63744, 127488 and 191232. That is a stride of
498 sectors of 128 bytes. Four copies fill 254,976 of the 256,256
bytes on the side.

The copies are not identical. On disk1side1 they differ from each
other in between 492 and 3,634 bytes.
