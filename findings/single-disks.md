# One disk per program

Every program also sits on its own bootable disk in `disks/single/`. The
format matches the originals: disk header in sector 0, one catalog entry,
program body from sector 20, the way an application disk for the Iskra-226
looked.

**All checked: loaded, started, played to an outcome.**

| Disk | Program | Title | Source lines | Sectors |
|---|---|---|---|---|
| `iskra226-life.dsk` | LIFE | Жизнь Конвея | 63 | 3 |
| `iskra226-lunar.dsk` | LUNAR | Посадка на Луну | 36 | 3 |
| `iskra226-hamurabi.dsk` | HAMURA | Хаммурапи | 87 | 5 |
| `iskra226-wumpus.dsk` | WUMPUS | Охота на Вумпуса | 172 | 10 |
| `iskra226-bagels.dsk` | BAGELS | Багель | 82 | 5 |
| `iskra226-depth.dsk` | DEPTH | Глубинная бомба | 69 | 4 |
| `iskra226-startrek.dsk` | STARTRK | Звездный путь | 131 | 8 |
| `iskra226-ugaday.dsk` | UGADAY | Угадай число | 16 | 1 |
| `iskra226-tablit.dsk` | TABLIT | Таблица умножения | 13 | 1 |
| `iskra226-plan.dsk` | PLAN | Плановое хозяйство | 26 | 2 |
| `iskra226-artil.dsk` | ARTIL | Артиллерийская дуэль | 31 | 2 |
| `iskra226-tetris.dsk` | TETRIS | Падающие блоки | 432 | 30 |
| `iskra226-snake.dsk` | SNAKE | Змейка | 128 | 7 |
| `iskra226-chat.dsk` | CHAT | Терминал связи | 25 | 3 |

## Why one each

On the real machine you put in a disk per task, and the recovered originals
show exactly that: STIPENDIYA alone on disk3side0, the BAM suite alone on
disk2side1. One disk per program matches that practice and makes every image
passable on its own, without anyone needing the whole package.

The collection disks `iskra226-classics.dsk`, seven canon titles, and
`iskra226-games.dsk`, five of my own, are kept as well.

## Loading

```python
from iskra_basic import Disk, load_token_map
import iskra_run
disk = Disk('iskra226-wumpus.dsk')
it = iskra_run.Interp(disk, load_token_map())
it.run('WUMPUS')
```

The program name is in the catalog of each disk and in the *Program* column
above, limited to eight characters as the original format requires.

For the two real-time programs, TETRIS and SNAKE, supply keystrokes through
`it.key_source`, a callable returning a key code or None:

```python
keys = list("6644882")
it.key_source = lambda: (ord(keys.pop(0)) if keys else None)
```

## These are not a find

Everything on these disks was written for this project in 2026. The
mechanics of the canon titles are common property and the code is original;
nothing is a reprint. No Soviet games disk was recovered, and if one ever
is, it will look nothing like this.

What the disks do prove is that the format knowledge runs both ways. Reading
a disk can be wrong without anyone noticing. Writing one that an independent
parser then executes cannot.

## Limits

What is tested is the emulator, not the hardware. The images follow the
attested format rules; whether a surviving Iskra-226 accepts them can only
be shown by a test on a real machine. That is the one open question left on
this part of the project, and I would very much like someone to answer it.


## Addendum: SNAKE grew a body

The first SNAKE was fifty-six lines and honest about what it was: a head, a
step counter, an apple that walked a fixed path, one status line per turn.
It existed to force KEYIN into the interpreter and it did that job. As a
game it was a steering exercise that most players never even saw, because
its loop jumped back to line 100 and the screen-page heuristic wiped every
frame.

The rebuilt SNAKE is a hundred and twenty-eight lines and is the game the
name promises. A bordered field drawn once and updated cell by cell with
PRINT AT. A body that grows by one segment per apple, kept in a ring buffer
(A10/A11) with head and tail indices, and a grid array (A20) so the self
collision test is one lookup instead of a walk along the body. Food placed
by RND with a retry loop when it lands on the snake. Reversal into your own
neck is ignored rather than fatal. Score on the top line, updated in place.
The main loop starts at line 200, above the screen-page boundary, so the
field persists and the eye sees a game instead of a flicker.

None of this outran the dialect: it is the same statement set the 1988
programs use, plus the expression layer the statistics packages proved. The
old fifty-six-line version stays readable at the v1.0 tag, where its whole
story is told.
