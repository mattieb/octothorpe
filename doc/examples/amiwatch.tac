#!/usr/bin/env python
#
# Copyright (c) 2013, 2014 Matt Behrens <matt@zigg.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


from twisted.application import internet, service
from twisted.internet.protocol import ReconnectingClientFactory

from octothorpe.ami import AMIProtocol


"""Example to watch events fly by on an Asterisk Manager Interface

This is the Twisted application .tac version.  Invoke like so:

    twistd -ny amiwatch.tac

It can also be run as a daemon.

"""


class AMIWatcher(AMIProtocol):
    def __init__(self, username, secret, factory=None):
        self.username = username
        self.secret = secret
        self.factory = factory


    def bannerReceived(self, banner):
        AMIProtocol.bannerReceived(self, banner)
        d = self.loginMD5(self.username, self.secret)
        d.addCallback(self.loginSucceeded)


    def loginSucceeded(self, result):
        try:
            self.factory.resetDelay()
            print 'Connection delay reset'
        except AttributeError:
            pass


    def eventReceived(self, event, message):
        AMIProtocol.eventReceived(self, event, message)
        print 'Event received:', event
        for key in sorted(message.keys()):
            print '\t%r: %r' % (key, message[key])


class AMIWatcherFactory(ReconnectingClientFactory):
    def buildProtocol(self, addr):
        return AMIWatcher('manager', 'secret', factory=self)


application = service.Application('amiwatch')
service = internet.TCPClient('172.20.64.100', 5038, AMIWatcherFactory())
service.setServiceParent(application)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
