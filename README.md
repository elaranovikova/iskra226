# Iskra-226

The Iskra-226 (Искра 226) was a Soviet desktop computer, designed from
1974/78 at the Leningrad ГСКТБ "Счётмаш" under chief designer
V. E. Kuznetsov and built in series at Kursk from 1980/81. It is a Wang
2200 work-alike on its own K589 bit-slice hardware, compatible at the
BASIC level and not a hardware clone.

No emulator for it existed. This is the work toward one, and everything I
have had to find out on the way.

## What runs today

Not the machine. I am not going to write this as though something boots.

`emulator/iskra226_emu.py` is a research tool at the CPU level. It loads a
firmware build, disassembles it, executes the instruction classes whose
semantics are documented and traps precisely on the rest. Coverage is about
12 % executable, 30 % class-known, 58 % unknown. It does not boot, and
`findings/` says exactly why.

`emulator/iskra_basic.py` is the decoder underneath the disks: catalog,
format, LIST, hex dump. It turns a tokenized BASIC 02 program back into
source, which is how `listings/` was made.

`emulator/iskra.py` is the disk, sector and catalog toolkit.
`emulator/firmware_extract.py` recovers the interpreter builds.

Tonight the question changed. What the boot sides carry is not microcode.
It is machine code for a processor built out of the K589 slices, 67
instructions, 16 bits wide, and the real microcode sits in the ПМК, which I
do not have and no longer need. `findings/architecture.md` is that argument
written out; `findings/path-to-full-emulation.md` is the route from here.

## Contents

**disks/**, `880.rar`, the original archive, plus the six extracted sector
images. 1001 logical sectors of 256 bytes per side.

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

**findings/**, `isa-findings.md` is the main document: the reconstructed
architecture and instruction set, with every falsified hypothesis and the
criterion that killed it. `microcode-or-machine-code.md` is the question I
got wrong for a month, kept because the wrong month is part of the record.
`architecture.md` is the answer. `run-report.md` is what the research tool
does when you point it at a build.

**listings/**, decoded BASIC source, straight from the disks by
`iskra_basic.py`: the STIPENDIYA payroll system of vocational school
SPTU-132, 1988/89, authors Gorenburgov, Vintskevich and Muchkina, and the
BAM database suite.

**reconstruction/**, an HTML reproduction of the dispatcher, in Russian and
in a Russian/English version. It is a re-implementation, not emulation; the
Python is what executes bytes.

**docs/**, the scanned Russian manuals, mirrored from Jim Battle's
collection at wang2200.org, plus the independent on-disk format
documentation.

**wang-reference/**, Wang 2200 VP boot disk, CPU implementation and
disassembler from WangEmu 3.0, as a behavioural reference for BASIC-2. The
VP microcode is 24 bits wide and the Iskra runs 16-bit macro-instructions,
so opcode-level alignment between them does not work.

## Please mirror this

The disk images survive nowhere else. Jim Battle at wang2200.org explicitly
asks for Iskra-226 material.
