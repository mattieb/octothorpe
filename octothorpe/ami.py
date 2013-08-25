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


AMI_BANNER_START = 'Asterisk Call Manager/'
END_COMMAND = '--END COMMAND--'

KEY_ACTION = 'action'
KEY_ACTIONID = 'actionid'
KEY_AUTHTYPE = 'authtype'
KEY_CHALLENGE = 'challenge'
KEY_EVENT = 'event'
KEY_KEY = 'key'
KEY_RESPONSE = 'response'
KEY_USERNAME = 'username'

VALUE_CHALLENGE = 'Challenge'
VALUE_ERROR = 'Error'
VALUE_FOLLOWS = 'Follows'
VALUE_LOGIN = 'Login'
VALUE_MD5 = 'MD5'
VALUE_SUCCESS = 'Success'


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
        self.started = False
        self.lines = []
        self.pendingActions = {}


    def lineReceived(self, line):
        if not self.started:
            if not line.startswith(AMI_BANNER_START):
                raise ProtocolError('unknown banner: %r' % (line,))
            self.bannerReceived(line)

        else:
            if line:
                self.lines.append(line)
                return

            message = {}
            body = None
            for line in self.lines:
                if line.endswith(END_COMMAND):
                    response = message.get(KEY_RESPONSE)
                    if response != VALUE_FOLLOWS:
                        raise ProtocolError('body in non-Follows response')
                    body = line[:-len(END_COMMAND)]
                else:
                    # Normalize the key by lowercasing, and don't require a
                    # space between the colon and value, since some AMI
                    # fields don't supply it.
                    key, value = line.split(':', 1)
                    message[key.lower()] = value.lstrip()
            self.lines = []

            event = message.pop(KEY_EVENT, None)
            if event:
                self.eventReceived(event, message)
                return

            response = message.pop(KEY_RESPONSE, None)
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
        actionid = message.pop(KEY_ACTIONID)
        try:
            d = self.pendingActions.pop(actionid)
        except KeyError:
            raise ProtocolError('unknown actionid %r' % (actionid,))
        if response == VALUE_SUCCESS:
            if body is not None:
                raise ProtocolError('body on Success response')
            d.callback((message, None))
        elif response == VALUE_ERROR:
            if body is not None:
                raise ProtocolError('body on Error response')
            d.errback(ActionException(message))
        elif response == VALUE_FOLLOWS:
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
        fields[KEY_ACTION] = actionName
        fields[KEY_ACTIONID] = actionid = str(uuid1())
        for field in fields:
            self.sendLine(field.lower() + ': ' + fields[field])
        self.sendLine('')
        d = self.pendingActions[actionid] = Deferred()
        return d


class AMIProtocol(BaseAMIProtocol):
    """AMI protocol"""

    def _cbRespondToLoginChallenge(self, (fields, body), username, secret):
        return self.sendAction(VALUE_LOGIN, {
            KEY_AUTHTYPE: VALUE_MD5,
            KEY_USERNAME: username,
            KEY_KEY: md5(fields[KEY_CHALLENGE] + secret).hexdigest()
        })


    def loginMD5(self, username, secret):
        """Log in using MD5 challenge-response"""

        d = self.sendAction(VALUE_CHALLENGE, {KEY_AUTHTYPE: VALUE_MD5})
        d.addCallback(self._cbRespondToLoginChallenge, username, secret)
        return d


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
