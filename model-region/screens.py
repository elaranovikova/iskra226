#!/usr/bin/env python3
"""
Render the screens in screens/ from REGION.bas.

What these images are, exactly, because the difference matters:

  * title, profit-curve and pollution-curves are the program's own PRINT
    and TAB statements, executed as written. No model state enters them.
  * state uses the program's own PRINTUSING masks, read out of REGION.bas
    at render time so they cannot drift, but the numbers in the left hand
    column come from model.py, which is a re-implementation. Its right
    hand column is the program's own stored reference, line 22.
  * tipping is not a program screen at all. It is a table of what the
    model does over sixteen turns, in the machine's screen geometry
    because that is the size the thing was thought in.

The 80 by 24 KOI-8 screen and the green-on-black rendering are the same
ones emulator/iskra_run.py uses for the STIPENDIYA screenshots, so these
sit next to those without a change of units. to_png below mirrors the one
in iskra_run.py; the only difference is that it looks for a font that
exists on the machine this was rendered on.

    python3 screens.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "emulator"))
from iskra_run import Screen                                   # noqa: E402
from model import Region                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "screens")

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
]


def to_png(scr, path, label=""):
    """Mirrors emulator/iskra_run.py to_png, with a wider font search."""
    from PIL import Image, ImageDraw, ImageFont
    CW, CH, PAD = 11, 22, 24
    extra = 30 if label else 0
    img = Image.new("RGB", (scr.W * CW + 2 * PAD, scr.H * CH + 2 * PAD + extra),
                    (10, 12, 10))
    dr = ImageDraw.Draw(img)
    f = fs = None
    for cand in FONTS:
        try:
            f = ImageFont.truetype(cand, 16)
            fs = ImageFont.truetype(cand, 12)
            break
        except OSError:
            continue
    if f is None:
        f = fs = ImageFont.load_default()
    dr.rectangle([PAD - 6, PAD - 6, scr.W * CW + PAD + 6, scr.H * CH + PAD + 6],
                 outline=(60, 90, 60), width=2)
    for y in range(scr.H):
        for x in range(scr.W):
            ch = scr.buf[y][x]
            if ch != " ":
                dr.text((PAD + x * CW, PAD + y * CH), ch, font=f,
                        fill=(150, 240, 150))
    if label:
        dr.text((PAD, scr.H * CH + PAD + 10), label, font=fs, fill=(120, 160, 120))
    img.save(path)


def listing():
    """The program's own source, keyed by line number."""
    src = {}
    path = os.path.join(HERE, "REGION.bas")
    for raw in open(path, encoding="utf-8"):
        num, _, rest = raw.rstrip("\n").partition(" ")
        if num.isdigit():
            src[int(num)] = rest
    return src


SRC = listing()


def mask_of(line_number):
    """Pull the PRINTUSING format string out of a line of the listing."""
    text = SRC[line_number]
    start = text.index('"') + 1
    return text[start:text.index('"', start)]


def using(mask, *values):
    """
    PRINTUSING against the program's own mask.

    Two field shapes turn up in this program: ###.### for every reading,
    and ## for the year counter in line 330. Both are right justified in
    the width of the field.
    """
    out, taken = [], 0
    i = 0
    while i < len(mask):
        if mask[i:i + 7] == "###.###":
            out.append(f"{values[taken]:7.3f}")
            taken += 1
            i += 7
        elif mask[i:i + 2] == "##":
            out.append(f"{int(values[taken]):2d}")
            taken += 1
            i += 2
        else:
            out.append(mask[i])
            i += 1
    return "".join(out)


def line(scr, text=""):
    scr.puts(text)
    scr.newline()


def tab(scr, col, text):
    scr.tab(col)
    scr.puts(text)


# ------------------------------------------------------------------ screens

def title():
    """Lines 3 and 4."""
    scr = Screen()
    scr.newline()
    tab(scr, 30, "ПРОГРАММА")
    scr.newline()
    scr.newline()
    tab(scr, 26, '"МОДЕЛЬ РЕГИОНА"')
    scr.newline()
    return scr, "REGION.bas lines 3 to 4"


def state():
    """Lines 160 to 330 at the opening position, turn 1."""
    r = Region()
    scr = Screen()
    line(scr, SRC[160].split('"')[1])
    line(scr, SRC[170].split('"')[1])
    # Previous turn is zero on the first pass, set in line 15.
    rows = [
        (180, r.quality_of_life(), 0.0, 9.0),
        (200, r.density(), 0.0, 4.123),
        (220, r.growth_percent(), 0.0, 2.759),
        (240, r.environment(), 0.0, -2.429),
        (260, r.B1, 0.0, 13.0),
        (270, r.P1, 0.0, 28.0),
        (310, r.profit_gain(), 0.0, 6.87),
    ]
    for num, now, prev, ref in rows:
        line(scr, using(mask_of(num), now, prev, ref))
    scr.newline()
    line(scr, using(mask_of(330), 1))
    scr.newline()
    line(scr, "НАЧНИТЕ РАСПРЕДЕЛЕНИЕ ПРИБЫЛИ")
    line(scr, "------- ------------- -------")
    line(scr, using(mask_of(400), r.profit_gain())
              + "    СКОЛЬКО НА РАЗИТИЕ Н/Х? ")
    return scr, ("REGION.bas lines 160 to 400, opening position. "
                 "The right hand column is the program's own line 22.")


