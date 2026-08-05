# Iskra-226 CPU: Reconstructed Instruction Set Architecture

Status: 2026-08-05. Sources: Aladiev/Martynenko/Shilenko, *Personal
Computer Iskra-226: Architecture and Software* (Kiev: Main Editorial
Board of the Ukrainian Soviet Encyclopedia, 1988, 152 pp., ISBN
5-88500-004-2), ch. 1.3-1.5, OCR at 200 dpi; Balasanian et al.,
*Programming the Iskra 226 Microcomputer* (Moscow: Finansy i
Statistika, 1987, 264 pp.); statistical verification against
the six disk images recovered from `oldpc.su/0/880.rar`
(Wayback Machine snapshot 2016-08-04, the only known copy).

## Executive summary

The Iskra-226 boot floppies do **not** contain horizontal microcode.
They contain the BASIC interpreter written in the CPU's own 16-bit
machine language, a custom ISA of **67 base instructions**, which
the ROM loader copies into control memory (УП) at power-on. The true
bit-slice microcode lives in a separate 2K-word store (ПМК) and ships
in ROM together with the loader and an assembler translator.

An emulator therefore targets this 16-bit ISA, the same abstraction
level as Jim Battle's Wang 2200 emulator. No K589/Intel-3000
modelling is required.

## Machine state

Bit numbering per Soviet convention: **bit 1 = LSB, bit 16 = MSB**
(verified: jump `A34C` -> "address in bits 1-14" = 0x3FFF mask =
9036 decimal, matching the book exactly).

Registers:
- `RB0..RB14`, base registers (16-bit). Addressing roles:
  - `RB13`, segment base for direct operand memory (ОП) access
  - `RB14`, pointer to top of the return stack (stack lives in ОП)
  - bit 16 of an RB selects device vs. memory in directed addressing
- `RR0..RR14`, working registers (16-bit), no addressing role
- `RS`, 16-bit accumulator ("summator")
- `RK`, instruction register
- `RP1..RP4`, flag registers, updated after the last operation of
  a two-operation instruction
- ALU: 16-bit

Register fields in instructions are 4 bits, legal values 0-14;
value 15 encodes special variants (verified statistically: the RR
field of class-0 instructions is 0xF in only 1.05% of 26,829 cases
vs. 6.7% random expectation).

## Memory model (УОП, 128 KB total)

| Region | Size | Role |
|---|---|---|
| УП, control memory | up to 64K x 16-bit words, 4 pages of 16K words | interpreter code, loaded from disk |
| ОП, operand memory | up to 32K x 16-bit words, byte/word access | BASIC program + data |
| ПМК, microcode store | up to 2K x 16-bit words | real bit-slice microcode (ROM domain) |
| СВОП | 30 x 16-bit | the RB/RR register file |

Per-byte parity checked in hardware.

## Instruction classes (67 base instructions)

| Class | Count | Encoding (established / hypothesis) |
|---|---|---|
| arithmetic & logic | 49 | high nibble 0x0 (imm form) and others, see below |
| directed device addressing | 4 | within 0xE block (E8-EB hypothesised) |
| indirect ОП access | 4 | within 0xE block (E4-E7 hypothesised) |
| table lookup | 4 | within 0xE block (E0-E3 hypothesised) |
| control transfer | 6 | words 0x8000-0xBFFF carry a 14-bit page address |

Instructions are "two-one-address": one instruction may perform two
operations (e.g. add register, then add immediate).

## Documented instruction examples (all verified against OCR at 200 dpi)

### `007E`, arithmetic, immediate form
"RS + RB7 + constant 14 -> RB7."
Decoded layout: `0 | subop | reg | imm4`. Explains why 21% of the
instruction stream has high nibble 0.

### `E045`, table lookup
Address = RS + RB4 into УП; the 16-bit constant found there is
loaded into RS and then RR5. The constant array may also follow the
instruction inline (this variant plausibly uses field value 0xF,
which appears in 15% of E0-E3 words).

### `E578`, indirect operand-memory access
Address = bits 16-2 of RB7 (word aligned); the word read from ОП is
added to RS and stored to RR8.

