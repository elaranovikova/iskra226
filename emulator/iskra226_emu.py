#!/usr/bin/env python3
"""
iskra226_emu - research emulator for the Iskra-226 CPU (16-bit ISA).

The instruction encoding implemented here is not a hypothesis. It is the
encoding used by the machine's own tooling: the BASIC-written disassembler
DASB2, recovered from disk image w005-s1v1.dsk, carries the complete
mnemonic table and the field-extraction code (its lines 9704-9920). The
semantics come from the manufacturer's assembler manual "Ассемблер 226"
(V. N. Shilko, Leningrad 1985), sections 2.1 to 2.19, whose worked examples
are reproduced by this emulator bit for bit (see cmd_selftest).

Word format, from DASB2 line 9710/9714:

    bits 16-15 = 00   /УПij/  conditional branch, PC-relative, +/-1023
    bits 16-15 = 01   /ПВ/    call, 14-bit address inside the current page
    bits 16-15 = 10   /БП/    jump, 14-bit address inside the current page
    bits 16-15 = 11   one of 64 base instructions, selected by the high byte;
                      low byte holds field I (bits 8-5) and field J (bits 4-1)

Field value 15 means "operand absent" and selects the one-address form of
the instruction (DASB2 line 9740/9744).

Soviet bit numbering is used throughout: bit 1 = LSB, bit 16 = MSB.

Usage:
    python3 iskra226_emu.py dis      <image.bin> [start_word] [count]
    python3 iskra226_emu.py run      <image.bin> [start_word] [max_steps]
    python3 iskra226_emu.py map      <image.bin>
    python3 iskra226_emu.py walk     <image.bin>
    python3 iskra226_emu.py messages <firmware.bin>
    python3 iskra226_emu.py selftest
"""

import sys
import struct
from collections import Counter

PAGE_WORDS = 16 * 1024          # one УП page = 16K words
NUM_PAGES = 4
HEADER_BYTES = 32               # magic + signature + test pattern


# ---------------------------------------------------------------------------
# the instruction table
# ---------------------------------------------------------------------------
#
# Index = high byte of the word, 0xC0 .. 0xFF. Transcribed from array A$ of
# DASB2 (read out of the raw sector bytes, not from a lister, to avoid
# transcription artefacts).
#
# Columns: family tag, assembler template, execution status.
#   "doc"   semantics established and executed here
#   "class" instruction identified, but execution needs something this
#           emulator does not model (channel device, ПМК microcode, the
#           system-level extracode routines)
#
# Template placeholders: I = field I, J = field J, L = field J as a 0..15
# constant, K = field J + 1 as a shift width, C = whole low byte 0..255.