def profit_curve():
    """Lines 1510 to 1543, drawn exactly as the FOR loop draws it."""
    scr = Screen()
    line(scr, "ПРИБЫЛЬ РАСТЕТ ЗА СЧЕТ:")
    line(scr, "------- ------ -- ----")
    line(scr, "                             1.РАЗВИТИЯ Н/Х,")
    line(scr, "                             2.РОСТА НАСЕЛЕНИЯ.")
    scr.newline()
    line(scr, "                             Y-ПРИБЫЛЬ")
    i = 1.0
    while i <= 6.0001:
        tab(scr, 30, "I")
        tab(scr, int(78 - i * i), "$")
        tab(scr, int(79 - 6 * i), "*")
        scr.newline()
        i += 0.5
    line(scr, "                              " + "-" * 49)
    line(scr, "                                     " + " " * 40 + "X")
    scr.newline()
    line(scr, "            ГДЕ $ - ЗАВИСИМОСТЬ ИЗМЕНЕНИЯ ВЕЛИЧИНЫ ПРИБЫЛИ "
              "ОТ ЧИСЛ. НАСЕЛЕНИЯ.")
    line(scr, "                * - ЗАВИСИМОСТЬ ИЗМЕНЕНИЯ ВЕЛИЧИНЫ ПРИБЫЛИ "
              "ОТ РАЗВИТИЯ Н/Х.")
    return scr, "REGION.bas lines 1510 to 1543, its own plotting loop"


def pollution_curves():
    """Lines 1570 to 1601."""
    scr = Screen()
    line(scr, "УРОВЕНЬ ЗАГРЯЗНЕНИЯ ПОВЫШАЕТСЯ ЗА СЧЕТ РАЗВИТИЯ Н/Х,")
    line(scr, "УРОВЕНЬ ЗАГРЯЗНЕНИЯ ПОНИЖАЕТСЯ ЗА СЧЕТ СРЕДСТВ, "
              "ВЛОЖЕННЫХ В ПОДДЕРЖАНИЕ СРЕДЫ.")
    scr.newline()
    scr.newline()
    line(scr, " Y-УРОВЕНЬ ЗАГРЯЗНЕНИЯ                  Y-УРОВЕНЬ ЗАГРЯЗНЕНИЯ")
    i = 1.0
    while i <= 3.5001:
        tab(scr, 1, "I")
        tab(scr, int(32 - 2 * i * i), "$")
        tab(scr, 40, "I")
        tab(scr, int(40 + i * i * i), "*")
        scr.newline()
        i += 0.3
    line(scr, " " + "-" * 34 + "     " + "-" * 38)
    line(scr, "      РАЗВИТИЕ Н/Х                            "
              "КОЛИЧЕСТВО ВЛОЖЕННЫХ СРЕДСТВ")
    return scr, "REGION.bas lines 1570 to 1601, its own plotting loop"


def tipping():
    """
    The threshold crossed, with a policy that survives long enough to reach
    it: a fifth of the profit into the economy, a tenth into the
    environment, the rest into quality of life. The last column is the
    self cleaning term of lines 1250 to 1270, and it changes sign.
    """
    scr = Screen()
    line(scr, "20% В Н/Х, 10% В СРЕДУ, 70% В КАЧЕСТВО ЖИЗНИ")
    line(scr, "--- - ---  --- - ------ --- - -------- ------")
    scr.newline()
    line(scr, "  ТУР   ЗАГРЯЗНЕНИЕ   БЛАГОСОСТОЯНИЕ   НАСЕЛЕНИЕ   САМООЧИСТКА")
    line(scr, "  ---   -----------   --------------   ---------   -----------")
    r = Region()
    for _ in range(25):
        available = r.V + r.profit_gain()
        s = r.turn(available * 0.2, available * 0.1, available * 0.7, 0.0)
        pop = (f"{s['population']:9.2f}" if s["population"] > 0 else "     ----")
        mark = "  <-- ЗНАК" if s["cleaning"] > 0 else ""
        line(scr, f"{s['turn']:5d}{s['pollution']:14.2f}"
                  f"{s['prosperity']:17.2f}{pop:>12s}"
                  f"{s['cleaning']:14.2f}{mark}")
        if s["dead"]:
            line(scr, "        ВЫ ПОГУБИЛИ ВСЕ НАСЕЛЕНИЕ")
            break
    scr.newline()
    line(scr, "Строка 751 предупреждает на 35, и предупреждение видно с 14 тура.")
    line(scr, "О пороге 50 программа не говорит ничего. На 16 туре самоочистка")
    line(scr, "становится положительной: она уже не чистит, она добавляет.")
    return scr, ("Not a program screen. The figures come from model.py, the "
                 "re-implementation; the messages are the program's own.")


SCREENS = [
    ("title", title),
    ("state", state),
    ("profit-curve", profit_curve),
    ("pollution-curves", pollution_curves),
    ("tipping", tipping),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in SCREENS:
        scr, label = fn()
        path = os.path.join(OUT, f"{name}.png")
        to_png(scr, path, label)
        with open(os.path.join(OUT, f"{name}.txt"), "w", encoding="utf-8") as fh:
            fh.write(scr.render_text().rstrip() + "\n")
        print(f"{name}.png")


if __name__ == "__main__":
    main()
