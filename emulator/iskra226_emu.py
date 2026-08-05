#!/usr/bin/env python3
"""
iskra226_emu - research emulator for the Iskra-226 CPU (16-bit ISA).

Implements everything the surviving documentation establishes
(see isa-findings.md) and *traps* on everything it does not.
The point of this emulator is honesty: it executes the documented
instruction classes, disassembles the rest, and halts with a precise
report the moment it would have to guess semantics. Every trap is a
work item for the next round of documentation mining.

Usage:
    python3 iskra226_emu.py dis  <image.dsk> [start_word] [count]
    python3 iskra226_emu.py run  <image.dsk> [start_word] [max_steps]
    python3 iskra226_emu.py map  <image.dsk>
    python3 iskra226_emu.py messages <firmware.bin>
"""

import sys
import struct
from collections import Counter

PAGE_WORDS = 16 * 1024          # one УП page = 16K words
NUM_PAGES = 4
HEADER_BYTES = 32               # magic + signature + test pattern


# ---------------------------------------------------------------------------
# decoding
# ---------------------------------------------------------------------------

def decode(w):
    """
    Classify one 16-bit word.

    Returns (mnemonic, detail, confidence) where confidence is:
      'doc'   semantics documented in Aladiev (safe to execute)
      'class' class known, exact semantics not (disassemble only)
      'unk'   nothing established
    """
    hi = w >> 12

    if hi == 0x0:
        sub = (w >> 8) & 0xF
        reg = (w >> 4) & 0xF
        imm = w & 0xF
        if sub == 0:
            return ("ADDI", "RS + RB%d + %d -> RB%d" % (reg, imm, reg), "doc")
        return ("ARI.%X" % sub, "reg=%d imm=%d (sub-op undocumented)"
                % (reg, imm), "class")

    if 0x8 <= hi <= 0xB:
        addr = w & 0x3FFF
        sub = hi & 0x3
        if hi == 0xA:
            return ("JMP", "-> %04X (page-relative, unconditional)" % addr,
                    "doc")
        names = {0x8: "JT0", 0x9: "JT1", 0xB: "JT3"}
        return (names[hi], "-> %04X (transfer variant, semantics open)"
                % addr, "class")

    if hi == 0xE:
        # Sub-op nibble (bits 11-8). Only the three sub-blocks with a
        # worked example in Aladiev are trusted; LE field statistics
        # show the rest of the E block carries mode bits (F-heavy
        # fields), so it is disassembled but not executed.
        sub = (w >> 8) & 0xF
        rb = (w >> 4) & 0xF
        rr = w & 0xF
        if sub == 0x0 and rb != 0xF and rr != 0xF:
            return ("TBL", "УП[RS+RB%d] -> RS,RR%d" % (rb, rr), "doc")
        if sub == 0x5 and rb != 0xF and rr != 0xF:
            return ("MEMW", "ОП[RB%d]+RS -> RR%d" % (rb, rr), "doc")
        if sub == 0x8 and rb != 0xF and rr != 0xF:
            return ("DEV", "RB%d gateway -> RR%d (УП byte / КУ)" % (rb, rr),
                    "doc")
        return ("E%X." % sub, "E sub-op, mode fields open (rb=%X rr=%X)"
                % (rb, rr), "class")

    return ("W_%X" % hi, "class undocumented", "unk")


# ---------------------------------------------------------------------------
# machine
# ---------------------------------------------------------------------------

class Trap(Exception):
    def __init__(self, page, pc, word, mnem, detail):
        self.page, self.pc, self.word = page, pc, word
        self.mnem, self.detail = mnem, detail
        super().__init__("%s %04X @ page %d:%04X - %s"
                         % (mnem, word, page, pc, detail))


