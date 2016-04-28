cold
====

*This project has been superceded by
https://github.com/briansteffens/ccold*

This is currently a just-for-fun language experiment. Cold is an
assembly-influenced language designed to be easy to generate
procedurally. The basic goal is to feed it a list of known inputs
and outputs and have cold brute-force a programmatic solution.

It is an interpreted language, and the current interpreter uses a
copy-on-write scheme to save on memory when executing many versions
of a program in parallel.

Use of the clustering feature is pretty much a necessity for any
non-trivial use.

The code is pretty much an experimental nightmare right now, use at
your own risk. If you're really interested in this stuff, contact me.

This project is currently stalled a bit, as I'm trying to decide
whether to switch it to be based on floating point or maybe give
it a proper type system to support both floats and ints.
