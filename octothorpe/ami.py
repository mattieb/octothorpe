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


from hashlib import md5

from octothorpe.base import BaseAMIProtocol


"""Higher-level Asterisk Manager Interface protocol"""


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
        self.variables = {}
        self.extensions = []


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

        If the event mentions a Channel, is not Newchannel (which
	causes the creation of a new Channel object), and an event
        handler method (e.g. event_Newexten) exists on the named Channel
        object, it will be dispatched there.  If none of these stars
        align, we fall back on BaseAMIProtocol behavior.

        """
        name = message.get('channel')
        if name and event != 'Newchannel':
            eventHandler = getattr(self.channels[name], 'event_' + event, None)
            if eventHandler:
                eventHandler(message)
                return
        BaseAMIProtocol.eventReceived(self, event, message)


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