BASE_OPS = {
    # 2.5  register +/- register           (bit 4 = type of I, bit 3 = sign,
    0xC0: ("ARI", "+Р{I} -Р{J}", "doc"),   #  bit 2 = type of J, bit 1 = store)
    0xC1: ("ARI", "+Р{I} -Р{J} *", "doc"),
    0xC2: ("ARI", "+Р{I} -Б{J}", "doc"),
    0xC3: ("ARI", "+Р{I} -Б{J} *", "doc"),
    0xC4: ("ARI", "+Р{I} +Р{J}", "doc"),
    0xC5: ("ARI", "+Р{I} +Р{J} *", "doc"),
    0xC6: ("ARI", "+Р{I} +Б{J}", "doc"),
    0xC7: ("ARI", "+Р{I} +Б{J} *", "doc"),
    0xC8: ("ARI", "+Б{I} -Р{J}", "doc"),
    # DASB2 repeats "+БI -БJ *" here; the bit pattern of C9 = 1001 demands
    # "-Р{J} *", and the other 15 entries of the block are strictly regular.
    # Corrected, and flagged in the report.
    0xC9: ("ARI", "+Б{I} -Р{J} *", "doc"),
    0xCA: ("ARI", "+Б{I} -Б{J}", "doc"),
    0xCB: ("ARI", "+Б{I} -Б{J} *", "doc"),
    0xCC: ("ARI", "+Б{I} +Р{J}", "doc"),
    0xCD: ("ARI", "+Б{I} +Р{J} *", "doc"),
    0xCE: ("ARI", "+Б{I} +Б{J}", "doc"),
    0xCF: ("ARI", "+Б{I} +Б{J} *", "doc"),
    # 2.6 register +/- 4-bit constant, 2.9 logical shifts
    0xD0: ("ARI", "+Р{I} -{L}", "doc"),
    0xD1: ("ARI", "+Р{I} -{L} *", "doc"),
    0xD2: ("SHF", "+Р{I} /СДЛ/{K}", "doc"),
    0xD3: ("SHF", "+Р{I} /СДЛ/{K} *", "doc"),
    0xD4: ("ARI", "+Р{I} +{L}", "doc"),
    0xD5: ("ARI", "+Р{I} +{L} *", "doc"),
    0xD6: ("SHF", "+Р{I} /СДП/{K}", "doc"),
    0xD7: ("SHF", "+Р{I} /СДП/{K} *", "doc"),
    0xD8: ("ARI", "+Б{I} -{L}", "doc"),
    0xD9: ("ARI", "+Б{I} -{L} *", "doc"),
    0xDA: ("SHF", "+Б{I} /СДЛ/{K}", "doc"),
    0xDB: ("SHF", "+Б{I} /СДЛ/{K} *", "doc"),
    0xDC: ("ARI", "+Б{I} +{L}", "doc"),
    0xDD: ("ARI", "+Б{I} +{L} *", "doc"),
    0xDE: ("SHF", "+Б{I} /СДП/{K}", "doc"),
    0xDF: ("SHF", "+Б{I} /СДП/{K} *", "doc"),
    # 2.7 summator +/- 8-bit constant, 2.8 logic, 2.10 moves, 2.11 direct ОЗУ
    0xE0: ("LOG", "/СР/Р{I} * Р{J}", "doc"),
    0xE1: ("ARI", "/-/{C}", "doc"),
    0xE2: ("LOG", "/СРК/{C}", "doc"),
    0xE3: ("MOV", "+Р{I} * Р{J}", "doc"),
    0xE4: ("LOG", "/ЛУ/Р{I} * Р{J}", "doc"),
    0xE5: ("ARI", "/+/{C}", "doc"),
    0xE6: ("LOG", "/ЛУК/{C}", "doc"),
    0xE7: ("MOV", "+Р{I} * Б{J}", "doc"),
    0xE8: ("LOG", "/СР/Б{I} * Б{J}", "doc"),
    0xE9: ("CEL", "-/ЯЧ/{C}", "doc"),
    0xEA: ("CEL", "/СРЯ/{C}", "doc"),
    0xEB: ("MOV", "+Б{I} * Р{J}", "doc"),
    0xEC: ("LOG", "/ЛУ/Б{I} * Б{J}", "doc"),
    0xED: ("CEL", "+/ЯЧ/{C}", "doc"),
    0xEE: ("CEL", "/ЛУЯ/{C}", "doc"),
    0xEF: ("MOV", "+Б{I} * Б{J}", "doc"),
    # 2.11 store, 2.14 constants, 2.17 switch, 2.12 indirect ОЗУ,
    # 2.16 return, 2.18 directed addressing, 2.13 table fetch
    0xF0: ("CEL", "*/ЯЧ/{C}", "doc"),
    0xF1: ("KON", "/КОН/{L} * Р{I}", "doc"),
    0xF2: ("SWI", "/ПК/{C}", "doc"),
    0xF3: ("MEM", "+Р{I} * /СЛ/Б{J}", "doc"),
    0xF4: ("SWI", "/ПВК/{C}", "doc"),
    0xF5: ("MEM", "+/СЛ/Б{I} * Р{J}", "doc"),
    0xF6: ("RET", "/ВВ/", "doc"),
    0xF7: ("MEM", "+Р{I} * /БТ/Б{J}", "doc"),
    0xF8: ("NAD", "/НАД/Б{I} * Р{J}", "doc"),
    0xF9: ("MEM", "+/БТ/Б{I} * Р{J}", "doc"),
    0xFA: ("NAD", "/НАД/Б{I} * Б{J}", "doc"),
    0xFB: ("KON", "/КОН/{L} * Б{I}", "doc"),
    # type 2 of 2.18: bit 16 of Б{J} clear hands control to a ПМК
    # microprogram, set sends to the channel device. Neither is modelled.
    0xFC: ("NAD", "+Р{I} * /НАД/Б{J}", "class"),
    0xFD: ("TAB", "/ТАБ/Б{I} * Р{J}", "doc"),
    0xFE: ("NAD", "+Б{I} * /НАД/Б{J}", "class"),
    0xFF: ("TAB", "/ТАБ/Б{I} * Б{J}", "doc"),
}

# 2.19 extension set. DASB2 line 9732-9736: high byte F6 with a low byte
# below 0x13 is not /ВВ/ but an extracode; array C$ holds the names.
EXTRACODES = [
    "/ЭК/", "/ВВЭК/", "/ЗР/", "/ЗБ/", "/ВР/", "/ВБ/", "/ЗП/", "/ВП/",
    "/УМН/", "/ДЕЛ/", "/КЕД/", "/ПУР/", "/ПСЛ/", "/ПСЛУП/", "/ПБ/",
    "/СРТ/", "/ПОИСК/", "/ЛОПМ/", "/УСОБ/",
]
# extracodes 2..7 (/ЗР/ /ЗБ/ /ВР/ /ВБ/ /ЗП/ /ВП/) carry a register mask in
# the following word, per manual 2.19.4/2.19.5 and DASB2 line 9736.
EXTRACODE_WITH_MASK = set(range(2, 8))

# 2.15: the eight conditional transfers, in the order of DASB2 array B$.
COND_NAMES = ["УП10", "УП11", "УП20", "УП21",
              "УП30", "УП31", "УП40", "УП41"]


def field_text(tpl, i, j, lo):
    """Render an assembler template with the operand fields filled in."""
    out = tpl
    if "{I}" in out:
        out = out.replace("{I}", "" if i == 15 else str(i))
    if "{J}" in out:
        out = out.replace("{J}", "" if j == 15 else str(j))
    out = out.replace("{L}", str(j)).replace("{K}", str(j + 1))
    out = out.replace("{C}", str(lo))
    return out


