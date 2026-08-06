# Survey of all six disk sides

An inventory of the recovered set, 256,256 bytes per side, 1001 sectors of
256 bytes, with a run test of every program found, in the BASIC-level
emulator `emulator/iskra_run.py`.

## Overview

| Side | Type | Contents | Extent |
|---|---|---|---|
| **disk1side0** | system | **BASIC PL5** 30.09.84, plus three BASIC 01 builds in the other slots | 979 sectors in use |
| **disk1side1** | system | **BASIC 02**, four builds: 16.12.83, 22.04.84, 10.10.84, 10.09.86 | 966 sectors in use |
| **disk2side0** | system | **BASIC PL5** 30.09.84 in all four slots, byte-identical | 996 sectors in use |
| **disk2side1** | application | **BAM database suite**, 19 programs plus one deleted entry, about 4,650 lines | sectors 6 to 886 |
| **disk3side0** | application | **STIPENDIYA** payroll software, S0/S1/S2/S2\* plus the data file 132 | sectors 24 to 812 |
| **disk3side1** | nothing | **entirely blank**, no sector in use | none |

The system sides carry the signature `06 90 09 90 07 90` and a plain-text
identifier in sector 0, followed by the interpreter image; further back
there are utility strings such as CATALOG, LABEL, SECTORS and BREPLACE.

## disk2side1: the BAM suite

The origin note is encoded inside BAM0 itself:

> ВЕРСИЯ 1.2 РАЗРАБОТАНА В РИГЕ, НИИП ГОСПЛАНА ЛАТВИЙСКОЙ ССР,
> ОТДЕЛ "ПОМ" /ЯУГИЕТИС А.В./
> ДОРАБОТАНА В ЛЕНИНГРАДЕ, НТПО "ЛЕНСИСТЕМОТЕХНИКА",
> ОТДЕЛ 215 /ЛЕВИТАН Л.И./

A generic database and reporting system from the Gosplan planning institute
of the Latvian SSR in Riga, developed further in Leningrad: classifiers,
indicators (показатели), a form designer, a query subsystem and import from
magnetic tape. Internal version 3.9, correction dates 1985 to 1987, target
firmware "БЕЙСИК 02 10.09.86".

That target is a newer revision than the 22.04.84 I had been using as the
project reference, and it is one of the eight builds recovered from the boot
slots. It was on disk1side1 the whole time, in slot 2.

Soviet software genealogy with real names in it is not common. Two
institutes, two departments, two people, written into a program by whoever
was maintaining it.

### Inventory and smoke test

Every program was loaded and executed with minimal input.
**Result: 19 of 19 run without a crash.** Menus, dialogues and segment
chains all work.

| File | Lines | Function | Run |
|---|---|---|---|
| BAM | 109 | main dispatcher, "РАБОТА (0 - КОНЕЦ)?" | runs |
| BAM0 | 124 | array directory, origin note, version | runs |
| BAM00 | 33 | configuration and limits, 08.02.85 | runs, **chains correctly to BAM0** |
| BAM1 | 177 | forming indicator descriptions | runs |
| BAM2 | 358 | create and maintain a classifier | runs |
| BAM3 | 202 | form designer, "ПРОЕКТИРОВАНИЕ ФОРМЫ" | runs |
| BAM4 | 291 | module, 04.01.86 | runs |
| BAM5 | 453 | block loader with library check | runs |
| BAM6 | 475 | block loader, second implementation | runs |
| BAM7 | 96 | module, 13.08.86 | runs |
| BAM8 | 86 | module, 05.06.86 | runs |
| BAM9 | 627 | data import, including **magnetic tape** | runs, device menu appears |
| BAM10 | 514 | largest module, 25.04.87 | runs, correctly reports an empty link file |
| LBAM | 88 | loader with menu, including a demonstration mode | runs, the demo branch navigates |
| S/BAM01 | 177 | query subsystem, 15.01.87 | runs |
| S/BAM02 | 118 | indicator cleanup | runs |
| S/BAM03 | 131 | query subsystem, 04.08.86 | runs |
| S/BAM04 | 254 | copy and list queries | runs |
| S/BAM05 | 340 | query execution, link file modes | runs |
| СПИСОК | | deleted entry, scratched | |

Notably correct behaviour against the empty virtual disk: BAM5 and BAM10
report "В ФАЙЛЕ СВЯЗИ НЕТ ЗАПИСЕЙ", no records in the link file. The
originals' own data checks fire.

## disk3side0: STIPENDIYA

Five files: the dispatcher S0, the segments S1, S2 and S2\*, and the data
file 132 at 561 sectors. Authors Gorenburgov M. A., Vintskevich V. V. and
Muchkina L. V., dated 04.04.1989, banner "ВЕРСИЯ СПТУ-132 01.09.88".

All five load and run, and the payroll arithmetic is verified: see
`findings/vedomost-printed.png` and `findings/purchasing-power-1988.md`.

The data file is not decoded. It has students' names in it.

## Total

24 of 24 findable programs load and run without a crash. Two complete
application systems from two corners of the Soviet Union, eight interpreter
builds spanning five years, and one side that was never written to.

## Limits, stated plainly

The BAM suite targets a firmware revision newer than the one the
interpreter was developed against, which shows up as occasional scatter in
the menu positioning and a handful of mangled strings: at least one
positioning statement and one encoding variant of the 1986 dialect are not
implemented. Depth of function is untested for BAM, because the suite's own
working data files are not on the disk. The smoke test proves that the
programs load, chain and dialogue. It does not prove they compute.
