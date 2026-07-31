# Is this microcode at all?

Written 31 July 2026, at the end of a month that produced two firmware
masters, eight interpreter builds, a lot of statistics and not one decoded
instruction. This is the open question, stated as precisely as I can state
it, so that whoever answers it first can see exactly where I stopped.

## What is in hand

Eight distinct interpreter builds, recovered from the four slots each boot
side carries. `emulator/firmware_extract.py` pulls them out and they are
byte-identical wherever they repeat:

    BASIC 01  15.12.81      BASIC 02  16.12.83
    BASIC 01  12.07.82      BASIC 02  22.04.84
    BASIC 01  27.12.82      BASIC 02  10.10.84
    BASIC PL5 30.09.84      BASIC 02  10.09.86

Each is 63,744 bytes. Each begins with an entry vector and an eighteen
character signature. The BASIC 02 family and PL5 share the vector
`9006 9009 9007`; BASIC 01 has its own, `AD43 8092 ACFB`, and its descriptor
table sits 396 bytes further in. So BASIC 01 is a different program, not an
earlier revision of the same one.

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
with one byte carrying about 0.6 bits more entropy than the other. It is
not 24 bits, which is what the Wang 2200 VP microcode uses, and that already
rules out the shortcut I was hoping for.

Mutual information between adjacent bit positions has minima that suggest
field boundaries after bit 4 and bit 12. I do not believe them. The
histogram of the top 4 bits is not the shape an opcode field makes: it is
too flat in the middle and has no dominant idle encoding. Either the field
is not there or it is not at the top of the word.

## The question

I have been asking *what does this microcode do*, and I have spent three
weeks on it, and I am now no longer sure the question is well formed.

Two readings fit the evidence I have:

**A. It is horizontal microcode** for the K589 slices, loaded into writable
control store at power-on. Then the 16-bit unit is a microinstruction, the
field boundaries are real and I am failing to find them, and the flat
histogram means the encoding is denser than I assume.

**B. It is machine code** for a processor built *out of* the slices, whose
own microcode lives somewhere I do not have, in ROM on the board. Then the
16-bit unit is an ordinary instruction word, the flat histogram is what you
would expect from a compiled interpreter, and the reason the field analysis
fails is that there is nothing statistical to find: it is an opcode table,
and tables are read, not inferred.

Under A, the boot disk is the whole machine and the emulator is a matter of
finding the fields. Under B, the boot disk is a *program*, the machine is
underneath it and still missing, and everything I have measured this month
measures the wrong layer.

I cannot separate the two from the binary alone. What would separate them:
the processor's техническое описание, or a photograph of the board showing
whether there is a ROM next to the slices, or one confirmed instruction
decoded by hand from a known behaviour.

I have four scanned manuals in `docs/` that I have read for structure and not
for content. That is the next thing.
