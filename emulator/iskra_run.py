#!/usr/bin/env python3
"""
iskra_run - a working Iskra-226 BASIC 02 interpreter.

Not a reconstruction of the CPU firmware: an independent, clean
implementation of the same BASIC-2 dialect, built to run the original
programs correctly. Loads a disk image, decodes the tokenized BASIC 02
program, and executes it on an 80x24 KOI-8 screen.

Ground truth for iteration: the 5,842 decoded source lines of the
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

import math
import random
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


# Function tokens: the firmware name area at 0x1A4D lists ABS( INT( RND(
# SGN( SQR( LOG( EXP( SIN( COS( TAN( in fixed order and the token values
# run consecutively from 0xF2. Corpus proof: ABS clamps |r|>=1 and SGN
# rebuilds the sign (STAT01:650), INT rounds via INT(W+0.50)
# (WILCOX:1565), SQR forms the standard errors SQR(N), SQR(N-1),
# SQR(2(N-1)) (STAT01:510), LOG accumulates LOG(x)^2 in the linearised
# regression (STAT01:540).
FN_NAMES = {0xF2: "ABS", 0xF3: "INT", 0xF4: "RND", 0xF5: "SGN",
            0xF6: "SQR", 0xF7: "LOG", 0xF8: "EXP", 0xF9: "SIN",
            0xFA: "COS", 0xFB: "TAN"}


def _is_bcd(b):
    return (b >> 4) <= 9 and (b & 0xF) <= 9


def parse_expr(pl, tokens):
    items = []
    i = 0
    while i < len(pl):
        b = pl[i]
        if b == 0xE1 and i + 3 < len(pl):
            # STR() substring atom (CORRECTED from the earlier tab reading:
            # the zero-suppression routine at 4000+ compares and ASSIGNS
            # through this atom, which is unambiguous substring semantics).
            #   E1 <slot> (pos,len)            -> STR(Vslot, pos, len)
            #   E1 <arr> <idx> D0 (pos,len)    -> STR(Aarr(Vidx), pos, len)
            opnd = None
            j = i + 1
            if j + 2 < len(pl) and pl[j] < 0x80 and pl[j + 1] < 0x80 \
                    and pl[j + 2] == 0xD0:
                opnd = ("aref", pl[j], pl[j + 1]); j += 3
            elif pl[j] < 0x80:
                opnd = ("var", pl[j]); j += 1
            def _arg(a, off):
                # a position/length argument: E8 <bcd>, E7 <bcd><bcd>,
                # or a variable slot
                if off < len(pl) and pl[off] == 0xE8 and off + 1 < len(pl):
                    v0 = pl[off + 1]
                    return ("num", (v0 >> 4) * 10 + (v0 & 0xF)), off + 2
                if off < len(pl) and pl[off] == 0xE7 and off + 2 < len(pl):
                    return ("num", bcd2(pl[off + 1], pl[off + 2])), off + 3
                if off < len(pl) and pl[off] < 0x80:
                    return ("var", pl[off]), off + 1
                return None, off
            if opnd == ("var", 0x31):
                # E1 is a generic function atom; id 0x31 = AT(rows, col):
                # on the printer a line-feed count plus column (this is
                # the definitive reading of the long-debated E1-31 -
                # the STR() reading applies to the aref form only)
                a1, j2 = _arg(pl, j)
                if a1 is not None and j2 < len(pl) and pl[j2] == 0xDE:
                    a2, j3 = _arg(pl, j2 + 1)
                    if a2 is not None and j3 < len(pl) \
                            and pl[j3] == 0xD0:
                        items.append(("at2", a1, a2))
                        i = j3 + 1
                        continue
            if opnd is not None:
                a1, j2 = _arg(pl, j)
                if a1 is not None and j2 < len(pl) and pl[j2] == 0xDE:
                    a2, j3 = _arg(pl, j2 + 1)
                    if a2 is not None and j3 < len(pl) \
                            and pl[j3] == 0xD0:
                        items.append(("strfn", opnd, a1, a2))
                        i = j3 + 1
                        continue
            items.append(("byte", b)); i += 1
        elif b == 0xE3 and i + 1 < len(pl):
            n = pl[i + 1]
            items.append(("str", koi8(pl[i + 2:i + 2 + n])))
            i += 2 + n
        elif b in (0xEA, 0xEE, 0xEB, 0xE4, 0xDF) and items \
                and items[-1][0] in (
                "num", "str", "var", "aref", "arefl", "rpar", "strfn",
                "lineref", "lenfn", "divfn"):
            # arithmetic operators in operand position.
            #   EA = +   (16 accumulator patterns "X = X EA ...", 4 of
            #             them "X = X EA 1"; E9 appears once)
            #   EE, EB, E4 are the remaining high-frequency binary
            #   operators; mapped by frequency to * , - , / , tentative,
            #   only EA is corpus-proven.
            items.append(("op", {0xEA: "+", 0xEE: "*",
                                 0xEB: "-", 0xE4: "/",
                                 0xDF: "*"}[b]))
            i += 1
        elif b == 0xE9 and items and items[-1][0] in (
                "num", "str", "var", "aref", "arefl", "rpar", "strfn",
                "lineref", "lenfn", "divfn"):
            # E9 after an OPERAND is binary minus; after an operator or at
            # the start of an expression it introduces a negative literal
            # (the "-1" end code). The earlier lookahead-based rule
            # mis-read "X - 1" at the end of a payload as "X" plus a
            # stray -1, retracted.
            items.append(("op", "-")); i += 1
        elif b == 0xE9 and i + 2 < len(pl) and pl[i + 1] == 0xE8:
            # unary minus:  E9 E8 <bcd>  ->  negative numeric literal
            v = pl[i + 2]
            items.append(("num", -((v >> 4) * 10 + (v & 0xF))))
            i += 3
        elif b == 0xE9:
            # unary minus before a variable, paren or function (REGION's
            # -L and -(...) forms); eval_rex applies it with the right
            # precedence
            items.append(("op", "-")); i += 1
        elif b == 0xE8 and i + 1 < len(pl):
            v = pl[i + 1]
            items.append(("num", (v >> 4) * 10 + (v & 0xF)))
            i += 2
        elif b == 0xE2 and i + 1 < len(pl) and pl[i + 1] >= 1 \
                and i + 2 + pl[i + 1] <= len(pl):
            # HEX( with a LENGTH byte, then that many raw bytes. The old
            # compact-AT reading (fixed two bytes) is refuted by the
            # corpus: E2 01 03 clears the screen in LFORMAT:1530, E2 01
            # 12 / E2 01 11 bracket the input prompt in S0:190, klerk's
            # tools carry seven-byte escape sequences E2 07 1B ...  The
            # AT reading survived because S0's E2 02 03 07 happened to
            # parse as a row/column pair.
            n = pl[i + 1]
            items.append(("hexs", bytes(pl[i + 2:i + 2 + n])))
            i += 2 + n
        elif b == 0xD5 and i + 6 < len(pl) and pl[i + 1] == 0xE8 \
                and pl[i + 3] == 0xDE and pl[i + 4] == 0xE8 \
                and pl[i + 6] == 0xD0:
            # full AT( row , col ) form:  D5 E8 rr DE E8 cc D0
            r = pl[i + 2]; c = pl[i + 5]
            items.append(("at", (r >> 4) * 10 + (r & 0xF),
                          (c >> 4) * 10 + (c & 0xF)))
            i += 7
        elif b == 0xD5:
            # outside the AT form, D5 is the "not equal" relation
            items.append(("op", "<>")); i += 1
        elif b == 0xDF and i + 2 < len(pl) and pl[i + 1] == 0xE8:
            nn = pl[i + 2]
            items.append(("tab", (nn >> 4) * 10 + (nn & 0xF)))
            i += 4 if (i + 3 < len(pl) and pl[i + 3] == 0xD0) else 3
        elif b == 0xDF:
            # TAB( with a full expression argument (TAB(V17) in
            # STAT01:60, TAB(78-I*I) in REGION); the closing rpar stays
            # in the stream and ends the argument. The operand-position
            # multiplication reading is handled above.
            items.append(("tabx",))
            i += 1
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
        elif b == 0xD6:
            # <= by the firmware relation order D4 > D5 <> D6 <= D7 >=;
            # in DBACKSPACE context the same byte is the BEG suffix and
            # is recognised there by item value.
            items.append(("op", "<=")); i += 1
        elif b == 0xD7:
            # >=, proven by IF ABS(A0A(I)) >= 1 THEN clamp (STAT01:650);
            # doubles as the END suffix in DSKIP.
            items.append(("op", ">=")); i += 1
        elif b == 0xDC:
            # the power operator: A03(I)^A06(I) and X^(N-1) in the
            # polynomial regression (STAT01:860, STAT01A:550), and
            # FOR V4E = V3E^2-1 ... (LVSTAV:1050)
            items.append(("op", "^")); i += 1
        elif b == 0xD2:
            # STEP in FOR: 60 5F D1 E8 01 D2 E9 E8 01 is
            # FOR V60 = V5F TO 1 STEP -1 (LFORMAT:1400)
            items.append(("stepmark",)); i += 1
        elif b in FN_NAMES:
            items.append(("func", FN_NAMES[b])); i += 1
        elif b == 0xE5 and i + 1 < len(pl) and _is_bcd(pl[i + 1]) \
                and pl[i + 1] != 0:
            # the general numeric literal: E5 <ab> <digit nibbles...>
            # with a integer and b fraction digits, right-padded to whole
            # bytes, trailing zero bytes droppable. Verified against 60+
            # corpus constants: 0.5, 0.05, 0.01, 0.999, 1.96 and 2.58
            # side by side (WILCOX:2055), 3.14, 0.301 = log10(2).
            a2 = pl[i + 1] >> 4
            b2 = pl[i + 1] & 0xF
            need = (a2 + b2 + 1) // 2
            digs = []
            j = i + 2
            while j < len(pl) and len(digs) < 2 * need and _is_bcd(pl[j]):
                digs += [pl[j] >> 4, pl[j] & 0xF]
                j += 1
            while len(digs) < a2 + b2:
                digs.append(0)
            ip = "".join(map(str, digs[:a2])) or "0"
            fp = "".join(map(str, digs[a2:a2 + b2]))
            items.append(("num", float(ip + "." + fp) if fp else
                          float(ip)))
            i = j
        elif b in (0x2B, 0x2D, 0x2A, 0x2F):
            # context-sensitive: an operator only AFTER an operand;
            # otherwise these byte values are variable slots (0x2A-0x2F).
            # An array access  <slot> <idx> ')'  takes precedence.
            prev = items[-1][0] if items else None
            if prev in ("num", "str", "var", "aref", "rpar"):
                items.append(("op", chr(b)))
                i += 1
            elif i + 3 < len(pl) and pl[i + 1] == 0xE8 \
                    and pl[i + 3] == 0xD0:
                v = pl[i + 2]
                items.append(("arefl", b, (v >> 4) * 10 + (v & 0xF)))
                i += 4
            elif i + 2 < len(pl) and pl[i + 1] < 0x80 \
                    and pl[i + 2] == 0xD0:
                items.append(("aref", b, pl[i + 1]))
                i += 3
            else:
                items.append(("var", b))
                i += 1
        elif b == 0xED and i + 3 < len(pl) and pl[i + 1] < 0x80 \
                and pl[i + 2] < 0x80 and pl[i + 3] == 0xD0:
            # ED <aref> = LEN(), proven by line 3192: the last character
            # of the name (position LEN, length 1) is tested against "*"
            items.append(("lenfn", ("aref", pl[i + 1], pl[i + 2])))
            i += 4
        elif b == 0xE5 and i + 2 < len(pl) and pl[i + 1] < 0x80 \
                and pl[i + 2] < 0x80:
            # E5 <a> <b> = a / b, the pro-rata factor (worked days over
            # month days) at line 3194; full-month students carry a "*"
            items.append(("divfn", pl[i + 1], pl[i + 2]))
            i += 3
        elif b == 0xD8 and i + 1 < len(pl):
            # D8 <expr> ( , n ) = ROUND to n decimals (line 3200 rounds
            # the pro-rated wage to 2 places)
            items.append(("roundfn",))
            i += 1
        elif b == 0xE0 and i + 1 < len(pl) and pl[i + 1] < 0x80:
            # whole-array reference in disk-I/O argument lists
            items.append(("whole", pl[i + 1])); i += 2
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
        elif b < 0x80 and i + 3 < len(pl) and pl[i + 1] == 0xE8 \
                and pl[i + 3] == 0xD0:
            # array access with a literal index:  <arr> E8 <bcd> ')'
            v = pl[i + 2]
            items.append(("arefl", b, (v >> 4) * 10 + (v & 0xF)))
            i += 4
        elif b < 0x80 and i + 2 < len(pl) and pl[i + 1] < 0x80 \
                and pl[i + 2] == 0xD0:
            # array access  <arr> <idx> ')'  ->  A_arr(V_idx)
            items.append(("aref", b, pl[i + 1])); i += 3
        elif b < 0x80:
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
        elif name in ("GOTO", "GOSUB") and plen == 2:
            # standalone GOTO/GOSUB carry the target as a raw BCD pair
            # (no D3 marker, unlike branch targets embedded in IF)
            tgt = bcd2(pl[0], pl[1])
            stmts.append((name, [("goto", tgt)]))
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
        self.diskrecs = []       # virtual record store (persists across
        self.recptr = 0          #  segment chain-loads, like the real disk)
        self.eof_goto = None     # target set by the 1E on-end statement
        self.print_device = 5    # SELECT PRINT device: 5 = console (80),
        self.print_width = 80    #  12 = line printer (132 columns)
        self.printer = []        # captured printer output, line by line
        self._pline = ""
        self._pg = {}            # printer page grid: row -> {col: char}
        self._prow = 0
        self._pcol = 0
        # --- communication line, device 015 -------------------------
        # Writing to device 015 sends a line to the host; the host's
        # reply is queued and delivered to the program through INPUT,
        # one line per INPUT, terminated by a single "." line.
        self.comm_out = []       # lines written by the program
        self._cline = ""         # partial line on the comm device
        self.comm_in = []        # reply lines waiting to be INPUT
        self.llm_handler = None  # callable(str) -> str, set by the host
        # --- keyboard buffer for KEYIN --------------------------------
        # Non-blocking: get_key() returns None when nothing is pending,
        # which is what makes the poll loop in the corpus work.
        self.keys = []           # pending keystrokes, consumed in order
        self.key_source = None   # optional callable() -> key or None
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
                    # % image line: keep the mask text for PRINTUSING.
                    # Decoded through the KOI-8 map: REGION's masks carry
                    # their Cyrillic labels inside the image line.
                    mask = koi8(rec[2:])
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
        if k == "arefl":
            return self.arrays.get(it[1], {}).get(it[2], 0), idx + 1
        if k == "lenfn":
            base, _ = self.eval_value([it[1]], 0)
            return len(str(base).rstrip()), idx + 1
        if k == "divfn":
            a = self.nvars.get(it[1], 0)
            b = self.nvars.get(it[2], 0)
            try:
                return (float(a) / float(b)) if float(b) else 0, idx + 1
            except (TypeError, ValueError):
                return 0, idx + 1
        if k == "roundfn":
            # ROUND(x, n): evaluate the inner expression, then read the
            # decimal count from the following ( , n ) group
            v, j = self.eval_value(items, idx + 1)
            n2 = 2
            while j < len(items):
                if items[j][0] == "num":
                    n2 = items[j][1]; j += 1
                elif items[j][0] in ("comma", "rpar", "lpar"):
                    j += 1
                else:
                    break
            try:
                return round(float(v), int(n2)), j
            except (TypeError, ValueError):
                return 0, j
        if k == "hexs":
            # in value position a HEX string is its characters (BAM3:331
            # assigns a pseudographic ruler to a string variable)
            return koi8(it[1]), idx + 1
        if k == "lineref":
            # E7 <bcd><bcd> is a 4-digit numeric literal in expressions;
            # the same encoding serves as a line reference in PRINTUSING
            return it[1], idx + 1
        if k == "strfn":
            base, _ = self.eval_value([it[1]], 0)
            s = str(base)
            pos, _ = self.eval_value([it[2]], 0)
            ln2, _ = self.eval_value([it[3]], 0)
            pos = int(pos) if pos else 1
            ln2 = int(ln2) if ln2 else 1
            return s[pos - 1:pos - 1 + ln2], idx + 1
        return 0, idx + 1

    @staticmethod
    def _apply_fn(name, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0
        try:
            if name == "ABS":
                return abs(v)
            if name == "INT":
                return float(math.floor(v))
            if name == "SGN":
                return (v > 0) - (v < 0)
            if name == "SQR":
                return math.sqrt(v) if v >= 0 else 0
            if name == "LOG":
                return math.log(v) if v > 0 else 0
            if name == "EXP":
                return math.exp(v)
            if name == "RND":
                return random.random()
            if name == "SIN":
                return math.sin(v)
            if name == "COS":
                return math.cos(v)
            if name == "TAN":
                return math.tan(v)
        except (OverflowError, ValueError):
            return 0
        return 0

    def eval_rex(self, items, idx):
        """Recursive-descent evaluation with real precedence:
        unary minus over a power, ^ (right associative), then * /,
        then + -. Leaves go through eval_value, so array references,
        STR() and the corpus specials keep their existing behaviour."""

        def prim(i):
            if i >= len(items):
                return 0, i
            it = items[i]
            if it[0] == "op" and it[1] == "-":
                v, j = powr(i + 1)
                try:
                    return -v, j
                except TypeError:
                    return 0, j
            if it[0] == "op" and it[1] == "+":
                return powr(i + 1)
            if it[0] == "lpar":
                v, j = summ(i + 1)
                if j < len(items) and items[j][0] == "rpar":
                    j += 1
                return v, j
            if it[0] == "func":
                v, j = summ(i + 1)
                if j < len(items) and items[j][0] == "rpar":
                    j += 1
                return self._apply_fn(it[1], v), j
            if it[0] == "roundfn":
                v, j = self.eval_value(items, i)
                return v, j
            return self.eval_value(items, i)

        def powr(i):
            v, j = prim(i)
            if j < len(items) and items[j] == ("op", "^"):
                r, j = powr(j + 1)
                # unary minus binds looser than the power: -3^x is
                # -(3^x). The parser folds E9 E8 03 into the literal -3,
                # so the sign is peeled off again here.
                neg = (items[i][0] == "num" and i + 1 == j - 1 - 0
                       and isinstance(v, (int, float)) and v < 0)
                neg = (items[i][0] == "num"
                       and isinstance(v, (int, float)) and v < 0)
                try:
                    base = -v if neg else v
                    v = float(base) ** float(r)
                    if neg:
                        v = -v
                except (TypeError, ValueError, OverflowError,
                        ZeroDivisionError):
                    v = 0
                if isinstance(v, complex):
                    v = 0
            return v, j

        def term(i):
            v, j = powr(i)
            while j < len(items) and items[j][0] == "op" \
                    and items[j][1] in "*/":
                op = items[j][1]
                r, j = powr(j + 1)
                try:
                    if op == "*":
                        v = v * r
                    else:
                        v = v / r if r else 0
                except TypeError:
                    v = 0
            return v, j

        def summ(i):
            v, j = term(i)
            while j < len(items) and items[j][0] == "op" \
                    and items[j][1] in "+-":
                op = items[j][1]
                r, j = term(j + 1)
                try:
                    if op == "+":
                        v = v + r
                    else:
                        v = v - r
                except TypeError:
                    v = str(v) + str(r)
            return v, j

        return summ(idx)

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

    def _pr(self, s):
        """Emit to the currently selected device. The printer keeps a
        2-D page (the form is laid out with AT(row,col)), flushed to
        self.printer line by line via _pr_flush."""
        if self.print_device == 15:
            self._cline += str(s)
        elif self.print_device == 12:
            row = self._pg.setdefault(self._prow, {})
            for ch in str(s):
                row[self._pcol] = ch
                self._pcol += 1
        else:
            self.scr.puts(s)

    def _pr_nl(self):
        if self.print_device == 15:
            if self._cline:
                self.comm_out.append(self._cline)
            self._cline = ""
        elif self.print_device == 12:
            self._prow += 1
            self._pcol = 0
        else:
            self.scr.newline()

    def _pr_tab(self, col):
        if self.print_device == 12:
            self._pcol = max(self._pcol, col)
        else:
            self.scr.tab(col)

    def _pr_at(self, row, col):
        if self.print_device == 12:
            # On the line printer AT(n, col) cannot seek: the first
            # argument is a LINE-FEED count (always 1 in the corpus -
            # resolving the long-open question of its role), the second
            # the column on the new line.
            self._prow += max(1, row)
            self._pcol = max(0, col)
        else:
            self.scr.at(row, col)

    def _comm_flush(self):
        """Hand the buffered question to the host and queue the reply."""
        if self._cline:
            self.comm_out.append(self._cline)
            self._cline = ""
        if not self.comm_out:
            return
        question = "\n".join(self.comm_out)
        self.comm_out = []
        if self.llm_handler is None:
            reply = "СВЯЗЬ НЕ УСТАНОВЛЕНА"
        else:
            try:
                reply = self.llm_handler(question)
            except Exception as exc:                # noqa: BLE001
                reply = "ОШИБКА СВЯЗИ: %s" % exc
        for ln in str(reply).split("\n"):
            self.comm_in.append(ln)
        self.comm_in.append(".")

    def _pr_flush(self):
        """Convert the accumulated printer page into text lines."""
        if not self._pg:
            return
        top = min(self._pg)
        bottom = max(self._pg)
        for r in range(top, bottom + 1):
            row = self._pg.get(r, {})
            if row:
                w = max(row) + 1
                line = "".join(row.get(c, " ") for c in range(w))
            else:
                line = ""
            self.printer.append(line.rstrip())
        self._pg = {}
        self._prow = 0
        self._pcol = 0

    def exec_print(self, items):
        i = 0
        trailing = False
        while i < len(items):
            k = items[i][0]
            if k == "at":
                self._pr_at(items[i][1], items[i][2]); i += 1; trailing = True
            elif k == "at2":
                r2, _ = self.eval_value([items[i][1]], 0)
                c2, _ = self.eval_value([items[i][2]], 0)
                self._pr_at(int(r2 or 1), int(c2 or 0))
                i += 1; trailing = True
            elif k == "tab":
                self._pr_tab(items[i][1]); i += 1; trailing = True
            elif k == "tabx":
                v, j = self.eval_rex(items, i + 1)
                if j < len(items) and items[j][0] == "rpar":
                    j += 1
                try:
                    self._pr_tab(int(v))
                except (TypeError, ValueError):
                    pass
                i = j; trailing = True
            elif k == "hexs":
                self._exec_hex(items[i][1]); i += 1; trailing = True
            elif k in ("semi", "comma"):
                i += 1; trailing = True
            elif k in ("str", "asc"):
                self._pr(items[i][1]); i += 1; trailing = False
            elif k in ("num", "var", "aref", "arefl", "func") \
                    or (k == "op" and items[i][1] == "-"):
                val, i = self.eval_rex(items, i)
                self._pr(self._fmt(val)); trailing = False
            elif k in ("lpar", "rpar"):
                i += 1
            else:
                i += 1
        if not trailing:
            self._pr_nl()

    def _exec_hex(self, bs):
        """PRINT HEX(..): raw bytes to the console. Control semantics as
        far as the corpus pins them down: 03 clears (S0's opening
        HEX(0307)), 0C form-feeds which on the CRT is also a clear, 0A
        and 0D move the cursor, 01 homes it. Attribute codes 11/12
        (around S0's input prompt and REGION's warnings) and the bell
        have no visual effect in this renderer; escape sequences are
        swallowed whole. Bytes from 0x20 up are ordinary characters:
        BAM3 builds whole pseudographic rulers out of HEX strings."""
        for b in bs:
            if b == 0x1B:
                break
            if b in (0x03, 0x0C):
                self.scr.clear()
            elif b == 0x0A:
                self._pr_nl()
            elif b == 0x0D:
                self.scr.cx = 0
            elif b == 0x01:
                self.scr.at(1, 1)
            elif b >= 0x20:
                self._pr(koi8(bytes([b])))

    def exec_printusing(self, items, lines):
        """Formatted print through a % image line (E7 line reference)."""
        ref = None
        vals = []
        ri = None
        for i, it in enumerate(items):
            if it[0] == "lineref":
                ref = it[1]
                ri = i
                break
        trailing = bool(items) and items[-1][0] == "semi"
        if ri is not None:
            # arguments are the comma/semicolon separated segments after
            # the reference; each segment is a full expression (REGION
            # passes -L, S2 passes STR() slices and plain variables)
            seg = []
            depth = 0
            for it in items[ri + 1:]:
                if it[0] in ("lpar", "func"):
                    depth += 1
                elif it[0] == "rpar":
                    depth -= 1
                if depth == 0 and it[0] in ("comma", "semi"):
                    if seg:
                        v, _ = self.eval_rex(seg, 0)
                        vals.append(v)
                        seg = []
                else:
                    seg.append(it)
            if seg:
                v, _ = self.eval_rex(seg, 0)
                vals.append(v)
        mask = ""
        if ref in lines and lines[ref] and lines[ref][0][0] == "IMAGE":
            mask = lines[ref][0][1]
        if not mask:
            self._pr(" ".join(str(v) for v in vals))
            if not trailing:
                self._pr_nl()
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
                if isinstance(v, str) and v.strip() \
                        and not v.strip().replace(".", "").replace(
                            "-", "").isdigit():
                    # string value (e.g. the name) in a # field:
                    # left-aligned, clipped to the field width
                    out.append(v.ljust(len(field))[:len(field)])
                    i = j
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    fv = 0.0
                if "." in field:
                    dec = len(field) - field.index(".") - 1
                    s = ("%%.%df" % dec) % fv
                else:
                    s = "%d" % int(fv)
                out.append(s.rjust(len(field))[:len(field)])
                i = j
            else:
                out.append(mask[i])
                i += 1
        self._pr("".join(out))
        if not trailing:
            self._pr_nl()

    def exec_assign(self, items):
        # multiple targets before the '=': N,Y7=0 puts the comma
        # separated left-hand items in front of the D9 (59 corpus
        # examples in VIC); the right side is evaluated once
        eq = None
        depth = 0
        for i, it in enumerate(items):
            if it[0] in ("lpar", "func"):
                depth += 1
            elif it[0] == "rpar":
                depth -= 1
            elif depth == 0 and it[0] == "op" and it[1] == "=":
                eq = i
                break
        if eq is not None and any(it[0] == "comma"
                                  for it in items[:eq]):
            targets = [it for it in items[:eq]
                       if it[0] in ("var", "aref", "arefl")]
            val, _ = self.eval_rex(items, eq + 1)
            for tgt in targets:
                if tgt[0] == "var":
                    if isinstance(val, str):
                        self.svars[tgt[1]] = val
                    else:
                        self.nvars[tgt[1]] = val
                elif tgt[0] == "aref":
                    index = int(self.nvars.get(tgt[2], 0))
                    self.arrays.setdefault(tgt[1], {})[index] = val
                else:
                    self.arrays.setdefault(tgt[1], {})[tgt[2]] = val
            return
        if items and items[0][0] == "strfn":
            opnd = items[0][1]
            pos, _ = self.eval_value([items[0][2]], 0)
            ln2, _ = self.eval_value([items[0][3]], 0)
            pos = int(pos) if pos else 1
            ln2 = int(ln2) if ln2 else 1
            j = 1
            while j < len(items) and not (items[j][0] == "op"
                                          and items[j][1] == "="):
                j += 1
            if j >= len(items):
                return
            val, _ = self.eval_rex(items, j + 1)
            repl = str(val).ljust(ln2)[:ln2]
            base, _ = self.eval_value([opnd], 0)
            s = str(base)
            if len(s) < pos - 1 + ln2:
                s = s.ljust(pos - 1 + ln2)
            s = s[:pos - 1] + repl + s[pos - 1 + ln2:]
            if opnd[0] == "var":
                self.svars[opnd[1]] = s
            else:
                arr, ivar = opnd[1], opnd[2]
                index = int(self.nvars.get(ivar, 0))
                self.arrays.setdefault(arr, {})[index] = s
            return
        if items and items[0][0] == "arefl":
            arr, index = items[0][1], items[0][2]
            j = 1
            while j < len(items) and not (items[j][0] == "op"
                                          and items[j][1] == "="):
                j += 1
            if j >= len(items):
                return
            val, _ = self.eval_rex(items, j + 1)
            self.arrays.setdefault(arr, {})[index] = val
            return
        if items and items[0][0] == "aref":
            arr, ivar = items[0][1], items[0][2]
            j = 1
            while j < len(items) and not (items[j][0] == "op"
                                          and items[j][1] == "="):
                j += 1
            if j >= len(items):
                return
            val, _ = self.eval_rex(items, j + 1)
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
        val, _ = self.eval_rex(items, j + 1)
        if isinstance(val, str):
            self.svars[slot] = val
        else:
            self.nvars[slot] = val

    _RELS = ("=", ">", "<", "<>", "<=", ">=")

    def eval_relation(self, items):
        # find the top-level relation, depth-aware, so that IF S-N1 >=
        # -.01 and IF ABS(N1) <= P1 split at the right place
        depth = 0
        ri = None
        for i, it in enumerate(items):
            if it[0] in ("lpar", "func"):
                depth += 1
            elif it[0] == "rpar":
                depth -= 1
            elif depth == 0 and it[0] == "op" and it[1] in self._RELS:
                ri = i
                break
            elif depth == 0 and it[0] == "roundfn":
                # 0xD8 turns up relationally in IF (IF N D8 30 before the
                # Wilcoxon normal approximation); reading it as >= keeps
                # both corpora consistent, the S2 ROUND use is not inside
                # an IF
                ri = i
                break
        if ri is None:
            return None, None
        op = items[ri][1] if items[ri][0] == "op" else ">="
        rhs = list(items[ri + 1:])
        target = None
        while rhs and rhs[-1][0] == "goto":
            target = rhs[-1][1]
            rhs.pop()
        left, _ = self.eval_rex(items[:ri], 0)
        right, _ = self.eval_rex(rhs, 0)
        try:
            if op == "=":
                cond = left == right
            elif op == ">":
                cond = left > right
            elif op == "<":
                cond = left < right
            elif op == "<>":
                cond = left != right
            elif op == "<=":
                cond = left <= right
            elif op == ">=":
                cond = left >= right
            else:
                cond = False
        except TypeError:
            cond = False
        return cond, target

    def get_key(self):
        """Return the next pending keystroke, or None if none is ready."""
        if self.keys:
            return self.keys.pop(0)
        if self.key_source is not None:
            return self.key_source()
        return None

    def press(self, *keys):
        """Queue keystrokes. Codes >= 128 count as special/function keys."""
        for k in keys:
            self.keys.append(k)

    def get_input(self):
        # a queued reply from the communication line is consumed first
        if self.comm_in:
            return self.comm_in.pop(0)
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
                elif nm in ("GOSUB'", "S28") and any(
                        it[0] == "lineref" for it in items):
                    # PRINTUSING: token 0x28 with an E7 image-line reference.
                    # Must not catch ordinary assignments whose right-hand
                    # side happens to be an E7 numeric literal.
                    self.exec_printusing(items, lines)
                elif nm in ("LET", "", "S36"):
                    self.exec_assign(items)
                elif nm == "INPUT":
                    for it in items:
                        if it[0] == "str":
                            self._pr(it[1])
                            self._pr("? ")
                            break
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
                        if p == "":
                            continue
                        try:
                            self.nvars[slot] = int(p)
                        except ValueError:
                            try:
                                self.nvars[slot] = float(p)
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
                            try:
                                self.arrays.setdefault(arr,
                                                       {})[index] = float(p)
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
                            # resume at the NEXT STATEMENT after the GOSUB,
                            # not at the next line (a line may continue
                            # with e.g. ": GOTO nnnn" after the call)
                            self.gosub.append((pos, si))
                            jump = it[1]
                    if jump is not None:
                        break
                elif nm == "RETURN":
                    if self.gosub:
                        rpos, rsi = self.gosub.pop()
                        pos = rpos
                        start_si = rsi + 1
                        jump = None
                        si = None
                        break
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
                    # 57 <len> <var> <start expr> D1 <limit expr>
                    # [D2 <step expr>]; LFORMAT:1400 runs backwards with
                    # STEP -1, REGION's explanation plots step by .5
                    var = None
                    k = 0
                    if items and items[0][0] == "var":
                        var = items[0][1]
                        k = 1
                    ti = next((x for x, it in enumerate(items)
                               if it[0] == "to"), len(items))
                    sm = next((x for x, it in enumerate(items)
                               if it[0] == "stepmark"), len(items))
                    start, _ = self.eval_rex(items[k:ti], 0)
                    limit, _ = self.eval_rex(items[ti + 1:sm], 0)                         if ti < len(items) else (0, 0)
                    if sm < len(items):
                        step, _ = self.eval_rex(items[sm + 1:], 0)
                    else:
                        step = 1
                    try:
                        step = float(step) if step else 1
                    except (TypeError, ValueError):
                        step = 1
                    if var is not None:
                        self.nvars[var] = start
                        # loop home: statement AFTER this FOR
                        self.forstack.append((var, limit, step, pos, si))
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
                        fvar, limit, step, fpos, fsi = frame
                        v2 = self.nvars.get(fvar, 0) + step
                        self.nvars[fvar] = v2
                        try:
                            lim2 = float(limit)
                        except (TypeError, ValueError):
                            lim2 = 0
                        eps = 1e-9
                        keep = (v2 <= lim2 + eps if step >= 0
                                else v2 >= lim2 - eps)
                        if keep:
                            pos = fpos
                            start_si = fsi + 1
                            jump = None
                            si = None  # signal: position set manually
                            break
                        else:
                            self.forstack.remove(frame)
                elif nm == "S1E":
                    # on end-of-data GOTO: payload is a raw BCD line pair
                    if len(items) >= 2 and items[0][0] == "var" \
                            and items[1][0] == "var":
                        self.eof_goto = bcd2(items[0][1], items[1][1])
                elif nm == "S74":            # DATALOAD-family: read record
                    # Records are POSITIONAL byte streams on the real disk:
                    # values are read back in argument order (S1 writes
                    # A01..A16; S2 reads the same record into A02..A17).
                    slots = [it[1] for it in items if it[0] == "whole"]
                    if self.recptr < len(self.diskrecs):
                        rec = self.diskrecs[self.recptr]
                        self.recptr += 1
                        vals = rec.get("_seq", [])
                        for i2, s2 in enumerate(slots):
                            if i2 < len(vals):
                                self.arrays[s2] = dict(vals[i2])
                    elif self.eof_goto is not None:
                        jump = self.eof_goto
                        break
                elif nm == "S76":            # DATASAVE-family: write record
                    slots = [it[1] for it in items if it[0] == "whole"]
                    if not slots:
                        slots = sorted(self.arrays.keys())
                    rec = {"_seq": [dict(self.arrays.get(s2, {}))
                                    for s2 in slots]}
                    while len(self.diskrecs) <= self.recptr:
                        self.diskrecs.append({"_seq": []})
                    self.diskrecs[self.recptr] = rec
                    self.recptr += 1
                elif nm == "DBACKSPACE":
                    if any(it == ("op", "<=") or (it[0] == "byte"
                           and it[1] == 0xD6) for it in items):
                        self.recptr = 0                    # DBACKSPACE BEG
                    else:
                        n2 = 1
                        for it in items:
                            if it[0] == "num":
                                n2 = it[1]
                        self.recptr = max(0, self.recptr - n2)
                elif nm == "DSKIP":
                    if any(it == ("op", ">=") or (it[0] == "byte"
                           and it[1] == 0xD7) for it in items):
                        self.recptr = len(self.diskrecs)   # DSKIP END
                    else:
                        # DSKIP (index-1)*blocksize+hdr : one group occupies
                        # one block, so the leading (index-1) is the block
                        # number relative to the preceding DBACKSPACE BEG
                        n2 = 0
                        for k, it in enumerate(items):
                            if it[0] in ("var", "aref", "arefl", "num"):
                                v, _ = self.eval_expr(items, k)
                                try:
                                    n2 = int(v)
                                except (TypeError, ValueError):
                                    n2 = 0
                                break
                        self.recptr += max(0, n2)
                elif nm == "INIT":
                    # INIT ,<char> <var> : fill the string variable with
                    # the character (ruler lines of '-' or '*')
                    ch = None
                    tgt = None
                    for it in items:
                        if it[0] in ("var", "byte") and ch is None \
                                and it[0] != "comma":
                            ch = it[1]
                        elif it[0] == "var" and ch is not None \
                                and tgt is None:
                            tgt = it[1]
                    if ch is not None and tgt is not None:
                        self.svars[tgt] = chr(ch) * self.print_width
                elif nm == "KEYIN":
                    # KEYIN <var>, <line-if-key>, <line-if-special>
                    # Corpus: 104 occurrences, ALL payload length 5
                    # (one slot + two 2-byte BCD line numbers). 103 have
                    # both targets equal; BAM3 line 990 is the decisive
                    # exception, "KEYIN V21, 1000, 1160 : GOTO 990" -
                    # the canonical non-blocking poll: branch on a key,
                    # fall through to the GOTO when the buffer is empty.
                    # Line 1160 opens with "ON V21+1", a function-key
                    # dispatcher, confirming the second target's role.
                    raw = [x[1] for x in items
                           if x[0] in ("var", "num", "byte")]
                    slot = raw[0] if raw else 0
                    t1 = t2 = None

                    def _bcd(b):
                        return (b >> 4) * 10 + (b & 0xF)

                    if len(raw) >= 5:
                        t1 = _bcd(raw[1]) * 100 + _bcd(raw[2])
                        t2 = _bcd(raw[3]) * 100 + _bcd(raw[4])
                    ch = self.get_key()
                    if ch is None:
                        pass                      # no key: fall through
                    else:
                        code = ord(ch[0]) if isinstance(ch, str) and ch \
                            else int(ch)
                        special = code >= 128
                        # the corpus compares the result numerically
                        # (BAM3: "ON V21+1"), so the slot holds the code;
                        # a stale string in the same slot would shadow it
                        self.nvars[slot] = code
                        self.svars.pop(slot, None)
                        tgt = t2 if special else t1
                        if tgt is not None:
                            jump = tgt
                            break
                elif nm == "CONVERT":
                    # CONVERT <src> TO <dst> , '<picture>' : format the
                    # numeric source through the # picture into a string
                    src_it = None
                    dst_it = None
                    pic = None
                    seen_to = False
                    for it in items:
                        if it[0] == "to":
                            seen_to = True
                        elif it[0] == "str":
                            pic = it[1]
                        elif it[0] in ("var", "aref", "arefl"):
                            if not seen_to and src_it is None:
                                src_it = it
                            elif seen_to and dst_it is None:
                                dst_it = it
                    if src_it is not None and dst_it is not None:
                        v, _ = self.eval_value([src_it], 0)
                        try:
                            fv = float(v)
                        except (TypeError, ValueError):
                            fv = 0.0
                        if pic and "." in pic:
                            dec = len(pic) - pic.index(".") - 1
                            s2 = ("%%0%d.%df" % (len(pic), dec)) % fv
                        elif pic:
                            s2 = ("%%0%dd" % len(pic)) % int(fv)
                        else:
                            s2 = str(v)
                        s2 = s2[:len(pic)] if pic else s2
                        if dst_it[0] == "var":
                            self.svars[dst_it[1]] = s2
                        elif dst_it[0] == "aref":
                            idx2 = int(self.nvars.get(dst_it[2], 0))
                            self.arrays.setdefault(dst_it[1], {})[idx2] = s2
                        else:
                            self.arrays.setdefault(dst_it[1],
                                                   {})[dst_it[2]] = s2
                elif nm == "SELECT":
                    # SELECT PRINT <device> [ ( width ) ]
                    #   device 005 = console (80 col), 012 = printer (132)
                    nums = [x[1] for x in items if x[0] in ("var", "byte",
                                                            "num")]
                    if len(nums) >= 2 and nums[0] == 7:
                        prev = self.print_device
                        self.print_device = nums[1]
                        if prev == 15 and nums[1] != 15:
                            self._comm_flush()
                        for x in items:
                            if x[0] == "byte" and x[1] > 100:
                                self.print_width = x[1]
                            elif x[0] == "num" and x[1] in (80, 132):
                                self.print_width = x[1]
                elif nm == "LIMITS":
                    # disk-catalog query: LIMITS T <file>, start, end, free.
                    # Virtual disk: report a valid range so the write path
                    # proceeds (real sectors are not used by this layer).
                    tv = [it[1] for it in items if it[0] == "var"]
                    if len(tv) >= 4:
                        self.nvars[tv[-3]] = 1
                        self.nvars[tv[-2]] = 100
                        self.nvars[tv[-1]] = 99
                elif nm == "STOP":
                    # Wang semantics: STOP is a resumable pause, the user
                    # presses CONTINUE and the program resumes at the next
                    # statement. CONTINUE is a bare keypress, not data, so
                    # in scripted mode it must not consume an answer.
                    if self.auto is None:
                        try:
                            input("[STOP, press Enter to CONTINUE] ")
                        except EOFError:
                            self.halted = True
                            break
                elif nm == "END":
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
        self._pr_flush()


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
