#!/usr/bin/env python3
"""
iskra_asm.py, a small assembler for the Iskra-226 BASIC 02 tokenised
disk format, built entirely from the encodings decoded in
isa-findings.md (addenda 1-19).

This is the write direction of the format: it turns a restricted BASIC
source text into the same byte stream the original 1988 programs use,
and writes it into a disk image as a catalog entry.

Supported subset (everything the decoding established with proof):
    LET / bare assignment      V<nn> = <expr>          A<nn>(<slot>) = ...
    PRINT   with strings, expressions, TAB(), semicolons
    INPUT   into variables
    IF <expr> <rel> <expr> GOTO <line>
    GOTO / GOSUB / RETURN / FOR / NEXT / END / STOP / REM
    arithmetic + - * /   relations = < > <>

Line format:      <bcd-hi> <bcd-lo> <len> <statement bytes...> FE
Statement format: <token> <payload-len> <payload...>
"""

import re
import sys

# ---------------------------------------------------------------- tokens
T_GOTO = 0x21
T_GOSUB = 0x22
T_IF = 0x24
T_LET = 0x36          # bare assignment (the common form in the corpus)
T_INPUT = 0x41
T_STOP = 0x42
T_PRINT = 0x4C
T_NEXT = 0x52
T_REM = 0x56
T_FOR = 0x57
T_END = 0x59
T_RETURN = 0x2D0      # placeholder, see NAMES below

NAMES = {
    "GOTO": T_GOTO, "GOSUB": T_GOSUB, "IF": T_IF, "INPUT": T_INPUT,
    "STOP": T_STOP, "PRINT": T_PRINT, "NEXT": T_NEXT, "REM": T_REM,
    "FOR": T_FOR, "END": T_END,
}

# atoms (all corpus-proven)
A_LPAR = 0xEB
A_RPAR = 0xD0
A_COMMA = 0xDE
A_SEMI = 0xDD
A_EQ = 0xD9
A_NE = 0xD5
A_LT = 0xCF
A_GT = 0xD4
A_PLUS = 0xEA
A_MINUS = 0xE9
A_MUL = 0xDF
A_DIV = 0xE4
A_STR = 0xE3          # E3 <len> <chars>
A_NUM1 = 0xE8         # E8 <bcd>          (0-99)
A_NUM2 = 0xE7         # E7 <bcd> <bcd>    (0-9999)
A_TAB = 0xDF          # DF E8 nn D0  (TAB(, same byte as *, disambiguated
                      # by the following E8 ... D0, exactly as the
                      # interpreter's parser does)
A_TO = 0xD1          # corpus: line 3290 "57 05 37 e8 01 d1 00" = FOR V37=1 TO V00

# KOI-8 style mapping used by the corpus (upper case Cyrillic)
CYR = {
    'А': 0xE1, 'Б': 0xE2, 'В': 0xF7, 'Г': 0xE7, 'Д': 0xE4, 'Е': 0xE5,
    'Ж': 0xF6, 'З': 0xFA, 'И': 0xE9, 'Й': 0xEA, 'К': 0xEB, 'Л': 0xEC,
    'М': 0xED, 'Н': 0xEE, 'О': 0xEF, 'П': 0xF0, 'Р': 0xF2, 'С': 0xF3,
    'Т': 0xF4, 'У': 0xF5, 'Ф': 0xE6, 'Х': 0xE8, 'Ц': 0xE3, 'Ч': 0xFE,
    'Ш': 0xFB, 'Щ': 0xFD, 'Ъ': 0xFF, 'Ы': 0xF9, 'Ь': 0xF8, 'Э': 0xFC,
    'Ю': 0xE0, 'Я': 0xF1,
}


