# wang-reference/

Nothing in this directory is mine. It is Wang 2200 material, and it is here
because the Iskra-226 was built for compatibility with Wang 2200 BASIC at the
software level. A working Wang emulator is therefore the only oracle I have
for what the Iskra's BASIC was supposed to do.

## Whose it is

**WangEmu 3.0**, by **Jim Battle**.

    https://github.com/jtbattle/wangemu
    http://wang2200.org/emu.html

WangEmu is released under the MIT License, Copyright (c) 2019 Jim Battle. The
full text is in `LICENSE-WANGEMU`, in this directory, and it is the license
these five files are under. The MIT License at the root of this repository is
mine. It covers my work and it does not reach in here.

`ucode_2200T.cpp` carries a second credit in its own first lines: the 2200T
ROM image in it was contributed by **Carl Coffman**.

The scanned manuals in `docs/` come from Jim Battle's collection as well. He
has been the reason this was possible twice over, and if you mirror this
repository, mirror his name with it.

| file | what it is |
|---|---|
| `Cpu2200vp.cpp` | the Wang 2200 VP micromachine, every microinstruction implemented and tested |
| `Cpu2200t.cpp` | the same for the 2200T micromachine |
| `dasm_vp.cpp` | the VP microcode disassembler |
| `ucode_2200T.cpp` | a static image of the 2200T ROMs |
| `vp-boot-2.4.wvd` | the VP boot disk, which carries the BASIC-2 microcode |

## Unmodified, and how to check

Compared on 6 August 2026 against `github.com/jtbattle/wangemu`, branch
`master`. SHA-256 of the files as they sit here:

    515b9ccc99a49feb97820988c91cc1dfa9ec493b749d784eaf09ccb8bcac4501  Cpu2200t.cpp
    d88d98c612a8f1ef3eef613115431432266a199df1b318ce493cc643ebd0d389  Cpu2200vp.cpp
    ca8410f3f743b5b0d8f0bfbaa50a96c12026b512e1a49c9e3b1675f203637935  dasm_vp.cpp
    3a2350c13070380512448a3ec122681bbee45cd8e29a36e0943509b6eca4b712  ucode_2200T.cpp
    84df000baef5037f1d96f9e7e0fa7a38c9d574f5b29519d654c3f9c206a19e6e  vp-boot-2.4.wvd

Four of the five are byte-identical to upstream. `Cpu2200vp.cpp` is identical
in content and differs only in its line endings: the copy here has CRLF, which
is how it arrived. Strip the carriage returns and it hashes to
`d0f2d20a724daedac3a77a925d0e570e5f05d1db75626e3f80514c0494da797c`, which is
upstream exactly. I have left it as it came rather than tidy somebody else's
file.

## What I did with it, and what I did not

I read it. The VP microcode is 24 bits wide and the Iskra runs 16-bit
macro-instructions, so the opcode-level alignment these were fetched for does
not work, and `findings/isa-findings.md` addendum 15 says why the 2200T is no
better. What remains is behaviour: what BASIC-2 does with a given input, which
is a thing I can compare against without copying anything.

Nothing in `emulator/` is derived from these files. No line of this C++ was
translated into that Python. If that ever stops being true, this file changes
in the same commit.
