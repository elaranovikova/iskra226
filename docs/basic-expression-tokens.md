# BASIC 02 expression tokens, second pass

The first pass decoded the statement tokens and enough of the
expression layer to run the STIPENDIYA and BAM software: numbers to
9999, strings, the four arithmetic operators, four relations, branch
targets. What it never met, because payroll code never needs it, were
the functions, the power operator, fractional constants and screen
control. The mathematics packages on the 2026 archive are full of all
four, and their formulas are textbook statistics, so the meaning of a
token can be read off the mathematics around it. This file records that
second pass. Everything below is corpus-attested; file:line refers to
the tokenised programs on the w-series disks.

## Functions: consecutive from 0xF2

The firmware's name area at byte 0x1A4D lists the functions in fixed
order: `ABS( INT( RND( SGN( SQR( LOG( EXP( SIN( COS( TAN( ARCSIN(
ARCCOS( ARCTAN(`. The token values run consecutively from 0xF2 in that
order. Call form: `<token> <expression> D0`.

| token | function | proof |
|---|---|---|
| F2 | ABS( | `IF ABS(A0A(I)) >= 1 THEN` clamping a correlation coefficient, STAT01:650 |
| F3 | INT( | `INT(W + 0.50)`, the rounding idiom, WILCOX:1565 |
| F4 | RND( | position in the list only |
| F5 | SGN( | `r = 0.999 * SGN(r)` after the clamp, STAT01:650 |
| F6 | SQR( | `SQR(N)`, `SQR(N-1)`, `SQR(2*(N-1))`, the standard errors, STAT01:510 |
| F7 | LOG( | `S = S + LOG(x) * LOG(x)` in the linearised regression, STAT01:540 |
| F8 | EXP( | next to `2*(3.14)` in a normal density, WILCOX:1194 |

## The power operator: 0xDC

`A03(I) ^ A06(I)` and `X ^ (N-1)` in the polynomial regression
(STAT01:860, STAT01A:550), and `FOR V4E = V3E^2-1 TO ...`
(LVSTAV:1050). Precedence note for implementers: unary minus binds
looser than the power, `-3^X` is `-(3^X)`; the on-disk form folds `-3`
into a negative literal, so the evaluator has to peel the sign back
off. REGION's population collapse runs through exactly this case.

## The general numeric literal: 0xE5

`E5 <ab> <digit nibbles...>` where the first byte is BCD with a =
digits before the point and b = digits after it. The nibbles that
follow are the digits, right-padded with zeros to whole bytes; trailing
all-zero bytes may be dropped, the parser pads. Value =
digits[0:a].digits[a:a+b].

Sixty-plus corpus constants decode under this rule and every one is
plausible: 0.5 (the continuity correction, 18 times), 0.05 and 0.01
(significance levels), 0.999 (the clamp), **1.96 and 2.58 side by side**
(the normal quantiles for 95% and 99%, WILCOX:2055), **3.14** inside
`2*(3.14)*EXP(...)`, **0.301 = log10(2)** (REGRESS:5516), 7.5 and 8000
(digitizer geometry), 150. No decode is absurd, which is the strongest
argument the rule is right.

This retires the earlier "divfn" reading of `E5 <a> <b>` as a two-slot
division, which came from a payroll line whose bytes happen to be valid
BCD. Under the literal rule that line reads `= 0.5`, and the payroll's
other E5 sites become the rates 16.24 and 21.12 and the constant 28.5,
all more sensible than divisions of unset variables. E8 (to 99) and E7
(to 9999) remain the compact integer forms.

## Relations: D4 to D9 consecutive

`D4 >`, `D5 <>`, `D6 <=`, `D7 >=`, `D9 =`, with `CF <` apart. D7 is
proven by the clamp test above; D6 by the firmware's relation-name
order and window checks in the digitizer code. D8 appears relationally
in IF (e.g. `IF N D8 30` before Wilcoxon's normal approximation) and as
ROUND elsewhere; it is treated as >= in relational position and left
open otherwise.

## THEN is GOTO

All 185 IF payloads in the corpus end in `D3 <bcd target>`. `IF..THEN
510` and `IF..GOTO 510` tokenise identically; the word exists only in
listings.

## HEX( is E2 with a length byte

`E2 <n> <n raw bytes>`. Proof: `E2 01 03` clears the screen
(LFORMAT:1530), `E2 01 12` and `E2 01 11` bracket S0's input prompt
(the same attribute codes REGION puts around its warnings), `E2 02 07
0C` rings and clears, and the klerk tools carry seven-byte escape
sequences `E2 07 1B ...`. BAM3:331 assigns a 58-byte HEX string of
pseudographic characters to a variable, so the length byte runs well
past two.

This retires the earlier compact-AT reading of E2 as a fixed two-byte
row/column pair. It survived because S0's `E2 02 03 07` happened to
parse as a plausible pair; the corrected reading clears the screen and
rings the bell there, which is what the menu actually does. The real
AT( remains the D5 full form and the E1 31 atom.

## Assorted, all attested

* `TAB(` with a full expression argument: `DF <expr> D0` (TAB(V17),
  STAT01:60). In operand position DF stays multiplication.
* `STEP` in FOR is `D2`: `FOR V60 = V5F TO 1 STEP -1` is
  `60 5f d1 e8 01 d2 e9 e8 01` (LFORMAT:1400).
* INPUT with a prompt: token 41, the E3 string, then the slot directly.
* Multiple assignment: the targets stand comma-separated in front of
  the D9 (59 examples in VIC).
* Integer variables carry the `%` suffix in source (`FOR I%=1TO9`,
  REGION) and are ordinary slots on disk.
* PRINTUSING is statement token 0x28 with an `E7 <line>` reference to a
  `%` image line (statement token 0x3F carrying the mask text,
  Cyrillic included). Inline masks in source are placed on free lines
  by the assembler, which is the corpus form.

## What this enabled

With these tokens, `emulator/iskra_asm.py` assembles the recovered
МОДЕЛЬ РЕГИОНА source completely (420 lines, 61 named variables, 21
image lines) and `emulator/iskra_run.py` executes it. The run is
verified in `model-region/verify_run.py`: 26 full turns in lockstep
with the independent re-implementation, largest state deviation zero to
nine decimals, and the final mark agrees through the whole game. The
thirteen game sources still assemble byte-identically to the disks
built before this pass, which is the regression test for the encoder.
