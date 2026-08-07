#!/usr/bin/env python3
"""
iskra_chat.py, host bridge for the CHAT diskette.

The BASIC program on iskra226-chat.dsk talks to the outside world
through device 015, a "communication line". This module is the other
end of that line: it receives the question the program sent, asks an
LLM, and hands the reply back one line at a time.

Wiring it up on the deployment site
-----------------------------------

    from iskra_basic import Disk, load_token_map
    import iskra_run, iskra_chat

    def my_llm(question: str) -> str:
        # any callable: a hosted model, one you run yourself, a RAG chain
        return my_client.complete(system=iskra_chat.SYSTEM_PROMPT,
                                  user=question)

    disk = Disk('iskra226-chat.dsk')
    term = iskra_chat.Terminal(disk, my_llm)
    term.ask("Что такое Искра-226?")     # -> list of screen lines

`Terminal.ask` runs the BASIC program far enough to send one question
and collect the reply, so the web layer can drive it turn by turn.

Link handling
-------------

The BASIC side prints URLs as plain text, because a 1984 terminal has
no notion of a hyperlink. `linkify()` turns them into anchors for the
web layer; `extract_links()` returns them separately if the frontend
prefers to render its own list. Both work on the screen text, so they
also catch links the model puts inside prose.
"""

import html
import re

__all__ = ["SYSTEM_PROMPT", "Terminal", "extract_links", "linkify",
           "to_iskra_text", "offline_handler"]


# --------------------------------------------------------------- prompt

SYSTEM_PROMPT = """\
You answer questions about the Iskra-226 emulation project: a Soviet
Wang-2200 clone whose rescued 1988 floppy images were reverse
engineered until the original payroll software (STIPENDIYA) ran again
and printed a verified pay sheet.

Key facts you may rely on:
- The machine is a Soviet clone of the Wang 2200. Two BASIC dialects
  were rescued: BASIC 02 (22.04.84) and BASIC PL5 (30.09.84).
- Six diskette sides survived: three system disks, the BAM database
  suite (developed in Riga at the Gosplan research institute of the
  Latvian SSR, further developed in Leningrad at Lensistemotekhnika),
  the STIPENDIYA payroll application with its live data file, and one
  blank side.
- The payroll run was verified to the kopeck against an independent
  hand calculation: net payout 212.30 roubles for three students.
- A bidirectional understanding of the tokenised BASIC format was
  demonstrated by writing an assembler and porting twelve programs.
- The microcode level (K589 ROM) remains unsolved and needs a dump
  from surviving hardware.

Answer in the language of the question. Keep answers short: this is a
24x80 character terminal. Use plain URLs on their own line when
pointing somewhere. Do not use Markdown formatting, it will be shown
on a 1984 text screen.
"""


# ------------------------------------------------------------ utilities

URL_RE = re.compile(r'https?://[^\s<>"\')]+')


def extract_links(text):
    """Return the URLs appearing in the text, in order, without repeats."""
    seen = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip('.,;:')
        if u not in seen:
            seen.append(u)
    return seen


def linkify(text, target="_blank"):
    """HTML-escape the text and turn plain URLs into clickable anchors.

    The emulator screen is rendered as text on the web page; running it
    through this makes every URL the model printed a real link while
    leaving the rest of the 24x80 layout untouched.
    """
    out = []
    pos = 0
    raw = text or ""
    for m in URL_RE.finditer(raw):
        out.append(html.escape(raw[pos:m.start()]))
        url = m.group(0)
        trail = ""
        while url and url[-1] in '.,;:':
            trail = url[-1] + trail
            url = url[:-1]
        safe = html.escape(url, quote=True)
        out.append('<a href="%s" target="%s" rel="noopener noreferrer">%s</a>'
                   % (safe, target, safe))
        out.append(html.escape(trail))
        pos = m.end()
    out.append(html.escape(raw[pos:]))
    return "".join(out)


