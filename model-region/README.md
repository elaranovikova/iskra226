# МОДЕЛЬ РЕГИОНА

A Soviet teaching game about running a region for 25 years, written in
BASIC for the Iskra-226. The player divides the profit between the
economy, the environment, the standard of living and birth control, and
the model answers.

It has a point of no return built into it. Above a pollution of 50 the
term that cleans the environment changes sign and starts adding instead.
Nothing in the program says so.

![the title screen](screens/title.png)

## What this is

420 lines of BASIC, no author, no institute and no date anywhere in the
source. The program names itself in lines 3 and 4 and then gets on with
it. It states its goal only once, in line 597, and it does so while
telling the player off:

> ВАША ЦЕЛЬ - ВЫСОКОЕ КАЧЕСТВО ЖИЗНИ ПРИ У М Е Л О М УПРАВЛЕНИИ
> СИСТЕМОЙ В ЦЕЛОМ

A high quality of life under skilful management of the system as a
whole. The spaced out letters are in the original. Whoever wrote this
wanted the word *skilful* read slowly. Line 1140 calls the thing an
имитационная система, a simulation system, which is what its author
thought he had built.

## Where it came from

Side `012 1` of the Iskra-226 diskette archive. The side carries no
catalog, which is why it sat unread for a while: `iskra.py` looks for a
Wang style directory in sector 0, finds nothing that parses, and reports
the side as unknown. That verdict was wrong twice over. The side is
readable and it is full.

What is on it is the output of BASIC's own `LIST DC` statement, source
text written straight to the surface with no directory in front of it.
REGION line 2 is the author's own tooling for exactly that, and line 1
jumps over it so it never runs by accident:

```
1 GOTO 3
2 SCRATCH R/1C,"REGION":SAVE DC R/1C,T("REGION")"REGION":LIST DC R/1C,"R":END
```

`listing_format.py` in this folder reads and writes that layout. The
format is in its docstring. The short version: a header sector `01`
followed by an eight byte name, then text sectors prefixed `02 80`,
`8F 80` and `03 80` for first, middle and last, lines separated by `85`,
an end record `1C 00 78`, and no line ever split across a sector.

`region.dsk` is built by that writer from `REGION.bas`. Its sectors 0 to
119 are byte for byte the same as sectors 203 to 322 of the original
side. That equality is the reason this folder exists in the form it
does: the program is preserved exactly, without publishing a stranger's
read of a diskette that also holds three other people's work.

    python3 listing_format.py names region.dsk
    python3 listing_format.py read  region.dsk REGION

## The screens

The opening position. The right hand column is not computed at run time,
it is stored in line 22 as the reference the player is measured against.

![the state of the system](screens/state.png)

The program teaches while it plays. In the first twelve turns it offers
to explain itself, and the explanations are plots, drawn with `PRINT`,
`TAB` and a `FOR` loop. Profit against the economy and against
population:

![how profit grows](screens/profit-curve.png)

Pollution against production on the left, against money spent on the
environment on the right. Two curves of different shape, side by side on
an 80 column screen, in 1980s BASIC:

![what pollution depends on](screens/pollution-curves.png)

## The state, and what the player can touch

Six variables, set in line 10.

| | start | |
|---|---:|---|
| `P1` | 28 | invested in the national economy |
| `B1` | 13 | spent on keeping the environment |
| `G1` | 20 | prosperity, from which quality of life follows |
| `Z1` | 17 | pollution |
| `H1` | 29 | population |
| `K1` | 2 | birth control |

Each turn the player divides the profit four ways. Three of the four
levers only take money. Line 413 refuses to let the economy shrink:
*СОГЛАСИТЕСЬ, ЧТО СВЕРТЫВАТЬ РАЗВИТИЕ Н/Х НЕЦЕЛЕСООБРАЗНО*, agree that
winding down the national economy is not expedient. Birth control is the
only lever that works in both directions, and it is capped at one unit
per turn.

Money not spent stays as profit. Once per turn the allocation can be
taken back and done again, line 703.

## The feedbacks

Lines 708 to 790, in the order the program runs them.

```
K1 <- K1 + birth control
B  <- 1 - B1^1.5 / 20          effect of the environment money
Z1 <- Z1 + B + P               P is pollution from production
Z1 <- Z1 + C                   C is self cleaning
G1 <- G1 + Z + L               environment and density hit prosperity
G1 <- G1 + G                   prosperity decays on its own
```

Pollution from production doubles its slope once the economy passes 45,
lines 1280 to 1300. Prosperity drifts toward the threshold of 12 with no
help from anyone, lines 1230 to 1240, so a region left alone slides. And
below a prosperity of 12 the population does not decline, it falls off a
cliff: line 820 is `A8 = -3^(1-G1) * H1/20`, an exponential whose
exponent grows the further prosperity drops.

Two loops run against each other, both delayed. Investment makes profit,
profit allows investment, investment makes dirt, dirt lowers the
environment, the environment lowers prosperity. At the same time
prosperity raises the population, the population raises the density, and
the density lowers prosperity again.

## The threshold at 50

Self cleaning, lines 1250 to 1270:

```
Z1 <  0    C = 2^Z1                                practically nothing
0 <= Z1 <30 C = -(Z1^2 + 45*Z1 + 250)/(10*Z1+250)  nature cleans
Z1 >= 30   C = -(50 - Z1)/5
```

The third branch is the one that matters. At a pollution of 30 the term
returns minus four per turn. At 45 it returns minus one. At 50 it is
exactly zero, and above 50 it is positive, which means it no longer
cleans, it adds. Past that point the pollution is its own source and no
amount of money brings it back.

    python3 model.py

