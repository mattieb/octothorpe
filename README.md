`octothorpe`
============

`octothorpe` is an [Asterisk Manager Interface][2] (AMI) library
for the [Twisted][1] engine.

In this release, it now offers asynchronous AGI functionality—see
the `*hello` examples in `doc/examples`.

At the moment, `octothorpe` is still in development.  Because of
this, I cannot at this time offer API stability, but I intend to
do this as it shapes up further.

`octothorpe`'s primary design goal is to disentangle the myriad
multiplexed event streams that all come over the AMI, making it
easier to focus on them individually.  For example, when a new
channel comes up, the `newChannel` method is called, giving a `Channel`
object you will thereafter receive channel-associated events on as
well as be able to issue actions against.  (Of course, you can
subclass `Channel`.)

Requirements
------------

`octothorpe` depends only on Twisted, and is developed against the
latest release version (currently 13.2.0).

Development
-----------

`octothorpe` is fully developed with a test-first methodology.  All
functionality is covered by the unit tests, which can be verified
with [`coverage.py`][4] (see `COVERAGE.md`).

The unit tests (which you can run with `trial octothorpe`) additionally
require [Mock][3].

[1]: http://twistedmatrix.com/
[2]: https://wiki.asterisk.org/wiki/display/AST/The+Asterisk+Manager+TCP+IP+API
[3]: http://www.voidspace.org.uk/python/mock/
[4]: http://nedbatchelder.com/code/coverage/

