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

## Addendum 2 (session of 2026-08-05, cont.)

Code/data separation via a KOI-8/ASCII text mask marks 35.1% of the
firmware as data (strings, tables). Class statistics over code-only
words show classes 0-B and D with clean 4-bit register fields
(field value 15 at 0.2-8%), class C with one special-value field,
and classes E/F with genuinely F-heavy fields, the E block carries
mode bits, so the earlier 4+4+4 sub-division is retired. The decoder
now trusts only the three book-attested sub-blocks (E0/E5/E8 with
register operands) and disassembles the rest.

Cold-start path so far: vector `9006` -> 0x1006; three `E501`
(indirect ОП reads, executable); halt at `E3F7` (E3 sub-op, mode
fields open). Two competing hypotheses for E3xx-with-F: inline
immediate consuming the following word, or a single-word mode
variant; deciding between them is the first task of the next
session, the wrong one desynchronises the instruction stream
within two words, which is itself a usable test.

## Addendum 3: instruction length settled; cold-start listing

Recursive-descent exploration from the boot vectors under three
length hypotheses is decisive: with **every instruction one word**,
18,581 words are reached with **zero** operand/instruction conflicts;
any rule that lets E-words with field 15 consume a following word
produces 39 conflicts. The ISA is fixed-length, one 16-bit word per
instruction, including the E3xF "inline constant" form, whose
constant block must therefore be addressed (RS-indexed) rather than
consumed by PC.

The cold-start sequence (0x1006 ff.) is now a stable listing. Two
observations for the next session:
- F-class words appear with small second-byte operands
  (F000/F100/FB00/FA00, F002/F003, F03B/F03C/F03D, F80F) -
  the signature of an op+imm8 format, plausibly device/system
  commands or byte immediates; likely home of part of the
  49 ALU set and the КУ interface.
- D-class shows the same shape (D591/D6F1/DD02/DE00) with a
  near-perfect register field elsewhere (0.2% F), probably
  reg+imm8 forms.
Cracking F- and D-class semantics via the self-test path (the code
that ends in the сбой ОЗУ / сбой УП messages) is the next work item.

## Addendum 4: first semantic hypotheses from idiom analysis

Evidence collected from the cold-start control-flow graph
(18,504 reachable words) and repeated-idiom mining:

1. **`E501` is used as NOP/delay.** It occurs in runs of four or
   more identical words 34 times across the firmware (also E102,
   E502 runs). No real code re-reads the same operand four times in
   a row; these runs are padding/timing. Explains the three E501 at
   the cold-start entry.
2. **First identified I/O wait loop** at 01B7: call 03B3 / DEV read
   RB12->RR3 / ARI.3 test imm 5 / conditional exit B->3D78 /
   loop 8->01B7. A device-status poll (keyboard or floppy).
3. **A shared wait-then-read idiom** appears verbatim twice
   (0x6A5, 0x7EA): `D912 F51F D6F0 2402 D914 <branch-back> DD12`.
   Reading: poll (D912) - mask (F51F) - test - poll again - on
   ready fall through to the data access `DD12` on the same
   low byte 0x12. Suggests **D-class = port/system I/O, op nibble +
   port imm8** (D9=status?, DD=data?).
4. **F-class = RS-op-imm8 ALU forms.** The book states arithmetic
   works "between RS and constants held in the instruction itself";
   the imm4 form is class 0 (007E documented), the imm8 form fits
   F-class exactly (F51F = AND #1F in the mask position of the
   idiom). This is where most of the 49 ALU instructions live.
5. Jump-type usage: 8-type closes backward polls (conditional),
   B-type exits forward (conditional, other sense/flag), A
   unconditional (book), 9 opens the boot vector (call-like).

Next session: encode hypotheses 3-5 as executable trial semantics,
run the cold start, and let coherence (the path must reach the
message-table printer at word 10AC, READY) confirm or kill them.

## Addendum 5: message table and print routine located

The system message table sits at word 0x10AE (byte 0x2158), entries
separated by `:\x00`, KOI-8:
`READY` / `СБОЙ СИСТЕМЫ` (system fault) / `СБОЙ ОЗУ` (RAM fault) /
`СБОЙ УП` (control-store fault) / `СБОЙ МО` / `ERR 01` / `ERR 02` ...

