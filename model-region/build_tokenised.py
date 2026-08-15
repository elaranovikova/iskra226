#!/usr/bin/env python3
"""Build region-tokenised.dsk: REGION assembled into BASIC 02 tokens on
a catalogued disk, the form the interpreter loads.

This is a different artifact from region.dsk. That one is the byte-exact
rebuild of the flat source listing as it sits on side 012-1; this one is
the same program tokenised by emulator/iskra_asm.py so that
emulator/iskra_run.py can execute it. The original tokenised REGION, if
one ever existed, has not survived; this encoding uses the token forms
decoded from the corpus (see docs/basic-expression-tokens.md), so every
byte form on this disk is attested, but the disk as a whole is a build,
not a find.

    python3 build_tokenised.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "emulator"))
import iskra_asm                                             # noqa: E402


def build(out_path=None):
    src = open(os.path.join(HERE, "REGION.bas"), encoding="utf-8").read()
    body, symbols, masks = iskra_asm.assemble(src, with_symbols=True)
    out = out_path or os.path.join(HERE, "region-tokenised.dsk")
    with open(out, "wb") as f:
        f.write(bytes(256 * 1001))
    iskra_asm.init_catalog(out)
    s0, s1 = iskra_asm.write_to_disk(out, "REGION", body, 20)
    iskra_asm.add_catalog_entry(out, "REGION", s0, s1)
    return out, body, symbols, masks


if __name__ == "__main__":
    out, body, symbols, masks = build()
    print(f"{out}")
    print(f"  {len(body)} bytes tokenised, sectors 20..{20 + (len(body) + 253) // 254 - 1}")
    print(f"  {len(symbols)} variables, {len(masks)} PRINTUSING image lines")
    print("  name -> slot: " + " ".join(
        f"{k}={v:02X}" for k, v in sorted(symbols.items())))
