#!/usr/bin/env python3
"""
iskra_basic - functional emulator layer for Iskra-226 BASIC 02 disks.

Reads the original .dsk sector images, parses the catalog, decodes the
tokenized BASIC 02 program format, and lists programs as source.

This operates at the BASIC level: it runs the surviving *software*, not
the CPU. The interpreter firmware is not executed (its data-operation
semantics are still unrecovered - see isa-findings.md).
Everything shown here is decoded from the original disks.

Usage:
    python3 iskra_basic.py cat   <image.dsk>
    python3 iskra_basic.py list  <image.dsk> <FILENAME>
    python3 iskra_basic.py dump  <image.dsk> <FILENAME>
"""

import sys
import struct

SECTOR = 256

# --- character set -------------------------------------------------------
# KOI-8 style: 0xC0-0xDF lowercase, 0xE0-0xFF uppercase, in KOI letter order.
KOI_ORDER = "юабцдефгхийклмнопярстужвьызшэщчъ"
KOI = {0xC0 + i: c for i, c in enumerate(KOI_ORDER)}
KOI.update({0xE0 + i: c.upper() for i, c in enumerate(KOI_ORDER)})


def koi8(bs):
    return "".join(KOI.get(b, chr(b) if 0x20 <= b < 0x7F else "·") for b in bs)


# --- statement tokens ----------------------------------------------------
# Recovered from the interpreter's alphabetical keyword list (file offset
# 0x1840) plus the 51-byte permutation array at 0x19B6.
KEYWORDS = ("ADD AND( BACKSPACE BIN( BOOL CLEAR COM CONVERT COPY DATA "
            "DBACKSPACE DEFFN DIM DSKIP END FOR GOSUB GOTO HEXPRINT IF "
            "INIT INPUT KEYIN LET LIMITS LIST LOAD MOVE NEXT ON OR( PACK( "
            "PRINT READ REM RENUMBER RES RETURN REWIND ROTATE RUN SAVE "
            "SCRATCH SELECT SKIP STOP TRACE UNPACK( VERIFY XOR( $GIO").split()


def load_token_map(firmware=None):
    """token byte -> keyword, from the permutation array if available."""
    if firmware:
        try:
            fw = open(firmware, "rb").read()
            base = fw.find(b"ADDAND(BACKSPACE")
            if base > 0:
                perm = fw[base + 0x176:base + 0x176 + len(KEYWORDS)]
                if len(perm) == len(KEYWORDS):
                    return {perm[i]: k for i, k in enumerate(KEYWORDS)}
        except OSError:
            pass
    # fallback: the table as published
    fixed = {
        0x21: "GOTO", 0x22: "GOSUB", 0x24: "IF", 0x25: "KEYIN", 0x26: "ON",
        0x27: "DEFFN'", 0x28: "GOSUB'", 0x29: "DATA", 0x2A: "SAVE",
        0x2B: "RENUMBER", 0x2C: "CLEAR", 0x2D: "LOAD", 0x2E: "LIST",
        0x2F: "RUN", 0x35: "LET", 0x36: "", 0x40: "$GIO", 0x41: "INPUT",
        0x42: "STOP", 0x43: "AND(", 0x44: "READ", 0x45: "BOOL", 0x46: "DIM",
        0x47: "CONVERT", 0x48: "PACK(", 0x4A: "ADD", 0x4B: "BIN(",
        0x4C: "PRINT", 0x4D: "ROTATE", 0x4E: "COM", 0x50: "HEXPRINT",
        0x52: "NEXT", 0x53: "REWIND", 0x54: "SELECT", 0x55: "BACKSPACE",
        0x56: "REM", 0x57: "FOR", 0x58: "SKIP", 0x59: "END", 0x5A: "DEFFN",
        0x5C: "RES", 0x5D: "UNPACK(", 0x5E: "RETURN", 0x5F: "TRACE",
        0x61: "OR(", 0x62: "XOR(", 0x64: "INIT", 0x6D: "COPY",
        0x79: "DBACKSPACE", 0x7A: "DSKIP", 0x7B: "LIMITS", 0x7E: "MOVE",
        0x81: "SCRATCH", 0x83: "VERIFY",
    }
    return fixed


# --- disk ----------------------------------------------------------------

class Disk:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.sectors = len(self.data) // SECTOR

    def sector(self, n):
        return self.data[n * SECTOR:(n + 1) * SECTOR]

    def catalog(self):
        idx = struct.unpack(">H", self.data[0:2])[0]
        out = []
        for s in range(0, idx + 1):
            sec = self.sector(s)
            for k in range(0, SECTOR, 16):
                e = sec[k:k + 16]
                if e[0] in (0x10, 0x11):
                    start = struct.unpack(">H", e[2:4])[0]
                    end = struct.unpack(">H", e[4:6])[0]
                    raw = e[8:16].rstrip(b" ")
                    out.append({
                        "name": koi8(raw),
                        "raw": raw,
                        "start": start,
                        "end": end,
                        "scratched": e[0] == 0x11,
                    })
        return out

    def body(self, entry):
        """Concatenated payload of all 0x02 body sectors of a file."""
        buf = bytearray()
        for s in range(entry["start"], entry["end"] + 1):
            sec = self.sector(s)
            if sec[0] == 0x02:
                buf += sec[2:]
        return bytes(buf)


# --- program decoding ----------------------------------------------------

