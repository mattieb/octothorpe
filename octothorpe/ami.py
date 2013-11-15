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

from octothorpe.base import BaseAMIProtocol
from octothorpe.channel import Channel


"""Higher-level Asterisk Manager Interface protocol"""


class AMIProtocol(BaseAMIProtocol):
    """AMI protocol"""

    channelClass = Channel


    def connectionMade(self):
        BaseAMIProtocol.connectionMade(self)
        self.channels = {}


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
        the appropriate handler method (i.e. event_XXX).  If no such
        Channel event handlers are found, we fall back on
        BaseAMIProtocol behavior.

        """
        if 'oldname' in message and event == 'Rename':
            names = [message['oldname']]
        elif 'channel' in message and event != 'Newchannel':
            names = [message['channel']]
        elif (event in ('Link', 'Unlink') and
              'channel1' in message and 'channel2' in message):
            names = [message['channel1'], message['channel2']]            
        elif 'source' in message and event == 'Dial':
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


    def event_Newchannel(self, message):
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


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
