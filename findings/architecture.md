# Iskra-226: processor architecture, and the answer to July

Written 6 August 2026, 01:44.

Sources: Aladjev / Martynenko / Shilenko, "Персональный компьютер
Искра-226. Архитектура и программное обеспечение", chapters 1.3 to 1.6,
from the OCR in `docs/`; Balasanyan and others, "Программирование на
микроЭВМ Искра 226", 1987; and my own analysis of the six disk images.

## The finding

What lies on the boot sides is NOT horizontal microcode, and it is not a
3002 function stream either. It is the BASIC interpreter, written in the
16-bit machine language of the central processor (ЦП): an instruction set
of its own with 67 basic instructions, loaded at power-on into the control
store pages (УП). The actual microcode of the K589 bit slices sits
separately in the ПМК, 2K words, and belongs with the loader and the
assembler translator to the ROM part of the machine.

So option B, from `microcode-or-machine-code.md`. Reading B was right and I
spent July on reading A.

An emulator therefore needs NO bit-slice reconstruction. The target is an
interpreter for the 67-instruction ISA, the same level of abstraction Jim
Battle's Wang 2200 emulator works at.

## Memory model (УОП, 128 KB total)

| Area | Size | Purpose |
|---|---|---|
| УП, control store | up to 64K x 16 bit, 4 pages of 16K words | interpreter code, loaded from disk |
| ОП, working store | up to 32K x 16 bit, byte and word addressable | BASIC program and data |
| ПМК, microinstruction store | up to 2K x 16 bit | the actual microcode |
| СВОП | 30 x 16 bit | register file |

Parity is checked per byte in hardware, "СБОЙ КР" on failure.

## Registers

- РБ0 to РБ14: base registers, for indirect addressing and device
  addressing. РБ13 is the segment base for direct access to ОП, РБ14 is the
  stack pointer of the return stack, which lives in ОП.
- РР0 to РР14: working registers, no addressing function.
- РС: 16-bit accumulator, the "summator".
- РК: instruction register. РП1 to РП4: flag registers. ALU is 16 bit.
- Register fields in instructions are 4 bits wide, valid 0 to 14. The value
  15 encodes special variants, see the verification below.

## Instruction classes, 67 in total

| Class | Count |
|---|---|
| arithmetic and logic | 49 |
| directed addressing of ИДП devices | 4 |
| indirect ОП access | 4 |
| table instructions | 4 |
| transfer of control | 6 |

Instructions are "two-one-address" and 16 bits wide. That matches the word
width the entropy split gave me in July, which is the one thing from that
month that survives.

## Documented example encodings, from Aladjev 1.4

- `E865`, directed addressing: read РБ6, test bit 16 (a). With a=0, access
  УП at (РБ6>>1)+РС, byte constant into РР5, byte selected by bit 1 of РБ6.
  With a=1, access the control unit КУ, control information from РБ6, result
  through РС into РР5.
- `2578`, indirect ОП access: address from bits 16 to 2 of РБ7, the word
  read plus РС into РР8.
- `F045`, table instruction: address РС+РБ4 in УП, 16-bit constant into РС
  and РР5. The constant field may also sit directly behind the instruction,
  the inline variant.
- `A4AC`, unconditional jump within the 16K-word page.

Jumps: unconditional, conditional, unconditional with return address,
return, jump through РС, and jump on РС state with return address.

## Verification against the boot images

`disk1side1.dsk`, BASIC 02 22.04.84, 126,960 words excluding header and
empty space:

- Table instructions `F0xx`: the destination register field, bits 3 to 0, is
  0xF in only 0.58 % of cases, consistent with a register field of 0 to 14
  where chance would give 6.7 %. Bits 7 to 4 are 0xF in 34 % of cases,
  consistent with the documented inline-constant variant as a special value.
- Jumps `Axxx`, 4.6 % of all words: both lower nibbles are freely
  distributed, consistent with an address field rather than register fields.
- Only 10,138 distinct 16-bit words, and 99 % of byte positions sit inside
  repeated sequences. That is a machine code profile, not a microcode one.

This is what the field analysis could never have told me. The structure is
in the encoding table, and encoding tables are read, not inferred.

## Known interpreter builds

Eight, recovered from the slots by `emulator/firmware_extract.py` and
byte-identical wherever they repeat:

    BASIC 01  15.12.81   BASIC 02  16.12.83
    BASIC 01  12.07.82   BASIC 02  22.04.84
    BASIC 01  27.12.82   BASIC 02  10.10.84
    BASIC PL5 30.09.84   BASIC 02  10.09.86

The Balasanyan manual shows a screenshot of a BASIC 02 build dated
05.10.84, which is not among them. So there was at least a ninth.

## Open for the emulator core

1. The complete encoding table for the 67 instructions. Candidates: the
   remaining pages of the Aladjev manual with 1.4 fully OCR'd, the 264-page
   Balasanyan book in its non-OCR form with the appendices, ISKRA-226
   Technical Information at 48 pages with hand-drawn block diagrams that have
   to be read visually, and the device documentation mentioned on zx-pk.ru.
2. Entry state after loading: start address, page selection of the УП.
3. The format of the boot process on disk. 250 KB have to go into 128 KB of
   УП, so presumably overlays plus character set and test programs.
4. The КУ interface and the twelve ИВВ interface commands, for peripheral
   emulation.
