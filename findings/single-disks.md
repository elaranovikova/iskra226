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
| `iskra226-tetris.dsk` | TETRIS | Падающие блоки | 92 | 5 |
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
