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
from uuid import uuid1

from twisted.internet.defer import Deferred
from twisted.protocols.basic import LineOnlyReceiver
from twisted.python import log


"""Asterisk Manager Interface support"""


class ActionException(Exception):
    """Error response to an action received"""


class ProtocolError(Exception):
    """Protocol error"""


class BaseAMIProtocol(LineOnlyReceiver):
    """Base AMI protocol support.

    Supports banners, sending actions (and receiving responses), and
    receiving events.

    """
    def connectionMade(self):
        LineOnlyReceiver.connectionMade(self)
        self.started = False
        self.lines = []
        self.pendingActions = {}


    def lineReceived(self, line):
        if not self.started:
            if not line.startswith('Asterisk Call Manager/'):
                raise ProtocolError('unknown banner: %r' % (line,))
            self.bannerReceived(line)

        else:
            if line:
                self.lines.append(line)
                return

            message = {}
            body = None
            for line in self.lines:
                if line.endswith('--END COMMAND--'):
                    response = message.get('response')
                    if response != 'Follows':
                        raise ProtocolError('body in non-Follows response')
                    body = line[:-15]
                else:
                    # Normalize the key by lowercasing, and don't require a
                    # space between the colon and value, since some AMI
                    # fields don't supply it.
                    key, value = line.split(':', 1)
                    message[key.lower()] = value.lstrip()
            self.lines = []

            event = message.pop('event', None)
            if event:
                self.eventReceived(event, message)
                return

            response = message.pop('response', None)
            if response:
                self.responseReceived(response, message, body)
                return

            raise ProtocolError('bad message %r' % (message,))


    def eventReceived(self, event, message):
        """An event was received.

	The event message will be dispatched to an event handler method
	(e.g. event_FullyBooted), if it exists.

        """
        eventHandler = getattr(self, 'event_' + event, None)
        if eventHandler:
            eventHandler(message)


    def responseReceived(self, response, message, body):
        """A response was received.

        pendingActions will be searched for a matching Deferred, which
        is then called back with a tuple (message, body) if either a
        Success or Follows response, or erred back with an
        ActionException containing the message if an Error response.

        """
        actionid = message.pop('actionid')
        try:
            d = self.pendingActions.pop(actionid)
        except KeyError:
            raise ProtocolError('unknown actionid %r' % (actionid,))
        if response == 'Success':
            if body is not None:
                raise ProtocolError('body on Success response')
            d.callback((message, None))
        elif response == 'Error':
            if body is not None:
                raise ProtocolError('body on Error response')
            d.errback(ActionException(message))
        elif response == 'Follows':
            if body is None:
                raise ProtocolError('no body on Follows response')
            d.callback((message, body))
        else:
            raise ProtocolError('bad response %r' % (response,))


    def bannerReceived(self, banner):
        """A banner was received.

        The basic implementation starts the protocol by setting the
        started attribute to True.  If you want to check the protocol
        version, override this method.

        The logical thing to implement in any override would be a login
        action.

        """
        self.started = True


    def sendAction(self, actionName, fields):
        """Send an action.

        Returns a Deferred that will fire when a Success response is
        received.

        """
        fields['action'] = actionName
        fields['actionid'] = actionid = str(uuid1())
        for field in fields:
            self.sendLine(field.lower() + ': ' + fields[field])
        self.sendLine('')
        d = self.pendingActions[actionid] = Deferred()
        return d


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
