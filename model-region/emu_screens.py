#!/usr/bin/env python3
"""Render REGION screens from the running interpreter.

Unlike screens.py, which re-creates the screens from the listing, these
come out of the emulator executing the tokenised program: the same
Screen buffer the STIPENDIYA screenshots use, captured at three moments
of a real run. The run is the verify_run.py policy, so the numbers on
the state screen are the machine's own.

    python3 emu_screens.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "emulator"))
sys.path.insert(0, HERE)
import iskra_basic                                           # noqa: E402
import iskra_run                                             # noqa: E402
from build_tokenised import build                            # noqa: E402
from screens import to_png                                   # noqa: E402

OUT = os.path.join(HERE, "screens")


def main():
    disk, _, symbols, _ = build(os.path.join(HERE, "region-tokenised.dsk"))
    tokens = iskra_basic.load_token_map(
        os.path.join(HERE, "..", "firmware", "basic02_101084.bin"))
    it = iskra_run.Interp(iskra_run.Disk(disk), tokens)

    shots = {}
    buf, cur = [], [None]

    def rd(x):
        return int(x * 100) / 100.0

    orig_pr = it._pr

    def spy(s):
        buf.append(str(s))
        if "Д О  С В И Д А Н И Я" in str(s) and "credits" not in shots:
            shots["credits"] = it.scr.render_text()
        orig_pr(s)
    it._pr = spy

    def driver():
        p = "".join(buf[-10:])
        del buf[:]
        if "ВАС ОЗНАКОМИТЬ С ПРАВИЛАМИ" in p and "title" not in shots:
            shots["title"] = it.scr.render_text()
        if "СКОЛЬКО НА РАЗ" in p:
            if "state" not in shots:
                shots["state"] = it.scr.render_text()
            cur[0] = tuple(rd(it.nvars.get(symbols["V"], 0) * w)
                           for w in (0.1, 0.4, 0.5)) + (0,)
            return str(cur[0][0])
        if "ПОДДЕРЖАНИЕ СРЕДЫ" in p and "СКОЛЬКО" in p:
            return str(cur[0][1])
        if "КАЧЕСТВО ЖИЗНИ" in p and "СКОЛЬКО" in p:
            return str(cur[0][2])
        if "УПРАВЛ" in p and "СКОЛЬКО" in p:
            return str(cur[0][3])
        if "СЫГРАТЬ ЕЩЕ РАЗ" in p:
            return "0"
        if "(ДА-1,НЕТ-0)" in p:
            return "0"
        return ""
    it.get_input = driver
    it.run("REGION", max_steps=1200000)

    labels = {
        "title": "the interpreter running the tokenised REGION; "
                 "captured at the rules prompt",
        "state": "year 1 as the interpreter prints it, PRINTUSING "
                 "masks and all; the policy is verify_run.py's",
        "credits": "the credits screen, reached by playing all 26 "
                   "turns and declining another game",
    }
    os.makedirs(OUT, exist_ok=True)
    for name, text in shots.items():
        scr = iskra_run.Screen()
        for k, line in enumerate(text.split("\n")[:24]):
            scr.buf[k] = list(line.ljust(scr.W)[:scr.W])
        path = os.path.join(OUT, f"emu-{name}.png")
        to_png(scr, path, "iskra_run.py, " + labels[name])
        with open(os.path.join(OUT, f"emu-{name}.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
        print(f"emu-{name}.png")


if __name__ == "__main__":
    main()
