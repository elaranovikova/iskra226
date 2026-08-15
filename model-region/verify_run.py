#!/usr/bin/env python3
"""Play the tokenised REGION in the interpreter and hold every turn
against model.py, in lockstep.

Both sides run the same policy as a pure function of their own state:
each turn a rounded tenth of the profit goes to the economy, four tenths
to the environment, five tenths to quality of life. Identical states
produce identical inputs, so the two runs stay in lockstep until the
first genuine divergence, and any semantic error in interpreter,
assembler or model surfaces as a growing difference.

The run goes the full game. Which is 26 turns, not 25: line 315 tests
M>25 before the allocation and M starts at zero, so the years run 1 to
26 while the program's own rules speak of 25 tours. The final mark is
compared too; it passes through the accumulated quality of every turn
and the quadruple weight of turn 17, so it is a checksum of the whole
game.

    python3 verify_run.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "emulator"))
sys.path.insert(0, HERE)
import iskra_basic                                           # noqa: E402
import iskra_run                                             # noqa: E402
from build_tokenised import build                            # noqa: E402
from model import Region                                     # noqa: E402


def rd(x):
    return int(x * 100) / 100.0


def alloc(v):
    return (rd(v * 0.1), rd(v * 0.4), rd(v * 0.5), 0)


def main():
    disk, _, symbols, _ = build(os.path.join(HERE, "region-tokenised.dsk"))
    tokens = iskra_basic.load_token_map(
        os.path.join(HERE, "..", "firmware", "basic02_101084.bin"))
    it = iskra_run.Interp(iskra_run.Disk(disk), tokens)

    S = {n: symbols[n] for n in ("V", "P1", "B1", "G1", "Z1", "H1")}
    samples, scores, buf, cur = [], [], [], [None]

    orig_pr = it._pr

    def spy(s):
        buf.append(str(s))
        if "ОЦЕНКА ВАШЕЙ ДЕЯТЕЛЬНОСТИ" in str(s):
            scores.append(str(s))
        orig_pr(s)
    it._pr = spy

    def driver():
        p = "".join(buf[-8:])
        del buf[:]
        if "СКОЛЬКО НА РАЗ" in p:
            samples.append({k: it.nvars.get(v, 0) for k, v in S.items()})
            cur[0] = alloc(it.nvars.get(S["V"], 0))
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

    r = Region()
    mrows = []
    for _ in range(26):
        vnow = r.V + r.profit_gain()
        mrows.append({"V": vnow, "P1": r.P1, "B1": r.B1,
                      "G1": r.G1, "Z1": r.Z1, "H1": r.H1})
        st = r.turn(*alloc(vnow))
        if st["dead"]:
            break

    worst = 0.0
    n = min(len(samples), len(mrows))
    for k in range(n):
        for key in S:
            worst = max(worst, abs(float(samples[k][key])
                                   - float(mrows[k][key])))

    m = re.search(r"ОЦЕНКА ВАШЕЙ ДЕЯТЕЛЬНОСТИ\s+(-?[\d.]+)",
                  " ".join(scores))
    basic_score = float(m.group(1)) if m else None

    print(f"turns compared: {n}")
    print(f"largest state deviation: {worst:.9f}")
    print(f"final mark, interpreter: {basic_score}")
    print(f"final mark, model.py:    {r.score():.3f}")
    ok = (n >= 26 and worst < 1e-6 and basic_score is not None
          and abs(basic_score - r.score()) < 0.005)
    print("VERIFIED" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
