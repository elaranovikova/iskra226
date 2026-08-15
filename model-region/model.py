#!/usr/bin/env python3
"""
The MODEL REGIONA state machine, re-implemented from REGION.bas.

This is not emulation. The Iskra runs the BASIC; this is Python doing the
same arithmetic so that the model can be examined without playing 25 turns
by hand. Every function names the source lines it comes from, so any claim
here can be checked against the listing.

The re-implementation checks itself: the program stores its own opening
values in line 22 as the ISKH.ZNACH. reference column, and four of them
fall out of these formulas exactly. Run this file to see that check.

    python3 model.py                the self check and the tipping point
    python3 model.py sweep          pollution against investment, 25 turns
"""

import math
import sys


def cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


class Region:
    """Six state variables, set in line 10."""

    def __init__(self, hard=False):
        self.P1 = 28.0        # invested in the national economy
        self.Z1 = 17.0        # pollution
        self.B1 = 13.0        # spent on keeping the environment
        self.H1 = 29.0        # population
        self.G1 = 20.0        # prosperity, from which quality of life follows
        self.K1 = 2.0         # birth control
        self.V = 0.0          # profit in hand
        self.M = 0            # turn counter
        self.Y = 0.0          # accumulated score
        self.Y2 = 0.0         # the score of turn 17, line 886
        self.F1 = self.H1
        self.A8 = self.H1 / 14 + self.G1 ** 2 * 0.002     # line 20
        if hard:
            # Lines 27 and 28, the second run: almost double the pollution
            # and two thirds of the quality of life.
            self.B1 = 20.0
            self.G1 = 16.0
            self.Z1 = 30.0

    # ------------------------------------------------------------ readings

    def quality_of_life(self):
        """Lines 110 to 130. The break at 12 is the whole game."""
        return self.G1 - 11 if self.G1 >= 12 else self.G1 - 12

    def density(self):
        """Line 190, inhabitants per square kilometre."""
        return 1 + math.sqrt(self.H1 ** 3) / 50

    def growth_percent(self):
        """Line 210."""
        return 100 / self.F1 * self.A8 * (1 - self.K1 / 8)

    def environment(self):
        """Lines 222 to 230, piecewise in the pollution."""
        if self.Z1 <= 0:
            return -self.Z1 / 41
        if self.Z1 >= 37:
            return 31 - self.Z1
        return -self.Z1 / 7

    def profit_gain(self):
        """Lines 280 to 300. Linear in investment, cube root in density."""
        R = (self.P1 / 5) * 4.123 ** (-1 / 3) * cbrt(self.density())
        H = math.sqrt(self.H1 ** 3) / 123
        return R + H

    # ------------------------------------------------------------ feedback

    def production_pollution(self):
        """Lines 1280 to 1300. Above 45 the slope doubles."""
        if self.P1 >= 45:
            return (2 * self.P1 - 45) / 5
        return self.P1 / 5

    def self_cleaning(self):
        """
        Lines 1250 to 1270, the construction this whole folder is about.

        Above a pollution of 30 the return is a straight line that reaches
        zero at 50 and turns positive after it. Positive means the term no
        longer cleans, it adds. Past 50 the pollution feeds itself and no
        spending brings it back.
        """
        if self.Z1 >= 30:
            return -(50 - self.Z1) / 5
        if self.Z1 >= 0:
            return -(self.Z1 ** 2 + 45 * self.Z1 + 250) / (10 * self.Z1 + 250)
        return 2 ** self.Z1

    def prosperity_drift(self):
        """Lines 1230 to 1240. Prosperity decays on its own toward 12."""
        return 4 - self.G1 / 4 if self.G1 >= 20 else 3 - self.G1 / 4

    # ------------------------------------------------------------ one turn

    def turn(self, to_economy=0.0, to_environment=0.0, to_life=0.0,
             to_birth=0.0):
        """
        One round, lines 708 to 910, in the order the program runs them.
        The four arguments are the player's allocation of the profit.
        """
        self.V += self.profit_gain()                      # line 300
        spend = to_economy + to_environment + to_life + abs(to_birth)
        if spend > self.V + 0.01:
            raise ValueError("allocated more than the profit in hand")

        self.P1 += to_economy                             # line 460
        self.B1 += to_environment                         # line 550
        self.G1 += to_life                                # line 620
        self.K1 += to_birth                               # line 708
        self.V -= spend

        B = 1 - math.sqrt(self.B1 ** 3) / 20              # line 708
        self.Z1 += B + self.production_pollution()        # line 720
        self.Z1 += self.self_cleaning()                   # line 740
        degraded = self.Z1 >= 35                          # line 750

        L = -self.density()                               # line 190
        self.G1 += self.environment() + L                 # line 770
        self.G1 += self.prosperity_drift()                # line 790

        before = self.H1
        if self.G1 >= 12:                                 # line 830
            self.A8 = self.H1 / 14 + self.G1 ** 2 * 0.002
            self.F1 = self.H1
            self.H1 += self.A8 * (1 - self.K1 / 8 + 1 / (10 * self.K1))
        else:                                             # line 820
            self.A8 = -3 ** (-self.G1 + 1) * self.H1 / 20
            self.F1 = self.H1
            self.H1 += self.A8

        Y1 = self.quality_of_life()                       # lines 850 to 870
        if self.H1 < before:                              # line 882
            Y1 -= 3 * (before - self.H1)
        if self.M == 17:                                  # line 886
            self.Y2 = Y1
        self.Y += Y1
        self.M += 1

        return {"turn": self.M, "pollution": self.Z1, "prosperity": self.G1,
                "population": self.H1, "profit": self.V,
                "cleaning": self.self_cleaning(), "degraded": degraded,
                "dead": self.H1 <= 0}

    def score(self):
        """Line 940. Turn 17 counts four times over. The code does not say why."""
        return (self.Y + 3 * self.Y2) / self.M if self.M else 0.0