def decode(w):
    """
    Classify one 16-bit word.

    Returns (family, detail, confidence) where confidence is:
      'doc'   semantics established, executed by this emulator
      'class' instruction identified, execution not possible here
      'unk'   nothing established
    """
    cls = w >> 14

    if cls == 0:                                    # /УПij/, 2.15
        cond = (w >> 11) & 0x7
        sign = (w >> 10) & 0x1
        mag = w & 0x3FF
        return ("J" + COND_NAMES[cond],
                "/%s/ %s%d (relative)" % (COND_NAMES[cond],
                                          "+" if sign else "-", mag),
                "doc")

    if cls == 1:                                    # /ПВ/, 2.16
        return ("PV", "/ПВ/ %04X (call, in page)" % (w & 0x3FFF), "doc")

    if cls == 2:                                    # /БП/, 2.16
        return ("BP", "/БП/ %04X (jump, in page)" % (w & 0x3FFF), "doc")

    hi, lo = w >> 8, w & 0xFF
    i, j = (lo >> 4) & 0xF, lo & 0xF

    if hi == 0xF6:                                  # 2.16 return / 2.19 ext
        if lo == 0xFF:
            return ("RET", "/ВВ/", "doc")
        if lo < len(EXTRACODES):
            return ("EXT", "%s (extracode, system level)" % EXTRACODES[lo],
                    "class")
        return ("EXT", "ЭКСТРАКОД %02X (system level)" % lo, "class")

    fam, tpl, conf = BASE_OPS[hi]
    return (fam, field_text(tpl, i, j, lo), conf)


# ---------------------------------------------------------------------------
# machine
# ---------------------------------------------------------------------------

class Trap(Exception):
    def __init__(self, pc, word, mnem, detail):
        self.pc, self.word = pc, word
        self.mnem, self.detail = mnem, detail
        super().__init__("%s %04X @ %04X - %s" % (mnem, word, pc, detail))


