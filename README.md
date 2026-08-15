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
from the disk bytes. `findings/vedomost-printed.png` is a payment sheet
the original software printed for me. It is not a surviving document: the
program is the one from 1989, the three students I typed in are not. What
the machine did with them is its own: 144.50 and 105.00 gross, 249.50
accrued, 37.20 withheld, 212.30 net. I checked those against a hand
calculation before I believed them.

All 23 programs on the two application sides load and run without a crash.
Twenty-three is the count of catalog entries whose second byte is 0x80.
The two entries with 0x00 are data, one of them the file `132`, and an
earlier version of this README counted them as programs.

**This runs the software, not the CPU.** The interpreter firmware is not
executed. The distinction matters and I am not going to bury it.

`emulator/iskra_basic.py` is the decoder underneath: catalog, format, LIST,
hex dump.

Since 15 August the interpreter also runs the mathematics the payroll
corpus never needed: the functions ABS INT RND SGN SQR LOG EXP SIN COS
TAN, the power operator, fractional constants, HEX() screen control,
PRINTUSING with image lines, STEP in FOR, and full expression
precedence. The token forms were decoded out of the statistics packages
on the 2026 archive, where the formulas are textbook and give every
byte away; `docs/basic-expression-tokens.md` holds the evidence. Two
earlier readings fell in the process, and the file says which and why.

What that bought: **МОДЕЛЬ РЕГИОНА runs.** `model-region/verify_run.py`
assembles the recovered 1980s teaching game from its listing, plays all
26 turns against the independent re-implementation in lockstep, and the
state agrees to nine decimals through to the final mark. The thirteen
game sources still assemble byte-identically, which is the regression
test.

`emulator/iskra226_emu.py` is a research tool at the CPU level. It loads
a firmware build, disassembles it, and executes what is documented. For
three months that meant trapping on most of the image; since 15 August
it means the opposite. The machine documented itself twice in the same
archive: DASB2, a disassembler written in BASIC on w005-s1v1, carries
the complete mnemonic table of the 16-bit ISA, and the manufacturer's
Assembler 226 manual (Shilko, Leningrad 1985) sits on w007/w011 as a
text volume and carries the semantics with worked examples. The
examples reproduce bit for bit in the self-test. Coverage on the words
reachable from the cold-start vectors: 99.78 % documented, 0.22 %
class-known, 0.00 % unknown. The cold start walks ten instructions and
stops exactly at the handoff into the microprogram store, which is the
one artefact no disk in the archive carries.

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

**listings/**, 5,842 decoded BASIC source lines from 23 programs: the four
segments of the STIPENDIYA payroll system of vocational school SPTU-132,
1988/89, authors Gorenburgov, Vintskevich and Muchkina, and the nineteen
programs of the BAM database suite. Decoded straight from the disks by
`iskra_basic.py`. The count moved on 6 August, when the lister turned out
to be dropping four BAM programs the survey had already counted.

**findings/**, `isa-findings.md` is the main document: the reconstructed
architecture and instruction set with nineteen dated addenda, including
every falsified hypothesis and the criterion that killed it.
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

Not solved, until 15 August 2026: the data operations, 49 arithmetic
and logic instructions and the D-class addressing modes. I wrote here
that they were not derivable from the binary by structural or
statistical means, and that was true. They were derivable from the
archive: the key was DASB2, the machine's own disassembler, written in
BASIC by somebody at the Institute of Physical Chemistry, sitting on a
disk I was sent in August. The paragraph above has the numbers. The
earlier boundary statement stays in `findings/`, kept because being
wrong about where the boundary was is part of the record.

Still missing: the Iskra's own 8 KB ПЗУ plus 2 KB ПМК, the
microprogram store. Nine entry points into it are written out in
`findings/` so a future dump can be read on target. If you have
surviving hardware, I would like to hear from you.

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