All six references to that region are jumps to word **0x00C3**, the
central **string-print routine** (very low address = core service,
consistent with the ROM-resident console driver). Call sites share a
prologue: a `DD..`/`ED..` word (message-pointer setup, D/E class as
predicted in Addendum 4) then `F7F4` or `F0xx` then `90C3` (jump to
printer). Example: `DD41 E520 F7F4 90C3` and `DD41 ED27 F7F4 90C3`
both print the message selected by pointer byte 0x41.

This nails three things for the next session:
- **0x00C3 = putstring**; emulating just this routine plus its DEV
  writes to the display gives on-screen output.
- **DDxx loads a message/table pointer** (D-class confirmed as
  pointer/port ops).
- The success path is now concrete: reach any `90C3` with a valid
  pointer and the emulator prints a real Iskra message. The self-test
  either prints `READY`-adjacent success or a `СБОЙ` fault, both are
  authentic boot output.

Remaining to run it: implement the ~20-instruction putstring loop at
00C3 (needs D-class pointer load, F-class compare/AND, one
conditional branch, and the DEV display write), then drive the
self-test path into it.

## Addendum 6: putstring is a call tree; selector convention spotted

Annotating 0x00C3 shows putstring is not a leaf loop: it immediately
fans out into service calls (`8E01`->0x0E01, `9328`->0x1328 twice,
plus 0x0678, 0x019A, 0x26C3), a console driver built on putchar/
cursor subroutines. Executing it therefore requires the call/return
mechanism of the J8/J9 transfer types plus the F-class ALU ops; both
remain the open core.

New evidence from the call sites: the F-word before each `90C3`
varies per site (`F7F4`, `F06B`, `F042`, `F7F4`) while `DD41`
repeats, the **imm8 of that F-word is the message selector
candidate** (not a byte offset into the table; ID-to-pointer mapping
still unknown).

Honest status of the attempted test run: execution reaches 0x00C3's
first instruction and stops, output requires the two unknowns
above. No screen output was produced and none is claimed.

The two questions that unlock the boot screen, precisely:
1. J8/J9 semantics incl. return (where is the return address kept -
   RR14? a ОП stack via РБ14 as the book says for the *machine* level?)
2. F-class op nibble map (AND/CMP/ADD/... per F0..FF).
Both are answerable from the Wang-VP alignment (`Cpu2200vp.cpp`
implements the exact same console architecture) or from any surviving
процессор ТО. Everything else on the path is already in hand.

## Addendum 7: transfer-type model narrowed by coherence search

Brute-force coherence testing over call/return hypotheses (fitness:
stack balance, no hot loops, address coverage) yields a consistent
model:
- **J9 = call** (supported: the cold-start vector is 9006; runs with
  9-as-call behave sanely until switch tables, see below);
- **J8 and JB = conditional branches** (8-as-pure-conditional runs
  20,000 steps / 284 distinct addresses without crashing under an
  alternating-branch policy);
- **JA = unconditional** (book).
The single failure mode of the 9-as-call model is instructive: it
overflows at 0x13C6, inside the loop 13BE..13C6, whose body words
13C1..13C4 hold the values 13C5/13C7/1444/13C9, **addresses near
themselves**. This is an inline address table: the book's
"switch on РС" computed-goto, with the constant block following the
instruction exactly as documented for table commands. Class-1 words
are (at least partly) inline address constants, not instructions -
resolving their earlier anomalous profile.