### `E865`, directed addressing
Reads RB6, tests its bit 16 (a).
- a = 0: read УП at ((RB6 >> 1) + RS); a one-byte constant goes to
  RR5; bit 1 of RB6 selects low/high byte of the УП word.
- a = 1: transaction with the channel device (КУ); control info from
  RB6, response data flows КУ -> RS -> RR5.
These four instructions are also the gateway "to the microprogram
level" (ПМК access).

### `A34C`, unconditional jump within page
Target = bits 1-14 of the instruction = 0x234C = 9036. Confirms:
jump class = `10xxxxxx xxxxxxxx`, 14-bit in-page address (a page is
exactly 16K words). The six control-transfer instructions are:
unconditional; conditional; unconditional with return-address save;
return; switch via RS; switch on RS state with return-address save.
Sub-type field within bits 15-12 (0x8/9/A/B all occur, each ~5% of
the stream; `A` = unconditional per the book's example).

## Statistical verification (disk1side1, BASIC 02 build 22.04.84)

126,960 words analysed (32-byte header and trailing blank area
excluded):

| Observation | Value | Consistent with |
|---|---|---|
| distinct 16-bit words | 10,138 / 65,536 | machine code, not data |
| high nibble 0x0 | 21.1% | imm-form arithmetic |
| words 0x8000-0xBFFF | 17.2% | jump density of interpreter code |
| class-0 RR field = 0xF | 1.05% | 4-bit register field 0-14 |
| jump sub-types (bits 13-12) | 27/23/27/23 % split | four in-word jump variants |
| `A34C & 0x3FFF` | 9036 | book's worked example, exact |

## Known firmware builds

| Signature | Where found |
|---|---|
| `BASIC PL5 30.09.84` | disk1side0, disk2side0 (identical headers) |
| `BASIC 02  22.04.84` | disk1side1 |
| `BASIC 02  05.10.84` | screen photo in Balasanian 1987 |
| `BASIC 02  10.09.86` | version string inside the BAM application programs |

Disk header layout: 6 magic bytes `06 90 09 90 07 90`, then the
18-char ASCII signature, then the keyboard test pattern
`987654321 0 ABCDE`, then code. The header words are plausibly
themselves class-0 instructions, but the entry protocol of the ROM
loader is not yet established.

## Open items

1. Full opcode map for the 49 arithmetic/logic instructions
   (sub-operation nibble semantics) and the exact sub-coding of the
   0xE and jump blocks. Best leads: remaining Aladiev appendices,
   the 264-page Balasanian print edition, of which the scan under
   `docs/` is the 171-page digital set, the hand-drawn block
   diagrams in *ISKRA-226 Technical Information* (48 pp., needs
   visual reading, OCR fails), and the device documentation scanned
   on zx-pk.ru.
2. ROM loader protocol: load map of the ~250 KB disk contents into
   the 128 KB УП (overlays are certain, the image is bigger than
   the memory), entry address, page selection.
3. КУ (channel device) command set and the 12 ИВВ interface
   commands, needed for peripheral emulation.

## Addendum 2026-08-05 (late): byte order and boot vectors, established

Disk words are **little-endian**. Evidence: jump locality rises from
2.1% to 38.1%, tight backward loops from 4 to 162, and the 6-byte
header decodes as `9006 9009 9007`, a three-entry vector table of
transfer instructions (cold start / warm start / test). Earlier
big-endian field statistics in this file are superseded; the
book-derived opcode facts (007E, E045, E578, E865, A34C) are
ISA-level and unaffected. Emulator updated.

First real execution from the cold-start vector (`9006` -> 0x1006):
three `E501` words, then `E3F7`, the table-lookup instruction in
its field-15 **inline-constant variant**, i.e. almost certainly
load-immediate. Its exact operand-fetch rule is the single next
unknown on the boot path. Under LE the coverage map reads:
27.2% executable / 9.7% class-known / 63.1% unknown, with the
E-block at 23.9% of the stream, the register-register forms of the
49 ALU instructions most likely live there.
