# Writing programs for the Iskra-226: the assembler

Up to here the tokenized BASIC 02 format was only ever **read**.
`iskra_asm.py` writes it: BASIC source to token bytes to a disk image that
the emulator loads and runs. That makes the format knowledge bidirectional,
which is the sharpest test available without original hardware.

## The round trip as proof

A decoder can be wrong without anyone noticing. Misread a byte and it still
produces *some* result. An encoder cannot do that. Emit the wrong bytes and
an independently written parser fails immediately. Programs I assembled
myself running cleanly through `iskra_run.py` checks both sides against each
other.

Exactly that test exposed two errors, both corrected from the corpus rather
than guessed:

| Construct | first assumption | corpus evidence | correct |
|---|---|---|---|
| relation `>` / `<` | `D7` / `D6` | parser table | **`D4` / `CF`** |
| `TO` in FOR | `2A` | line 3290: `57 05 37 e8 01 d1 00` | **`D1`** |

With the wrong `TO`, the parser read `2A` context-dependently as
multiplication and the loop ran exactly once. A silent failure that only the
round trip makes visible.

## Language covered

Everything whose encoding is proven:

```
assignment    V<nn> = <expr>            A<nn>(V<nn>) = <expr>
PRINT         strings, expressions, TAB(), semicolons
INPUT         one or more variables
IF <expr> <relation> <expr> GOTO <line>
GOTO / GOSUB / FOR ... TO / NEXT / END / STOP / REM
arithmetic    + - * /        relations   = < > <>
```

Line format `<BCD hi> <BCD lo> <length> <statements> FE`, statement format
`<token> <payload length> <payload>`; numeric literals `E8 <BCD>` for 0 to 99
and `E7 <BCD> <BCD>` for 0 to 9999; strings `E3 <length> <KOI characters>`.

The assembler also writes the disk header, meaning catalog extent, last
sector used and capacity, with the layout taken from sector 0 of
`disk3side0`, and the catalog entries: the `10` marker, big-endian start and
end, and an eight character name from offset 16.

## The games disk

`disks/iskra226-games.dsk`. Three programs of my own, no reprinted listing;
mechanics are common property, the code is newly written and in Russian.
Sources in `games-src/`.

| Program | Sectors | Content |
|---|---|---|
| **UGADAY** | 20 | number guessing with МЕНЬШЕ / БОЛЬШЕ feedback and an attempt counter |
| **TABLIT** | 21 | multiplication drill, a FOR loop over nine rounds with scoring |
| **PLAN** | 22-23 | "Плановое хозяйство", a ten-year resource game: split grain between food and seed, harvest x3, famine on shortfall |

Verified runs:

```
UGADAY  50 -> МЕНЬШЕ | 25 -> БОЛЬШЕ | 37 -> ВЕРНО! ПОПЫТОК 3
TABLIT  nine rounds, right and wrong answers scored correctly
PLAN    yearly cycle, harvest, population loss on famine
```

`PLAN` is resource management in the tradition of the early BASIC planning
games, on a machine whose sister software, BAM, came out of a Gosplan
planning institute. The joke writes itself.

## Limits

- What is tested is the **emulator**, not the hardware. The bytes follow the
  attested rules, but only a test on a surviving Iskra-226 can show whether
  real firmware accepts them.
- The dialect's random number atom is undecoded, so `UGADAY` uses a fixed
  number.
- Floating point literals, string variables and `PRINTUSING` are not written
  yet. Only the proven core.

## Use

```python
import iskra_asm
iskra_asm.build_disk('mine.dsk', [('NAME', source)])
```

Then load and run it with `iskra_run.py` like any original program.

## Addendum: ARTIL, and why GORILLA.BAS cannot be ported

The obvious question, "does the Microsoft monkey game run?", has the answer
no, for three independent reasons.

**GORILLA.BAS**, QBasic, shipped with MS-DOS 5.0 in 1991, fails on:

1. **Dialect.** QBasic with `SUB` procedures and no line numbers; the Iskra
   format knows only line-numbered, tokenized statements.
2. **Graphics.** `SCREEN 9` at EGA 640x350, `LINE`, `CIRCLE`, `PAINT`. In
   the dialect we have decoded, the Iskra-226 is a pure character terminal.
   Not one graphics atom is attested.
3. **Runtime.** Sound via `PLAY`, timers, and floating point trigonometry
   with `SIN` and `COS`, for which no atom values are known.

What *is* portable is the mechanic, which is older than the gorillas: enter
angle and power, compute range, "too short / too far", adjust. The classic
artillery duel.

`ARTIL` does that in the proven core. Without trigonometry it approximates
`sin(2a)` with a triangle function: `f = 90 - |90 - 2a|`, range
`= power squared times f over 900`. That reproduces the decisive properties
of a real ballistic arc: maximum at 45 degrees, symmetric falloff on both
sides, quadratic dependence on power. The absolute value comes from two `IF`
branches, because `ABS()` is not attested either.

A verified ranging sequence against a target at 250:

