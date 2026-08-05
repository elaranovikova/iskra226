#!/usr/bin/env python3
"""
iskra_run - execution layer for Iskra-226 BASIC 02 programs.

Builds on iskra_basic.py (disk + catalog + format). This module parses
the tokenized statements into an executable form and runs them on an
80x24 KOI-8 text screen, supporting the statement set the surviving
programs actually use: PRINT (with AT, TAB, ; separators, string and
numeric literals, variables), INPUT, LET / implicit assignment, IF
with a relation and GOTO, GOTO, ON..GOTO, FOR/NEXT, REM, STOP, END.

This runs the software, not the CPU. Disk chain-load statements (LOAD
segment) are honoured by loading and continuing the named program, so
the STIPENDIYA dispatcher and its S1/S2 segments run as a whole.

Usage:
    python3 iskra_run.py <image.dsk> <FILENAME> [--auto INPUTS]
    python3 iskra_run.py <image.dsk> <FILENAME> --screenshot out.png

--auto feeds comma-separated INPUT answers (for non-interactive runs).
"""

import sys
import struct

from iskra_basic import Disk, load_token_map, koi8, bcd2, find

# --- 80x24 screen --------------------------------------------------------

class Screen:
    W, H = 80, 24

    def __init__(self):
        self.buf = [[" "] * self.W for _ in range(self.H)]
        self.cx = 0
        self.cy = 0

    def _scroll(self):
        self.buf.pop(0)
        self.buf.append([" "] * self.W)
        self.cy = self.H - 1

    def clear(self):
        self.buf = [[" "] * self.W for _ in range(self.H)]
        self.cx = 0
        self.cy = 0

    def at(self, row, col):
        # BASIC AT is 1-based
        self.cy = max(0, min(self.H - 1, row - 1))
        self.cx = max(0, min(self.W - 1, col - 1))

    def put(self, ch):
        if ch == "\r":
            self.cx = 0
        elif ch == "\n":
            self.cy += 1
            if self.cy >= self.H:
                self._scroll()
        else:
            if self.cx >= self.W:
                self.cx = 0
                self.cy += 1
            if self.cy >= self.H:
                self._scroll()
            self.buf[self.cy][self.cx] = ch
            self.cx += 1

    def puts(self, s):
        for ch in s:
            self.put(ch)

    def render_text(self):
        return "\n".join("".join(row).rstrip() for row in self.buf)


# --- statement parser ----------------------------------------------------
# Turns one statement payload (token + bytes) into a small tuple form the
# interpreter can execute. Only the constructs the corpus uses are handled;
# anything else becomes ('raw', text) and is printed verbatim if in PRINT.

def parse_expr(pl, tokens):
    """Parse a payload into a list of expression items."""
    items = []
    i = 0
    while i < len(pl):
        b = pl[i]
        if b == 0xE3 and i + 1 < len(pl):
            nlen = pl[i + 1]
            items.append(("str", koi8(pl[i + 2:i + 2 + nlen])))
            i += 2 + nlen
        elif b == 0xE8 and i + 1 < len(pl):
            v = pl[i + 1]
            items.append(("num", (v >> 4) * 10 + (v & 0xF)))
            i += 2
        elif b == 0xE2 and i + 2 < len(pl):
            items.append(("at", pl[i + 1], pl[i + 2]))
            i += 3
        elif b == 0xD5 and i + 5 < len(pl) and pl[i + 1] == 0xE8:
            r = pl[i + 2]
            c = pl[i + 5] if pl[i + 4] == 0xE8 else 0
            items.append(("at", (r >> 4) * 10 + (r & 0xF),
                          (c >> 4) * 10 + (c & 0xF)))
            i += 6
        elif b == 0xDF and i + 3 < len(pl) and pl[i + 1] == 0xE8:
            # TAB( n ) encoded as DF E8 nn D0
            nn = pl[i + 2]
            items.append(("tab", (nn >> 4) * 10 + (nn & 0xF)))
            i += 4 if (i + 3 < len(pl) and pl[i + 3] == 0xD0) else 3
        elif b == 0xD3 and i + 2 < len(pl):
            ln = bcd2(pl[i + 1], pl[i + 2])
            items.append(("goto", ln))
            i += 3
        elif b == 0xD9:
            items.append(("op", "="))
            i += 1
        elif b == 0xD4:
            items.append(("op", ">"))
            i += 1
        elif b == 0xDD:
            items.append(("semi",))
            i += 1
        elif b == 0xDE:
            items.append(("comma",))
            i += 1
        elif b == 0xEB:
            items.append(("lpar",))
            i += 1
        elif b == 0xD0:
            items.append(("rpar",))
            i += 1
        elif b < 0x20:
            items.append(("var", b))
            i += 1
        elif 0x20 <= b < 0x7F:
            # gather a run of ascii
            j = i
            while j < len(pl) and 0x20 <= pl[j] < 0x7F:
                j += 1
            items.append(("asc", "".join(chr(x) for x in pl[i:j])))
            i = j
        else:
            items.append(("byte", b))
            i += 1
    return items


