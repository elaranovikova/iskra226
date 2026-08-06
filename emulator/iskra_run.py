#!/usr/bin/env python3
"""
iskra_run - a working Iskra-226 BASIC 02 interpreter.

Not a reconstruction of the CPU firmware: an independent, clean
implementation of the same BASIC-2 dialect, built to run the original
programs correctly. Loads a disk image, decodes the tokenized BASIC 02
program, and executes it on an 80x24 KOI-8 screen.

Ground truth for iteration: the 4,189 decoded source lines of the
STIPENDIYA payroll system and BAM database suite. When output is wrong
the responsible statement is directly visible, so the interpreter can
be debugged against real software.

Supported: PRINT (AT, TAB, ;/, separators, string/number/variable,
arithmetic), INPUT, LET and implicit assignment, IF/THEN relations,
GOTO, GOSUB/RETURN, ON..GOTO, REM, STOP/END, numeric and string
variables, and chain-loading between program segments.

Usage:
    python3 iskra_run.py <image.dsk> <FILE> [--auto a,b,c] [--trace]
    python3 iskra_run.py <image.dsk> <FILE> --screenshot out.png
"""

import sys
from iskra_basic import Disk, load_token_map, koi8, bcd2, find


class Screen:
    W, H = 80, 24

    def __init__(self):
        self.clear()

    def clear(self):
        self.buf = [[" "] * self.W for _ in range(self.H)]
        self.cx = self.cy = 0

    def _scroll(self):
        self.buf.pop(0)
        self.buf.append([" "] * self.W)
        self.cy = self.H - 1

    def at(self, row, col):
        self.cy = max(0, min(self.H - 1, row - 1))
        self.cx = max(0, min(self.W - 1, col - 1))

    def tab(self, col):
        self.cx = max(0, min(self.W - 1, col))

    def put(self, ch):
        if ch == "\r":
            self.cx = 0
        elif ch == "\n":
            self.newline()
        else:
            if self.cx >= self.W:
                self.newline()
            self.buf[self.cy][self.cx] = ch
            self.cx += 1

    def puts(self, s):
        for ch in s:
            self.put(ch)

    def newline(self):
        self.cx = 0
        self.cy += 1
        if self.cy >= self.H:
            self._scroll()

    def render_text(self):
        return "\n".join("".join(r).rstrip() for r in self.buf)


