# Iskra-226 Emulator: First Run Report

Date: 2026-08-05. Emulator: `iskra226_emu.py`. Target image:
`disk1side1.dsk` (BASIC 02, build 22.04.84), 128,112 words.

## What happened

The emulator loads the boot image into the four УП pages, starts at
word 0x10 (first word after header, signature and keyboard test
pattern) and executes.

Entry sequence: `87C0`, a control-transfer word (class 0x8,
"unconditional with return-address save" per the documented list of
six transfer types, i.e. a CALL) targeting page address 0x07C0.
Executing it under the CALL hypothesis lands on `62DD`, a class-0x6
word whose semantics are undocumented. Execution halts there with a
precise trap, one instruction deep.

This is the expected honest result: the interpreter's first act is a
call into the arithmetic-heavy runtime, and the 49 arithmetic/logic
instructions are exactly the part of the ISA the surviving overview
documentation does not enumerate.

## Decode coverage of the full image

| Category | Share | Meaning |
|---|---|---|
| executable now (documented semantics) | 13.5% | ADDI, JMP, TBL, MEMW, DEV |
| class known, semantics open | 28.3% | ARI sub-ops, transfer variants 8/9/B |
| unknown class | 58.2% | high nibbles 1-7, C, D, F |

By family: W_1..7 and W_F blocks 37.9%+12.0% (almost certainly the
bulk of the 49 arithmetic/logic instructions in register-register
and direct-memory forms), ARI (0x0 imm forms) 15.8%, transfers
12.5%+4.6%, table/device/memory 2.9%.

## What blocks a full boot

A single missing artefact: the encoding table of the 49
arithmetic/logic instructions (and the exact sub-coding of the
transfer and 0xE blocks). With ~42% of the stream in those classes,
every execution path traps within a few instructions.

## Where that table most plausibly survives

1. **ISKRA-226 Technical Information** (wang2200.org, 48 pp.) -
   hand-drawn diagrams and tables, OCR-resistant; needs page-by-page
   visual reading. Highest-probability source.
2. The 264-page print edition of Balasanian 1987 (appendices; the
   digital set under `docs/` is 171 pages of it).
3. The device documentation scans discussed on zx-pk.ru (threads
   9276, 16298), and the technical descriptions that go with the
   two complete machines those threads report, one in Almaty and
   one in Rostov. Those would settle everything, including the
   ПМК microcode. What matters here is the machines and their
   paperwork, not who keeps them; the holders are private people
   and are not named.
4. Cross-checking against the Wang 2200VP instruction list at
   wang2200.org: the Iskra ISA is an independent 16-bit design, but
   the *functional* inventory (what 49 ALU ops an interpreter of
   this family needs) should map one-to-one and constrains the
   search.

## Files

- `iskra226_emu.py`, emulator/disassembler/coverage mapper
- `isa-findings.md`, reconstructed architecture reference
- `iskra.py`, disk/catalog/extraction toolkit