Consequence: the executor needs table-aware stepping (an ED/E3
dispatch instruction that indexes the following address block and
jumps), and the return mechanism is the last control-flow unknown.
The Cx02 epilogue candidate (CD02/CE01 at putstring's tail) remains
the prime suspect for return/restore.

## Addendum 8: computed-goto decoded; transfer model stabilised

The 0x13C6 bottleneck is fully explained. The sequence is a
**computed-goto**:
```
13C0  F203         dispatch, 3-entry table follows
13C1  13C5 \
13C2  13C7  |      inline address table (targets near self)
13C3  1444  |
13C4  13C9 /
13C5  5229         (entry 0 body)
13C6  93BE         loop back (conditional)
```
So `F2xx` = table dispatch, imm8 = entry count; the executor must
skip the following imm8 words. With that rule plus "J9-forward =
call, J9-backward = conditional loop, J8/JB = conditional, JA =
unconditional, Cx02 = return", the cold start now runs **36,401
instructions over 413 distinct addresses** with a balanced stack
(depth 8 at the stop) before hitting an unrelated hot loop at 0x2A24
- two orders of magnitude past every earlier attempt.

This is the deepest coherent execution achieved. The remaining
crash at 2A24 is an ordinary ALU-semantics gap (a loop whose exit
test is an unimplemented F/D compare), not a control-flow unknown.
Control flow is now essentially solved; what stands between here and
on-screen output is the arithmetic core (the F/D compare + counter
ops that terminate delay/test loops), reachable by the same
coherence method one loop at a time.

## Addendum 9: limit of control-flow-only execution reached

With loop-escape (forcing untaken conditionals in hot loops) and
stack-unwind escapes for device wait routines, the explorer runs
3,000,000 steps and maps **782 distinct addresses** of boot-path
skeleton (55 wait-routine returns, stack never corrupted). It does
not organically reach putstring (0x00C3) or any message call site.

The reason is now precise: the paths to the console layer run
through **data-dependent E-class dispatches** (EDxx pointer
indirection through RB registers). Control flow alone cannot pick
the right table entries when every register is zero. This is the
genuine boundary of the coherence method: everything decidable from
structure has been decided (byte order, vectors, one-word ISA,
transfer types, computed-goto, return, dispatch skip, NOP idioms,
wait loops); the residue, E/D/F data semantics, is exactly the
part that requires an external oracle: the Wang-VP alignment of the
console call trees, or the processor's техническое описание.

State of the port: 36,401 coherent instructions from cold start
under the stabilised model; 782-address boot skeleton mapped;
console entry, message table, and success criterion located and
verified. The machine is one document (or one focused alignment
effort) away from printing its first word in forty years.

## Addendum 10: correction, putstring/message-pointer thread retracted

A constraint check invalidated the Addendum 5-6 identification.
Counting real references: exactly **one** word jumps to 0x00C3
(from 0x404F), not six; and **no word in the firmware holds the
message-table address 0x10AE**. A routine that printed the message
table would have to load that pointer somewhere, it never does.
Therefore 0x00C3 is not the message printer, the "six call sites"
were an artefact of an over-broad earlier scan, and the
DD41-as-selector / scaling analysis was built on a false premise
(which is why no linear selector->offset map hit the real entry
boundaries). Retracted.

What the same constraints established positively:
- **DEV (E8xx) instructions are rare and localised: only 10 in the
  whole interpreter.** Their most common target base register is
  RB12 (4 of 10), at words 0x00CA, 0x01B8, 0x0358, 0x0368, 0x036C,
  0x046A, 0x055B, 0x063B, 0x128E, 0x1652.
- The device-poll loop at 0x01B7 (found in Addendum 4) uses
  `E8C3` = DEV via RB12, a genuine port access to that same port.
So the real output path runs through these ten DEV writes, not the
message table. Next: read each DEV-via-RB12 site in context and find
the one whose data comes from a character register loaded from a
string, that is the display port.

## Addendum 11: ML framing corrected, layer mismatch; behavioural path defined

Format check on the Wang side is decisive: `Cpu2200vp.cpp` decodes a
**24-bit** microword (`uop &= 0x00FFFFFF`; immediate split across
bits [23:14]+[7:4]; 10-bit page-branch targets). The Iskra stream is
**16-bit macro-instructions**. They implement the same BASIC-2 but at
different machine layers, VP horizontal microcode vs. Iskra
byte-code interpreter. Therefore field-by-field opcode alignment
against the VP microcode is invalid (right language, wrong layer);
the 0.92 keyword-Jaccard lives in the shared BASIC token data, not in
the encodings. The "parallel corpus at the instruction level" framing
is retracted.

The identifiable ML formulation that survives is **behavioural
supervision**, not encoding transfer:
- Oracle = observable BASIC-2 I/O behaviour (bytes emitted for given
  input), which the VP emulator can generate on demand. This is
  layer-independent and well-defined (no loss-function ambiguity).
- Search = the same coherence method that solved control flow, with a
  behavioural fitness: candidate data-op semantics are scored by
  whether loops terminate, string walks stay in KOI-8 text, and the
  RB12 console writes emit byte sequences that match the known
  message strings.
- Prior = the shared token tables and the localised console kernel
  (0x00C0-0x00D2) narrow the search to a few instruction classes.

Concrete data captured toward this:
- Console kernel uses D-class words with a recurring `#93`
  (also #C3, #12), but `#93` occurs 82x firmware-wide as a D-imm8,
  and the top D-imm8 values (#71 116x, #11 114x, #41 93x) look like a
  **port/pointer address space**, not characters. So D-imm8 is an
  operand address, consistent with the Rosetta poll-then-access idiom
  on port #12. The console DEV writes target RB12 (4 of 10 DEV ops).
- This means putchar reads the character indirectly (via a D-class
  pointer op) and writes it through the RB12 DEV gateway; decoding it
  needs the D-class addressing semantics, which behavioural search
  can pin because a wrong choice fails to emit valid KOI-8.

Status unchanged at the boundary: control flow fully solved; data
semantics require either behavioural supervision (a real build, not a
sandbox step) or the processor's техническое описание. No encoding
oracle exists at the Iskra's layer among the files in hand.

## Addendum 12: the keyword/descriptor table, located, decoded, and two hypotheses falsified

Working on `firmware/basic02_220484.bin` (word addresses = byte/2 from
file start; word 0 is the cold-start vector `9006`).

### The table

At **word 0x0B66** the interpreter holds two pointers, `0x19B6`
(permutation array) and `0x1840` (keyword list), both byte offsets,
matching the independent format analysis of the BASIC 02 on-disk
encoding. Immediately after, at **word 0x0B67**, follows a table of
**86 pairs** `[keyword byte-offset][16-bit value]`, ordered exactly
like the alphabetical keyword list. 51 pairs cover the primary
keywords; the remaining 35 point into the compound-keyword region at
0x192F (RESTORE, PRINTUSING, DATALOAD DC …).

### What the second column is NOT (two pre-registered tests, both negative)

**Test 1, handler addresses with a constant load offset.** Criteria
fixed before running: a single offset Δ must place ≥80 % of the 86
targets in reachable non-text code, and beat the runner-up by ≥0.15.
Result: best score 0.721 across three Δ values tied at the same
score, i.e. no unique winner and no signal, 62 % of the image is
reachable code anyway, so any plausible Δ scores ~0.7. **Rejected.**

**Test 2, handler addresses at Δ = 0.** Of the 51 primary values,
40 land on non-text words (random expectation 0.661; observed 0.784 -
not significant). Decisively: **only 1 of 51 values is an actual jump
target anywhere in the firmware.** Handler addresses would be jumped
to. **Rejected.**

### What the second column is

Keywords sharing a value share a *syntax*, not an implementation:

- `0x01DF`, `END`, `RETURN`, `TRACE` (no arguments)
- `0x0532`, `GOSUB`, `GOTO` (one line number)
- `0x08BD`, `AND(`, `OR(`, `XOR(` (identical function syntax)

The column is therefore a **syntax/argument-class descriptor** used by
the tokenizer-parser, not a code pointer. This also explains why no
address interpretation could ever fit. Locating the actual statement
handlers remains open; they are presumably reached through a third
structure indexed by the token byte from the permutation array.

### Full primary table


## Addendum 12: the keyword/descriptor table, located, decoded, and two hypotheses falsified

Working on `firmware/basic02_220484.bin` (word addresses = byte/2 from
file start; word 0 is the cold-start vector `9006`).

### The table

At **word 0x0B66** the interpreter holds two pointers, `0x19B6`
(permutation array) and `0x1840` (keyword list), both byte offsets,
matching the independent format analysis of the BASIC 02 on-disk
encoding. Immediately after, at **word 0x0B67**, follows a table of
**86 pairs** `[keyword byte-offset][16-bit value]`, ordered exactly
like the alphabetical keyword list. 51 pairs cover the primary
keywords; the remaining 35 point into the compound-keyword region at
0x192F (RESTORE, PRINTUSING, DATALOAD DC ...).

### What the second column is NOT (two pre-registered tests, both negative)

**Test 1 - handler addresses with a constant load offset.** Criteria
fixed before running: a single offset must place >=80% of the 86
targets in reachable non-text code, and beat the runner-up by >=0.15.
Result: best score 0.721 across three offsets tied at the same score,
i.e. no unique winner and no signal - 62% of the image is reachable
code anyway, so any plausible offset scores ~0.7. **Rejected.**

**Test 2 - handler addresses at offset 0.** Of the 51 primary values,
40 land on non-text words (random expectation 0.661; observed 0.784 -
not significant). Decisively: **only 1 of 51 values is an actual jump
target anywhere in the firmware.** Handler addresses would be jumped
to. **Rejected.**

### What the second column is

Keywords sharing a value share a *syntax*, not an implementation:

- `0x01DF` - `END`, `RETURN`, `TRACE` (no arguments)
- `0x0532` - `GOSUB`, `GOTO` (one line number)
- `0x08BD` - `AND(`, `OR(`, `XOR(` (identical function syntax)

The column is therefore a **syntax/argument-class descriptor** used by
the tokenizer-parser, not a code pointer. This also explains why no
address interpretation could ever fit. Locating the actual statement
handlers remains open; they are presumably reached through a third
structure indexed by the token byte from the permutation array.

### Full primary table

| keyword | kw offset | descriptor |
|---|---|---|
| `ADD` | 0x1840 | 0x090B |
| `AND(` | 0x1843 | 0x08BD |
| `BACKSPACE` | 0x1847 | 0x09E2 |
| `BIN(` | 0x1850 | 0x08F2 |
| `BOOL` | 0x1854 | 0x0903 |
| `CLEAR` | 0x1858 | 0x069C |
| `COM` | 0x185D | 0x054F |
| `CONVERT` | 0x1860 | 0x0561 |
| `COPY` | 0x1867 | 0x0BCD |
| `DATA` | 0x186B | 0x0932 |
| `DBACKSPACE` | 0x186F | 0x0A76 |
| `DEFFN` | 0x1879 | 0x0675 |
| `DIM` | 0x187E | 0x0553 |
| `DSKIP` | 0x1881 | 0x0A8A |
| `END` | 0x1886 | 0x01DF |
| `FOR` | 0x1889 | 0x0640 |
| `GOSUB` | 0x188C | 0x0532 |
| `GOTO` | 0x1891 | 0x0532 |
| `HEXPRINT` | 0x1895 | 0x047C |
| `IF` | 0x189D | 0x05DB |
| `INIT` | 0x189F | 0x017B |
| `INPUT` | 0x18A3 | 0x084F |
| `KEYIN` | 0x18A8 | 0x09F3 |
| `LET` | 0x18AD | 0x05A0 |
| `LIMITS` | 0x18B0 | 0x0C1C |
| `LIST` | 0x18B6 | 0x0763 |
| `LOAD` | 0x18BA | 0x0978 |
| `MOVE` | 0x18BE | 0x0B1F |
| `NEXT` | 0x18C2 | 0x0658 |
| `ON` | 0x18C6 | 0x073F |
| `OR(` | 0x18C8 | 0x08BD |
| `PACK(` | 0x18CB | 0x091C |
| `PRINT` | 0x18D0 | 0x043C |
| `READ` | 0x18D5 | 0x06AD |
| `REM` | 0x18D9 | 0x06AB |
| `RENUMBER` | 0x18DC | 0x06BD |
| `RES` | 0x18E4 | 0x06B3 |
| `RETURN` | 0x18E7 | 0x01DF |
| `REWIND` | 0x18ED | 0x06B9 |
| `ROTATE` | 0x18F3 | 0x0C3E |
| `RUN` | 0x18F9 | 0x010E |
| `SAVE` | 0x18FC | 0x09A5 |
| `SCRATCH` | 0x1900 | 0x0B95 |
| `SELECT` | 0x1907 | 0x06DE |
| `SKIP` | 0x190D | 0x09CA |
| `STOP` | 0x1911 | 0x0735 |
| `TRACE` | 0x1915 | 0x01DF |
| `UNPACK(` | 0x191A | 0x0927 |
| `VERIFY` | 0x1921 | 0x0BB4 |
| `XOR(` | 0x1927 | 0x08BD |
| `$GIO` | 0x192B | 0x09FD |

Descriptor groups (>1 keyword):

- `0x01DF`, `END`, `RETURN`, `TRACE`
- `0x0532`, `GOSUB`, `GOTO`
- `0x08BD`, `AND(`, `OR(`, `XOR(`

Secondary-region entries: 35 (kw offsets 0x192F–0x19B6, i.e. the compound-keyword table at 0x192F)

## Addendum 13: message pointer table found, Addendum 10 partially retracted

Addendum 10 concluded that no word in the firmware holds the address
of the message table, and retracted the message-printer thread on that
basis. **That conclusion was wrong**, because the search used *word*
addresses. The book's description of `E865` states the address is
`(RB >> 1) + RS` with the byte half chosen by bit 1 of RB, i.e.
pointers are **byte addresses**. Searching for byte addresses finds
the table immediately.

At words **0x107D** and **0x108D–0x1094** the firmware holds a message
pointer table:

| word | value (byte addr) | message |
|---|---|---|
| 0x107D | 0x2158 | `READY` |
| 0x108D | 0x2160 | (table+8) |
| 0x108E | 0x2162 | `СБОЙ СИСТЕМЫ` |
| 0x108F | 0x2172 | `СБОЙ ОЗУ` |
| 0x1090 | 0x217E | `СБОЙ УП` |
| 0x1091 | 0x2188 | `СБОЙ МО` |
| 0x1093 | 0x2192 | `ERR 01` |
| 0x1094 | 0x219C | `ERR 02` |

The offsets (8, 10, 26, 38, 48, 58, 68 from table start 0x2158) match
the independently measured entry boundaries of the message table
exactly. Further pointers into the same region occur at words 0x1087,
0x13B2, 0x1459, 0x2B8C, 0x3336–0x333C, 0x468D.

**Consequence for the ISA.** `DEV` (E8 sub-op) with bit 16 of the base
register clear is not a device write but a **byte load from control
memory**: `RR := byte at byte-address RB, word-indexed by RS`. That is
exactly the character-fetch primitive a string printer needs. So
`E8C3` inside the loop at 0x01B7 is most likely *fetching* characters
via RB12 as a byte pointer, and the console output path is the
bit-16-set branch of the same instruction, not a separate port.

This also restores the plausibility of a message-printing routine and
gives the first fully known-value anchor for testing data-operation
semantics: pointer table, target strings, and addressing rule are all
established independently of any hypothesis.

## Addendum 14: first data-operation semantics verified

`iskra226_emu.py messages firmware/basic02_220484.bin` now produces:

```
ptr @107D -> 'READY '
ptr @108E -> 'СБОЙ СИСТЕМЫ'
ptr @108F -> 'СБОЙ ОЗУ'
ptr @1090 -> 'СБОЙ УП'
ptr @1091 -> 'СБОЙ МО'
ptr @1093 -> 'ERR 01'
ptr @1094 -> 'ERR 02'
```

These characters are not printed from a decoded table: each byte is
fetched through the machine's own addressing rule, from the pointer
values the firmware itself holds. **Verified semantics:**

- `DEV rb,rr` with bit 16 of RB clear = **byte load from control
  memory**: `RR := byte at ((RB >> 1) + RS)`, half chosen by bit 1 of
  RB, i.e. RB is a plain byte address into УП.
- Strings are walked by incrementing the byte pointer by 1 per
  character (verified: the RS-as-counter variant yields garbage,
  the RB-increment variant yields exact text).
- Message entries terminate on `0x00` or `':'`.

Seven independent pointers, seven exact matches, no exceptions. This
is the first *data*-operation semantics established in this project;
everything before it was control flow or structure.

**Honest limits.** The state is forced, not reached from cold start:
the pointer is taken from the firmware's table and handed to the
routine. The **output channel**, the bit-16-set branch of the same
instruction, which hands the byte to the display, is still
unverified, as is the arithmetic of the surrounding loop (class-0
sub-ops other than the documented 0). So this reads the machine's
messages correctly but does not yet print them the way the machine
would. Two instructions, not a whole ISA, now stand between the
emulator and genuine console output.

## Addendum 15: the three layers, documented, where the missing semantics live

Two more leads checked; both close the same way, and together they
pin the one remaining gap precisely.

**Wang 2200-T variant (ucode_2200T.cpp).** Jim Battle's Iskra page
states the interpreter is T-BASIC (the Wang 2200-**T** dialect), so
the T micromachine was checked as a better reference than VP. It is
not: the T microword is ~20-bit horizontal microcode
(`opcode1 = (uop>>15)&0x1F`, mini-op at bit 10, FETCH_A/FETCH_B
register-load bits), the same *kind* of object as VP, just narrower.
Both Wang models emulate the Wang bit-slice **microcode** layer.
The Iskra runs 16-bit **macro**-instructions. Opcode-level alignment
to either Wang model is therefore impossible for the same reason as
in addendum 11, right language, wrong layer.

**K589 / Intel 3000 family (datasheet obtained).** The Iskra CPU is
built from K589 bit-slices = Intel 3001 MCU + 3002 CPE clones. The
3001 datasheet (now in docs/) documents that layer fully: a pure
microcode **sequencer** with a 9-bit address organised as a 32x16
matrix (512 microinstructions), eleven jump functions (JCC, JZR,
JCR, JCE, JFL, JCF, JZF, JPR, JLL, JRL, JPX), C/Z flags, exact bit
encodings in its Appendix A. Crucially the datasheet states plainly
that "the microprogram interprets a higher level of instructions
called macroinstructions", i.e. the 3001/3002 chips are the
*machinery* on which an engineer implements a macro-ISA via
self-written microcode. They do not define the 67 Iskra macro
instructions.

**The layer map, now fully documented:**

```
K589 bit-slices (3001 MCU + 3002 CPE)   <- semantics in datasheets (have)
        |  microcode in the Iskra's own ПМК/ПЗУ
        v
Iskra 67-instruction 16-bit macro ISA   <- control flow solved; data ops open
        |  the BASIC interpreter, as macro-code on disk
        v
BASIC 02 tokenized program format       <- fully solved; runs in iskra_run.py
```

The **only** missing piece is the middle arrow: the Iskra's own ПМК
microcode (2K words) plus the ПЗУ, which is what turns K589
slices into the 67-instruction ISA. No Wang model and no K589
datasheet contains it, it is specific to the Iskra's ROMs. This is
why the data-operation semantics could not be derived from the
firmware binary, from statistics, or from either related machine:
the information physically resides in ROM chips we do not have a dump
of.

How large that ПЗУ is, the sources do not agree on: 8 KB in the
ru.wikipedia and computer-museum.ru descriptions, 16 Кбайт in the
Balasanian manual mirrored under `docs/`, and 24 KB in the 1989
Grubov/Kirdan/Kozubovsky ЭВМ handbook. The machine shipped in seven
configurations, so the three figures need not contradict each other,
but nothing available to me decides between them. No single one of
them is quoted anywhere in this file as if it were the number.

**What the datasheets buy us anyway:** when a ПМК/ПЗУ dump is
obtained from surviving hardware, it is now *readable*, the 3001
datasheet gives the microword addressing (32x16 matrix, 9-bit,
eleven jump functions, C/Z), and the 3002 datasheet the ALU/register
semantics (R0-R9, T, accumulator, MAR, matching the reconstructed
РБ/РР/РС/segment/stack registers). The disassembly path for a future
dump is therefore already specified.

**Verified positive result this project still stands on** (addendum
14): `DEV` with bit 16 clear = byte load from control memory, proven
against all seven message-pointer entries. That is one macro
instruction genuinely recovered; the rest await the ROM dump.

This is the honest endpoint of what is reachable from the available
material and the public record. The remaining step is physical: a
ПМК/ПЗУ dump from a surviving Iskra-226, small and dumpable at
any of the three sizes the sources give, or the processor's
техническое описание, sought via zx-pk.ru (threads 9276, 16298) and
phantom.sannata.org. The path from such a dump to a booting emulator
is now fully specified end to end.

## Addendum 16: BASIC 02 format, three corrections and a verified computation

Interpreter iteration against the STIPENDIYA suite established, with
corpus evidence:

- **`E1` is the STR() substring atom, not positioning** (retracting
  the tab-to-column reading given one addendum earlier). Forms:
  `E1 <slot> (pos,len)` and `E1 <arr> <idx> D0 (pos,len)`, usable as
  value AND as assignment target. Proof: the routine at lines
  4000-4197 ("ПОДПРОГРАММА ПОДАВЛЕНИЯ ВЕДУЩИХ НУЛЕЙ") compares
  `STR(A(i),k,1)` against "0"/"." and assigns " " through it -
  unambiguous substring semantics.
- **Standalone GOTO/GOSUB carry raw BCD targets** (`21 02 40 06` =
  GOTO 4006), unlike IF-embedded branches which use the D3 marker.
- **Operators 2A/2B/2D/2F are context-sensitive**: operator only
  after an operand, otherwise variable slots; the array pattern
  `<slot><idx>D0` takes precedence. (DIM lists and REM text had
  produced false "formula" hits.)
- Also decoded: `E7 <bcd><bcd>` = line-number reference; token `3F`
  = % image line; token-28 statement with an E7 reference = formatted
  print through the image (PRINTUSING semantics).

**Verified computation:** seeding the ten payroll columns with
zero-padded amounts and executing the original suppression routine
(4001-4197) yields 10/10 correct results, including the deliberate
edge case that a zero immediately before the decimal point is kept
("0000.75" -> "   0.75"). First full run of original computational
logic, field-verified.