def bcd(n):
    """two decimal digits into one packed BCD byte"""
    n = int(n) % 100
    return ((n // 10) << 4) | (n % 10)


def enc_char(ch):
    if ch in CYR:
        return CYR[ch]
    return ord(ch) & 0xFF


def enc_string(s):
    body = bytes(enc_char(c) for c in s)
    return bytes([A_STR, len(body)]) + body


def enc_number(v):
    v = int(v)
    if 0 <= v <= 99:
        return bytes([A_NUM1, bcd(v)])
    if 0 <= v <= 9999:
        return bytes([A_NUM2, bcd(v // 100), bcd(v % 100)])
    raise ValueError("literal out of range: %d" % v)


VAR_RE = re.compile(r'^V([0-9A-F]{1,2})$', re.I)


def enc_at_arg(tok):
    """AT() argument: a literal (E8 <bcd>) or a bare variable slot.
    Encoding proven by the E1-31 form in the print branch of S2."""
    tok = tok.strip()
    m = VAR_RE.match(tok)
    if m:
        return bytes([int(m.group(1), 16)])
    return bytes([A_NUM1, bcd(int(tok))])


def enc_lineref(v):
    """line numbers are the same two-byte BCD used by GOTO/GOSUB"""
    v = int(v)
    return bytes([bcd(v // 100), bcd(v % 100)])


# ------------------------------------------------------------ expressions
#
# Two layers of source dialect meet here. The game sources address
# variables as V<hex slot> and array elements as A<arr>(V<idx>); REGION
# and the other recovered 1980s listings use the machine's own names, N,
# P1, Z1, A8. Names are resolved through a per-assembly symbol table to
# free slots; the mapping is deterministic (first appearance) and is
# reported by assemble() so a run can be read back against the listing.

ARR_RE = re.compile(r'^A([0-9A-F]{1,2})\(V([0-9A-F]{1,2})\)$', re.I)
ARRL_RE = re.compile(r'^A([0-9A-F]{1,2})\((\d+)\)$', re.I)
NAME_RE = re.compile(r'^[A-ZА-Я][0-9]?[%$]?$')

# extended atoms, decoded 2026-08-15 (research/note-expression-tokens.md)
A_POW = 0xDC          # power operator, polynomial regression corpus
A_LE = 0xD6           # <=
A_GE = 0xD7           # >=
A_STEP = 0xD2         # STEP in FOR
A_HEX = 0xE2          # HEX( <len> <raw bytes>
A_FLOAT = 0xE5        # E5 <ab bcd> <digit nibbles>, general number
A_BRANCH = 0xD3
T_PRINTUSING = 0x28
T_IMAGE = 0x3F

FN_TOKENS = {"ABS": 0xF2, "INT": 0xF3, "RND": 0xF4, "SGN": 0xF5,
             "SQR": 0xF6, "LOG": 0xF7, "EXP": 0xF8, "SIN": 0xF9,
             "COS": 0xFA, "TAN": 0xFB}

OPS = {'+': A_PLUS, '-': A_MINUS, '*': A_MUL, '/': A_DIV, '^': A_POW,
       '=': A_EQ, '<>': A_NE, '<': A_LT, '>': A_GT, '<=': A_LE,
       '>=': A_GE}

RELS = ('<=', '>=', '<>', '=', '<', '>')


class Symbols:
    """named variable -> slot, first come first served"""

    def __init__(self):
        self.map = {}
        self.next = 0x01

    def slot(self, name):
        name = name.upper()
        if name not in self.map:
            if self.next > 0x7F:
                raise ValueError("out of variable slots")
            self.map[name] = self.next
            self.next += 1
        return self.map[name]


def enc_float(text):
    """the E5 literal, encoded from the written digits so that the byte
    stream round-trips: .5 -> E5 01 50, 4.123 -> E5 13 41 23,
    100 -> E5 30 10 (trailing zero bytes dropped, the parser pads)"""
    neg = text.startswith('-')
    if neg:
        text = text[1:]
    if '.' in text:
        ip, fp = text.split('.', 1)
    else:
        ip, fp = text, ''
    ip = ip.lstrip('0') or ('0' if not fp else '')
    if len(ip) > 9 or len(fp) > 9:
        raise ValueError("literal too long: %r" % text)
    digits = ip + fp
    if not digits:
        digits = '0'
    out = [A_FLOAT, (len(ip) << 4) | len(fp)]
    if len(digits) % 2:
        digits += '0'
    mant = [int(digits[i]) << 4 | int(digits[i + 1])
            for i in range(0, len(digits), 2)]
    while len(mant) > 1 and mant[-1] == 0:
        mant.pop()
    body = bytes(out + mant)
    return (bytes([A_MINUS]) + body) if neg else body


def enc_num_literal(text):
    """integers keep the compact corpus forms (E8 to 99, E7 to 9999);
    fractions and anything larger take the general E5 literal"""
    if re.fullmatch(r'\d+', text) and int(text) <= 9999:
        return enc_number(int(text))
    return enc_float(text)


TOK_RE = re.compile(r"""
    (?P<str>"[^"]*"|'[^']*') |
    (?P<num>\d+\.\d*|\.\d+|\d+) |
    (?P<word>[A-ZА-Я][A-ZА-Я0-9]*[%$]?) |
    (?P<rel><=|>=|<>) |
    (?P<ch>[-+*/^()=<>,;])
""", re.X | re.I)


def enc_expr(text, sym=None):
    """expression source -> token bytes, linear translation; precedence
    lives in the interpreter, the encoder just carries the parentheses"""
    out = b''
    prev_operand = False
    i = 0
    text = text.strip()
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        m = TOK_RE.match(text, i)
        if not m:
            raise ValueError("cannot encode operand: %r" % text[i:i + 20])
        i = m.end()
        if m.group('str'):
            out += enc_string(m.group('str')[1:-1])
            prev_operand = True
        elif m.group('num'):
            out += enc_num_literal(m.group('num'))
            prev_operand = True
        elif m.group('word'):
            w = m.group('word').upper()
            if w in FN_TOKENS and i < len(text) and text[i] == '(':
                out += bytes([FN_TOKENS[w]])
                i += 1
                prev_operand = False
            elif w == 'TAB' and i < len(text) and text[i] == '(':
                out += bytes([A_TAB])
                i += 1
                prev_operand = False
            elif w == 'HEX' and i < len(text) and text[i] == '(':
                j = text.index(')', i)
                hx = re.sub(r'\s', '', text[i + 1:j])
                raw = bytes(int(hx[k:k + 2], 16)
                            for k in range(0, len(hx), 2))
                out += bytes([A_HEX, len(raw)]) + raw
                i = j + 1
                prev_operand = True
            elif re.fullmatch(r'A[0-9A-F]{1,2}', w) and i < len(text) \
                    and text[i] == '(' and not (NAME_RE.match(w)
                                                and sym is not None
                                                and w in sym.map):
                # array element A<arr>(V<idx>) / A<arr>(<n>): slot, index,
                # closing rpar, no marker byte (corpus form)
                j = text.index(')', i)
                inner = text[i + 1:j].strip()
                arr = int(w[1:], 16)
                mv = VAR_RE.match(inner)
                if mv:
                    out += bytes([arr, int(mv.group(1), 16), A_RPAR])
                elif re.fullmatch(r'\d+', inner):
                    out += bytes([arr]) + enc_number(int(inner)) \
                        + bytes([A_RPAR])
                elif NAME_RE.match(inner) and sym is not None:
                    out += bytes([arr, sym.slot(inner), A_RPAR])
                else:
                    raise ValueError("cannot encode index: %r" % inner)
                i = j + 1
                prev_operand = True
            else:
                mv = VAR_RE.match(w)
                if mv:
                    out += bytes([int(mv.group(1), 16)])
                elif NAME_RE.match(w) and sym is not None:
                    out += bytes([sym.slot(w)])
                else:
                    raise ValueError("cannot encode operand: %r" % w)
                prev_operand = True
        elif m.group('rel'):
            out += bytes([OPS[m.group('rel')]])
            prev_operand = False
        else:
            ch = m.group('ch')
            if ch == '(':
                out += bytes([A_LPAR])
                prev_operand = False
            elif ch == ')':
                out += bytes([A_RPAR])
                prev_operand = True
            elif ch == '-' and not prev_operand:
                # unary minus; before a small integer it folds into the
                # corpus negative-literal form E9 E8 <bcd>
                out += bytes([A_MINUS])
                prev_operand = False
            elif ch in OPS:
                out += bytes([OPS[ch]])
                prev_operand = False
            elif ch == ',':
                out += bytes([A_COMMA])
                prev_operand = False
            elif ch == ';':
                out += bytes([A_SEMI])
                prev_operand = False
            else:
                raise ValueError("cannot encode operand: %r" % ch)
    return out


def enc_operand(tok, sym=None):
    tok = tok.strip()
    m = VAR_RE.match(tok)
    if m:
        return bytes([int(m.group(1), 16)])
    m = ARR_RE.match(tok)
    if m:
        return bytes([int(m.group(1), 16), int(m.group(2), 16), A_RPAR])
    m = ARRL_RE.match(tok)
    if m:
        return (bytes([int(m.group(1), 16)])
                + enc_number(int(m.group(2))) + bytes([A_RPAR]))
    if tok.startswith('"') and tok.endswith('"'):
        return enc_string(tok[1:-1])
    if re.match(r'^-?\d+$', tok):
        if int(tok) < 0:
            return bytes([A_MINUS]) + enc_number(-int(tok))
        return enc_number(int(tok))
    if sym is not None and NAME_RE.match(tok.upper()):
        return bytes([sym.slot(tok)])
    raise ValueError("cannot encode operand: %r" % tok)


def _split_top(text, seps, quotes="\"'"):
    """split at top-level separator characters, respecting quotes and
    parentheses; returns (parts, separators)"""
    parts, sepout = [], []
    buf = ''
    depth = 0
    q = None
    for ch in text:
        if q:
            buf += ch
            if ch == q:
                q = None
        elif ch in quotes:
            q = ch
            buf += ch
        elif ch == '(':
            depth += 1
            buf += ch
        elif ch == ')':
            depth -= 1
            buf += ch
        elif depth == 0 and ch in seps:
            parts.append(buf)
            sepout.append(ch)
            buf = ''
        else:
            buf += ch
    parts.append(buf)
    return parts, sepout


def _find_rel(text):
    """position and text of the top-level relation, quotes respected"""
    depth = 0
    q = None
    i = 0
    while i < len(text):
        ch = text[i]
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            two = text[i:i + 2]
            if two in ('<=', '>=', '<>'):
                return i, two
            if ch in '=<>':
                return i, ch
        i += 1
    return None, None


# ------------------------------------------------------------- statements
def asm_statement(src, sym=None, images=None):
    src = src.strip()
    if not src:
        return b''
    up = src.upper()

    if up.startswith('KEYIN'):
        parts = [p.strip() for p in src[5:].split(',')]
        pl = enc_operand(parts[0], sym)
        pl += enc_lineref(parts[1])
        pl += enc_lineref(parts[2] if len(parts) > 2 else parts[1])
        return bytes([0x25, len(pl)]) + pl

    if up.startswith('SELECT PRINT'):
        dev = int(src.split()[2])
        pl = bytes([0x07, dev])
        return bytes([0x54, len(pl)]) + pl

    if up.startswith('RETURN'):
        return bytes([0x5E, 0])   # corpus token map: 5E = RETURN

    if up.startswith('REM'):
        body = bytes(enc_char(c) for c in src[3:].strip())
        return bytes([T_REM, len(body)]) + body

    if up.startswith(('SCRATCH', 'SAVE', 'LIST')):
        # the self-listing line of the recovered sources (REGION line 2);
        # it never executes and is preserved as prose
        body = bytes(enc_char(c) for c in src)
        return bytes([T_REM, len(body)]) + body

    if up.startswith('PRINTUSING'):
        rest = src[len('PRINTUSING'):].strip()
        parts, _ = _split_top(rest, ',')
        mask = parts[0].strip()
        if not (mask.startswith('"') and mask.rstrip(';').endswith('"')):
            raise ValueError("PRINTUSING needs a mask string: %r" % src)
        trailing = parts[-1].rstrip().endswith(';')
        if trailing:
            parts[-1] = parts[-1].rstrip().rstrip(';')
        if images is None:
            raise ValueError("PRINTUSING outside assemble()")
        ref = images.line_for(mask.strip().strip('"'))
        pl = bytes([A_NUM2]) + enc_lineref(ref)
        for arg in parts[1:]:
            if arg.strip():
                pl += bytes([A_COMMA]) + enc_expr(arg, sym)
        if trailing:
            pl += bytes([A_SEMI])
        return bytes([T_PRINTUSING, len(pl)]) + pl

    if up.startswith('PRINT'):
        rest = src[5:].strip()
        pl = b''
        for item in split_print(rest):
            if item == ';':
                pl += bytes([A_SEMI])
            elif item == ',':
                pl += bytes([A_COMMA])
            elif item.upper().startswith('ATV('):
                inner = item[4:item.index(')')]
                a, b = [x.strip() for x in inner.split(',')]
                pl += bytes([0xE1, 0x31]) + enc_operand(a, sym) \
                    + bytes([0xDE]) + enc_operand(b, sym) + bytes([0xD0])
            elif item.upper().startswith('AT('):
                inner = item[3:item.rindex(')')]
                a, b = [x.strip() for x in inner.split(',')]
                pl += bytes([0xE1, 0x31]) + enc_at_arg(a) \
                    + bytes([A_COMMA]) + enc_at_arg(b) + bytes([A_RPAR])
            elif item.startswith('"') and item.endswith('"'):
                pl += enc_string(item[1:-1])
            elif item.startswith("'") and item.endswith("'"):
                pl += enc_string(item[1:-1])
            else:
                pl += enc_expr(item, sym)
        return bytes([T_PRINT, len(pl)]) + pl

    if up.startswith('INPUT'):
        rest = src[5:].strip()
        pl = b''
        parts, _ = _split_top(rest, ',')
        emitted = 0
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if emitted:
                pl += bytes([A_COMMA])
            if p.startswith('"') or p.startswith("'"):
                pl += enc_string(p[1:-1])
            else:
                pl += enc_operand(p, sym)
            emitted += 1
        return bytes([T_INPUT, len(pl)]) + pl

    if up.startswith('IF'):
        m = re.match(r'IF\s*(.+?)\s*(?:THEN|GOTO)\s*(\d+)\s*$',
                     src, re.I | re.S)
        if not m:
            raise ValueError("unsupported IF: %r" % src)
        cond, target = m.group(1), m.group(2)
        ri, rel = _find_rel(cond)
        if ri is None:
            pl = enc_expr(cond, sym)
        else:
            pl = enc_expr(cond[:ri], sym) + bytes([OPS[rel]]) \
                + enc_expr(cond[ri + len(rel):], sym)
        pl += bytes([A_BRANCH]) + enc_lineref(target)
        return bytes([T_IF, len(pl)]) + pl

    if re.match(r'^GOTO\s*\d+$', up):
        pl = bytes([A_BRANCH]) + enc_lineref(re.sub(r'\D', '', src))
        return bytes([T_GOTO, len(pl)]) + pl

    if re.match(r'^GOSUB\s*\d+$', up):
        pl = bytes([A_BRANCH]) + enc_lineref(re.sub(r'\D', '', src))
        return bytes([T_GOSUB, len(pl)]) + pl

    if up.startswith('FOR'):
        m = re.match(
            r'FOR\s*([A-ZА-Я][0-9]?[%$]?|V[0-9A-F]{1,2})\s*=\s*(.+?)'
            r'TO(.+?)(?:STEP(.+))?$',
            src, re.I)
        if not m:
            raise ValueError("unsupported FOR: %r" % src)
        pl = enc_operand(m.group(1), sym) + enc_expr(m.group(2), sym) \
            + bytes([A_TO]) + enc_expr(m.group(3), sym)
        if m.group(4):
            pl += bytes([A_STEP]) + enc_expr(m.group(4), sym)
        return bytes([T_FOR, len(pl)]) + pl

    if up.startswith('NEXT'):
        pl = enc_operand(src[4:].strip(), sym)
        return bytes([T_NEXT, len(pl)]) + pl

    if up in ('END',):
        return bytes([T_END, 0])
    if up in ('STOP',):
        return bytes([T_STOP, 0])

    # assignment, including the multi-target form N,Y7=0 (targets are
    # comma-separated in front of the D9, 59 corpus examples in VIC)
    ri, rel = _find_rel(src)
    if rel == '=':
        lhs, rhs = src[:ri], src[ri + 1:]
        tparts, _ = _split_top(lhs, ',')
        pl = b''
        for k, tp in enumerate(tparts):
            if k:
                pl += bytes([A_COMMA])
            pl += enc_operand(tp.strip(), sym)
        pl += bytes([A_EQ]) + enc_expr(rhs.strip(), sym)
        return bytes([T_LET, len(pl)]) + pl

    raise ValueError("unsupported statement: %r" % src)


def split_print(rest):
    """split a PRINT argument list at top-level ; and , keeping quoted
    strings (both quote characters) intact"""
    parts, seps = _split_top(rest, ';,')
    items = []
    for k, p in enumerate(parts):
        if p.strip():
            items.append(p.strip())
        if k < len(seps):
            items.append(seps[k])
    return items


class Images:
    """PRINTUSING image-line allocator: identical masks share a line"""

    def __init__(self, base=9000, step=2):
        self.base = base
        self.step = step
        self.masks = {}

    def line_for(self, mask):
        if mask not in self.masks:
            self.masks[mask] = self.base + self.step * len(self.masks)
        return self.masks[mask]

    def records(self):
        out = b''
        for mask, ln in sorted(self.masks.items(), key=lambda kv: kv[1]):
            body = bytes(enc_char(c) for c in mask)
            rec = bytes([T_IMAGE, len(body)]) + body
            out += enc_lineref(ln) + bytes([len(rec) + 1]) + rec \
                + bytes([0xFE])
        return out


def asm_line(num, text, sym=None, images=None):
    stmts = b''
    for part in split_statements(text):
        stmts += asm_statement(part, sym, images)
    if len(stmts) + 1 > 0xFF:
        raise ValueError("line %d too long (%d bytes)" % (num, len(stmts)))
    body = enc_lineref(num) + bytes([len(stmts) + 1]) + stmts + bytes([0xFE])
    return body


def split_statements(text):
    """split on ':' outside quotes (both quote characters)"""
    out = []
    buf = ''
    q = None
    for ch in text:
        if q:
            buf += ch
            if ch == q:
                q = None
        elif ch in '\"\'':
            q = ch
            buf += ch
        elif ch == ':':
            out.append(buf)
            buf = ''
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


def assemble(source, with_symbols=False):
    """source text -> program body bytes; with_symbols also returns the
    name->slot map and the PRINTUSING mask lines"""
    sym = Symbols()
    images = Images()
    body = b''
    for raw in source.split('\n'):
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        m = re.match(r'^(\d+)\s+(.*)$', raw)
        if not m:
            raise ValueError("line without number: %r" % raw)
        body += asm_line(int(m.group(1)), m.group(2), sym, images)
    body += images.records()
    if with_symbols:
        return body, sym.map, dict(images.masks)
    return body


def write_to_disk(image_path, name, body, start_sector):
    """place the assembled program into a disk image as data sectors"""
    with open(image_path, 'rb') as f:
        raw = bytearray(f.read())
    sectors = []
    off = 0
    while off < len(body):
        chunk = body[off:off + 254]
        sec = bytearray(256)
        sec[0] = 0x02                    # data-sector marker
        sec[1] = 0x00
        sec[2:2 + len(chunk)] = chunk
        sectors.append(bytes(sec))
        off += 254
    for k, sec in enumerate(sectors):
        s = start_sector + k
        raw[s * 256:(s + 1) * 256] = sec
    with open(image_path, 'wb') as f:
        f.write(bytes(raw))
    return start_sector, start_sector + len(sectors) - 1


def init_catalog(image_path, index_sectors=4, total_sectors=1000):
    """Write the disk header: catalog span, last used sector, capacity.
    Layout taken from disk3side0 sector 0: 00 18 | 03 2d | 03 e8
    (catalog spans sectors 0..24, last used 813, capacity 1000)."""
    import struct
    with open(image_path, 'rb') as f:
        raw = bytearray(f.read())
    raw[0:2] = struct.pack('>H', index_sectors)
    raw[2:4] = struct.pack('>H', total_sectors - 1)
    raw[4:6] = struct.pack('>H', total_sectors)
    with open(image_path, 'wb') as f:
        f.write(bytes(raw))


def add_catalog_entry(image_path, name, start, end, index_sector=0):
    """Write a catalog entry (0x10 marker, BE start/end, 8-char name).
    Entries begin at offset 16 of sector 0, 16 bytes each."""
    import struct
    with open(image_path, 'rb') as f:
        raw = bytearray(f.read())
    base = index_sector * 256
    for k in range(16, 256, 16):
        if raw[base + k] not in (0x10, 0x11):
            entry = bytearray(16)
            entry[0] = 0x10
            entry[1] = 0x00
            entry[2:4] = struct.pack('>H', start)
            entry[4:6] = struct.pack('>H', end)
            nm = name.encode('ascii', 'replace')[:8].ljust(8, b' ')
            entry[8:16] = nm
            raw[base + k:base + k + 16] = entry
            break
    with open(image_path, 'wb') as f:
        f.write(bytes(raw))


def build_disk(image_path, programs, start_sector=20):
    """programs: list of (name, source). Lays them out and catalogs them."""
    import struct
    with open(image_path, 'wb') as f:
        f.write(bytes(256 * 1001))
    init_catalog(image_path)
    sec = start_sector
    for name, source in programs:
        body = assemble(source)
        s0, s1 = write_to_disk(image_path, name, body, sec)
        add_catalog_entry(image_path, name, s0, s1)
        sec = s1 + 1
    return sec


if __name__ == '__main__':
    src = open(sys.argv[1]).read()
    body = assemble(src)
    print("assembled %d bytes" % len(body))