The program warns at 35 and says nothing at all at 50. Here is a run
that gets there, twenty percent of the profit to the economy, ten to the
environment, the rest to quality of life. The last column is `C`:

![the threshold crossed](screens/tipping.png)

Sixteen turns. The warning appears at turn 14, the sign changes at turn
16, and by then the population is gone. A player watching the screen
sees the warning; the number that decides the outcome is never printed.

Two things should be said against overreading this. The threshold is
often unreachable in practice because prosperity collapses first and
ends the game earlier, which is what happens if you put everything into
the economy. And the model has no floor under pollution: spend heavily
enough on the environment and `Z1` runs away downward without limit,
which is as unphysical as it sounds. This is a teaching model of 1980s
vintage, not a defensible simulation, and its interest is in what it
chose to represent.

## What the program teaches

It interrupts. Fixed messages fire on turns 1, 2, 4, 8, 13 and 20, among
them *ВЫ НЕДООЦЕНИВАЕТЕ ПАГУБНОЕ ВЛИЯНИЕ ЗАГРЯЗНЕНИЯ ОКРУЖАЮЩЕЙ СРЕДЫ*,
you are underestimating the ruinous effect of pollution. A weak result
gets the lesson in plain words, line 1060 onward: you must learn to
think about the future and to take the interactions between the elements
of the system into account. A top result gets no praise to rest on, only
*ПОПРОБУЙТЕ СЫГРАТЬ ЕЩЕ ЛУЧШЕ*, try to play better still.

There was a printed booklet. Line 3620 tells the player to read the
guide to the game again before starting the next one. I have not found
it.

Lines 27 and 28 set a second difficulty for a repeat player: almost
double the pollution to start with, and two thirds of the quality of
life.

## Scoring, and the clause against gaming it

Each turn adds the prosperity surplus to a running total. If the
population fell against the previous turn, three times the loss is
subtracted, line 882, which makes losing people the most expensive
mistake available.

The final mark is `(Y + 3*Y2)/M`, where `Y2` is the score of turn 17.
Turn 17 therefore counts four times over. The code does not say why, and
neither will I.

Then there is line 592. From turn 21 on, a player who pushes more than
half the profit into quality of life gets warned, and on the second
offence the mark is divided by 1.2 with the message *ВАШИ НЕЛОГИЧНЫЕ
ДЕЙСТВИЯ В КОНЦЕ ИГРЫ ПРИВЕЛИ К СНИЖЕНИЮ ОЦЕНКИ ДЕЯТЕЛЬНОСТИ*. The
author expected players to farm the objective function against the model
in the closing turns, and priced it in. That is a person who had watched
people play.

## The disk it sits on

Four programs, in this order:

| sector | name | |
|---:|---|---|
| 203 | `REGION` | this game |
| 323 | `SNAKE` | the snake game |
| 343 | `MANAGEM` | a second business game, and this one is signed |
| 450 | `SIG1` | not a listing, and the header flag byte says so |

`MANAGEM` line 10 is a comment, and it is the only attribution anywhere
on the side:

```
10 REM MANAGEM.01/28.04.83/ГОРПЕНКО/ДЕЛОВАЯ ИГРА
```

A business game, version 01, 28 April 1983, by Gorpenko. It is a market
simulation for up to twenty players with monthly cycles, raw material
bids, fixed costs, market conditions and random emergencies. Its
subroutine comments are in Russian throughout.

So the side is a teaching set of business games, and one of the two is
dated to April 1983. Elsewhere in the same archive, side `w006-s1`
carries `PRESID`, a third one. `МОДЕЛЬ РЕГИОНА` itself stays anonymous.

The header flag byte is `0x20` on the three listings and `0x21` on
`SIG1`, whose sectors are not text. One byte, one bit, and the reader
knows whether to expect source.

## What is not established

* **No author, no institute, no date for `МОДЕЛЬ РЕГИОНА`.** The
  abbreviation `Н/Х` for the national economy and the tone of the
  prompts point at a teaching institution. That is an impression, not a
  finding.
* **`M3` does not reproduce.** Line 22 stores seven reference values.
  Two of them, `M5` and `M6`, are copies of state and prove nothing. Of
  the remaining five, four fall out of the formulas exactly. The fifth,
  the growth intensity of 2.759, matches neither the value before the
  scaling of line 210 nor the value after it. `model.py` prints this
  rather than hiding it, and the state screenshot above shows the
  mismatch in the machine's own columns: 7.426 against 2.759.
* **Turn 17 and its quadruple weight** have no explanation in the code.
* **The printed guide the program refers to** has not been found.

## Files here

    README.md             this
    REGION.bas            the listing, 420 lines, verbatim including the
                          trailing spaces, which a byte exact rebuild needs
    region.dsk            a side holding only REGION, built by
                          listing_format.py and equal to the original
                          sectors byte for byte
    listing_format.py     read and write the flat listing format
    model.py              the state machine, re-implemented, with the
                          self check against line 22
    screens.py            renders screens/
    screens/*.png         the images above, plus the same screens as .txt

The screens marked as such in `screens.py` are the program's own `PRINT`
and `TAB` statements executed as written. The two that carry numbers use
`model.py`, which is a re-implementation and not the Iskra executing
anything. The distinction is the same one the top level README makes
about `reconstruction/`, and it is kept here for the same reason.

## Whose this is

The image of side `012 1` came from **dk_spb**, who read the physical
diskettes and has kept this material alive for years. Without his
archive there is no folder here and no repository either. The program
itself is the work of somebody at a Soviet teaching institution in the
1980s whose name is not on it.

My code in this folder is MIT and my prose is CC BY 4.0, the same as the
rest of the repository. The decoded listing is a Soviet work of the
1980s and is reproduced here as a historical document.
