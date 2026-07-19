# Is this microcode at all?

Written 14 July 2026. Everything below is measurement. The conclusions I
would like to draw from it are not in here, because I cannot draw them yet.

## What is in hand

Two error-corrected masters, 63,744 bytes each, one from disk1side1 and one
from disk1side0. Each boot side carries the same 32-byte header four times
over, at a stride of 498 sectors, and taking the most common byte at every
offset across those four copies is what produces the masters. 60,101 of
63,744 offsets are unanimous on the BASIC 02 side; the rest go three to one
or two to two, and the two-to-two positions are the ones I trust least.

Each master opens with an entry vector and an eighteen character signature.
disk1side1 reads `BASIC 02  22.04.84`, disk1side0 reads
`BASIC PL5 30.09.84`, and the vector `9006 9009 9007` is the same in both.
Those three strings are the whole of what these files say about themselves.

## What the statistics say

Entropy per byte position modulo N, over the BASIC 02 22.04.84 body:

    N=2   7.48 6.88                 spread 0.60
    N=3   7.41 7.42 7.42            spread 0.01
    N=4   7.47 6.87 7.49 6.88       spread 0.62
    N=5   7.42 ... (five values)    spread 0.01
    N=6   7.47 6.88 7.46 ...        spread 0.63
    N=7   7.42 ... (seven values)   spread 0.01
    N=8   7.44 6.84 7.47 ...        spread 0.65

Even N splits into two populations, odd N does not. That is a 16-bit unit,
with one byte carrying about 0.6 bits more entropy than the other. It holds
for every even N I tested and it is the first structural fact about this
image that did not come from a string.

What a 16-bit unit means is the next question. A microinstruction that wide
would be narrow for horizontal microcode and ordinary for machine code, and
the difference between those two readings is the whole project. I am not
going to guess it from one number.

## Not a Wang

The Wang 2200 VP microcode is 24 bits wide. This is 16. Whatever the
Iskra is doing, it is not running the VP's control store, and the
shortcut I was hoping for is gone.
