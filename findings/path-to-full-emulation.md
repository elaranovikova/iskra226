# Iskra-226: Path to Full Emulation

Date: 2026-08-05. This document defines the working route to booting
the recovered BASIC 02 firmware to a READY prompt, and records the
groundwork completed today.

## Why the documentation route is closed

All reachable printed sources have been mined. The Aladiev reference
gives the architecture and five worked opcodes (see
`isa-findings.md`); the 48-page *Technical Information*
collection was read visually page by page and contains only
peripheral service manuals (interface block 015-85, display block
БОСГИ-1920, filter block 020-01, keyboard 007-31, machine ТО
1.320.136 of 1983), no CPU instruction table. The full opcode map
of the 49 arithmetic/logic instructions survives, if anywhere, in
the processor's own техническое описание, which is not online.

## The route that is open: known-plaintext alignment against Wang VP

The Iskra BASIC was built for full software compatibility with Wang
2200 BASIC-2. Wang's side of the equation is completely solved:
Jim Battle's WangEmu 3.0 ships

- `vp-boot-2.4.wvd`, the VP boot disk containing the BASIC-2
  microcode (the known plaintext),
- `Cpu2200vp.cpp`, a complete, tested implementation of every VP
  microinstruction (the semantics oracle),
- `dasm_vp.cpp`, a VP microcode disassembler.

The attack: locate functionally identical routines in both firmwares
via shared data anchors, align them instruction-by-instruction, and
read the unknown Iskra encodings off the known VP semantics.

### Anchor status (verified today)

- Both firmwares carry ASCII BASIC keyword tables.
  - Iskra: dense sorted list
    `...SKIP END FOR GOSUB GOTO HEX PRINT IF INIT INPUT KEYIN LET
    LIMITS LIST LOAD MOVE NEXT ON OR( PACK( PRINT READ REM RENUMBER...`
  - Wang VP: token-prefixed list `9C 06 GOSUB / 9A 06 RETURN / ...`
  - The structures differ (Iskra: parser table; Wang: token
    decompression table), but the shared vocabulary pins the lexical
    layer and both parsers' neighborhoods.
- Iskra error strings sit directly after `READY \r\n`:
  `сбой системы`, `сбой ОЗУ`, `сбой УП` (KOI-8), self-test
  reporting, meaning the self-test routines (RAM test, УП test) are
  adjacent and are ideal first alignment targets: memory tests are
  short, idiomatic loops whose semantics are unambiguous.
- Numeric runtime anchors still to locate: the 8-byte BCD float
  constant tables (powers of ten) that both interpreters must
  contain in identical numeric form.

### Firmware recovered in clean form

The 250 KB boot image carries the same 32-byte header four times over,
at a stride of 498 sectors, 63,744 bytes apart. For three weeks I read
that as redundancy against media errors and voted the four copies
together. It is not redundancy. The four slots hold four different
builds, years apart, and voting them returns a version that never
existed. `emulator/firmware_extract.py` takes the slots apart instead,
and eight distinct builds survive across the three boot sides, 1981 to
1986, each byte-identical wherever it repeats:

| File | Content |
|---|---|
| `basic01_151281.bin`, `basic01_120782.bin`, `basic01_271282.bin` | BASIC 01, a different program with its own entry vector `AD43` |
| `basicpl5_300984.bin` | BASIC PL5, 30.09.84 |
| `basic02_161283.bin`, `basic02_220484.bin`, `basic02_101084.bin`, `basic02_100986.bin` | the BASIC 02 family |

Each build is 63,744 bytes; BASIC 02 22.04.84 is 31,872 words, exactly
two УП pages. Nothing had to be corrected and nothing had to be
guessed, which is what the vote never gave me.

The loader story is simple: read one 498-sector slot, verify, fall back
to the next slot on a parity error, which is exactly what the ROM
loader's сбой УП message implies. УП population is two 16K-word pages.
Whether the interpreter overlays code into them while running is not
settled by the slots and stays open here.

## Work plan to READY

1. **Idiom mining on the self-test** (no Wang needed): disassemble
   the code around the сбой strings; a RAM test is
   write-pattern/read/compare/branch in a tight loop, this pins the
   store, load, compare and conditional-branch encodings, i.e. the
   most frequent unknown classes (0x1-0x7 blocks).
2. **BCD anchor alignment**: find the power-of-ten tables in both
   firmwares; the surrounding add/shift/decimal-adjust code gives
   the arithmetic core encodings against `Cpu2200vp.cpp` semantics.
3. **Keyword dispatch**: from the keyword table, follow the parser's
   dispatch into per-statement handlers; PRINT and LET handlers in
   both systems provide long parallel instruction runs for bulk
   opcode confirmation.
4. **Close the loop in the emulator**: every newly pinned opcode
   moves words from "class known"/"unknown" into "executable" in
   `iskra226_emu.py`'s coverage map (currently 13.5 / 28.3 / 58.2%).
   Boot is reached when the path from the entry CALL (`87C0` ->
   0x07C0) through self-test to the READY print loop is fully
   executable; the READY string's known address (0x2158 in the disk,
   word offset in УП page 0) provides the success criterion.
5. **Peripherals minimum**: КУ transactions for keyboard-in and
   display-out (the DEV gateway is already implemented); the БОСГИ
   character generator matrix is preserved as a photographed page in
   *Technical Information* p.9 for faithful glyph rendering.

## Deliverables in this directory

- `firmware/`, the eight interpreter builds, 1981 to 1986, one file
  per build (worldwide, these exist only as the 2016 Wayback
  snapshot; mirror them)
- `iskra226_emu.py`, emulator (loader/decoder/interpreter/coverage)
- `iskra.py`, disk toolkit
- `isa-findings.md`, reconstructed architecture
- `run-report.md`, first-run report
- `vp-boot-2.4.wvd`, `Cpu2200vp.cpp`, `dasm_vp.cpp`, the Wang side
  of the alignment (from WangEmu 3.0, Jim Battle)