def bcd2(hi, lo):
    """two packed-BCD bytes -> line number, or None if not valid BCD."""
    for b in (hi, lo):
        if (b >> 4) > 9 or (b & 0xF) > 9:
            return None
    return (hi >> 4) * 1000 + (hi & 0xF) * 100 + (lo >> 4) * 10 + (lo & 0xF)


def render_payload(pl, tokens):
    """Render one statement payload approximately as LIST would."""
    out = []
    i = 0
    while i < len(pl):
        b = pl[i]
        if b == 0xE3 and i + 1 < len(pl):          # string literal
            n = pl[i + 1]
            out.append('"' + koi8(pl[i + 2:i + 2 + n]) + '"')
            i += 2 + n
        elif b == 0xE8 and i + 1 < len(pl):        # 1-byte BCD number
            v = pl[i + 1]
            out.append(str((v >> 4) * 10 + (v & 0xF)))
            i += 2
        elif b == 0xE2 and i + 2 < len(pl):        # AT(row,col) compact
            out.append("AT(%d,%d)" % (pl[i + 1], pl[i + 2]))
            i += 3
        elif b == 0xD5 and i + 5 < len(pl) and pl[i + 1] == 0xE8:
            r = pl[i + 2]
            c = pl[i + 5] if pl[i + 4] == 0xE8 else 0
            out.append("AT(%d,%d)" % ((r >> 4) * 10 + (r & 0xF),
                                      (c >> 4) * 10 + (c & 0xF)))
            i += 6
        elif b == 0xD3 and i + 2 < len(pl):        # branch target
            ln = bcd2(pl[i + 1], pl[i + 2])
            out.append("GOTO %d" % ln if ln is not None else "GOTO ?")
            i += 3
        elif b == 0xDD:
            out.append(";")
            i += 1
        elif b == 0xEB:
            out.append("(")
            i += 1
        elif b == 0xD0:
            out.append(")")
            i += 1
        elif b == 0xDE:
            out.append(",")
            i += 1
        elif b == 0xD9:
            out.append("=")
            i += 1
        elif b == 0xD4:
            out.append(">")
            i += 1
        elif b < 0x20:                              # variable slot
            out.append("V%02X" % b)
            i += 1
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
            i += 1
        else:
            out.append("‹%02X›" % b)
            i += 1
    return " ".join(out)


def decode_lines(body, tokens, start=0, limit=None):
    """Decode [BCD][BCD][len][statements][FE] records from an offset."""
    lines = []
    i = start
    while i + 3 < len(body):
        ln = bcd2(body[i], body[i + 1])
        length = body[i + 2]
        if ln is None or length == 0 or i + 3 + length > len(body):
            i += 1
            continue
        rec = body[i + 3:i + 3 + length]
        if rec[-1] != 0xFE:
            i += 1
            continue
        stmts = []
        j = 0
        payload = rec[:-1]
        while j + 1 < len(payload):
            tok = payload[j]
            plen = payload[j + 1]
            if j + 2 + plen > len(payload):
                break
            pl = payload[j + 2:j + 2 + plen]
            name = tokens.get(tok, "‹S%02X›" % tok)
            if name == "REM":
                stmts.append("REM " + koi8(pl))
            elif name == "":
                stmts.append(render_payload(pl, tokens))
            else:
                stmts.append((name + " " + render_payload(pl, tokens)).strip())
            j += 2 + plen
        lines.append((ln, " : ".join(stmts)))
        i += 3 + length
        if limit and len(lines) >= limit:
            break
    return lines


def best_decode(body, tokens):
    """Slide the start offset; keep the run with most ascending lines."""
    best = []
    for s in range(0, min(len(body), 400)):
        got = decode_lines(body, tokens, s)
        asc = []
        last = -1
        for ln, txt in got:
            if ln > last:
                asc.append((ln, txt))
                last = ln
            else:
                break
        if len(asc) > len(best):
            best = asc
    return best


# --- commands ------------------------------------------------------------

def cmd_cat(path):
    d = Disk(path)
    print("%s, %d sectors" % (path, d.sectors))
    for e in d.catalog():
        print("  %-8s %4d..%-4d %3d sect%s"
              % (e["name"], e["start"], e["end"],
                 e["end"] - e["start"] + 1,
                 "  [scratched]" if e["scratched"] else ""))


def find(d, name):
    for e in d.catalog():
        if e["name"].strip().upper() == name.strip().upper():
            return e
    return None


def cmd_list(path, name, firmware=None):
    d = Disk(path)
    e = find(d, name)
    if not e:
        print("no such file: %s" % name)
        return
    tokens = load_token_map(firmware)
    lines = best_decode(d.body(e), tokens)
    print("%s, %d lines decoded\n" % (e["name"], len(lines)))
    for ln, txt in lines:
        print("%4d %s" % (ln, txt))


def cmd_dump(path, name):
    d = Disk(path)
    e = find(d, name)
    if not e:
        print("no such file: %s" % name)
        return
    b = d.body(e)
    for off in range(0, min(len(b), 512), 16):
        print("%04X  %-47s  %s"
              % (off, b[off:off + 16].hex(" "), koi8(b[off:off + 16])))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "cat":
        cmd_cat(argv[2])
    elif cmd == "list" and len(argv) > 3:
        cmd_list(argv[2], argv[3], argv[4] if len(argv) > 4 else None)
    elif cmd == "dump" and len(argv) > 3:
        cmd_dump(argv[2], argv[3])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