def to_iskra_text(text, width=78):
    """Fold a model reply into lines the terminal can display.

    The screen is 80 columns; long lines would be clipped. URLs are
    never broken, since a broken URL is not clickable.
    """
    lines = []
    for para in str(text).replace("\r", "").split("\n"):
        para = para.rstrip()
        if not para:
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= width:
                cur += " " + word
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    # a lone "." would end the transfer early
    return "\n".join(ln if ln.strip() != "." else ". " for ln in lines)


def offline_handler(question):
    """Fallback used when no LLM is wired up, so the diskette still runs."""
    q = (question or "").lower()
    facts = [
        (("искр", "iskra", "226"),
         "ИСКРА-226 - СОВЕТСКИЙ АНАЛОГ WANG 2200.\n"
         "ШЕСТЬ СТОРОН ДИСКЕТ СПАСЕНЫ В 2026 ГОДУ."),
        (("стипенд", "stipend", "ведомост", "зарплат"),
         "STIPENDIYA - ПРОГРАММА РАСЧЕТА ВЫПЛАТ УЧАЩИМСЯ.\n"
         "ПРОВЕРЕНО: К ВЫДАЧЕ 212.30 РУБ. НА ТРЕХ УЧАЩИХСЯ."),
        (("bam", "бам", "рига", "riga"),
         "BAM - СИСТЕМА БАЗ ДАННЫХ, ВЕРСИЯ 1.2.\n"
         "РАЗРАБОТАНА В РИГЕ, ДОРАБОТАНА В ЛЕНИНГРАДЕ."),
        (("игр", "game", "тетрис", "tetris"),
         "ДВЕНАДЦАТЬ ПРОГРАММ НАПИСАНЫ ЗАНОВО.\n"
         "СРЕДИ НИХ: ЖИЗНЬ, ЛУНА, ХАММУРАПИ, ВУМПУС."),
        (("wang", "ванг"),
         "АРХИВ WANG 2200 ДЖИМА БЭТТЛА:\n"
         "https://wang2200.org"),
    ]
    for keys, answer in facts:
        if any(k in q for k in keys):
            return answer
    return ("СПРАВОЧНАЯ СИСТЕМА РАБОТАЕТ БЕЗ МОДЕЛИ.\n"
            "СПРОСИТЕ ОБ ИСКРЕ, STIPENDIYA, BAM ИЛИ ИГРАХ.")


# -------------------------------------------------------------- terminal

class Terminal:
    """Drives the CHAT program on the diskette, one question per call."""

    def __init__(self, disk, llm=None, token_map=None, program="CHAT"):
        import iskra_run
        from iskra_basic import load_token_map
        self._runner = iskra_run
        self.disk = disk
        self.program = program
        self.token_map = token_map or load_token_map()
        self.llm = llm or offline_handler
        self.history = []

    def _handler(self, question):
        reply = self.llm(question)
        self.history.append((question, reply))
        return to_iskra_text(reply)

    def ask(self, question, max_steps=400000):
        """Send one question; return the screen lines the program printed."""
        it = self._runner.Interp(self.disk, self.token_map,
                                 auto=[question, "КОНЕЦ"])
        it.llm_handler = self._handler
        lines = []
        buf = {"cur": ""}
        put, nl = it.scr.puts, it.scr.newline

        def _puts(s):
            buf["cur"] += str(s)
            return put(s)

        def _nl():
            lines.append(buf["cur"])
            buf["cur"] = ""
            return nl()

        it.scr.puts = _puts
        it.scr.newline = _nl
        it.run(self.program, max_steps=max_steps)
        if buf["cur"]:
            lines.append(buf["cur"])
        return [ln for ln in lines]

    def ask_html(self, question, **kw):
        """Same as ask(), but returns HTML with clickable links."""
        return linkify("\n".join(self.ask(question, **kw)))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from iskra_basic import Disk
    d = Disk(sys.argv[1] if len(sys.argv) > 1
             else "iskra226-chat.dsk")
    t = Terminal(d)
    q = " ".join(sys.argv[2:]) or "Что такое Искра-226?"
    for line in t.ask(q):
        print(line)