```
45 deg / 30  ->  НЕДОЛЕТ НА 160
45 deg / 60  ->  ПЕРЕЛЕТ НА 110
45 deg / 50  ->  *** ПОПАДАНИЕ! ***  ВЫСТРЕЛОВ: 3
```

Bracketing, the way artillery does it: short, long, middle.

## Addendum: TETRIS, what works and what does not

Tetris is the first request that fails on a **real limit of the machine**
rather than on dialect differences.

**What is missing for real Tetris:**

- **Non-blocking key input.** The token `KEYIN`, `0x25`, is in the table but
  was not implemented in the interpreter, and without polling a key without
  waiting there is no real-time falling. That is the hard limit.
- **Timing.** No attested atom for waiting or a timer. Fall speed could only
  be approximated with empty loops whose duration depends on emulator speed
  rather than machine clock.
- **Graphics.** As with GORILLA.BAS: a pure character terminal, so a
  playfield can only be printed as a character grid.
- **Speed.** Redrawing the whole field per frame in interpreted BASIC would
  run at a few frames per second on the original machine.

**What works:** the turn-based version. `TETRIS` offers a 6x8 field, three
shapes in rotation (2x1, 1x2, 2x2), a column choice per move, gravity with
correct landing detection across all occupied columns, full line detection
with the rows above shifting down, scoring, and game over on overflow.

Worth noting in the implementation: the field is a one-dimensional array
`A20(idx)` with `idx = (row-1)*6 + column`. Two-dimensionality is produced
arithmetically, which is what the format invites. Shifting down after a
cleared line needs a **descending loop**, and since `STEP` is not attested,
it is built out of `IF` and `GOTO`.

Verified: pieces stack correctly, `*** ЛИНИЯ! ***` on clearing a full row,
`*** ИГРА ОКОНЧЕНА ***` on overflow, and the column check rejects
placements that are too wide.

93 source lines, 92 assembled program lines. The largest program written for
this machine so far.

## Addendum 2: TETRIS2, real time on character cells

With `KEYIN` decoded, in addendum 20, the input limit falls. Real bitmap
graphics stay impossible, because the machine has none. What becomes
possible is **character cell graphics with cursor positioning**, which is
exactly the kind of Tetris that ran on terminals of that era.

`TETRIS2`, 179 lines, draws a 10x12 playfield with a frame, moves the
falling piece by overwriting individual cells (erase at the old position,
draw at the new) and polls the keyboard without blocking in step with the
fall loop.

Assembler extensions needed:

- `PRINT AT(row,col)`, the full literal form `D5 E8 rr DE E8 cc D0`, which
  the interpreter needs in order to tell AT from the `<>` relation.
- `PRINT ATV(v1,v2)`, because for **variable** coordinates the literal form
  does not work. Here the generic function atom `E1 31 <arg> DE <arg> D0`
  carries it, and its arguments may be slots. Without this second form,
  moving character graphics would not be possible at all.
- `KEYIN <var>, <target1>, <target2>`.

Verified:

- Pieces fall on their own, stack on each other, game over on overflow.
- Steering left and right stacks the pieces against the respective wall, so
  the key branches take effect during play.
- Deliberately filling the bottom row clears **two lines, 20 points**,
  including the rows above shifting down.

### Two errors only this program revealed

1. **The key code landed in both variable spaces.** `KEYIN` wrote the
   character *and* the code; on comparison, `IF V07 = 52`, the string won
   and the condition always failed. The corpus compares numerically, BAM3
   line 1160 opens with `ON V21+1`, so the slot holds the code only.
2. **The screen-clearing heuristic fired inside the game loop.** The
   interpreter clears on backward jumps to lines at or below 100, which is
   meant for the menu redraws of the original programs. In TETRIS2 that
   wiped the playfield on every new piece. The heuristic stays, because it
   is verified against the original screenshots; the game puts its main loop
   on line 300 instead. **Anyone writing their own programs should choose
   backward jump targets above 100.**

### What is still missing

A time atom. Fall speed hangs on a counter over keyboard polls, `V06`, not
on a clock, so on the original machine the game would run at the pace of its
own interpreter. For a program of that period, though, that is the normal
way to build it.

## Addendum 3: TETRIS3 replaces both of them

The two above are gone from the disk set. `TETRIS3` does what they were each
reaching for and did not get to: all seven tetrominoes, a bordered field, and
real-time key polling, in 432 lines across 30 sectors. That is more than the
turn-based version and the real-time one put together, and it is the largest
program on any of the disks I wrote.

The two addenda above stay because the findings in them are not about the
games. The turn-based version is where the interpreter's numeric literal
limit first showed up, and the real-time one is where the redraw cost of a
character cell screen got measured. Both of those still hold. What changed is
which disk ships.

One honest gap: `games-src/` has no `TETRIS3.bas`. Every other disk here was
assembled from a source in that directory and the source is the proof that
the format works in both directions. For this one I have the image and not
the source, so the proof for TETRIS3 is narrower: it is that an independent
parser loads and runs it.