def parse_expr(pl, tokens):
    items = []
    i = 0
    while i < len(pl):
        b = pl[i]
        if b == 0xE1 and i + 7 < len(pl) and pl[i + 1] == 0x31 \
                and pl[i + 2] == 0xE8 and pl[i + 4] == 0xDE \
                and pl[i + 5] == 0xE8 and pl[i + 7] == 0xD0:
            # positioning atom  E1 31 (a, col):  observed only with a=1 in
            # the corpus (15 calls); role of the first argument unresolved.
            # Treated as tab-to-column; column values 11..80 match the
            # printed form layout (SELECT P routes to a 132-col printer).
            cc = pl[i + 6]
            items.append(("tab", (cc >> 4) * 10 + (cc & 0xF)))
            i += 8
        elif b == 0xE3 and i + 1 < len(pl):
            n = pl[i + 1]
            items.append(("str", koi8(pl[i + 2:i + 2 + n])))
            i += 2 + n
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
        elif b == 0xDF and i + 2 < len(pl) and pl[i + 1] == 0xE8:
            nn = pl[i + 2]
            items.append(("tab", (nn >> 4) * 10 + (nn & 0xF)))
            i += 4 if (i + 3 < len(pl) and pl[i + 3] == 0xD0) else 3
        elif b == 0xD3 and i + 2 < len(pl):
            items.append(("goto", bcd2(pl[i + 1], pl[i + 2])))
            i += 3
        elif b == 0xCD:
            i += 1
            tl = []
            while i + 1 < len(pl):
                ln = bcd2(pl[i], pl[i + 1])
                if ln is None:
                    break
                tl.append(ln)
                i += 2
            items.append(("gotolist", tl))
        elif b == 0xD9:
            items.append(("op", "=")); i += 1
        elif b == 0xD4:
            items.append(("op", ">")); i += 1
        elif b == 0xCF:
            items.append(("op", "<")); i += 1
        elif b in (0x2B, 0x2D, 0x2A, 0x2F):
            # context-sensitive: an operator only AFTER an operand;
            # otherwise these byte values are variable slots (0x2A-0x2F).
            # An array access  <slot> <idx> ')'  takes precedence.
            prev = items[-1][0] if items else None
            if prev in ("num", "str", "var", "aref", "rpar"):
                items.append(("op", chr(b)))
                i += 1
            elif i + 2 < len(pl) and pl[i + 1] < 0x60 \
                    and pl[i + 2] == 0xD0:
                items.append(("aref", b, pl[i + 1]))
                i += 3
            else:
                items.append(("var", b))
                i += 1
        elif b == 0xE7 and i + 2 < len(pl):
            # line-number reference (e.g. PRINTUSING image line)
            ref = bcd2(pl[i + 1], pl[i + 2])
            items.append(("lineref", ref)); i += 3
        elif b == 0xDD:
            items.append(("semi",)); i += 1
        elif b == 0xDE:
            items.append(("comma",)); i += 1
        elif b == 0xEB:
            items.append(("lpar",)); i += 1
        elif b == 0xD0:
            items.append(("rpar",)); i += 1
        elif b == 0xD1:
            items.append(("to",)); i += 1
        elif b < 0x60 and i + 2 < len(pl) and pl[i + 1] < 0x60 \
                and pl[i + 2] == 0xD0:
            # array access  <arr> <idx> ')'  ->  A_arr(V_idx)
            items.append(("aref", b, pl[i + 1])); i += 3
        elif b < 0x60:
            # Outside E3 strings every non-marker byte is a variable slot,
            # not ASCII text (digit bytes 0x30-0x39 are slots 48-57, not
            # the characters '0'-'9').
            items.append(("var", b)); i += 1
        else:
            items.append(("byte", b)); i += 1
    return items


def parse_line(rec, tokens):
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


