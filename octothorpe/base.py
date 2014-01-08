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


from uuid import uuid1

from twisted.internet.defer import Deferred
from twisted.protocols.basic import LineOnlyReceiver
from twisted.python import log


"""Asterisk Manager Interface support"""


class ActionException(Exception):
    """Error response to an action received"""


class ProtocolError(Exception):
    """Protocol error"""


class UnknownActionException(KeyError):
    """Response to unknown action received"""


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
        try:
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
                        # Normalize the key by lowercasing, and don't
                        # require a space between the colon and value,
                        # since some AMI fields don't supply it.
                        key, value = line.split(':', 1)
                        message[key.lower()] = value.lstrip()
                self.lines = []

                event = message.pop('event', None)
                if event:
                    self.eventReceived(event.lower(), message)
                    return

                response = message.pop('response', None)
                if response:
                    self.responseReceived(response, message, body)
                    return

                raise ProtocolError('bad message %r' % (message,))

        except Exception, e:
            self.protocolExceptionReceived(e)


    noDropExceptions = [UnknownActionException]
    def protocolExceptionReceived(self, exception):
        if exception.__class__ in self.noDropExceptions:
            log.msg('ignoring exception %s (%r)' % (exception, exception))
        else:
            log.err(exception)
            self.transport.loseConnection()


    def eventReceived(self, event, message):
        """An event was received.

	The event message will be dispatched to an event handler method
	(e.g. event_fullybooted), if it exists.

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
            raise UnknownActionException('unknown actionid %r' % (actionid,))
        if response == 'Success':
            d.callback((message, None))
        elif response == 'Error':
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
        version, override this method and be sure to either deal with
        the started attribute yourself or (even better) call this
        implementation.

        The logical thing to implement in an override would be a login
        action.

        """
        self.started = True


    def sendAction(self, actionName, fields):
        """Send an action.

        Returns a Deferred that will fire when a Success response is
        received.

        """
        fields['action'] = actionName
        if 'actionid' not in fields:
            fields['actionid'] = str(uuid1())
        actionid = fields['actionid']

        for field in fields:
            self.sendLine(field.lower() + ': ' + fields[field])
        self.sendLine('')
        d = self.pendingActions[actionid] = Deferred()
        return d


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