def self_check():
    """Line 22 keeps the opening values. Four of them are recomputable."""
    r = Region()
    rows = [
        ("quality of life", r.quality_of_life(), 9.0, "M1"),
        ("density", r.density(), 4.123, "M2"),
        ("growth percent", r.growth_percent(), 2.759, "M3"),
        ("environment", r.environment(), -2.429, "M4"),
        ("profit", r.profit_gain(), 6.87, "M7"),
    ]
    print("self check against the reference column in line 22")
    print("M5 and M6 are left out: they are copies of B1 and P1, not results.")
    print(f"{'':22s}{'computed':>12s}{'in the code':>14s}   ")
    ok = 0
    for name, got, want, tag in rows:
        hit = abs(got - want) < 0.002
        ok += hit
        print(f"  {name:20s}{got:12.4f}{want:14.3f}   {tag}  "
              f"{'matches' if hit else 'DOES NOT MATCH'}")
    print(f"\n{ok} of {len(rows)} reproduce. M3 is the one that does not, and")
    print("it is not an error in this code: neither the value before the")
    print("scaling in line 210 nor the value after it is 2.759.")


def tipping_point():
    print("\nself cleaning as a function of pollution, lines 1250 to 1270")
    print(f"{'pollution':>10s}{'per turn':>12s}")
    r = Region()
    for z in (0, 10, 20, 29, 30, 35, 40, 45, 50, 55, 60):
        r.Z1 = float(z)
        c = r.self_cleaning()
        mark = "cleans" if c < 0 else ("neutral" if c == 0 else "ADDS")
        print(f"{z:10d}{c:12.3f}   {mark}")
    print("\nAt 50 the term is exactly zero. Past it the pollution is its own")
    print("source. The program warns at 35 and says nothing at 50.")


def run(label, split):
    """
    Play 25 turns with a fixed split of the profit.

    split(available) returns the four allocations. Nothing here plays well;
    the point is only to show that the model answers differently to
    different policies, and that one of them is not survivable.
    """
    print(f"\n{label}")
    print(f"{'turn':>5s}{'pollution':>11s}{'prosperity':>12s}"
          f"{'population':>12s}{'cleaning':>10s}")
    r = Region()
    for _ in range(25):
        available = r.V + r.profit_gain()
        state = r.turn(*split(available))
        pop = (f"{state['population']:12.2f}" if state["population"] > 0
               else f"{'collapsed':>12s}")
        print(f"{state['turn']:5d}{state['pollution']:11.2f}"
              f"{state['prosperity']:12.2f}{pop}{state['cleaning']:10.2f}")
        if state["dead"]:
            print("  population gone. Line 845 ends the game here, so the")
            print("  figure the exponential in line 820 produces is never")
            print("  shown to a player.")
            break
    print(f"  score {r.score():.3f}")


def sweep():
    run("everything into the economy, nothing else",
        lambda a: (a, 0.0, 0.0, 0.0))
    run("a third to the economy, a third to the environment, "
        "a third to quality of life",
        lambda a: (a / 3, a / 3, a / 3, 0.0))


if __name__ == "__main__":
    self_check()
    tipping_point()
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        sweep()
