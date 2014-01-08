# Copyright (c) 2013 Matt Behrens <matt@zigg.com>
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


try:
    from hashlib import md5
except ImportError: # pragma: no cover
    from md5 import md5
from uuid import uuid1

from twisted.internet.defer import Deferred

from octothorpe.base import BaseAMIProtocol
from octothorpe.channel import Channel


"""Higher-level Asterisk Manager Interface protocol"""


class AMIProtocol(BaseAMIProtocol):
    """AMI protocol"""

    channelClass = Channel


    def connectionMade(self):
        BaseAMIProtocol.connectionMade(self)
        self.channels = {}
        self.pendingOrigs = {}


    def _cbRespondToLoginChallenge(self, (fields, body), username, secret):
        return self.sendAction('Login', {
            'authtype': 'MD5',
            'username': username,
            'key': md5(fields['challenge'] + secret).hexdigest()
        })



    def eventReceived(self, event, message):
        """An event was received.

        If we determine the event is handleable by one or more
        Channels, we will dispatch the a copy to each Channel that has
        the appropriate handler method (i.e. event_xxx).  If no such
        Channel event handlers are found, we fall back on
        BaseAMIProtocol behavior.

        """
        if 'oldname' in message and event == 'rename':
            names = [message['oldname']]
        elif 'channel' in message and event not in ['channelreload',
                                                    'newchannel']:
            names = [message['channel']]
        elif (event in ('link', 'unlink') and
              'channel1' in message and 'channel2' in message):
            names = [message['channel1'], message['channel2']]            
        elif 'source' in message and event == 'dial':
            names = [message['source']]
        else:
            names = []

        eventHandlers = []
        for name in names:
            eventHandler = getattr(self.channels[name], 'event_' + event, None)
            if eventHandler:
                eventHandlers.append(eventHandler)

        if eventHandlers:
            for eventHandler in eventHandlers:
                eventHandler(message)
        else:
            BaseAMIProtocol.eventReceived(self, event, message)
            return


    def loginMD5(self, username, secret):
        """Log in using MD5 challenge-response"""

        d = self.sendAction('Challenge', {'authtype': 'MD5'})
        d.addCallback(self._cbRespondToLoginChallenge, username, secret)
        return d


    def event_newchannel(self, message):
        """Handle a Newchannel event.

        This method will create a new object of class specified by our
        channelClass attribute (default Channel) and call our
        newChannel method with the channel name and object.

        """
        name = message['channel']
        self.channels[name] = channel = self.channelClass(self, name, message)
        self.newChannel(name, channel)


    def newChannel(self, name, channel):
        """A new channel has been created.

        name -- channel name

        channel -- channel object representing the current state of the
        channel

        """


    def originateQueued(self, (message, body), actionid):
        """An Originate action has been queued.

        (message, body) -- message dict and body (str or None) as
        passed by a sendAction callback.

        actionid -- ActionID from the original sendAction that will
        also be present in the eventual OriginateResponse event.

        """
        d = self.pendingOrigs[actionid] = Deferred()
        return d


    def event_originateresponse(self, message):
        """Handle an OriginateResponse event.

        Calls back the Deferred originally returned by originateQueued.
        
        """
        d = self.pendingOrigs.pop(message['actionid'])
        d.callback(None)


    def _originate(self, channel, message):
        actionid = str(uuid1())
        message.update({
            'actionid': actionid,
            'channel': channel,
            'async': 'true',
        })
        d = self.sendAction('Originate', message)
        d.addCallback(self.originateQueued, actionid)
        return d


    def originateCEP(self, channel, context, exten, priority):
        """Originate a call to a channel/exten/priority.

        The returned Deferred will be called back when the
        OriginateResponse event is received with a Success Response.

        channel -- channel name to originate on (e.g. SIP/200)

        context, exten, priority -- where to originate to

        """
        return self._originate(channel, {
            'context': context,
            'exten': exten,
            'priority': str(priority),
        })


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