class Interp:
    def __init__(self, disk, tokens, auto=None, trace=False):
        self.disk = disk
        self.tokens = tokens
        self.scr = Screen()
        self.nvars = {}
        self.svars = {}
        self.arrays = {}         # array slot -> {index: value}
        self.forstack = []       # (var, limit, line_pos, stmt_index)
        self.auto = list(auto) if auto else None
        self.auto_i = 0
        self.trace = trace
        self.gosub = []
        self.halted = False
        self.load_request = None

    def load_program(self, name):
        e = find(self.disk, name)
        if not e:
            return None
        body = self.disk.body(e)
        lines, order = {}, []
        # Find the first valid line header, then parse strictly sequentially.
        # (A find()-based or best-run scanner mis-synchronises on S2's long
        #  data-bearing lines, where embedded bytes look like BCD headers.)
        i = 0
        while i + 3 < len(body):
            ln = bcd2(body[i], body[i + 1])
            length = body[i + 2]
            if ln is not None and length and i + 3 + length <= len(body) \
                    and body[i + 2 + length] == 0xFE:
                break
            i += 1
        while i + 3 < len(body):
            ln = bcd2(body[i], body[i + 1])
            length = body[i + 2]
            if ln is None or length == 0 or i + 3 + length > len(body) \
                    or body[i + 2 + length] != 0xFE:
                i += 1
                continue
            rec = body[i + 3:i + 2 + length]
            if ln not in lines:
                if rec[:1] == b"\x3f":
                    # % image line: keep the raw mask text for PRINTUSING
                    mask = "".join(chr(c) if 0x20 <= c < 0x7F else " "
                                   for c in rec[2:])
                    lines[ln] = [("IMAGE", mask)]
                else:
                    lines[ln] = parse_line(rec, self.tokens)
                order.append(ln)
            i += 3 + length
        order.sort()
        return lines, order

    def eval_value(self, items, idx):
        it = items[idx]
        k = it[0]
        if k == "num":
            return it[1], idx + 1
        if k == "str":
            return it[1], idx + 1
        if k == "asc":
            s = it[1].strip()
            try:
                return int(s), idx + 1
            except ValueError:
                return it[1], idx + 1
        if k == "var":
            slot = it[1]
            if slot in self.svars:
                return self.svars[slot], idx + 1
            return self.nvars.get(slot, 0), idx + 1
        if k == "aref":
            arr, ivar = it[1], it[2]
            index = int(self.nvars.get(ivar, 0))
            return self.arrays.get(arr, {}).get(index, 0), idx + 1
        return 0, idx + 1

    def eval_expr(self, items, idx):
        val, idx = self.eval_value(items, idx)
        while idx < len(items) and items[idx][0] == "op" \
                and items[idx][1] in "+-*/":
            op = items[idx][1]
            rhs, idx = self.eval_value(items, idx + 1)
            try:
                if op == "+":
                    val = val + rhs
                elif op == "-":
                    val = val - rhs
                elif op == "*":
                    val = val * rhs
                elif op == "/":
                    val = val / rhs if rhs else 0
            except TypeError:
                val = str(val) + str(rhs)
        return val, idx

    def _fmt(self, v):
        if isinstance(v, float):
            return "%g" % v
        return str(v)

    def exec_print(self, items):
        i = 0
        trailing = False
        while i < len(items):
            k = items[i][0]
            if k == "at":
                self.scr.at(items[i][1], items[i][2]); i += 1; trailing = True
            elif k == "tab":
                self.scr.tab(items[i][1]); i += 1; trailing = True
            elif k in ("semi", "comma"):
                i += 1; trailing = True
            elif k in ("str", "asc"):
                self.scr.puts(items[i][1]); i += 1; trailing = False
            elif k in ("num", "var"):
                val, i = self.eval_expr(items, i)
                self.scr.puts(self._fmt(val)); trailing = False
            elif k in ("lpar", "rpar"):
                i += 1
            else:
                i += 1
        if not trailing:
            self.scr.newline()

    def exec_printusing(self, items, lines):
        """Formatted print through a % image line (E7 line reference)."""
        ref = None
        vals = []
        after_sep = False
        for it in items:
            if it[0] == "lineref":
                ref = it[1]
            elif it[0] == "semi":
                after_sep = True
            elif after_sep and it[0] in ("aref", "var", "num"):
                # arguments are the DD-separated items AFTER the reference
                # block (E7 ref DE <spec> DD arg DD arg ...); the bare byte
                # before the first separator is a spec, not an argument
                v, _ = self.eval_value([it], 0)
                vals.append(v)
        mask = ""
        if ref in lines and lines[ref] and lines[ref][0][0] == "IMAGE":
            mask = lines[ref][0][1]
        if not mask:
            self.scr.puts(" ".join(str(v) for v in vals))
            self.scr.newline()
            return
        out = []
        vi = 0
        i = 0
        while i < len(mask):
            if mask[i] == "#":
                j = i
                while j < len(mask) and mask[j] in "#.":
                    j += 1
                field = mask[i:j]
                v = vals[vi] if vi < len(vals) else 0
                vi += 1
                if "." in field:
                    dec = len(field) - field.index(".") - 1
                    s = ("%%.%df" % dec) % float(v)
                else:
                    s = "%d" % int(v)
                out.append(s.rjust(len(field))[:len(field)])
                i = j
            else:
                out.append(mask[i])
                i += 1
        self.scr.puts("".join(out))
        self.scr.newline()

    def exec_assign(self, items):
        if items and items[0][0] == "aref":
            arr, ivar = items[0][1], items[0][2]
            j = 1
            while j < len(items) and not (items[j][0] == "op"
                                          and items[j][1] == "="):
                j += 1
            if j >= len(items):
                return
            val, _ = self.eval_expr(items, j + 1)
            index = int(self.nvars.get(ivar, 0))
            self.arrays.setdefault(arr, {})[index] = val
            return
        if not items or items[0][0] != "var":
            return
        slot = items[0][1]
        j = 1
        while j < len(items) and not (items[j][0] == "op"
                                      and items[j][1] == "="):
            j += 1
        if j >= len(items):
            return
        val, _ = self.eval_expr(items, j + 1)
        if isinstance(val, str):
            self.svars[slot] = val
        else:
            self.nvars[slot] = val

    def eval_relation(self, items):
        left, j = self.eval_value(items, 0)
        if j >= len(items) or items[j][0] != "op":
            return None, None
        op = items[j][1]
        right, j = self.eval_value(items, j + 1)
        target = None
        for it in items[j:]:
            if it[0] == "goto":
                target = it[1]
            elif it[0] == "num" and target is None:
                target = it[1]
        try:
            if op == "=":
                cond = left == right
            elif op == ">":
                cond = left > right
            elif op == "<":
                cond = left < right
            else:
                cond = False
        except TypeError:
            cond = False
        return cond, target

    def get_input(self):
        if self.auto is not None:
            if self.auto_i >= len(self.auto):
                # scripted input exhausted: stop cleanly instead of feeding
                # a default that would take branches the user never chose
                self.halted = True
                return ""
            v = self.auto[self.auto_i]
            self.auto_i += 1
            return v
        try:
            return input("? ")
        except EOFError:
            self.halted = True
            return ""

    def run(self, name, max_steps=200000):
        loaded = self.load_program(name)
        if not loaded:
            self.scr.puts("NO PROGRAM %s" % name); self.scr.newline()
            return
        lines, order = loaded
        idx = {ln: k for k, ln in enumerate(order)}
        pos = 0
        steps = 0
        start_si = 0
        while pos < len(order) and steps < max_steps and not self.halted:
            ln = order[pos]
            jump = None
            stmts = lines[ln]
            si = start_si
            start_si = 0
            while si < len(stmts):
                st = stmts[si]
                nm = st[0]
                if nm == "REM":
                    si += 1
                    continue
                items = st[1]
                if self.trace:
                    sys.stderr.write("%4d %s %r\n" % (ln, nm, items))
                if nm == "PRINT":
                    self.exec_print(items)
                elif any(it[0] == "lineref" for it in items):
                    self.exec_printusing(items, lines)
                elif nm in ("LET", "", "S36"):
                    self.exec_assign(items)
                elif nm == "INPUT":
                    ans = self.get_input()
                    if self.halted:
                        break
                    # comma-separated answers fill the variables in order
                    # ("ЧЕРЕЗ ЗАПЯТУЮ: НОМЕР ГРУППЫ, ПОИМЕННЫЙ НОМЕР, ...")
                    parts = [p.strip() for p in str(ans).split(",")]
                    vslots = [it[1] for it in items if it[0] == "var"]
                    arefs = [it for it in items if it[0] == "aref"]
                    pi = 0
                    for slot in vslots:
                        if pi >= len(parts):
                            break
                        p = parts[pi]
                        pi += 1
                        try:
                            self.nvars[slot] = int(p)
                        except ValueError:
                            self.svars[slot] = p
                    for it in arefs:
                        if pi >= len(parts):
                            break
                        p = parts[pi]
                        pi += 1
                        arr, ivar = it[1], it[2]
                        index = int(self.nvars.get(ivar, 0))
                        try:
                            self.arrays.setdefault(arr, {})[index] = int(p)
                        except ValueError:
                            self.arrays.setdefault(arr, {})[index] = p
                elif nm == "IF":
                    cond, target = self.eval_relation(items)
                    if cond and target is not None:
                        jump = target
                        break
                elif nm == "GOTO":
                    for it in items:
                        if it[0] in ("goto", "num"):
                            jump = it[1]
                    if jump is not None:
                        break
                elif nm == "GOSUB":
                    for it in items:
                        if it[0] in ("goto", "num"):
                            self.gosub.append(pos)
                            jump = it[1]
                    if jump is not None:
                        break
                elif nm == "RETURN":
                    if self.gosub:
                        pos = self.gosub.pop()
                    break
                elif nm == "ON":
                    sel = None
                    targets = []
                    for it in items:
                        if it[0] == "var" and sel is None:
                            sel = self.nvars.get(it[1], 0)
                        elif it[0] == "gotolist":
                            targets = it[1]
                        elif it[0] in ("num", "goto"):
                            targets.append(it[1])
                    if sel and 1 <= sel <= len(targets):
                        jump = targets[sel - 1]
                        break
                elif nm == "FOR":
                    # 57 <len> <var> E8 <start> D1 <limit>
                    var = None
                    start = 1
                    limit = 0
                    seen_to = False
                    k = 0
                    while k < len(items):
                        it = items[k]
                        if it[0] == "var" and var is None:
                            var = it[1]
                            k += 1
                        elif it[0] == "to":
                            seen_to = True
                            k += 1
                        elif it[0] in ("num", "var", "aref"):
                            v, k = self.eval_value(items, k)
                            if seen_to:
                                limit = v
                            else:
                                start = v
                        else:
                            k += 1
                    if var is not None:
                        self.nvars[var] = start
                        # loop home: statement AFTER this FOR
                        self.forstack.append((var, limit, pos, si))
                elif nm == "NEXT":
                    var = None
                    for it in items:
                        if it[0] == "var":
                            var = it[1]
                    frame = None
                    for f in reversed(self.forstack):
                        if f[0] == var:
                            frame = f
                            break
                    if frame is not None:
                        fvar, limit, fpos, fsi = frame
                        self.nvars[fvar] = self.nvars.get(fvar, 0) + 1
                        if self.nvars[fvar] <= limit:
                            pos = fpos
                            start_si = fsi + 1
                            jump = None
                            si = None  # signal: position set manually
                            break
                        else:
                            self.forstack.remove(frame)
                elif nm in ("STOP", "END"):
                    self.halted = True
                    break
                elif nm in ("S7D", "LOAD", "S2D"):
                    seg = None
                    for it in items:
                        if it[0] == "str":
                            seg = it[1].strip()
                    if seg:
                        self.load_request = seg
                        self.halted = True
                        break
                si += 1
            steps += 1
            if si is None:
                continue        # NEXT set pos/start_si directly
            if jump is not None and jump in idx:
                new_pos = idx[jump]
                # A backward jump to a low line number is a full-screen
                # menu rebuild on the real 24-line terminal; clear so the
                # redraw does not overlay the previous frame. (Verified
                # against the known menu screenshots; not an invented
                # control byte.)
                if new_pos < pos and jump <= 100:
                    self.scr.clear()
                pos = new_pos
            else:
                pos += 1