class Iskra226:
    """
    Operational unit of the Iskra-226 per manual 2.1:
      УП   control store, addressed by word, four pages of 16K
      ОЗУ  operand store, addressed by byte, little endian words
      СМ   16-bit summator
      W1..W4 four flag triggers
      30 general registers, Б0..Б14 (base) and Р0..Р14 (working);
      Б13 is the ОЗУ segment base, Б14 the return-stack pointer (2.2.4)
    """

    def __init__(self):
        self.up = [0] * (NUM_PAGES * PAGE_WORDS)
        self.oz = bytearray(64 * 1024)
        self.rb = [0] * 15
        self.rr = [0] * 15
        self.sm = 0
        self.w = [0, 0, 0, 0]
        self.pc = 0
        self.steps = 0
        self.trace = []

    # -- loading -----------------------------------------------------------

    def load(self, path):
        """
        Load a boot image into УП. Word 0 of the file is the cold-start
        vector (/БП/ 1006), so the image is loaded verbatim, without
        skipping the signature block: those words are data that the loaded
        code never executes, and dropping them would shift every address.
        """
        data = open(path, "rb").read()
        n = min(len(data) // 2, len(self.up))
        for i in range(n):
            self.up[i] = struct.unpack_from("<H", data, i * 2)[0]
        return n

    # -- ALU helpers -------------------------------------------------------

    def _add(self, a, b):
        """
        a + b on the summator, 16-bit, flags per manual 2.4.2:
        W1/W2/W3 = carry out of bit 4 / 8 / 16, W4 = result is zero.
        """
        self.w[0] = 1 if (a & 0xF) + (b & 0xF) > 0xF else 0
        self.w[1] = 1 if (a & 0xFF) + (b & 0xFF) > 0xFF else 0
        total = a + b
        self.w[2] = 1 if total > 0xFFFF else 0
        r = total & 0xFFFF
        self.w[3] = 1 if r == 0 else 0
        return r

    def _sub(self, a, b):
        """a - b, executed as an addition of the two's complement, so the
        carry flags come out the way the machine reports them (checked
        against the example table of manual 2.6.2)."""
        return self._add(a, (-b) & 0xFFFF)

    def _logic(self, r):
        """Flags after a logical operation, manual 2.8.1: W1..W3 undefined
        (left as they were), W4 set if the result is zero."""
        self.w[3] = 1 if (r & 0xFFFF) == 0 else 0
        return r & 0xFFFF

    def _shift(self, v, k, left):
        """
        Logical shift by k places, manual 2.9.2, flags per 2.4.3: W1..W3
        are taken from bits of the summator as it stood before the *last*
        single-place shift (left: bits 4, 8, 16; right: bits 5, 9, 1).
        """
        if k <= 0:
            return v & 0xFFFF
        pre = ((v << (k - 1)) if left else (v >> (k - 1))) & 0xFFFF
        r = ((pre << 1) if left else (pre >> 1)) & 0xFFFF
        if left:
            self.w[0] = (pre >> 3) & 1     # bit 4
            self.w[1] = (pre >> 7) & 1     # bit 8
            self.w[2] = (pre >> 15) & 1    # bit 16
        else:
            self.w[0] = (pre >> 4) & 1     # bit 5
            self.w[1] = (pre >> 8) & 1     # bit 9
            self.w[2] = pre & 1            # bit 1
        self.w[3] = 1 if r == 0 else 0
        return r

    # -- register and memory access ----------------------------------------

    def _get(self, kind, n):
        return (self.rb if kind == "B" else self.rr)[n]

    def _set(self, kind, n, v):
        (self.rb if kind == "B" else self.rr)[n] = v & 0xFFFF

    def _oz_word(self, addr):
        return struct.unpack_from("<H", self.oz, addr & 0xFFFE)[0]

    def _oz_word_set(self, addr, v):
        struct.pack_into("<H", self.oz, addr & 0xFFFE, v & 0xFFFF)

    def _page(self):
        return self.pc & ~(PAGE_WORDS - 1)

    def _push(self, addr):
        """2.16.2: the return address goes into the top cell of the return
        stack, whose address is in Б14; Б14 then grows by 2."""
        self._oz_word_set(self.rb[14], addr)
        self.rb[14] = (self.rb[14] + 2) & 0xFFFF

    def _pop(self):
        """2.16.3: Б14 is decremented by 2 and the address fetched."""
        self.rb[14] = (self.rb[14] - 2) & 0xFFFF
        return self._oz_word(self.rb[14])

    # -- execution ---------------------------------------------------------

    def step(self):
        pc = self.pc
        w = self.up[pc]
        fam, detail, conf = decode(w)
        self.trace.append((pc, w, fam, detail))
        if conf != "doc":
            if (w >> 8) in (0xFC, 0xFE):
                # 2.18.4: with bit 16 of Б{J} clear this hands control to a
                # microprogram in the ПМК, addressed by bits 1-12 of Б{J};
                # with bit 16 set it is an output transaction to the channel
                # unit. Report which of the two, and the ПМК address, so the
                # trap names exactly what is missing.
                bj = self.rb[w & 0xF] if (w & 0xF) != 15 else 0
                if bj & 0x8000:
                    detail += "  -> КУ output, service word %04X" % bj
                else:
                    detail += "  -> ПМК microprogram at %03X (no ROM dump)" \
                              % (bj & 0xFFF)
            raise Trap(pc, w, fam, detail)

        cls = w >> 14
        if cls == 0:                                   # conditional transfer
            cond = (w >> 11) & 0x7
            want = cond & 1
            flag = self.w[cond >> 1]
            mag = w & 0x3FF
            taken = (flag == want)
            self.sm = 0                                # 2.15.2
            if taken:
                delta = mag if (w >> 10) & 1 else -mag
                self.pc = (pc + 1 + delta) & 0xFFFF
            else:
                self.pc = pc + 1
            self.steps += 1
            return

        if cls == 1:                                   # /ПВ/
            self._push(pc + 1)
            self.pc = self._page() | (w & 0x3FFF)
            self.steps += 1
            return

        if cls == 2:                                   # /БП/
            self.pc = self._page() | (w & 0x3FFF)
            self.steps += 1
            return

        hi, lo = w >> 8, w & 0xFF
        i, j = (lo >> 4) & 0xF, lo & 0xF
        nxt = pc + 1

        if hi == 0xF6:                                 # /ВВ/
            self.pc = self._pop()
            self.steps += 1
            return

        if 0xC0 <= hi <= 0xCF:                         # 2.5
            t1 = "B" if hi & 0x8 else "R"
            t2 = "B" if hi & 0x2 else "R"
            plus = bool(hi & 0x4)
            store = bool(hi & 0x1)
            if i != 15:
                self.sm = self._add(self.sm, self._get(t1, i))
            if j != 15:
                v = self._get(t2, j)
                self.sm = self._add(self.sm, v) if plus \
                    else self._sub(self.sm, v)
                if store:
                    self._set(t2, j, self.sm)
                    self.sm = 0

        elif 0xD0 <= hi <= 0xDF:                       # 2.6 and 2.9
            t = "B" if hi & 0x8 else "R"
            shift = bool(hi & 0x2)
            up = bool(hi & 0x4)
            store = bool(hi & 0x1)
            if i != 15:
                self.sm = self._add(self.sm, self._get(t, i))
            if shift:
                self.sm = self._shift(self.sm, j + 1, left=not up)
            else:
                self.sm = self._add(self.sm, j) if up \
                    else self._sub(self.sm, j)
            if store and i != 15:
                self._set(t, i, self.sm)
                self.sm = 0

        elif hi in (0xE0, 0xE4, 0xE8, 0xEC):           # 2.8 register logic
            t = "B" if hi in (0xE8, 0xEC) else "R"
            src = self._get(t, i) if i != 15 else 0
            r = (self.sm & src) if hi in (0xE4, 0xEC) else (self.sm ^ src)
            r = self._logic(r)
            if j == 15:
                self.sm = r                            # 2.8.2 one-address
            else:
                self._set(t, j, r)
                self.sm = 0

        elif hi in (0xE1, 0xE5):                       # 2.7 summator + const
            self.sm = self._add(self.sm, lo) if hi == 0xE5 \
                else self._sub(self.sm, lo)

        elif hi in (0xE2, 0xE6):                       # 2.8.3 const logic
            self.sm = self._logic(self.sm & lo if hi == 0xE6
                                  else self.sm ^ lo)

        elif hi in (0xE3, 0xE7, 0xEB, 0xEF):           # 2.10 moves
            t1 = "B" if hi in (0xEB, 0xEF) else "R"
            t2 = "B" if hi in (0xE7, 0xEF) else "R"
            if i != 15:
                self.sm = self._add(self.sm, self._get(t1, i))
            if j != 15:
                self._set(t2, j, self.sm)
            self.sm = 0                                # 2.10.2 / 2.10.3

        elif hi in (0xE9, 0xEA, 0xED, 0xEE, 0xF0):     # 2.11 direct ОЗУ
            addr = (self.rb[13] + 2 * lo) & 0xFFFF
            if hi == 0xF0:
                self._oz_word_set(addr, self.sm)
                self.sm = 0
            else:
                v = self._oz_word(addr)
                if hi == 0xED:
                    self.sm = self._add(self.sm, v)
                elif hi == 0xE9:
                    self.sm = self._sub(self.sm, v)
                elif hi == 0xEE:
                    self.sm = self._logic(self.sm & v)
                else:
                    self.sm = self._logic(self.sm ^ v)

        elif hi in (0xF3, 0xF7):                       # 2.12 store to ОЗУ
            if i != 15:
                self.sm = self._add(self.sm, self.rr[i])
            addr = self.rb[j] if j != 15 else 0
            if hi == 0xF3:
                self._oz_word_set(addr, self.sm)
            else:
                self.oz[addr & 0xFFFF] = self.sm & 0xFF
            self.sm = 0

        elif hi in (0xF5, 0xF9):                       # 2.12 load from ОЗУ
            addr = self.rb[i] if i != 15 else 0
            v = self._oz_word(addr) if hi == 0xF5 else self.oz[addr & 0xFFFF]
            self.sm = self._add(self.sm, v)
            if j != 15:
                self.rr[j] = self.sm
                self.sm = 0

        elif hi in (0xFD, 0xFF):                       # 2.13 /ТАБ/
            base = self.rb[i] if i != 15 else 0
            v = self.up[(self.sm + base) & (NUM_PAGES * PAGE_WORDS - 1)]
            self.w[3] = 1 if v == 0 else 0             # 2.13.3
            if j == 15:
                self.sm = v
            else:
                self._set("B" if hi == 0xFF else "R", j, v)
                self.sm = 0

        elif hi in (0xF1, 0xFB):                       # 2.14 /КОН/
            # constant block follows the instruction: j + 1 words, the one
            # selected sits at A + СМ + 1, execution resumes at A + j + 2
            addr = (pc + 1 + self.sm) & 0xFFFF
            v = self.up[addr]
            self.w[3] = 1 if v == 0 else 0             # 2.14.4
            if i == 15:
                self.sm = v
            else:
                self._set("B" if hi == 0xFB else "R", i, v)
                self.sm = 0
            nxt = pc + j + 2

        elif hi == 0xF2:                               # 2.17.3 /ПК/
            idx = self.sm if self.sm < lo else lo
            self.pc = self.up[(pc + 1 + idx) & 0xFFFF]
            self.sm = 0
            self.steps += 1
            return

        elif hi == 0xF4:                               # 2.17.4 /ПВК/
            self._push((pc + lo + 1) & 0xFFFF)
            self.pc = self.up[(pc + 1 + self.sm) & 0xFFFF]
            self.sm = 0
            self.steps += 1
            return

        elif hi in (0xF8, 0xFA):                       # 2.18 type 1
            base = self.rb[i] if i != 15 else 0
            if base & 0x8000:                          # 2.18.3, channel unit
                raise Trap(pc, w, fam,
                           "КУ transaction: channel device not modelled")
            # 2.18.2 with bit 16 clear: fetch a byte of УП whose address is
            # СМ plus Б{I} shifted right by one. Verified against all seven
            # message-pointer entries of the firmware (findings addendum 14).
            word = self.up[((base >> 1) + self.sm) & (NUM_PAGES * PAGE_WORDS - 1)]
            byte = (word & 0xFF) if (base & 1) == 0 else (word >> 8)
            self.w[0] = self.w[1] = self.w[2] = 0      # 2.18.5
            self.w[3] = 1 if byte == 0 else 0
            if j != 15:
                self._set("B" if hi == 0xFA else "R", j, byte)
            self.sm = 0

        else:
            raise Trap(pc, w, fam, detail)

        self.pc = nxt & 0xFFFF
        self.steps += 1

    def run(self, max_steps=100000):
        try:
            while self.steps < max_steps:
                self.step()
            return None
        except Trap as t:
            return t
        except (IndexError, ValueError) as e:
            return Trap(self.pc, self.up[self.pc & 0xFFFF] if
                        self.pc < len(self.up) else 0, "FAULT", str(e))


# ---------------------------------------------------------------------------
# static analysis
# ---------------------------------------------------------------------------

def inline_words(w):
    """
    How many words follow this instruction as operands rather than as
    instructions. Everything else is one word long.
    """
    if w >> 14 != 3:
        return 0
    hi, lo = w >> 8, w & 0xFF
    if hi in (0xF1, 0xFB):
        return (lo & 0xF) + 1               # /КОН/, manual 2.14.2
    if hi == 0xF2:
        return lo + 1                       # /ПК/, list of C+1 words
    if hi == 0xF4:
        return lo                           # /ПВК/, DASB2 line 9758
    if hi == 0xF6 and lo in EXTRACODE_WITH_MASK:
        return 1                            # register mask, 2.19.4
    return 0


def walk(words, entries):
    """
    Recursive descent over the instruction stream, honouring the four
    variable-length instructions. Returns (instruction words, operand
    words, conflicts), where a conflict is a word reached both as an
    instruction and as an operand of another instruction. Conflicts are the
    honest failure signal: a wrong length rule desynchronises the stream and
    produces them in quantity.
    """
    n = len(words)
    seen, operand = set(), set()
    todo = [e for e in entries if 0 <= e < n]
    while todo:
        pc = todo.pop()
        while 0 <= pc < n and pc not in seen:
            seen.add(pc)
            w = words[pc]
            cls = w >> 14
            page = pc & ~(PAGE_WORDS - 1)
            k = inline_words(w)
            for m in range(1, k + 1):
                if pc + m < n:
                    operand.add(pc + m)
            hi = w >> 8
            if cls == 0:
                mag = w & 0x3FF
                t = pc + 1 + (mag if (w >> 10) & 1 else -mag)
                if 0 <= t < n:
                    todo.append(t)
                pc += 1
            elif cls == 1:
                t = page | (w & 0x3FFF)
                if t < n:
                    todo.append(t)
                pc += 1
            elif cls == 2:
                pc = page | (w & 0x3FFF)
            elif cls == 3 and hi == 0xF6 and (w & 0xFF) == 0xFF:
                break                                   # /ВВ/
            elif cls == 3 and hi in (0xF2, 0xF4):
                for m in range(1, k + 1):
                    if pc + m < n and words[pc + m] < n:
                        todo.append(words[pc + m])
                if hi == 0xF2:
                    break                               # /ПК/ always transfers
                pc += k + 1
            else:
                pc += k + 1
    return seen, operand, seen & operand


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def words_of(path):
    """Word list used by `map` and `dis`. The 32-byte signature block is
    skipped, exactly as before, so the coverage figures stay comparable to
    the ones measured before this rewrite."""
    d = open(path, "rb").read()[HEADER_BYTES:]
    return [struct.unpack("<H", d[i:i + 2])[0]
            for i in range(0, len(d) - 1, 2)]


def words_of_full(path):
    d = open(path, "rb").read()
    return [struct.unpack("<H", d[i:i + 2])[0]
            for i in range(0, len(d) - 1, 2)]


def cmd_dis(path, start=0, count=48):
    ws = words_of_full(path)
    i = start
    end = min(start + count, len(ws))
    while i < end:
        w = ws[i]
        fam, detail, conf = decode(w)
        flag = {"doc": " ", "class": "?", "unk": "!"}[conf]
        print("%05X  %04X  %s %-6s %s" % (i, w, flag, fam, detail))
        k = inline_words(w)
        for m in range(1, k + 1):
            if i + m < len(ws):
                print("%05X  %04X    %-6s (operand)" % (i + m, ws[i + m], ""))
        i += 1 + k


def cmd_map(path):
    ws = words_of(path)
    conf = Counter(decode(w)[2] for w in ws)
    fam = Counter(decode(w)[0] for w in ws)
    n = len(ws)
    print("%s: %d words" % (path, n))
    print("executable now (doc): %6.2f%%" % (100 * conf["doc"] / n))
    print("class known (dis)   : %6.2f%%" % (100 * conf["class"] / n))
    print("unknown             : %6.2f%%" % (100 * conf["unk"] / n))
    print("\nby mnemonic family:")
    for k, v in fam.most_common():
        print("  %-6s %6.2f%%" % (k, 100 * v / n))

    # honest second figure: the same coverage restricted to the words the
    # machine actually reaches from its own cold-start vector.
    full = words_of_full(path)
    entries = [full[0] & 0x3FFF, full[1] & 0x3FFF, full[2] & 0x3FFF]
    seen, operand, clash = walk(full, entries)
    code = [full[i] for i in seen if i not in operand]
    if code:
        c2 = Counter(decode(w)[2] for w in code)
        print("\nreachable from the cold-start vectors:")
        print("  instruction words   : %d (%.2f%% of image)"
              % (len(seen), 100 * len(seen) / len(full)))
        print("  inline operand words: %d" % len(operand))
        print("  conflicts           : %d" % len(clash))
        print("  of the instruction words: doc %.2f%%  class %.2f%%  unk %.2f%%"
              % (100 * c2["doc"] / len(code), 100 * c2["class"] / len(code),
                 100 * c2["unk"] / len(code)))


def cmd_walk(path):
    ws = words_of_full(path)
    entries = [ws[0] & 0x3FFF, ws[1] & 0x3FFF, ws[2] & 0x3FFF]
    seen, operand, clash = walk(ws, entries)
    print("%s" % path)
    print("entry vectors      : %s" % " ".join("%04X" % e for e in entries))
    print("instruction words  : %d" % len(seen))
    print("inline operand words: %d" % len(operand))
    print("conflicts          : %d" % len(clash))
    fam = Counter(decode(ws[i])[0] for i in seen if i not in operand)
    for k, v in fam.most_common():
        print("  %-6s %6d" % (k, v))


def cmd_run(path, start=None, max_steps=100000):
    m = Iskra226()
    n = m.load(path)
    print("loaded %d words into УП" % n)
    m.pc = (m.up[0] & 0x3FFF) if start is None else start
    m.rb[14] = 0x0100                # a return stack somewhere in ОЗУ
    print("start at %04X" % m.pc)
    trap = m.run(max_steps)
    print("executed %d instructions" % m.steps)
    print("\nlast instructions:")
    for pc, w, fam, detail in m.trace[-14:]:
        print("  %04X  %04X  %-6s %s" % (pc, w, fam, detail))
    if trap:
        print("\nTRAP: %s" % trap)
        print("СМ=%04X  W=%s" % (m.sm, "".join(str(x) for x in m.w)))
        print("Б=%s" % " ".join("%04X" % r for r in m.rb))
        print("Р=%s" % " ".join("%04X" % r for r in m.rr))
    else:
        print("step limit reached without trap")


# --- the manual's worked examples, run as a self-test ----------------------

def cmd_selftest():
    """
    Reproduce every worked example of the manual that gives concrete
    register values. These are the sharpest available check on the
    encoding: each one fixes an opcode, both operand fields and all four
    flags at once.
    """
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print("  %-28s %-30s %s" % (label, got, "ok" if good else
                                    "MISMATCH, expected %s" % (want,)))

    def state(m):
        return (oct(m.sm)[2:].zfill(6),
                "".join(str(x) for x in m.w))

    print("2.5.2  +Р0+Б0, +Б9-Б0, *Б9   (СМ=0 Р0=100377 Б0=1 Б9=17400)")
    m = Iskra226()
    m.rr[0], m.rb[0], m.rb[9] = 0o100377, 0o1, 0o17400
    # +Р0+Б0  = C6 with I=0, J=0        (+РI +БJ)
    m.up[0] = 0xC600
    m.pc = 0
    m.step()
    chk("+Р0+Б0 -> СМ, W", state(m), ("100400", "1100"))
    # +Б9-Б0  = CA with I=9, J=0        (+БI -БJ)
    m.up[1] = 0xCA90
    m.step()
    chk("+Б9-Б0 -> СМ, W", state(m), ("117777", "0010"))
    # *Б9     = EF with I=15, J=9       (+БI * БJ, first operand absent)
    m.up[2] = 0xEFF9
    m.step()
    chk("*Б9 -> Б9", oct(m.rb[9])[2:].zfill(6), "117777")
    chk("*Б9 -> СМ", oct(m.sm)[2:].zfill(6), "000000")

    print("2.6.2  -1, +Р1+В10, +Б1-15*  (СМ=0 Р1=177777 Б1=377)")
    m = Iskra226()
    m.rr[1], m.rb[1] = 0o177777, 0o377
    m.up[0] = 0xD0F1          # -1        = +РI -L with I absent, L=1
    m.up[1] = 0xD418          # +Р1+8     = +РI +L, I=1, L=8 (В10 octal = 8)
    m.up[2] = 0xD91F          # +Б1-15*   = +БI -L *, I=1, L=15
    m.pc = 0
    m.step()
    chk("-1 -> СМ, W", state(m), ("177777", "0000"))
    m.step()
    chk("+Р1+В10 -> СМ, W", state(m), ("000006", "1110"))
    m.step()
    chk("+Б1-15* -> Б1", oct(m.rb[1])[2:].zfill(6), "000366")
    chk("+Б1-15* -> СМ, W", state(m), ("000000", "0010"))

    print("2.8.4  /СР/Р0, /ЛУК/7, /СР/Б1*Б1   (СМ=17 Р0=10 Б1=7)")
    m = Iskra226()
    m.sm, m.rr[0], m.rb[1] = 0o17, 0o10, 0o7
    m.up[0] = 0xE00F          # /СР/Р0     = /СР/РI * РJ, I=0, J absent
    m.up[1] = 0xE607          # /ЛУК/7
    m.up[2] = 0xE811          # /СР/Б1*Б1  = /СР/БI * БJ, I=1, J=1
    m.pc = 0
    m.step()
    chk("/СР/Р0 -> СМ", oct(m.sm)[2:].zfill(6), "000007")
    m.step()
    chk("/ЛУК/7 -> СМ", oct(m.sm)[2:].zfill(6), "000007")
    m.step()
    chk("/СР/Б1*Б1 -> Б1", oct(m.rb[1])[2:].zfill(6), "000000")
    chk("/СР/Б1*Б1 -> СМ, W4", (oct(m.sm)[2:].zfill(6), m.w[3]),
        ("000000", 1))

    print("2.9.5  +Р0/СДЛ/3*, +Б0/СДП/8, /СДЛ/8  (СМ=0 Р0=20040 Б0=177777)")
    m = Iskra226()
    m.rr[0], m.rb[0] = 0o20040, 0o177777
    m.up[0] = 0xD202          # +Р0/СДЛ/3*  -> +РI /СДЛ/K *, I=0, K=J+1=3
    m.up[0] = 0xD302
    m.up[1] = 0xDE07          # +Б0/СДП/8   -> +БI /СДП/K, I=0, K=8
    m.up[1] = 0xDE07
    m.up[2] = 0xD2F7          # /СДЛ/8      -> +РI /СДЛ/K, I absent, K=8
    m.pc = 0
    m.step()
    chk("+Р0/СДЛ/3* -> Р0", oct(m.rr[0])[2:].zfill(6), "000400")
    chk("+Р0/СДЛ/3* -> СМ, W", state(m), ("000000", "0110"))
    m.step()
    chk("+Б0/СДП/8 -> СМ, W", state(m), ("000377", "1110"))
    m.step()
    chk("/СДЛ/8 -> СМ, W", state(m), ("177400", "0100"))

    print("2.10.4 +Р10*Б12, *Б12, +Б12*Р10  (СМ=17 Р10=10 Б12=177777)")
    m = Iskra226()
    m.sm, m.rr[10], m.rb[12] = 0o17, 0o10, 0o177777
    m.up[0] = 0xE7AC          # +Р10*Б12 = +РI * БJ, I=10, J=12
    m.up[1] = 0xEFFC          # *Б12     = +БI * БJ, I absent, J=12
    m.up[2] = 0xEBCA          # +Б12*Р10 = +БI * РJ, I=12, J=10
    m.pc = 0
    m.step()
    chk("+Р10*Б12 -> Б12, W", (oct(m.rb[12])[2:].zfill(6),
                               "".join(str(x) for x in m.w)),
        ("000027", "1000"))
    m.step()
    chk("*Б12 -> Б12, W", (oct(m.rb[12])[2:].zfill(6),
                           "".join(str(x) for x in m.w)),
        ("000000", "1000"))
    m.step()
    chk("+Б12*Р10 -> Р10, W", (oct(m.rr[10])[2:].zfill(6),
                               "".join(str(x) for x in m.w)),
        ("000000", "0001"))

    print("2.13.4 /ТАБ/Б4  (СМ=2 Б4=1, УП[0..3]=000F 00F0 0F00 F000)")
    m = Iskra226()
    m.sm, m.rb[4] = 2, 1
    m.up[0], m.up[1], m.up[2], m.up[3] = 0x000F, 0x00F0, 0x0F00, 0xF000
    m.up[4] = 0xFD4F          # /ТАБ/Б4 = /ТАБ/БI * РJ, I=4, J absent
    m.pc = 4
    m.step()
    chk("/ТАБ/Б4 -> СМ", "%04X" % m.sm, "F000")
    chk("/ТАБ/Б4 -> W4", m.w[3], 0)

    print("2.14.5 /КОН/5*Б0 with СМ=2, six constants 100..5000 (octal)")
    m = Iskra226()
    m.sm = 2
    m.up[0] = 0xFB05          # /КОН/L * БI, I=0, L=5
    for k, v in enumerate((0o100, 0o1000, 0o2000, 0o3000, 0o4000, 0o5000)):
        m.up[1 + k] = v
    m.pc = 0
    m.step()
    chk("/КОН/5*Б0 -> Б0", oct(m.rb[0])[2:].zfill(6), "002000")
    chk("/КОН/5*Б0 -> next PC", "%d" % m.pc, "7")

    print("2.17.6 /ПК/5 with СМ=3 and with СМ=37, list L1..L6")
    for sm, want in ((3, 104), (0o37, 106)):
        m = Iskra226()
        m.sm = sm
        m.up[0] = 0xF205                     # /ПК/5, list of six words
        for k, v in enumerate((101, 102, 103, 104, 105, 106)):
            m.up[1 + k] = v
        m.pc = 0
        m.step()
        chk("/ПК/5 with СМ=%d" % sm, "%d" % m.pc, "%d" % want)

    print("\nself-test %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


# --- message table, kept from the previous version -------------------------

KOI = {0xC0 + i: c for i, c in enumerate("юабцдефгхийклмнопярстужвьызшэщчъ")}
KOI.update({0xE0 + i: c.upper()
            for i, c in enumerate("юабцдефгхийклмнопярстужвьызшэщчъ")})

MESSAGE_POINTERS = [0x107D, 0x108E, 0x108F, 0x1090, 0x1091, 0x1093, 0x1094]


def dev_byte_load(words, rb, rs=0):
    """The machine's own byte addressing rule, manual 2.18.2 with bit 16 of
    Б{I} clear (the /ПЗУ/ direction of /НАД/)."""
    addr = ((rb >> 1) + rs) & 0x3FFF
    w = words[addr]
    return (w & 0xFF) if (rb & 1) == 0 else (w >> 8)


def read_string(words, rb, limit=64):
    out = []
    for _ in range(limit):
        b = dev_byte_load(words, rb)
        if b in (0x00, 0x3A):          # NUL or ':' terminate an entry
            break
        out.append(KOI.get(b, chr(b) if 0x20 <= b < 0x7F else ""))
        rb = (rb + 1) & 0xFFFF
    return "".join(out)


def cmd_messages(path):
    ws = words_of_full(path)
    for pw in MESSAGE_POINTERS:
        print("  ptr @%04X -> %r" % (pw, read_string(ws, ws[pw])))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "selftest":
        return cmd_selftest()
    if len(argv) < 3:
        print(__doc__)
        return 1
    path = argv[2]
    a3 = int(argv[3], 0) if len(argv) > 3 else None
    a4 = int(argv[4], 0) if len(argv) > 4 else (48 if cmd == "dis" else 100000)
    if cmd == "dis":
        cmd_dis(path, a3 or 0, a4)
    elif cmd == "messages":
        cmd_messages(path)
    elif cmd == "map":
        cmd_map(path)
    elif cmd == "walk":
        cmd_walk(path)
    elif cmd == "run":
        cmd_run(path, a3, a4)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
