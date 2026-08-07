# The chat disk

`disks/single/iskra226-chat.dsk` is a terminal program on the Iskra-226 that
answers questions about the project. The machine itself of course cannot do
that: it sends the question down a teletype line to another computing centre
and prints what comes back. That is exactly how it is built.

## Architecture

```
   BASIC program CHAT               host (Python)              model
   ------------------               -------------              -----
   SELECT PRINT 015   ──────►  device 015 collects lines
   PRINT V01                   (the question)
   SELECT PRINT 005   ──────►  _comm_flush()  ──────►  handler(question)
                                                            │
   INPUT V02          ◄──────  reply queue    ◄─────────────┘
   PRINT V02                   (one line per INPUT,
   ... until "."                terminated with ".")
```

The trick is **device address 015**. The dialect knows
`SELECT PRINT <device>`, attested in the corpus with 005 for the screen at
80 columns and 012 for the line printer at 132. 015 is not attested and is
therefore free as an extension: the emulator treats it as a communication
line. On the BASIC side only proven statements are used, `SELECT`, `PRINT`,
`INPUT`, `IF` and `GOTO`. The program is 25 lines long.

**Said plainly:** 015 is an **invention of this project**, not a historical
finding. A real Iskra-226 would have found nothing at that address.
Everything else about the disk is original format, disk header, catalog
entry, tokenized program body.

## Wiring it up

```python
from iskra_basic import Disk
import iskra_chat

def handler(question: str) -> str:
    return my_gateway.complete(system=iskra_chat.SYSTEM_PROMPT,
                               user=question)

disk = Disk('iskra226-chat.dsk')
term = iskra_chat.Terminal(disk, handler)

term.ask("Что такое Искра-226?")   # -> list of screen lines
term.ask_html("...")               # -> HTML with clickable links
```

Without a handler the disk still runs: `offline_handler` answers basic
questions about the Iskra, STIPENDIYA, BAM and the games from a small fact
table. The image is demonstrable without any key.

`SYSTEM_PROMPT` carries the project facts, the machine, the recovered disks,
the 212.30 roubles verified to the kopek, Riga and Leningrad as the origin
of the BAM suite, the unsolved microcode gap, plus the instruction to answer
briefly and without markdown. On a 24 by 80 text screen, asterisks and
hashes are just character litter.

## Links

The machine knows no hyperlinks, so it prints URLs as text. The web layer
makes them clickable:

| Function | Purpose |
|---|---|
| `linkify(text)` | HTML-escapes the screen text and turns every URL into an anchor, `target="_blank"`, `rel="noopener noreferrer"` |
| `extract_links(text)` | returns the URLs as a list, if the front end wants to render them separately |
| `to_iskra_text(reply)` | folds the model's reply to 78 columns **without breaking URLs**, because a torn URL is not clickable |

Punctuation at the end of a link, `.`, `,`, `;`, stays outside the anchor, so
a link at the end of a sentence does not point into nothing with a full stop
attached. And a reply line consisting only of `.` is defused to `. `,
otherwise it would trigger end of transmission and cut the answer short.

## A verified session

```
*** ИСКРА-226 - ТЕРМИНАЛ СВЯЗИ ***
ЛИНИЯ 015 - СПРАВОЧНАЯ СИСТЕМА
ВВЕДИТЕ ВОПРОС. ПУСТАЯ СТРОКА - КОНЕЦ.

--- ЗАПРОС1
ОТВЕТ:
Проект восстановил советскую Искру-226. Подробности в архиве Джима Бэттла:
https://wang2200.org а форум здесь: https://zx-pk.ru/threads/9276/ Приятного
чтения!

--- ЗАПРОС2
*** СВЯЗЬ ЗАВЕРШЕНА ***
```

Both URLs survive the line wrap intact and `ask_html()` turns them into
anchors correctly.

## Limits

- What is tested is the emulator, not the hardware.
- One call to `ask()` restarts the program and asks exactly one question.
  The conversation is held by the host, in `Terminal.history`, not by the
  machine. It has no memory between runs, which is as it should be for a
  1984 terminal session.
- Answers should be short. The screen has 24 lines; longer text scrolls
  past.
