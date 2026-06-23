# Iskra-226

Tools for reading the floppy images of the Iskra-226 (Искра 226), a Soviet
desktop computer built at Schyotmash Kursk from 1980/81.

Right now this reads sectors, decodes the catalog, extracts files and
pulls text out of a disk image. The on-disk format is documented in
`docs/on-disk-format.md` against the bytes. There is no emulator here
and I am not promising one.

## Use

    python3 emulator/iskra.py info    <images...>
    python3 emulator/iskra.py cat     <image>
    python3 emulator/iskra.py extract <image> [outdir]
    python3 emulator/iskra.py text    <image>

## What this is not

It is not a CPU emulator. The Iskra has no microprocessor; it has K589 bit
slices, which are Intel 3000 clones. Nobody has written an emulator for this
machine and I do not yet know whether I can.

## Why

I have a disk I cannot read. Everything here follows from that.