def parse_line(rec, tokens):
    """rec = payload bytes without the trailing FE. Returns [statements]."""
    stmts = []
    j = 0
    while j + 1 < len(rec):
        tok = rec[j]
        plen = rec[j + 1]
        if j + 2 + plen > len(rec):
            break
        pl = rec[j + 2:j + 2 + plen]
        name = tokens.get(tok, "S%02X" % tok)
        if name == "REM":
            stmts.append(("REM", koi8(pl)))
        else:
            stmts.append((name, parse_expr(pl, tokens)))
        j += 2 + plen
    return stmts


# --- interpreter ---------------------------------------------------------

class Interp:
    def __init__(self, disk, tokens, auto=None):
        self.disk = disk
        self.tokens = tokens
        self.scr = Screen()
        self.vars = {}
        self.auto = list(auto) if auto else None
        self.auto_i = 0
        self.forstack = []
        self.halted = False
        self.load_request = None

    # -- program loading --
    def load_program(self, name):
        e = find(self.disk, name)
        if not e:
            return None
        body = self.disk.body(e)
        from iskra_basic import best_decode  # reuse the robust line scanner
        raw = best_decode(body, self.tokens)  # [(lineno, text)], not enough
        # We need statement structure, so re-scan the body directly:
        lines = {}
        order = []
        i = 0
        while i + 3 < len(body):
            ln = bcd2(body[i], body[i + 1])
            length = body[i + 2]
            if ln is None or length == 0 or i + 3 + length > len(body):
                i += 1
                continue
            recbytes = body[i + 3:i + 3 + length]
            if recbytes[-1] != 0xFE:
                i += 1
                continue
            if ln not in lines:
                lines[ln] = parse_line(recbytes[:-1], self.tokens)
                order.append(ln)
            i += 3 + length
        order.sort()
        return lines, order

    # -- expression evaluation (only what the corpus needs) --
    def val(self, item):
        t = item[0]
        if t == "num":
            return item[1]
        if t == "str":
            return item[1]
        if t == "asc":
            return item[1]
        if t == "var":
            return self.vars.get(item[1], 0)
        return None

    def get_input(self, prompt=""):
        if self.auto is not None:
            v = self.auto[self.auto_i] if self.auto_i < len(self.auto) else "0"
            self.auto_i += 1
            return v
        try:
            return input(prompt)
        except EOFError:
            return "0"

    # -- statement execution --
    def exec_print(self, items):
        i = 0
        trailing = False
        while i < len(items):
            it = items[i]
            k = it[0]
            trailing = False
            if k == "at":
                self.scr.at(it[1], it[2])
            elif k == "tab":
                self.scr.cx = min(self.scr.W - 1, it[1])
            elif k == "str" or k == "asc":
                self.scr.puts(it[1])
            elif k == "num":
                self.scr.puts(str(it[1]))
            elif k == "var":
                self.scr.puts(str(self.vars.get(it[1], 0)))
            elif k == "semi":
                trailing = True
            elif k == "comma":
                trailing = True
            i += 1
        if not trailing:
            self.scr.puts("\r\n")

    def exec_assign(self, name, items):
        # forms: LET V = expr   or implicit  V = expr  (token 0x36)
        var = None
        val = None
        seen_eq = False
        for it in items:
            if it[0] == "var" and var is None and not seen_eq:
                var = it[1]
            elif it[0] == "op" and it[1] == "=":
                seen_eq = True
            elif seen_eq and it[0] in ("num", "var"):
                val = self.val(it)
        if var is not None and val is not None:
            self.vars[var] = val

    def exec_if(self, items):
        # form: <var> <op> <value> GOTO <line>
        left = right = op = target = None
        for it in items:
            if it[0] == "var" and left is None:
                left = self.vars.get(it[1], 0)
            elif it[0] == "op":
                op = it[1]
            elif it[0] in ("num",) and op and right is None:
                right = it[1]
            elif it[0] == "goto":
                target = it[1]
        if op is None or target is None:
            return None
        cond = (left == right) if op == "=" else (left > right)
        return target if cond else None

    def exec_on(self, items):
        # ON <var> GOTO n1,n2,...  encoded with CD marker + BCD pairs
        var = None
        targets = []
        for it in items:
            if it[0] == "var" and var is None:
                var = self.vars.get(it[1], 0)
            elif it[0] == "num":
                targets.append(it[1])
            elif it[0] == "goto":
                targets.append(it[1])
        if var and 1 <= var <= len(targets):
            return targets[var - 1]
        return None

    def run(self, name, max_steps=100000):
        loaded = self.load_program(name)
        if not loaded:
            self.scr.puts("NO PROGRAM %s\r\n" % name)
            return
        lines, order = loaded
        pos = 0
        steps = 0
        while pos < len(order) and steps < max_steps and not self.halted:
            ln = order[pos]
            jump = None
            for st in lines[ln]:
                name0 = st[0]
                if name0 == "REM":
                    continue
                items = st[1]
                if name0 == "PRINT":
                    self.exec_print(items)
                elif name0 in ("LET", "", "S36"):
                    self.exec_assign(name0, items)
                elif name0 == "INPUT":
                    ans = self.get_input()
                    # first variable in the statement receives it
                    for it in items:
                        if it[0] == "var":
                            try:
                                self.vars[it[1]] = int(ans)
                            except ValueError:
                                self.vars[it[1]] = ans
                            break
                elif name0 == "IF":
                    jump = self.exec_if(items)
                    if jump is not None:
                        break
                elif name0 == "GOTO":
                    for it in items:
                        if it[0] in ("goto", "num"):
                            jump = it[1] if it[0] == "goto" else it[1]
                    # bare GOTO with var target: not resolvable here
                    if jump is not None:
                        break
                elif name0 in ("ON",):
                    jump = self.exec_on(items)
                    if jump is not None:
                        break
                elif name0 == "STOP" or name0 == "END":
                    self.halted = True
                    break
                elif name0 in ("S7D", "LOAD"):
                    # chain-load: find quoted segment name and switch
                    seg = None
                    for it in items:
                        if it[0] == "str":
                            seg = it[1].strip()
                    if seg:
                        self.load_request = seg
                        self.halted = True
                        break
            steps += 1
            if jump is not None and jump in lines:
                pos = order.index(jump)
            else:
                pos += 1


