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


from octothorpe.base import ProtocolError


"""Base Channel implementation for use with AMIProtocol"""


_states = [
    (0, 'Down'),
    (1, 'Rsrvd'),
    (2, 'OffHook'),
    (3, 'Dialing'),
    (4, 'Ring'),
    (5, 'Ringing'),
    (6, 'Up'),
    (7, 'Busy'),
    (8, 'Dialing Offhook'),
    (9, 'Pre-ring'),
]
STATES = {}
STATE_DESCS = {}

for state, desc in _states:
    STATES[desc.lower()] = state
    STATE_DESCS[state] = desc
    constname = desc.upper().replace(' ', '-').replace('_', '-') #<('_'<)
    globals()['STATE_' + constname] = state # Create STATE_XXX constants


class Channel(object):
    """Channel object"""

    def _synthesizeStateParams(self, desc):
        """Synthesize channelstate and channelstatedesc in our params."""

        self.state = self.params['channelstate'] = STATES[desc.lower()]
        self.params['channelstatedesc'] = desc


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

        try:
            self.state = self.params['channelstate']
        except KeyError:
            self._synthesizeStateParams(self.params['state'])

        self.variables = {}
        self.extensions = []
        self.linkedTo = None


    def event_Newstate(self, message):
        """Handle a Newstate event.

        Updates our state and params attributes, and calls our newState
        method.

        """
        try:
            self.params['channelstate'] = int(message['channelstate'])
            self.params['channelstatedesc'] = message['channelstatedesc']
        except KeyError:
            self._synthesizeStateParams(message['state'])

        self.state = self.params['channelstate']
        self.newState(self.state, self.params['channelstatedesc'])


    def newState(self, state, desc):
        """Called when we have a new state."""


    def event_NewCallerid(self, message):
        """Handle a NewCallerid event.

        Updates our params attribute and calls our newCallerId method.

        """
        self.params['calleridnum'] = message['calleridnum']
        self.params['calleridname'] = message['calleridname']
        self.newCallerId(message['calleridnum'], message['calleridname'])


    def newCallerId(self, number, name):
        """Called when we have a new caller ID."""


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


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
