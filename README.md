# Iskra-226

The Iskra-226 (Искра 226) was a Soviet desktop computer, designed from
1974/78 at the Leningrad ГСКТБ "Счётмаш" under chief designer
V. E. Kuznetsov and built in series at Kursk from 1980/81. It is a Wang
2200 work-alike on its own K589 bit-slice hardware, compatible at the
BASIC level and not a hardware clone.

No emulator for it existed. This is one, plus everything I had to work out
to write it.

## What runs today

`emulator/iskra_run.py` executes real 1988 software. It loads a disk image,
decodes the tokenized BASIC 02 program and runs it on an 80x24 KOI-8
screen: PRINT with AT and TAB, INPUT, LET and implicit assignment, IF/THEN
relations, GOTO, GOSUB/RETURN, ON..GOTO, REM, STOP/END, numeric and string
variables, and chain-loading between program segments.

```
python3 emulator/iskra_run.py disks/disk3side0.dsk S0 --auto 1
python3 emulator/iskra_run.py disks/disk3side0.dsk S0 --screenshot menu.png
```

`findings/stipendiya-menu.png` is the SPTU-132 dispatcher menu, rendered
from the disk bytes. `findings/vedomost-printed.png` is payment sheet No. 2,
computed by the original software: 144.50 and 105.00 gross, 249.50
accrued, 37.20 withheld, 212.30 net. I checked those against a hand
calculation before I believed them.

All 24 findable programs on the two application sides load and run without
a crash.

**This runs the software, not the CPU.** The interpreter firmware is not
executed. The distinction matters and I am not going to bury it.

`emulator/iskra_basic.py` is the decoder underneath: catalog, format, LIST,
hex dump.

`emulator/iskra226_emu.py` is a research tool at the CPU level. It loads a
firmware build, disassembles it, executes the instruction classes whose
semantics are documented and traps precisely on the rest. Coverage is about
12 % executable, 30 % class-known, 58 % unknown. It does not boot, and
`findings/` says exactly why.

`emulator/iskra.py` is the disk, sector and catalog toolkit.
`emulator/firmware_extract.py` recovers the interpreter builds.

## Contents

**disks/**, `880.rar`, the original archive, plus the six extracted sector
images. 1001 logical sectors of 256 bytes per side. Provenance is in
`disks/README.md`, and so is the one thing that is not here.

**firmware/**, eight distinct interpreter builds, 1981 to 1986, recovered
from the four slots each boot side carries. A boot side is not one
interpreter written four times; the slots hold different builds, and
majority-voting them produces a version that never existed. Each build is
63,744 bytes and byte-identical wherever it repeats. Words are
little-endian; word 0 is the cold-start vector `9006` for BASIC 02 and PL5,
`AD43` for BASIC 01.

    BASIC 01  15.12.81   BASIC 02  16.12.83
    BASIC 01  12.07.82   BASIC 02  22.04.84
    BASIC 01  27.12.82   BASIC 02  10.10.84
    BASIC PL5 30.09.84   BASIC 02  10.09.86

BASIC 02 10.09.86 is the revision the BAM suite on `disk2side1` declares it
was written for.

**listings/**, 4,189 decoded BASIC source lines from 19 programs: the
STIPENDIYA payroll system of vocational school SPTU-132, 1988/89, authors
Gorenburgov, Vintskevich and Muchkina, and the BAM database suite. Decoded
straight from the disks by `iskra_basic.py`.

**findings/**, `isa-findings.md` is the main document: the reconstructed
architecture and instruction set with twelve dated addenda, including every
falsified hypothesis and the criterion that killed it.
`microcode-or-machine-code.md` is the question I got wrong for a month, kept
because the wrong month is part of the record. `architecture.md` is the
answer.

**docs/**, the scanned Russian manuals, mirrored from Jim Battle's
collection at wang2200.org, plus the independent on-disk format
documentation.

**reconstruction/**, an HTML reproduction of the dispatcher, in Russian and
in a Russian/English version. It is a re-implementation, not emulation; the
Python is what executes bytes.

**wang-reference/**, Wang 2200 VP boot disk, CPU implementation and
disassembler from **WangEmu 3.0, by Jim Battle**, MIT licensed and as it
came, kept as a behavioural reference for BASIC-2. The VP microcode is 24
bits wide and the Iskra runs 16-bit macro-instructions, so opcode-level
alignment between them does not work. `wang-reference/README.md` says whose
the five files are and carries his license; nothing here is derived from
them.

## Solved, and not

Solved: byte order, the boot vector table, fixed one-word instruction
length, all four transfer types, computed goto with inline address tables,
the NOP idioms, the console output loop at word 0x01B7, the message table,
the keyword and descriptor table at word 0x0B67 with 86 entries, and the
complete on-disk file and token format.

The layer map: K589 bit slices, the 3001 MCU and 3002 CPE with datasheets in
`docs/`, then the Iskra's own ПМК and ПЗУ microcode, which is MISSING, then
the 16-bit macro ISA where control flow is solved, then the BASIC 02 format,
which is solved.

Not solved: the data operations. 49 arithmetic and logic instructions and
the D-class addressing modes. These are not derivable from the binary by
structural or statistical means, and that boundary is documented with its
evidence. Closing it needs the processor's техническое описание, or a ПМК
and ПЗУ dump from surviving hardware.

If you have either, I would like to hear from you.

## Whose this is

My code is MIT and my prose and the decoded listings are CC BY 4.0, in
`LICENSE` and `LICENSE-DOCS`. Three parts of this repository are neither,
and each of the three has a README that names the people:

* `disks/`, the six sides, published by vazman and read off the hardware by
  dk_spb.
* `docs/`, the scanned manuals, mirrored from Jim Battle's collection at
  wang2200.org.
* `wang-reference/`, five files from WangEmu, MIT License, Copyright (c)
  2019 Jim Battle, with the 2200T ROM image in `ucode_2200T.cpp`
  contributed by Carl Coffman.

I did not do the hard part of any of those three.

## Please mirror this

The disk images survive nowhere else. Jim Battle at wang2200.org explicitly
asks for Iskra-226 material.
