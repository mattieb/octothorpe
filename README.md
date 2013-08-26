`octothorpe`
============

`octothorpe` is an [Asterisk Manager Interface][2] (AMI) library
for the [Twisted][1] engine.

At the moment, `octothorpe` is still in early development, though
I intend it to eventually offer full asynchronous AGI functionality.

Because of this, I cannot at this time offer API stability, but
that is definitely in the cards for the first (0.1?) release.

`octothorpe`'s primary design goal is to disentangle the myriad
multiplexed event streams that all come over the AMI, making it
easier to focus on them individually.  For example, when a new
channel comes up, the `newChannel` method is called, giving a `Channel`
object you will thereafter receive channel-associated events on as
well as be able to issue actions against.  (Of course, you can
subclass `Channel`.)

`octothorpe` is fully developed with a test-first methodology.  All
functionality is covered by the unit tests.

Requirements
------------

`octothorpe` depends only on Twisted, and is developed against the
latest release version (currently 13.1.0).  The unit tests (which
you can run with `trial octothorpe`) additionally require [Mock][3].

[1]: http://twistedmatrix.com/
[2]: https://wiki.asterisk.org/wiki/display/AST/The+Asterisk+Manager+TCP+IP+API
[3]: http://www.voidspace.org.uk/python/mock/

