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

ARR_RE = re.compile(r'^A([0-9A-F]{1,2})\(V([0-9A-F]{1,2})\)$', re.I)
ARRL_RE = re.compile(r'^A([0-9A-F]{1,2})\((\d+)\)$', re.I)

OPS = {'+': A_PLUS, '-': A_MINUS, '*': A_MUL, '/': A_DIV,
       '=': A_EQ, '<>': A_NE, '<': A_LT, '>': A_GT}


def enc_operand(tok):
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
    raise ValueError("cannot encode operand: %r" % tok)


def split_expr(text):
    """split on top-level operators, keeping them"""
    out = []
    buf = ''
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        one = text[i]
        if two == '<>':
            out.append(buf.strip()); out.append('<>'); buf = ''; i += 2
            continue
        if one in '+-*/=<>' and buf.strip() and not buf.strip().endswith('('):
            out.append(buf.strip()); out.append(one); buf = ''; i += 1
            continue
        buf += one
        i += 1
    if buf.strip():
        out.append(buf.strip())
    return [p for p in out if p != '']


def enc_expr(text):
    out = b''
    for part in split_expr(text):
        if part in OPS:
            out += bytes([OPS[part]])
        else:
            out += enc_operand(part)
    return out


# ------------------------------------------------------------- statements
def asm_statement(src):
    src = src.strip()
    if not src:
        return b''
    up = src.upper()

    if up.startswith('KEYIN'):
        # KEYIN <var>, <line-if-key>, <line-if-special>
        parts = [p.strip() for p in src[5:].split(',')]
        pl = enc_operand(parts[0])
        pl += enc_lineref(parts[1])
        pl += enc_lineref(parts[2] if len(parts) > 2 else parts[1])
        return bytes([0x25, len(pl)]) + pl

    if up.startswith('SELECT PRINT'):
        # SELECT PRINT <device> : 005 = console, 012 = printer,
        # 015 = communication line (host bridge)
        dev = int(src.split()[2])
        pl = bytes([0x07, dev])
        return bytes([0x54, len(pl)]) + pl

    if up.startswith('RETURN'):
        return bytes([0x5E, 0])   # corpus token map: 5E = RETURN

    if up.startswith('REM'):
        body = bytes(enc_char(c) for c in src[3:].strip())
        return bytes([T_REM, len(body)]) + body

    if up.startswith('PRINT'):
        rest = src[5:].strip()
        pl = b''
        for item in split_print(rest):
            if item == ';':
                pl += bytes([A_SEMI])
            elif item.upper().startswith('AT('):
                inner = item[3:item.rindex(')')]
                a, b = [x.strip() for x in inner.split(',')]
                pl += bytes([0xE1, 0x31]) + enc_at_arg(a) \
                    + bytes([A_COMMA]) + enc_at_arg(b) + bytes([A_RPAR])
            elif item.upper().startswith('AT('):
                # AT(row,col): D5 E8 rr DE E8 cc D0, the full form the
                # interpreter requires to tell it from the <> relation
                inner = item[3:item.index(')')]
                r, c = [int(x) for x in inner.split(',')]
                pl += bytes([0xD5, 0xE8, bcd(r), 0xDE,
                             0xE8, bcd(c), 0xD0])
            elif item.upper().startswith('ATV('):
                # ATV(vr,vc): same shape but with variable slots
                inner = item[4:item.index(')')]
                a, b = [x.strip() for x in inner.split(',')]
                # variable coordinates use the generic function atom
                # E1 31 (= AT), whose arguments may be slots
                pl += bytes([0xE1, 0x31]) + enc_operand(a) \
                    + bytes([0xDE]) + enc_operand(b) + bytes([0xD0])
            elif item.upper().startswith('TAB('):
                n = int(item[4:item.index(')')])
                pl += bytes([A_TAB, A_NUM1, bcd(n), A_RPAR])
            elif item.startswith('"'):
                pl += enc_string(item[1:-1])
            else:
                pl += enc_expr(item)
        return bytes([T_PRINT, len(pl)]) + pl

    if up.startswith('INPUT'):
        rest = src[5:].strip()
        pl = b''
        parts = [p.strip() for p in rest.split(',')]
        for k, p in enumerate(parts):
            if k:
                pl += bytes([A_COMMA])
            if p.startswith('"'):
                pl += enc_string(p[1:-1])
            else:
                pl += enc_operand(p)
        return bytes([T_INPUT, len(pl)]) + pl

    if up.startswith('IF'):
        m = re.match(r'IF\s+(.*?)\s+GOTO\s+(\d+)$', src, re.I)
        if not m:
            raise ValueError("unsupported IF: %r" % src)
        pl = enc_expr(m.group(1))
        pl += bytes([0xD3]) + enc_lineref(m.group(2))
        return bytes([T_IF, len(pl)]) + pl

    if up.startswith('GOTO'):
        pl = bytes([0xD3]) + enc_lineref(src[4:].strip())
        return bytes([T_GOTO, len(pl)]) + pl

    if up.startswith('GOSUB'):
        pl = bytes([0xD3]) + enc_lineref(src[5:].strip())
        return bytes([T_GOSUB, len(pl)]) + pl

    if up.startswith('FOR'):
        m = re.match(r'FOR\s+(V[0-9A-F]{1,2})\s*=\s*(.+?)\s+TO\s+(.+)$',
                     src, re.I)
        pl = (enc_operand(m.group(1)) + enc_expr(m.group(2))
              + bytes([A_TO]) + enc_expr(m.group(3)))
        return bytes([T_FOR, len(pl)]) + pl

    if up.startswith('NEXT'):
        pl = enc_operand(src[4:].strip())
        return bytes([T_NEXT, len(pl)]) + pl

    if up in ('RETURN',):
        return bytes([0x5E, 0])          # corpus: line 8007 = "5e 00"
    if up in ('END',):
        return bytes([T_END, 0])
    if up in ('STOP',):
        return bytes([T_STOP, 0])

    # bare assignment
    if '=' in src:
        lhs, rhs = src.split('=', 1)
        pl = enc_operand(lhs.strip()) + bytes([A_EQ]) + enc_expr(rhs.strip())
        return bytes([T_LET, len(pl)]) + pl

    raise ValueError("unsupported statement: %r" % src)


def split_print(rest):
    """split a PRINT argument list, keeping quoted strings intact"""
    items = []
    buf = ''
    inq = False
    for ch in rest:
        if ch == '"':
            inq = not inq
            buf += ch
        elif ch == ';' and not inq:
            if buf.strip():
                items.append(buf.strip())
            items.append(';')
            buf = ''
        else:
            buf += ch
    if buf.strip():
        items.append(buf.strip())
    return items


def asm_line(num, text):
    stmts = b''
    for part in split_statements(text):
        stmts += asm_statement(part)
    body = enc_lineref(num) + bytes([len(stmts) + 1]) + stmts + bytes([0xFE])
    return body


def split_statements(text):
    """split on ':' outside quotes"""
    out = []
    buf = ''
    inq = False
    for ch in text:
        if ch == '"':
            inq = not inq
            buf += ch
        elif ch == ':' and not inq:
            out.append(buf)
            buf = ''
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


def assemble(source):
    """source text -> program body bytes"""
    body = b''
    for raw in source.split('\n'):
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        m = re.match(r'^(\d+)\s+(.*)$', raw)
        if not m:
            raise ValueError("line without number: %r" % raw)
        body += asm_line(int(m.group(1)), m.group(2))
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
