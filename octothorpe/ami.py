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

from octothorpe.base import BaseAMIProtocol, ProtocolError


"""Higher-level Asterisk Manager Interface protocol"""


STATE_DOWN = 0


class Channel(object):
    """Channel object"""

    def __init__(self, protocol, name, newchannelMessage):
        """Initialize the channel object.

        protocol -- protocol the Newchannel event was received on, used
        for e.g. actions that need to be sent.

        name -- channel name.

        newchannelMessage - Newchannel event message indicating the
        creation of the channel.

        """
        self.protocol = protocol
        self.name = name
        self.params = {}
        for key, value in newchannelMessage.iteritems():
            if key == 'channelstate':
                self.params[key] = int(value)
            else:
                self.params[key] = value
        self.state = self.params['channelstate']
        self.variables = {}
        self.extensions = []
        self.linkedTo = None


    def event_VarSet(self, message):
        """Handle a VarSet event.

        Sets the appropriate variable in the variables dict and calls
        our variableSet method.

        """
        variable = message['variable']
        self.variables[variable] = value = message['value']
        self.variableSet(variable, value)


    def variableSet(self, variable, value):
        """Called when a channel variable is set."""


    def event_Hangup(self, message):
        """Handle a Hangup event.

        Calls our hungUp method, then deletes the channel from the
        protocol's channels dict.

        """
        self.hungUp(int(message['cause']), message['cause-txt'])
        del self.protocol.channels[self.name]


    def hungUp(self, cause, causeText):
        """Called when a channel is hung up."""


    def event_Rename(self, message):
        """Handle a Rename event.

	Moves the channel to its new name in the protocol's channels
	dict, then calls our renamed method.

        """
        oldName = self.name
        self.name = message['newname']
        self.protocol.channels[self.name] = self.protocol.channels.pop(oldName)
        self.renamed(oldName, self.name)


    def renamed(self, oldName, newName):
        """Called when a channel is renamed."""


    def event_Newexten(self, message):
        """Handle a Newexten event.

        Records the context, extension, priority, application, and
        application data in our extensions list and passes same to our
        extensionEntered method.

        """
        data = (
            message['context'],
            message['extension'],
            int(message['priority']),
            message['application'],
            message['appdata']
        )
        self.extensions.append(data)
        self.extensionEntered(*data)


    def extensionEntered(self, context, extension, priority, application,
                         applicationData):
        """Called when a new context/extension/priority is entered."""


    def event_Link(self, message):
        """Handle a Link event.

        Locates the named channel and sets our linkedTo attribute to
        it, then calls our linked method with same.

        """
        if self.linkedTo is not None:
            raise ProtocolError('Link while already linked')
        if message['channel1'] == self.name:
            otherName = message['channel2']
        else:
            otherName = message['channel1']
        otherChannel = self.protocol.channels[otherName]
        self.linkedTo = otherChannel
        self.linked(otherChannel)


    def linked(self, otherChannel):
        """Called when we are linked to another channel."""


    def event_Unlink(self, message):
        """Handle an unlink event.

        Sets our linkedTo attribute to None and calls our unlinked
        method with the channel we've been unlinked from.

        """
        if self.linkedTo is None:
            raise ProtocolError('Unlink while not linked')
        if self.linkedTo.name not in (message['channel1'],
                                      message['channel2']):
            raise ProtocolError('Unlink from channel we are not linked to')
        otherChannel = self.linkedTo
        self.linkedTo = None
        self.unlinked(otherChannel)


    def unlinked(self, otherChannel):
        """Called when we are unlinked from another channel."""


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
