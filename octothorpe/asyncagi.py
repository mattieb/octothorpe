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


from urllib import unquote
from uuid import uuid1

from twisted.internet.defer import Deferred

from octothorpe.ami import AMIProtocol
from octothorpe.channel import Channel


"""AsyncAGI-supporting Asterisk Manager Interface protocol"""


class AGIException(Exception):
    """AGI exception"""

    def __init__(self, code, message):
        self.code = code
        self.message = message


    def __repr__(self):
        return '<AGIException code=%d message=%r>' % (self.code, self.message)


class AsyncAGIChannel(Channel):
    """AsyncAGI-supporting channel"""

    def __init__(self, *args, **kwargs):
        self.pendingAGI = {}
        Channel.__init__(self, *args, **kwargs)


    def event_asyncagi(self, message):
        """Respond to an AsyncAGI event"""

        if message['subevent'] == 'Start':
            self.agiEnv = env = {}
            for line in unquote(message['env']).split('\n'):
                if line:
                    key, value = line.split(': ')
                    env[key] = value
            self.asyncAGIStarted(
                env['agi_context'],
                env['agi_extension'],
                int(env['agi_priority']),
                env
            )
            
        elif message['subevent'] == 'Exec':
            commandid = message['commandid']
            try:
                d = self.pendingAGI[commandid]
            except KeyError:
                raise UnknownCommandException(commandid)

            codestr, message = unquote(message['result']).strip().split(' ', 1)
            code = int(codestr)
            if code != 200:
                d.errback(AGIException(code, message))
                return

            params = dict([pair.split('=', 1) for pair in message.split(' ')])
            result = int(params.pop('result'))
            d.callback((result, params))


    def _cbAGIQueued(self, result, commandid):
        """Called when AGI is queued.

        Sets up a deferred result for the eventual AGIExec event.

        """
        d = self.pendingAGI[commandid] = Deferred()
        return d


    def sendAGI(self, command):
        """Queue an AGI command.

        Returns a Deferred that will fire when a Success AGIExec event
        is received.

        """
        commandid = str(uuid1())
        d = self.sendAction('AGI', {
            'action': 'AGI',
            'command': command,
            'commandid': commandid,
        })
        d.addCallback(self._cbAGIQueued, commandid)
        return d


class AsyncAGIProtocol(AMIProtocol):
    """AsyncAGI-supporting AMI protocol"""

    channelClass = AsyncAGIChannel


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
