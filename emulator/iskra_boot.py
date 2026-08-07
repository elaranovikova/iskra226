#!/usr/bin/env python3
"""
iskra_boot - bring up every side of a disk set and say what happened.

Written after three of the six original sides turned out to crash the
catalog reader. They are system sides: sector 0 carries the boot signature
06 90 09 90 07 90, not a catalog, and reading it as the index word gave
1680, which walked straight past the end of a 1001 sector image.

The scan behind this also settled what those sides are. Across all 1001
sectors of each of them there is not one catalog-like entry and not one
file header sector. They are pure firmware images, not media with programs
on them, which is why they run 966 to 996 sectors full.

A word on "boot". For a data side it means every program is loaded, parsed
and started, which is real bring-up. For a system side it means only that
the side is recognised and described. Executing its firmware would mean
emulating K589 microcode, and that is the one hole this project has never
closed.

Usage:
    python3 iskra_boot.py <images...>
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iskra_basic import Disk, load_token_map          # noqa: E402
import iskra_run                                       # noqa: E402


def signature(disk):
    return disk.data[6:24].decode("ascii", "replace").strip()


def used_sectors(disk):
    return sum(1 for s in range(disk.sectors)
               if any(disk.sector(s)))


def boot(path, tokens):
    d = Disk(path)
    name = os.path.basename(path)
    kind = d.kind()

    if kind == "blank":
        print("%-16s blank    no sector in use" % name)
        return True

    if kind == "system":
        print("%-16s system   %-20s %4d sectors in use"
              % (name, signature(d), used_sectors(d)))
        return True

    entries = [e for e in d.catalog() if not e["scratched"]]
    ok = 0
    data_files = 0
    failed = []
    for e in entries:
        # A catalog entry is not necessarily a program. STIPENDIYA keeps its
        # student database in one, named 132, and a data file has no line
        # records to parse. That is not a failure, it is what it is.
        try:
            it = iskra_run.Interp(d, tokens)
            loaded = it.load_program(e["name"])
            if loaded and loaded[0]:
                ok += 1
            else:
                data_files += 1
        except Exception as exc:                       # noqa: BLE001
            failed.append((e["name"], exc))
    for nm, exc in failed:
        print("      %-10s FAILED: %s" % (nm, exc))
    extra = ", %d data file(s)" % data_files if data_files else ""
    print("%-16s data     %d program(s) loaded and started%s"
          % (name, ok, extra))
    return not failed


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    tokens = load_token_map()
    # A list, not a generator: all() would short-circuit and the sides
    # after the first failure would never be tested at all.
    results = [boot(p, tokens) for p in argv[1:]]
    good = all(results)
    print("\n%s" % ("all sides came up" if good else "at least one side failed"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
