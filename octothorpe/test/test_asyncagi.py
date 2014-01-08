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


from urllib import quote

from mock import Mock
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.asyncagi import AGIException, AsyncAGIProtocol, AsyncAGIChannel
from octothorpe.asyncagi import UnknownCommandException
from octothorpe.base import ProtocolError
from octothorpe.test.test_base import disassembleMessage


"""Tests for octothorpe.ami"""


class AsyncAGIProtocolTestCase(unittest.TestCase):
    """Test case for the AsyncAGI protocol"""

    def setUp(self):
        self.protocol = AsyncAGIProtocol()
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
        self.protocol.started = True


    def _spawnChannel(self, name='Foo/202-0'):
        self.protocol.channels[name] = channel = AsyncAGIChannel(
            self.protocol,
            name,
            {
                'calleridname': 'Foo',
                'calleridnum': '202',
                'channel': name,
                'channelstate': '0',
                'channelstatedesc': 'Down',
            }
        )
        return channel


    def test_AGIExceptionRepr(self):
        """repr() of an AGIException"""

        self.assertEqual(
            repr(AGIException(500, 'foobar')),
            "<AGIException code=500 message='foobar'>"
        )


    def test_asyncAGIStart(self):
        """Respond to an AsyncAGI Start event"""

        channel = self._spawnChannel()
        started = channel.asyncAGIStarted = Mock()
        env = quote(
            'agi_request: async\n'
            'agi_channel: Foo/202-0\n'
            'agi_context: default\n'
            'agi_extension: 400\n'
            'agi_priority: 1\n'
            '\n'
        )
        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'Channel: Foo/202-0\r\n'
            'Env: ' + env + '\r\n'
            'Subevent: Start\r\n'
            '\r\n'
        )
        started.assert_called_once_with(
            'default', '400', 1, {
                'agi_request': 'async',
                'agi_channel': 'Foo/202-0',
                'agi_context': 'default',
                'agi_extension': '400',
                'agi_priority': '1',
            }
        )


    def test_originateAsyncAGI(self):
        """Originate an AsyncAGI call, calling back with channel"""

        channel = self._spawnChannel()
        d = self.protocol.originateAsyncAGI('Foo/202')
        originated = Mock()
        d.addCallback(originated)

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'Originate')
        self.assertIn('actionid', message)
        self.assertEqual(message['application'], 'AGI')
        self.assertEqual(message['data'], 'agi:async')
        self.assertEqual(message['async'], 'true')

        varName, octoId = message['variable'].split('=')
        self.assertEqual(varName, 'AsyncOrigId')

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            'Message: Originate successfully queued\r\n'
            '\r\n'
            'Event: VarSet\r\n'
            'Channel: Foo/202-0\r\n'
            'Variable: AsyncOrigId\r\n'
            'Value: ' + octoId + '\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
            'Event: OriginateResponse\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            'Channel: Foo/202-0\r\n'
            'Response: Success\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.assertEqual(len(originated.mock_calls), 0)

        env = quote(
            'agi_request: async\n'
            'agi_channel: Foo/202-0\n'
            'agi_context: default\n'
            'agi_extension: 400\n'
            'agi_priority: 1\n'
            '\n'
        )
        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'Channel: Foo/202-0\r\n'
            'Env: ' + env + '\r\n'
            'Subevent: Start\r\n'
            '\r\n'
        )
        originated.assert_called_once_with((channel, {
            'agi_request': 'async',
            'agi_channel': 'Foo/202-0',
            'agi_context': 'default',
            'agi_extension': '400',
            'agi_priority': '1',
        }))


    def test_AGI(self):
        """Successfully run an AGI command"""

        channel = self._spawnChannel()
        d = channel.sendAGI('EXEC Playback hello-world')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'EXEC Playback hello-world')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('200 result=0 foo=bar\n') + '\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with((0, {'foo': 'bar'}))


    def test_AGIInvalid(self):
        """Fail to run an invalid AGI command"""

        channel = self._spawnChannel()
        d = channel.sendAGI('FOO')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'FOO')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('510 Invalid or unknown command\n') + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)
        self.assertFailure(d, AGIException)
        return d


    def test_unknownCommandId(self):
        """Connection is not dropped on an unknown command"""

        self._spawnChannel()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: bar\r\n'
            'Result: ' + quote('200 result=0\n') + '\r\n'
            '\r\n'
        )
        self.assertFalse(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 0)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
