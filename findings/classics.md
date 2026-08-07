# The classics pack

Seven titles from the BASIC canon, rewritten for the decoded BASIC 02
dialect and assembled into a disk image with `iskra_asm.py`. No listing is
reprinted from anywhere: game mechanics are common property, the code is
original and written in Russian, the way these programs would have looked in
a Soviet computing centre.

Disk: `disks/iskra226-classics.dsk` · sources: `games-src/`

| Program | Sectors | Original | Implemented |
|---|---|---|---|
| **LIFE** | 20-22 | Conway / Gardner 1970 | 10x8 grid, glider, 6 generations |
| **LUNAR** | 23-25 | Jim Storer 1969 | thrust 0-30, gravity 5, three landing classes |
| **HAMURA** | 26-30 | Dyment 1968 / Ahl 1973 | 10 years, land price, harvest, rats, famine, plague |
| **WUMPUS** | 31-40 | Gregory Yob 1973 | real dodecahedron, pits, bats, arrow |
| **BAGELS** | 41-45 | Ahl 1973 | 3 distinct digits, ФЕРМИ / ПИКО / БАГЕЛЬ |
| **DEPTH** | 46-49 | Ahl 1973 | 8x8x8 cube, direction hints, 6 salvos |
| **STARTRK** | 50-57 | Mike Mayfield 1971 | 64 quadrants, warp, phasers, torpedoes, bases |

## Verified play-throughs

Every program was not merely started but played to an outcome:

- **LIFE**, the glider runs its correct four-phase sequence and travels
  diagonally; checked against a hand calculation.
- **LUNAR**, the verified winning sequence lands at impact speed 2.5
  ("ОТЛИЧНАЯ ПОСАДКА"); doing nothing crashes at 70. The physics was
  checked numerically for **winnability** beforehand: with 400 units of
  fuel a soft landing exists, with 120 it does not.
- **HAMURA**, land prices vary across the years (26, 22, 19, 25), yields
  run 1 to 5 per hectare, famine deaths compute correctly.
- **WUMPUS**, warnings ("ЧУВСТВУЮ ВУМПУСА", "СКВОЗНЯК"), bat teleport,
  pathfinding across the graph, the kill.
- **BAGELS**, guess 1-2-3 against secret 9-0-7 returns "БАГЕЛЬ" correctly,
  then a hit.
- **DEPTH**, a miss at (4,4,4) against target (6,0,5) returns
  "ВОСТОЧНЕЕ / ЮЖНЕЕ / ГЛУБЖЕ", then the sinking.
- **STARTRK**, warp into the enemy quadrant, Klingon attack with damage,
  phaser fire, counter 3 to 2 to 1, plausible energy drain.

## What the pack taught us about the dialect

The games were the hardest test of the format so far and they exposed
**three errors**, two in the interpreter and one as a limit of the evidence:

1. **`E9`, minus, was disambiguated wrongly.** The old lookahead rule read
   `X - 1` at the end of a payload as "X" plus a stray literal of -1. The
   right rule is simpler: **after an operand, `E9` is binary minus;
   otherwise it opens a negative literal.** The retraction is documented,
   and the ведомость regression at 212.30 roubles confirms the correction
   did not damage the corpus.
2. **`RETURN` is `0x5E`**, not `0x2D`. `0x2D` is `LOAD`.
3. **Literals above 99 are unattested.** `E7 <bcd> <bcd>` is read by the
   interpreter as a *line reference*. Large constants are therefore built
   from small ones: `V60 = 12 : V60 = V60 * 10` rather than `120`. An
   honest gap, not a guessed workaround.

## The random number generator

The dialect's `RND` atom is unknown. Accounting software needs no
randomness, so the corpus does not give it up. Five of the seven games need
it anyway. The answer is a linear congruential generator in plain BASIC,
with the modulo done by repeated subtraction:

```
900 V50 = V50 * 21
910 V50 = V50 + 13
920 IF V50 < 100 GOTO 940
930 V50 = V50 - 100
935 GOTO 920
940 RETURN
```

The constants `a=21, c=13, m=100` give the **full period of 100**: a-1=20 is
divisible by every prime factor of 100, and c is coprime to it. The obvious
`a=13, c=7` would have had a period of 20.

A truncation routine goes with it, since `INT()` is unattested too:

```
950 V60 = 0
960 IF V61 < 1 GOTO 990
970 V60 = V60 + 1
980 V61 = V61 - 1
985 GOTO 960
990 RETURN
```

Convention: **V61 in, V60 out.** That separation became necessary after an
earlier version used the input variable as scratch and overwrote the
population in HAMURABI. Only playing the game made that visible.

## Limits

- What is tested is the **emulator**, not the hardware.
- The seed is fixed at `V50 = 37`, because no clock or timer function is
  attested: the same game every time. Historically that is authentic, which
  is why so many early BASIC games asked you to type a number first.
- STARTRK is a compact version: 64 quadrants without sector detail, phasers
  with a threshold rather than falloff with distance.