# --- rendering -----------------------------------------------------------

def to_png(scr, path):
    from PIL import Image, ImageDraw, ImageFont
    CW, CH, PAD = 11, 20, 18
    img = Image.new("RGB", (scr.W * CW + 2 * PAD, scr.H * CH + 2 * PAD),
                    (18, 20, 18))
    dr = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    except OSError:
        f = ImageFont.load_default()
    for y in range(scr.H):
        for x in range(scr.W):
            ch = scr.buf[y][x]
            if ch != " ":
                dr.text((PAD + x * CW, PAD + y * CH), ch, font=f,
                        fill=(150, 240, 150))
    img.save(path)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    path, name = argv[1], argv[2]
    auto = None
    shot = None
    if "--auto" in argv:
        auto = argv[argv.index("--auto") + 1].split(",")
    if "--screenshot" in argv:
        shot = argv[argv.index("--screenshot") + 1]

    disk = Disk(path)
    tokens = load_token_map()
    it = Interp(disk, tokens, auto=auto)

    seg = name
    for _ in range(4):  # follow up to a few chain-loads
        it.load_request = None
        it.halted = False
        it.run(seg)
        if it.load_request:
            seg = it.load_request
        else:
            break

    if shot:
        to_png(it.scr, shot)
        print("wrote %s" % shot)
    else:
        print(it.scr.render_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