def to_png(scr, path, label=""):
    from PIL import Image, ImageDraw, ImageFont
    CW, CH, PAD = 11, 22, 24
    extra = 30 if label else 0
    img = Image.new("RGB",
                    (scr.W * CW + 2 * PAD, scr.H * CH + 2 * PAD + extra),
                    (10, 12, 10))
    dr = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
        fs = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    except OSError:
        f = fs = ImageFont.load_default()
    dr.rectangle([PAD - 6, PAD - 6, scr.W * CW + PAD + 6,
                  scr.H * CH + PAD + 6], outline=(60, 90, 60), width=2)
    for y in range(scr.H):
        for x in range(scr.W):
            ch = scr.buf[y][x]
            if ch != " ":
                dr.text((PAD + x * CW, PAD + y * CH), ch, font=f,
                        fill=(150, 240, 150))
    if label:
        dr.text((PAD, scr.H * CH + PAD + 10), label, font=fs,
                fill=(120, 160, 120))
    img.save(path)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    path, name = argv[1], argv[2]
    auto = None
    if "--auto" in argv:
        raw = argv[argv.index("--auto") + 1]
        # ';' separates answers when a single answer itself contains commas
        auto = raw.split(";") if ";" in raw else raw.split(",")
    shot = argv[argv.index("--screenshot") + 1] if "--screenshot" in argv \
        else None
    trace = "--trace" in argv

    disk = Disk(path)
    tokens = load_token_map()
    it = Interp(disk, tokens, auto=auto, trace=trace)

    seg = name
    for _ in range(6):
        it.load_request = None
        it.halted = False
        it.run(seg)
        if it.load_request:
            seg = it.load_request
            it.scr.clear()      # a loaded segment starts on a fresh screen
        else:
            break

    if shot:
        to_png(it.scr, shot,
               "Iskra-226 BASIC 02  |  %s  |  iskra_run.py" % name)
        print("wrote %s" % shot)
    else:
        print(it.scr.render_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