class Iskra226:
    def __init__(self):
        self.up = [[0] * PAGE_WORDS for _ in range(NUM_PAGES)]  # УП
        self.op = bytearray(64 * 1024)                          # ОП
        self.rb = [0] * 15
        self.rr = [0] * 15
        self.rs = 0
        self.page = 0
        self.pc = 0
        self.steps = 0
        self.trace = []

    # -- loading -----------------------------------------------------------

    def load_disk(self, path, skip_header=True):
        """
        Load a boot image into УП pages sequentially.

        The real ROM loader's mapping is unknown (open item 2 in the
        findings); the image is larger than УП, so overlays exist. We
        load the first 4 pages' worth verbatim, which is the simplest
        hypothesis and enough to explore the resident code.
        """
        data = open(path, "rb").read()
        if skip_header:
            data = data[HEADER_BYTES:]
        words = [struct.unpack("<H", data[i:i + 2])[0]
                 for i in range(0, min(len(data),
                                       NUM_PAGES * PAGE_WORDS * 2) - 1, 2)]
        for i, w in enumerate(words):
            self.up[i // PAGE_WORDS][i % PAGE_WORDS] = w
        return len(words)

    # -- execution ---------------------------------------------------------

    def fetch(self):
        return self.up[self.page][self.pc]

    def _wreg(self, kind, n, v):
        (self.rb if kind == "rb" else self.rr)[n] = v & 0xFFFF

    def step(self):
        w = self.fetch()
        mnem, detail, conf = decode(w)
        self.trace.append((self.page, self.pc, w, mnem, detail))
        if conf != "doc":
            raise Trap(self.page, self.pc, w, mnem, detail)

        if mnem == "ADDI":
            reg = (w >> 4) & 0xF
            imm = w & 0xF
            if reg == 0xF:
                raise Trap(self.page, self.pc, w, mnem,
                           "reg field 15: special variant, undocumented")
            self._wreg("rb", reg, self.rs + self.rb[reg] + imm)
            self.pc = (self.pc + 1) & 0x3FFF

        elif mnem == "JMP":
            self.pc = w & 0x3FFF

        elif mnem == "TBL":
            rb = (w >> 4) & 0xF
            rr = w & 0xF
            if 0xF in (rb, rr):
                raise Trap(self.page, self.pc, w, mnem,
                           "field 15: inline-constant variant, undocumented")
            addr = (self.rs + self.rb[rb]) & 0x3FFF
            self.rs = self.up[self.page][addr]
            self._wreg("rr", rr, self.rs)
            self.pc = (self.pc + 1) & 0x3FFF

        elif mnem == "MEMW":
            rb = (w >> 4) & 0xF
            rr = w & 0xF
            if 0xF in (rb, rr):
                raise Trap(self.page, self.pc, w, mnem,
                           "field 15: byte/RS variant, undocumented")
            addr = (self.rb[rb] >> 1) & 0x7FFF
            word = struct.unpack_from(">H", self.op, (addr * 2) % 0xFFFE)[0]
            self._wreg("rr", rr, word + self.rs)
            self.pc = (self.pc + 1) & 0x3FFF

        elif mnem == "DEV":
            rb = (w >> 4) & 0xF
            rr = w & 0xF
            if 0xF in (rb, rr):
                raise Trap(self.page, self.pc, w, mnem,
                           "field 15 variant, undocumented")
            base = self.rb[rb]
            if base & 0x8000:
                raise Trap(self.page, self.pc, w, mnem,
                           "КУ transaction: channel device not emulated yet")
            addr = ((base >> 1) + self.rs) & 0x3FFF
            word = self.up[self.page][addr]
            byte = word & 0xFF if (base & 1) == 0 else word >> 8
            self.rs = byte
            self._wreg("rr", rr, byte)
            self.pc = (self.pc + 1) & 0x3FFF

        self.steps += 1

    def run(self, max_steps=100000):
        try:
            while self.steps < max_steps:
                self.step()
            return None
        except Trap as t:
            return t


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def words_of(path):
    d = open(path, "rb").read()[HEADER_BYTES:]
    return [struct.unpack("<H", d[i:i + 2])[0]
            for i in range(0, len(d) - 1, 2)]


def cmd_dis(path, start=0, count=48):
    ws = words_of(path)
    for i in range(start, min(start + count, len(ws))):
        w = ws[i]
        mnem, detail, conf = decode(w)
        flag = {"doc": " ", "class": "?", "unk": "!"}[conf]
        print("%05X  %04X  %s %-6s %s" % (i, w, flag, mnem, detail))


def cmd_map(path):
    ws = words_of(path)
    conf = Counter(decode(w)[2] for w in ws)
    cls = Counter(decode(w)[0].split(".")[0].rstrip("0123456789?")
                  for w in ws)
    n = len(ws)
    print("%s: %d words" % (path, n))
    print("executable now (doc): %6.2f%%" % (100 * conf["doc"] / n))
    print("class known (dis)   : %6.2f%%" % (100 * conf["class"] / n))
    print("unknown             : %6.2f%%" % (100 * conf["unk"] / n))
    print("\nby mnemonic family:")
    for k, v in cls.most_common():
        print("  %-6s %6.2f%%" % (k, 100 * v / n))


def cmd_run(path, start=0, max_steps=100000):
    m = Iskra226()
    n = m.load_disk(path)
    print("loaded %d words into УП (%d pages)" % (n, NUM_PAGES))
    m.pc = start
    trap = m.run(max_steps)
    print("executed %d instructions" % m.steps)
    print("\nlast instructions:")
    for page, pc, w, mnem, detail in m.trace[-12:]:
        print("  %d:%04X  %04X  %-6s %s" % (page, pc, w, mnem, detail))
    if trap:
        print("\nTRAP: %s" % trap)
        print("register file at trap:")
        print("  RS=%04X  RB=%s" % (m.rs,
              " ".join("%04X" % r for r in m.rb)))
    else:
        print("step limit reached without trap")




# --- verified addition 2026-08-05 ------------------------------------------
# DEV with bit 16 of the base register clear is a BYTE LOAD from control
# memory: RR := byte at ((RB >> 1) + RS), half selected by bit 1 of RB.
# Verified against all seven entries of the firmware message pointer table
# (see addendum 13/14 in isa-findings.md).

KOI = {0xC0 + i: c for i, c in enumerate("юабцдефгхийклмнопярстужвьызшэщчъ")}
KOI.update({0xE0 + i: c.upper()
            for i, c in enumerate("юабцдефгхийклмнопярстужвьызшэщчъ")})

MESSAGE_POINTERS = [0x107D, 0x108E, 0x108F, 0x1090, 0x1091, 0x1093, 0x1094]


def dev_byte_load(words, rb, rs=0):
    """The machine's own byte addressing rule (Aladiev, E865, a=0)."""
    addr = ((rb >> 1) + rs) & 0x3FFF
    w = words[addr]
    return (w & 0xFF) if (rb & 1) == 0 else (w >> 8)


def read_string(words, rb, limit=64):
    """Walk a string the way the firmware does: byte pointer, +1 per char."""
    out = []
    for _ in range(limit):
        b = dev_byte_load(words, rb)
        if b in (0x00, 0x3A):          # NUL or ':' terminate an entry
            break
        out.append(KOI.get(b, chr(b) if 0x20 <= b < 0x7F else ""))
        rb = (rb + 1) & 0xFFFF
    return "".join(out)


def cmd_messages(path):
    """Print the firmware's system messages using the machine's own rules."""
    ws = words_of_full(path)
    for pw in MESSAGE_POINTERS:
        print("  ptr @%04X -> %r" % (pw, read_string(ws, ws[pw])))


def words_of_full(path):
    d = open(path, "rb").read()
    return [struct.unpack("<H", d[i:i + 2])[0]
            for i in range(0, len(d) - 1, 2)]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, path = argv[1], argv[2]
    a3 = int(argv[3], 0) if len(argv) > 3 else 0
    a4 = int(argv[4], 0) if len(argv) > 4 else (48 if cmd == "dis" else 100000)
    if cmd == "dis":
        cmd_dis(path, a3, a4)
    elif cmd == "messages":
        cmd_messages(path)
    elif cmd == "map":
        cmd_map(path)
    elif cmd == "run":
        cmd_run(path, a3, a4)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
