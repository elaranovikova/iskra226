# The disks

Six sides, 256,256 bytes each. 1001 logical sectors of 256 bytes, or 77
tracks of 26 physical sectors of 128 bytes, which is IBM 3740 on 8-inch
media. Both readings are true; see `docs/on-disk-format.md`.

    disk1side0   boot, four slots: BASIC PL5 30.09.84 and three BASIC 01
    disk1side1   boot, four slots: BASIC 02, four builds 1983 to 1986
    disk2side0   boot, four slots: BASIC PL5 30.09.84, all four identical
    disk2side1   application, 20 entries, the BAM database suite
    disk3side0   application, STIPENDIYA, SPTU-132, 1988/89
    disk3side1   256,256 zero bytes, never written

## Where they come from

`880.rar` was published on oldpc.su. The physical disks belonged to the forum
user **vazman**, and **dk_spb** read them and put the images up. How he read
them is not written down in any post I can find, and in 2022 he was still
asking what the disk format was. The thread is on phantom.sannata.org. The
link died; the copy here came out of a Wayback snapshot from 2016, and as far
as I can establish it is the only one left.

Neither of them owes me anything and both of them are the reason any of this
was possible. If you mirror this repository, mirror their names with it.

## The data file 132

`disk3side0` carries a data file named `132`, 561 sectors. It is the student
database of a vocational school from 1989 and it has names in it. I have not
decoded it and I am not going to. The payroll programs that read it are in
`listings/`, so anyone can see what its fields are without me printing the
contents of somebody's file.

## The seventh image

There is one. It is not here.

It is an 8-inch disk that has been in my family since before I could read,
and I read it on 7 August 2026, thirty-seven years after it was written and
seventeen after it came to me. Everything else I found is in this
repository, including the parts that make me look slow.

I have spent four books arguing that archives belong to everyone and that a
state which keeps a file closed is telling you what it is ashamed of. I know
exactly what I am doing here and I am doing it anyway. The disk was not
addressed to the public and I am not going to be the person who publishes
it.

That is the whole of what I will say about it. Do not write and ask.
