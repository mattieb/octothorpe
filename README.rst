octothorpe
==========

octothorpe is an `Asterisk Manager Interface
<https://wiki.asterisk.org/wiki/display/AST/The+Asterisk+Manager+TCP+IP+API>`__
(AMI) library for the `Twisted <http://twistedmatrix.com/>`__ engine.

At the moment, octothorpe is still in development. Because of this,
I cannot at this time offer API stability, but I intend to do this
as it shapes up further.

octothorpe's primary design goal is to disentangle the myriad
multiplexed event streams that all come over the AMI, making it
easier to focus on them individually. For example, when a new channel
comes up, the ``newChannel`` method is called, giving a ``Channel``
object you will thereafter receive channel-associated events on as
well as be able to issue actions against. (Of course, you can
subclass ``Channel``.)

Requirements
------------

octothorpe depends only on Twisted, and is developed against the
latest release version (currently 13.2.0).

``requirements.txt`` specifies Development dependencies, including
those for running tests.

Development
-----------

As mentioned above, you should start by installing all development
requirements (you're using a `virtualenv <http://www.virtualenv.org/>`__,
right?):

::

    $ . bin/activate
    $ pip install `cat requirements.txt`

octothorpe is fully developed with a test-first methodology.  All
functionality is covered by the unit tests (which you can run with
``trial octothorpe``.) You can verify coverage with `coverage.py
<http://nedbatchelder.com/code/coverage/>`__:

::

    $ coverage run --source=octothorpe `which trial` octothorpe
    $ coverage report -m

If you're interested in a virtual environment for hacking on
octothorpe, I've supplied here my `Vagrant <http://www.vagrantup.com/>`__
and `Ansible <http://www.ansible.com/>`__ configurations for building
and doing the initial configuration for a box with Asterisk running
and ready to accept a SIP phone connection.

Pay close attention to ``Vagrantfile``—it contains a directive for
setting up a host-only network. I've randomly selected an RFC1918
address for this purpose; you'll want to connect your SIP softphone
and your octothorpe applications to this address. If you're happy
with this, run ``vagrant up``.

**Important Note:** Don't even *think* of using the config files
in ``etc/asterisk`` in production! They are wildly insecure.

